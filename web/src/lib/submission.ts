import type { Submitted } from "./contract.js";

/**
 * One photo, many groups. **This is the screen that earned the framework**, and the
 * state it tracks is the reason hand-written DOM code stopped scaling in the 2021 UI:
 * forty groups means forty independent outcomes, each landing at its own time, each
 * needing a different sentence.
 *
 * **The submit function is injected**, exactly as `src/sweep.ts` injects its attempt
 * function, so the rules here are testable without a network.
 */

/** What one group's submission is doing. Every arm carries what its sentence needs. */
export type ItemState =
	| { kind: "waiting" }
	| { kind: "sending" }
	| { kind: "queued"; publicId: string }
	| { kind: "resolved"; publicId: string; disposition: string }
	/** ADR-04. A question, NOT a failure. The person decides. */
	| {
			kind: "needsAcknowledgement";
			flickrCode: 6 | 7;
			firstSeenAt: number;
			stillPending: boolean;
	  }
	/**
	 * Carries the ERROR, not a message.
	 *
	 * A pre-rendered string here would either be developer text on the page -- which is
	 * what `500 unparseable` was -- or would drag user-facing copy down into a module
	 * that has no business holding it. The component calls `describeError` at render.
	 */
	| { kind: "failed"; error: unknown };

export type Batch = ReadonlyMap<string, ItemState>;

export type SubmitFn = (
	photoId: string,
	groupId: string,
	acknowledgedModeration: boolean,
) => Promise<Submitted>;

export function emptyBatch(groupIds: readonly string[]): Batch {
	return new Map(groupIds.map((id) => [id, { kind: "waiting" } as ItemState]));
}

function toState(reply: Submitted): ItemState {
	switch (reply.status) {
		case "queued":
			return { kind: "queued", publicId: reply.publicId };
		case "resolved":
			return {
				kind: "resolved",
				publicId: reply.publicId,
				disposition: reply.disposition,
			};
		case "needs_acknowledgement":
			return {
				kind: "needsAcknowledgement",
				flickrCode: reply.flickrCode,
				firstSeenAt: reply.firstSeenAt,
				stillPending: reply.stillPending,
			};
	}
}

/**
 * Submits each group in turn, reporting after every one.
 *
 * **Sequential on purpose, and this MUST NOT be "optimized" into parallel requests.**
 * A submission whose queue is empty triggers an immediate live `groups.pools.add`
 * inside the Worker, so forty parallel posts are forty simultaneous calls to Flickr on
 * one user's credentials. ADR-01 is a promise about not spending other people's
 * patience, and hammering the API on their token is the same discourtesy wearing a
 * performance costume. Forty groups at roughly 300 ms is about twelve seconds, and the
 * progress callback is what makes that acceptable rather than invisible.
 *
 * **A failure MUST NOT abort the batch.** The groups after it are independent, and
 * stopping would leave the user unable to tell which ones were even attempted.
 */
export async function runBatch(
	submit: SubmitFn,
	photoId: string,
	groupIds: readonly string[],
	acknowledged: ReadonlySet<string>,
	report: (batch: Batch) => void,
): Promise<Batch> {
	const batch = new Map<string, ItemState>(emptyBatch(groupIds));

	for (const groupId of groupIds) {
		batch.set(groupId, { kind: "sending" });
		report(new Map(batch));

		try {
			const reply = await submit(photoId, groupId, acknowledged.has(groupId));
			batch.set(groupId, toState(reply));
		} catch (error) {
			batch.set(groupId, { kind: "failed", error });
		}

		report(new Map(batch));
	}

	return batch;
}

/** Groups still holding an unanswered ADR-04 question, in submission order. */
export function awaitingAcknowledgement(batch: Batch): string[] {
	return [...batch]
		.filter(([, state]) => state.kind === "needsAcknowledgement")
		.map(([groupId]) => groupId);
}

/**
 * A Flickr photo id out of a URL a person pasted.
 *
 * **Returns null rather than throwing**, because a half-typed URL is the normal state
 * of this field and an exception per keystroke is not an error condition.
 *
 * The 2021 UI took `url.split("/")[5]` and checked it was numeric. That works for
 * `flickr.com/photos/user/12345` and breaks on a query string, a trailing slash, an
 * `/in/album-...` suffix, or `flic.kr/p/...`. This parses the URL properly and takes
 * the segment after `photos/<user>`.
 */
export function photoIdFromUrl(input: string): string | null {
	const trimmed = input.trim();
	if (trimmed === "") return null;

	// A bare id is a legitimate paste, and rejecting it would be pedantry.
	if (/^\d{5,}$/.test(trimmed)) return trimmed;

	let url: URL;
	try {
		url = new URL(trimmed.includes("://") ? trimmed : `https://${trimmed}`);
	} catch {
		return null;
	}

	const segments = url.pathname.split("/").filter((s) => s.length > 0);
	const photos = segments.indexOf("photos");

	// flickr.com/photos/<user>/<id>
	if (photos !== -1 && segments.length > photos + 2) {
		const candidate = segments[photos + 2];
		if (candidate !== undefined && /^\d{5,}$/.test(candidate)) return candidate;
	}

	return null;
}
