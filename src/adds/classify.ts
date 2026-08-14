import type { FlickrResult } from "../flickr/api.js";

/**
 * ADR-02 and ADR-01 as executable code. The most consequential function here.
 *
 * **An unrecognized outcome is TERMINAL.** The 2022 version defaulted the other way and
 * retried codes 1, 2, 4, 7, 8, 10 and 11 nightly forever -- every one a permanent
 * condition. An unknown failure is the one most likely to be permanent.
 */

export type Disposition =
	| {
			readonly kind: "resolved";
			readonly outcome: "succeeded" | "already_in_pool";
	  }
	/** In front of a person. Terminal. NOT a failure and NOT a success. */
	| { readonly kind: "moderated"; readonly code: 6 | 7 }
	/** The only path back into a queue. */
	| { readonly kind: "retry"; readonly code: number }
	| {
			readonly kind: "terminal";
			readonly code: number;
			readonly relink: boolean;
	  }
	/**
	 * Flickr never answered. Terminal, and kept separate from `terminal` because the
	 * user is owed a different sentence: "we could not confirm this", not "Flickr said
	 * no". A timed-out add may still have reached a moderator.
	 */
	| { readonly kind: "unconfirmed"; readonly detail: string };

/** **Adding to this set is the most dangerous edit in this repository.** 5 is the
 *  per-group per-user throttle FGA exists to wait out. 105 and 106 are transient. */
const RETRYABLE = new Set([5, 105, 106]);

const MODERATED = new Set([6, 7]);
const AUTH_FAILURE = new Set([98, 99]);

/** `code` is null on success -- Flickr returns none when the photo goes straight in. */
export function classifyAdd(code: number | null): Disposition {
	if (code === null) {
		return { kind: "resolved", outcome: "succeeded" };
	}

	// 3 is "already in pool": the goal state, reached another way. ADR-05.
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

	// Everything else, INCLUDING codes Flickr has not invented yet.
	return { kind: "terminal", code, relink: false };
}

/** ADR-04: this pair must be written to `moderated_pairs`. */
export function reachedAModerator(
	disposition: Disposition,
): disposition is { kind: "moderated"; code: 6 | 7 } {
	return disposition.kind === "moderated";
}

/**
 * Onto the schema's `outcome` column.
 *
 * **There is deliberately no value meaning "a moderator rejected it."** The Flickr API
 * never reports one, so naming it would make the schema, and the copy the user reads,
 * dishonest.
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

/** Exists so the `unreachable` branch cannot be skipped: a transport failure has no
 *  Flickr code, and inventing one would erase the distinction ADR-01 depends on. */
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
