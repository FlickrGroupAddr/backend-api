import { ApiError } from "./api.js";
import type { QueuedRequest } from "./contract.js";

/**
 * **This file is where ADR-01 is kept or broken.**
 *
 * Every other decision in this project implements the stopping. This is the only place
 * a person finds out it happened, and DECISIONS.md lists the exact wording as still
 * open. **These sentences are a first draft and MUST be reviewed as product copy, not
 * as code.**
 *
 * Three rules they follow:
 *
 *   1. **Never imply a moderator rejected anything.** Flickr reports no such signal, so
 *      claiming one would be a lie the schema deliberately refuses to store. "Waiting on
 *      a person" is the truth; "declined" is not available.
 *   2. **Say what FGA did and why, not what went wrong.** A stop reads as a bug unless
 *      it explains itself, and a user who thinks the tool is broken adds the photo by
 *      hand -- which recreates exactly the harm ADR-01 prevents.
 *   3. **Name the next action when there is one.** A dead end with no move is where
 *      people start clicking things.
 *
 * Kept in TypeScript rather than in the template so `tsc --noEmit` checks it and a
 * future test can assert on it. `svelte-check` cannot run here -- see ADR-18.
 */

export type Tone = "waiting" | "good" | "human" | "stopped";

export type Explanation = {
	readonly tone: Tone;
	readonly headline: string;
	/**
	 * **Null for the ordinary waiting case, and that is the point.**
	 *
	 * Found by looking at a rendered queue of ten: the same sentence about Flickr's
	 * daily cap appeared on every row and drowned the one thing that varied. A detail
	 * repeated on every row is not detail, it is wallpaper. The standing explanation
	 * now sits once on the group card; this field carries only what is true of THIS
	 * request and could not be guessed from its neighbours.
	 */
	readonly detail: string | null;
};

/** Flickr codes worth naming individually. Everything else is terminal-and-unknown. */
const TERMINAL_DETAIL: Record<number, string> = {
	1: "Flickr could not find that photo. It may have been deleted.",
	2: "That group no longer exists.",
	4: "The photo is already in as many groups as Flickr allows.",
	8: "The group refused the photo's content rating.",
	10: "The group's pool is full.",
	11: "The group has switched its pool off.",
	98: "Your Flickr sign-in has expired.",
	99: "Your Flickr sign-in has expired.",
};

export function explain(request: QueuedRequest): Explanation {
	if (request.state === "pending") {
		return {
			tone: "waiting",
			// The ticks carry the position, so the headline does not repeat it. It says
			// only whether tonight is this request's turn.
			headline: request.position === 1 ? "Next tonight" : "In line",
			detail: null,
		};
	}

	switch (request.outcome) {
		case "succeeded":
			return {
				tone: "good",
				headline: "Added",
				detail: "The photo is in the pool.",
			};

		case "already_in_pool":
			return {
				tone: "good",
				headline: "Already there",
				detail: "The photo was in the pool before we got to it.",
			};

		// ADR-01 and ADR-04. The single most important string in the product.
		case "queued_for_moderator":
			return {
				tone: "human",
				headline: "With a moderator",
				// Three sentences got truncated mid-word in a table row -- found by
				// looking at the render, where the single most important promise in the
				// product read "...and your photo is in the...". Two sentences fit and
				// keep both halves that matter: a person has it, and we stopped.
				detail:
					"A volunteer has it in their review queue. Flickr never reports their decision, so we stop here rather than send it to the same person twice.",
			};

		case "withdrawn":
			return {
				tone: "stopped",
				headline: "Withdrawn",
				detail: "You cancelled this one. Nothing was sent after that.",
			};

		case "failed": {
			const known =
				request.flickrCode === null
					? undefined
					: TERMINAL_DETAIL[request.flickrCode];

			if (request.flickrCode === 98 || request.flickrCode === 99) {
				return {
					tone: "stopped",
					headline: "Sign in again",
					detail:
						"Your Flickr sign-in expired, so we could not act for you. Sign in to resume.",
				};
			}

			return {
				tone: "stopped",
				headline: "Stopped",
				detail:
					known ??
					"Flickr refused this one and we do not recognize the reason, so we stopped rather than keep retrying. Adding it by hand will tell you why.",
			};
		}

		default:
			return {
				tone: "stopped",
				headline: "Stopped",
				detail: "This one is finished, and we cannot say more about it.",
			};
	}
}

