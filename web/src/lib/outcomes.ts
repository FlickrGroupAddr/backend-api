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
	readonly detail: string;
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
			headline:
				request.position === null
					? "Waiting"
					: request.position === 1
						? "Next in line"
						: `Number ${request.position} in line`,
			detail:
				request.attempts === 0
					? "We will try this tonight."
					: `Tried ${request.attempts} ${request.attempts === 1 ? "time" : "times"} so far. Flickr caps how many photos you may add to a group each day, so we wait and try again.`,
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
				detail:
					"A volunteer reviews adds for this group, and your photo is in their queue. Flickr never tells us what they decide, so we stop here rather than submit it to the same person again. If it does not appear, that was their call.",
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
