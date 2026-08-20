import { describe, expect, it } from "vitest";
import { ApiError } from "../web/src/lib/api.js";
import type { QueuedRequest } from "../web/src/lib/contract.js";
import {
	ago,
	describeError,
	explain,
	TICK_CAP,
	ticksFor,
} from "../web/src/lib/outcomes.js";

/**
 * ADR-01, ADR-03, ADR-04 and ADR-17, as the sentences a person reads.
 *
 * **`outcomes.ts` says of itself that it is where ADR-01 is kept or broken**, and until
 * 2026-08-19 nothing tested it. Every other decision in this project implements the
 * stopping; this is the only place anybody finds out it happened.
 *
 * **The copy is still open** -- `DECISIONS.md` lists the exact wording as unsettled, so
 * these tests pin the RULES the file states about itself rather than the strings. A test
 * asserting the current sentence word for word would have to be rewritten by the same
 * edit that improves it, which is how a suite starts arguing against its own project.
 */

function request(over: Partial<QueuedRequest> = {}): QueuedRequest {
	return {
		publicId: "11111111-1111-4111-8111-111111111111",
		photoId: "53912345678",
		state: "resolved",
		outcome: "succeeded",
		flickrCode: null,
		attempts: 1,
		queuedAt: 1_700_000_000_000,
		lastAttemptAt: 1_700_000_100_000,
		resolvedAt: 1_700_000_100_000,
		position: null,
		...over,
	};
}

/** Every outcome the contract can carry, plus the two pending shapes. */
const EVERY_CASE: readonly QueuedRequest[] = [
	request({ state: "pending", outcome: null, position: 1 }),
	request({ state: "pending", outcome: null, position: 7 }),
	request({ state: "pending", outcome: null, position: null }),
	request({ outcome: "succeeded" }),
	request({ outcome: "already_in_pool" }),
	request({ outcome: "queued_for_moderator" }),
	request({ outcome: "withdrawn" }),
	request({ outcome: "failed", flickrCode: 1 }),
	request({ outcome: "failed", flickrCode: 2 }),
	request({ outcome: "failed", flickrCode: 4 }),
	request({ outcome: "failed", flickrCode: 8 }),
	request({ outcome: "failed", flickrCode: 10 }),
	request({ outcome: "failed", flickrCode: 11 }),
	request({ outcome: "failed", flickrCode: 98 }),
	request({ outcome: "failed", flickrCode: 99 }),
	request({ outcome: "failed", flickrCode: 4242 }),
	request({ outcome: "failed", flickrCode: null }),
];

describe("explain, against the three rules the file states about itself", () => {
	/**
	 * **Rule 1, and it is the one ADR-01 exists to protect.** Flickr reports no rejection
	 * signal, so claiming one would be a lie the schema deliberately refuses to store.
	 * "Waiting on a person" is the truth. "Declined" is not available.
	 */
	it.each(EVERY_CASE)(
		"never implies a moderator decided (%#)",
		(queuedRequest) => {
			const { headline, detail } = explain(queuedRequest);
			const text = `${headline} ${detail ?? ""}`.toLowerCase();
			for (const forbidden of [
				"reject",
				"declin",
				"denied",
				"refused your",
				"turned down",
				"not approved",
			]) {
				expect(text).not.toContain(forbidden);
			}
		},
	);

	/** Rule 3. A dead end with no move is where people start clicking things. */
	it.each(EVERY_CASE)(
		"always answers with a headline (%#)",
		(queuedRequest) => {
			expect(explain(queuedRequest).headline.length).toBeGreaterThan(0);
		},
	);

	it("says whether tonight is this request's turn, and nothing about position", () => {
		const next = explain(
			request({ state: "pending", outcome: null, position: 1 }),
		);
		const later = explain(
			request({ state: "pending", outcome: null, position: 9 }),
		);

		expect(next.headline).toBe("Next tonight");
		expect(later.headline).toBe("In line");
		// The ticks carry the number. Repeating it here is the wallpaper this field
		// was emptied to avoid.
		expect(next.detail).toBeNull();
		expect(later.detail).toBeNull();
	});

	/** ADR-04 and ADR-01. The single most important string in the product. */
	it("marks a moderated request as a human holding it, not as a failure", () => {
		const { tone, detail } = explain(
			request({ outcome: "queued_for_moderator" }),
		);
		expect(tone).toBe("human");
		expect(detail).not.toBeNull();
		// It has to say a PERSON has it, and that we stopped. Both halves, or the
		// sentence is either alarming or silent about the stop.
		expect(detail?.toLowerCase()).toContain("volunteer");
		expect(detail?.toLowerCase()).toContain("stop");
	});

	it("treats an expired sign-in as an action, not as a dead end", () => {
		for (const code of [98, 99]) {
			const { headline, detail } = explain(
				request({ outcome: "failed", flickrCode: code }),
			);
			expect(headline).toBe("Sign in again");
			expect(detail?.toLowerCase()).toContain("sign in");
		}
	});

	it("names the reason when Flickr gave one it recognizes", () => {
		expect(
			explain(request({ outcome: "failed", flickrCode: 4 })).detail,
		).toContain("as many groups as Flickr allows");
	});

	/**
	 * **ADR-02's terminal-and-unknown case.** A code Flickr has not invented yet must
	 * still explain that FGA stopped ON PURPOSE, or the stop reads as a bug and the
	 * person adds the photo by hand -- recreating exactly the harm ADR-01 prevents.
	 */
	it.each([4242, null])(
		"says why it stopped on an unrecognized code %s",
		(code) => {
			const { detail } = explain(
				request({ outcome: "failed", flickrCode: code }),
			);
			expect(detail?.toLowerCase()).toContain("stopped");
		},
	);

	it("distinguishes added from already there", () => {
		const added = explain(request({ outcome: "succeeded" }));
		const already = explain(request({ outcome: "already_in_pool" }));

		expect(added.tone).toBe("good");
		expect(already.tone).toBe("good");
		expect(added.headline).not.toBe(already.headline);
	});

	it("says a withdrawal stopped everything after it", () => {
		const { tone, detail } = explain(request({ outcome: "withdrawn" }));
		expect(tone).toBe("stopped");
		expect(detail?.toLowerCase()).toContain("nothing was sent");
	});
});

