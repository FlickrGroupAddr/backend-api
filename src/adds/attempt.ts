import { alreadySucceeded, type QueueHead } from "../db/requests.js";
import { getFlickrTokens, markNeedsRelink } from "../db/users.js";
import type { UserCredentials } from "../flickr/api.js";
import { addPhotoToGroup, getPhotoPools } from "../flickr/api.js";
import type { AttemptFn } from "../sweep.js";
import { classifyResult, type Disposition } from "./classify.js";

/**
 * The production attempt: everything the sweep deliberately does not know about.
 *
 * The sweep owns ADR-10's walking rules and is tested without a network. This
 * owns credentials, ADR-05's idempotency checks, and the one side effect that
 * outlives a single request -- flagging a user for re-link.
 */

/**
 * Decrypting a user's token is two AES-GCM operations, and one sweep can walk
 * several of the same user's queues. The cache lives for exactly one sweep and
 * then goes out of scope with it; nothing decrypted is written anywhere.
 */
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
		// ADR-05, cheap pass. Costs no network call and catches the common case of
		// an overlapping or re-run sweep.
		if (await alreadySucceeded(env.DB, head.nsid, head.photoId, head.groupId)) {
			return { kind: "resolved", outcome: "already_in_pool" };
		}

		const creds = await credentialsFor(head.nsid);
		if (creds === null) {
			// The user row vanished between the queue query and here. Nothing to
			// act with, and nothing that will fix itself.
			return { kind: "terminal", code: -1, relink: false };
		}

		// ADR-05, authoritative pass. Run on EVERY attempt rather than only the
		// first, because it also sees adds FGA did not make -- the user adding the
		// photo by hand, or a second session. Skipping an add that would have
		// returned code 3 saves a throttle slot, so this call pays for itself in
		// the currency that is actually scarce here.
		//
		// A FAILED check returns null and falls through to the add deliberately:
		// not knowing whether the photo is already there is not a reason to stop,
		// and code 3 answers the same question authoritatively.
		const pools = await getPhotoPools(head.photoId, creds);
		if (pools?.includes(head.groupId)) {
			return { kind: "resolved", outcome: "already_in_pool" };
		}

		const disposition = classifyResult(
			await addPhotoToGroup(head.photoId, head.groupId, creds),
		);

		// ADR-07: codes 98 and 99 mean the stored token no longer works. Flagging
		// the user stops the next sweep from rediscovering it once per queue --
		// queueHeads excludes flagged users entirely.
		if (disposition.kind === "terminal" && disposition.relink) {
			await markNeedsRelink(env.DB, head.nsid);
			credentials.set(head.nsid, null);
		}

		return disposition;
	};
}