/**
 * A failure, as a sentence rather than a status line.
 *
 * **Found by looking at the running page, not by reading the code.** The group list
 * failed and the UI rendered `500 unparseable` -- which is `ApiError.message`, a debug
 * string of `${status} ${code}`. Nothing in the type system objects to printing it, and
 * a passing build has no opinion about it either.
 *
 * **It matters for the same reason ADR-01 does.** A message that reads as a crash tells
 * the user the tool is broken, and a user who believes that goes and adds the photo by
 * hand -- which is the exact harm the project exists to avoid. The status code belongs
 * in the console, never on the page.
 */
export function describeError(error: unknown, doing: string): string {
	const code = error instanceof ApiError ? error.code : null;

	switch (code) {
		case "no_flickr_credentials":
			return "Your Flickr sign-in is not linked any more. Sign in again to continue.";
		case "flickr_unavailable":
			return "Flickr did not answer. Nothing was changed, and trying again shortly usually works.";
		case "too_many_groups":
			// ADR-17. Says WHY the list is absent instead of quietly showing part of it.
			// A picker holding most of a wall is the failure the refusal exists to
			// prevent, and a user cannot tell which entries are missing.
			return "You are in more groups than FGA can list at once. It will not show a partial list, and nothing was submitted or changed.";
		case "invalid_request":
			return "That request did not look right, so nothing was sent.";
		case "unknown_cursor":
			return "That page of the queue has moved on. Reload to start from the top.";
		default:
			// Deliberately says what FGA did NOT do. Silence about consequences is what
			// makes an error feel like data loss.
			return `Something went wrong while ${doing}. Nothing was submitted or changed.`;
	}
}

/**
 * Queue position as a row of ticks: hollow for each request ahead of yours, filled for
 * yours. Null for a resolved request, which is in no line at all.
 *
 * **This is the one piece of ornament in the product that is actually data.** ADR-03
 * attempts requests strictly in append order within each `(user, group)` queue, and
 * that ordering is the single behavior a user is most likely to read as a bug — "why
 * did the photo I added later go through first, over there?" A bare number answers it
 * weakly. A line explains itself.
 *
 * **Capped at eight, because past that a glance becomes a counting exercise.** The
 * overflow count carries the rest, so the precise position is never lost.
 *
 * Lives here rather than in the component so `tsc --noEmit -p web` checks it — nothing
 * typechecks inside a `.svelte` file on this project. See ADR-18.
 */
export const TICK_CAP = 8;

export function ticksFor(
	position: number | null,
): { marks: boolean[]; overflow: number } | null {
	if (position === null || position < 1) return null;

	const shown = Math.min(position, TICK_CAP);

	// The last mark is yours; everything before it is somebody ahead of you.
	return {
		marks: Array.from({ length: shown }, (_, i) => i === shown - 1),
		overflow: Math.max(0, position - TICK_CAP),
	};
}

/** Relative time, because "3 hours ago" is read faster than a timestamp. */
const RELATIVE = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

const STEPS: readonly (readonly [Intl.RelativeTimeFormatUnit, number])[] = [
	["second", 1000],
	["minute", 60_000],
	["hour", 3_600_000],
	["day", 86_400_000],
	["week", 604_800_000],
	["month", 2_629_800_000],
	["year", 31_557_600_000],
];

export function ago(epochMillis: number, now: number = Date.now()): string {
	const elapsed = epochMillis - now;
	const size = Math.abs(elapsed);

	let unit: Intl.RelativeTimeFormatUnit = "second";
	let scale = 1000;
	for (const [candidate, millis] of STEPS) {
		if (size >= millis) {
			unit = candidate;
			scale = millis;
		}
	}

	return RELATIVE.format(Math.round(elapsed / scale), unit);
}
