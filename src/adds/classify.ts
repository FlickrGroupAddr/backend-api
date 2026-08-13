import type { FlickrResult } from "../flickr/api.js";

/**
 * Classification of `flickr.groups.pools.add` outcomes, per ADR-07 and ADR-08.
 *
 * This is the most consequential function in the project. The 2022
 * implementation classified codes 5 and 6 explicitly and swept everything else
 * into a catch-all its retry query then re-attempted nightly, forever. That
 * bucket held codes 1, 2, 4, 7, 8, 10 and 11 -- every one a permanent condition
 * that could never succeed, and code 7 means a human volunteer already has the
 * photo in front of them.
 *
 * **The default here is inverted from that, and the inversion is the point: an
 * unrecognized outcome is TERMINAL.** An unknown failure is the one most likely
 * to be permanent, and in the old design it was the one guaranteed to repeat.
 */

/** What the caller must do next. Exhaustive by construction. */
export type Disposition =
	/** Resolved well. Nothing further to do for this pair. */
	| {
			readonly kind: "resolved";
			readonly outcome: "succeeded" | "already_in_pool";
	  }
	/**
	 * The photo is in a moderation queue in front of a person. Terminal, and
	 * recorded permanently by ADR-11. NOT a failure and NOT a success.
	 */
	| { readonly kind: "moderated"; readonly code: 6 | 7 }
	/** A condition that may pass. The only path back into a queue. */
	| { readonly kind: "retry"; readonly code: number }
	/** Terminal failure. `relink` means the user must re-authorize FGA. */
	| {
			readonly kind: "terminal";
			readonly code: number;
			readonly relink: boolean;
	  }
	/**
	 * Flickr never answered, so FGA does not know what happened. Terminal, and
	 * separate from `terminal` because the reason differs and the user is owed a
	 * different sentence: "we could not confirm this" rather than "Flickr said
	 * no".
	 *
	 * **This is ADR-08 applied to the transport layer.** A request that times out
	 * may still have been processed, and if the pool was moderated the photo may
	 * now be sitting in front of a volunteer. Retrying would show it to them
	 * twice. Flickr's own 105 and 106 are different in kind -- there Flickr is
	 * telling us the write did not happen, which is why those stay retryable.
	 */
	| { readonly kind: "unconfirmed"; readonly detail: string };

/**
 * The only codes that may be attempted again.
 *
 * **5 is the reason this project exists** -- the per-group, per-user throttle
 * that FGA waits out on the user's behalf. 105 and 106 are transient Flickr
 * failures. Nothing else belongs here, and adding to this list is the single
 * most dangerous edit available in this codebase.
 */
const RETRYABLE = new Set([5, 105, 106]);

/** Codes meaning the photo reached a moderation queue. ADR-08's whole subject. */
const MODERATED = new Set([6, 7]);

/** Auth failures. Terminal for this request, and the user must re-link. */
const AUTH_FAILURE = new Set([98, 99]);

/**
 * Classifies one add attempt.
 *
 * `code` is null for success -- Flickr returns no error code when the photo goes
 * straight into the pool.
 */
export function classifyAdd(code: number | null): Disposition {
	if (code === null) {
		return { kind: "resolved", outcome: "succeeded" };
	}

	// 3 is "photo already in pool", which is the goal state reached by another
	// route. ADR-05 requires treating it as success rather than as an error.
	if (code === 3) {
		return { kind: "resolved", outcome: "already_in_pool" };
	}

	if (MODERATED.has(code)) {
		return { kind: "moderated", code: code as 6 | 7 };
	}

	if (RETRYABLE.has(code)) {
		return { kind: "retry", code };
	}

	if (AUTH_FAILURE.has(code)) {
		return { kind: "terminal", code, relink: true };
	}

	// Everything else, INCLUDING codes Flickr has not invented yet. ADR-07 and
	// ADR-08: where an outcome could mean a person declined, it is terminal.
	return { kind: "terminal", code, relink: false };
}

/** True when the pair must be written to `moderated_pairs`. ADR-11. */
export function reachedAModerator(
	disposition: Disposition,
): disposition is { kind: "moderated"; code: 6 | 7 } {
	return disposition.kind === "moderated";
}

/**
 * Maps a disposition onto the schema's `outcome` column.
 *
 * There is deliberately no value meaning "rejected by a moderator", because the
 * Flickr API never reports one -- see the verified-facts row on moderator
 * decisions being invisible. Naming the column for what is KNOWN keeps the
 * schema, and the copy the user eventually reads, honest.
 */
export function outcomeColumn(
	disposition: Disposition,
): "succeeded" | "already_in_pool" | "queued_for_moderator" | "failed" | null {
	switch (disposition.kind) {
		case "resolved":
			return disposition.outcome;
		case "moderated":
			return "queued_for_moderator";
		case "terminal":
		case "unconfirmed":
			return "failed";
		case "retry":
			// Still pending. The request stays in its queue.
			return null;
	}
}

/**
 * Classifies a call result, which is what callers actually hold.
 *
 * The `unreachable` branch is the whole reason this exists rather than every
 * caller reaching for `classifyAdd` directly: a transport failure has no Flickr
 * code, and inventing one for it would hide the distinction ADR-08 depends on.
 */
export function classifyResult(result: FlickrResult): Disposition {
	switch (result.kind) {
		case "ok":
			return classifyAdd(null);
		case "error":
			return classifyAdd(result.code);
		case "unreachable":
			return { kind: "unconfirmed", detail: result.detail };
	}
}
