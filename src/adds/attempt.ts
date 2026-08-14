import { alreadySucceeded, type QueueHead } from "../db/requests.js";
import { getFlickrTokens, markNeedsRelink } from "../db/users.js";
import type { UserCredentials } from "../flickr/api.js";
import { addPhotoToGroup, getPhotoPools } from "../flickr/api.js";
import type { AttemptFn } from "../sweep.js";
import { classifyResult, type Disposition } from "./classify.js";

/**
 * Everything `sweep` deliberately does not know about: credentials, ADR-05's idempotency
 * checks, and the one side effect that outlives a request.
 */

/** Decrypting a token is two AES-GCM operations, and one sweep can walk several of the
 *  same user's queues. Lives for exactly one sweep; nothing decrypted is written down. */
export function createAttempt(env: Env): AttemptFn {
	const credentials = new Map<string, UserCredentials | null>();

	async function credentialsFor(nsid: string): Promise<UserCredentials | null> {
		const cached = credentials.get(nsid);
		if (cached !== undefined) return cached;

		const tokens = await getFlickrTokens(env.DB, nsid, env.TOKEN_KEY);
		const resolved =
			tokens === null
				? null
				: {
						consumerKey: env.FLICKR_CONSUMER_KEY,
						consumerSecret: env.FLICKR_CONSUMER_SECRET,
						token: tokens.token,
						tokenSecret: tokens.tokenSecret,
					};

		credentials.set(nsid, resolved);
		return resolved;
	}

	return async (head: QueueHead): Promise<Disposition> => {
		// ADR-05, cheap pass. No network, catches an overlapping or re-run sweep.
		if (await alreadySucceeded(env.DB, head.nsid, head.photoId, head.groupId)) {
			return { kind: "resolved", outcome: "already_in_pool" };
		}

		const creds = await credentialsFor(head.nsid);
		if (creds === null) {
			// The user row vanished mid-sweep. Nothing to act with, nothing self-healing.
			return { kind: "terminal", code: -1, relink: false };
		}

		// ADR-05, authoritative pass. Runs on EVERY attempt, not just the first, because
		// it also sees adds FGA did not make. Skipping an add that would return code 3
		// saves a throttle slot, which is the currency that is actually scarce here.
		//
		// A FAILED check returns null and falls through on purpose: not knowing is not a
		// reason to stop, and code 3 answers the same question authoritatively.
		const pools = await getPhotoPools(head.photoId, creds);
		if (pools?.includes(head.groupId)) {
			return { kind: "resolved", outcome: "already_in_pool" };
		}

		const disposition = classifyResult(
			await addPhotoToGroup(head.photoId, head.groupId, creds),
		);

		// ADR-07: the stored token is now known bad. Flagging stops the next sweep
		// rediscovering it once per queue -- `queueHeads` excludes flagged users.
		if (disposition.kind === "terminal" && disposition.relink) {
			await markNeedsRelink(env.DB, head.nsid);
			credentials.set(head.nsid, null);
		}

		return disposition;
	};
}