describe("describeError", () => {
	/**
	 * **The defect this function exists for.** The group list failed and the page
	 * rendered `500 unparseable`, which is `ApiError.message` -- a debug string. A
	 * message that reads as a crash tells the user the tool is broken, and a user who
	 * believes that adds the photo by hand.
	 */
	it.each([
		"no_flickr_credentials",
		"flickr_unavailable",
		"too_many_groups",
		"invalid_request",
		"unknown_cursor",
	])("never leaks the status line for %s", (code) => {
		const sentence = describeError(
			new ApiError(500, code),
			"loading the queue",
		);
		expect(sentence).not.toContain("500");
		expect(sentence).not.toContain(code);
		expect(sentence.endsWith(".")).toBe(true);
	});

	/** ADR-17. Says WHY the list is absent instead of quietly showing part of it. */
	it("explains the group ceiling as a refusal, not as a failure", () => {
		const sentence = describeError(
			new ApiError(400, "too_many_groups"),
			"loading your groups",
		);
		expect(sentence).toContain("partial list");
		expect(sentence).toContain("nothing was submitted or changed");
	});

	/**
	 * **Silence about consequences is what makes an error feel like data loss.** The
	 * fallback has to say what FGA did NOT do, for a code nobody has seen yet and for a
	 * plain thrown Error alike.
	 */
	it.each([
		new ApiError(500, "something_new"),
		new Error("boom"),
		"a string nobody wrapped",
		null,
	])("says nothing was changed for an unknown failure (%#)", (thrown) => {
		const sentence = describeError(thrown, "submitting");
		expect(sentence).toContain("submitting");
		expect(sentence).toContain("Nothing was submitted or changed");
	});
});

describe("ticksFor, ADR-03's ordering made visible", () => {
	it.each([null, 0, -1])(
		"is null for %s, which is in no line at all",
		(position) => {
			expect(ticksFor(position)).toBeNull();
		},
	);

	it("fills exactly one mark, always the last", () => {
		for (const position of [1, 2, 5, TICK_CAP, TICK_CAP + 1, 40]) {
			const ticks = ticksFor(position);
			expect(ticks).not.toBeNull();
			const marks = ticks?.marks ?? [];
			expect(marks.filter(Boolean)).toHaveLength(1);
			expect(marks.at(-1)).toBe(true);
		}
	});

	it("draws one mark per place up to the cap", () => {
		expect(ticksFor(1)?.marks).toEqual([true]);
		expect(ticksFor(3)?.marks).toEqual([false, false, true]);
		expect(ticksFor(TICK_CAP)?.marks).toHaveLength(TICK_CAP);
		expect(ticksFor(TICK_CAP)?.overflow).toBe(0);
	});

	/** **The precise position is never lost.** Past the cap the overflow carries it. */
	it.each([TICK_CAP + 1, TICK_CAP + 7, 100])(
		"keeps the whole position across marks plus overflow at %s",
		(position) => {
			const ticks = ticksFor(position);
			expect(ticks?.marks).toHaveLength(TICK_CAP);
			expect((ticks?.marks.length ?? 0) + (ticks?.overflow ?? 0)).toBe(
				position,
			);
		},
	);
});

describe("ago", () => {
	const NOW = 1_700_000_000_000;

	it("reads as the past for a past instant", () => {
		expect(ago(NOW - 3 * 3_600_000, NOW)).toContain("3");
		expect(ago(NOW - 3 * 3_600_000, NOW)).toContain("hour");
		expect(ago(NOW - 2 * 86_400_000, NOW)).toContain("day");
	});

	it("picks the largest unit that fits", () => {
		expect(ago(NOW - 45_000, NOW)).toContain("second");
		expect(ago(NOW - 5 * 60_000, NOW)).toContain("minute");
		expect(ago(NOW - 3 * 604_800_000, NOW)).toContain("week");
		expect(ago(NOW - 400 * 86_400_000, NOW)).toContain("year");
	});

	/** A request stamped this instant must not read as one second in the future. */
	it("does not go negative on the same instant", () => {
		expect(ago(NOW, NOW)).not.toContain("-");
	});
});
