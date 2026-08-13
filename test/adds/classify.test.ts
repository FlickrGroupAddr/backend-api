import { describe, expect, it } from "vitest";
import {
	classifyAdd,
	classifyResult,
	outcomeColumn,
	reachedAModerator,
} from "../../src/adds/classify.js";

/**
 * ADR-07's table, and ADR-08's standing order, as executable assertions.
 *
 * This is the suite that would have caught the 2022 bug. That version retried
 * every unrecognized code nightly forever, which meant codes 1, 2, 4, 7, 8, 10
 * and 11 -- including code 7, where a volunteer moderator already has the photo
 * in front of them. Terry's words for what that produced: "I might have infinite
 * bombed a few group moderators by accident."
 */

/** Every code ADR-07 names, with the class the document assigns it. */
const TABLE: ReadonlyArray<readonly [number | null, string]> = [
	[null, "resolved"],
	[3, "resolved"],
	[6, "moderated"],
	[7, "moderated"],
	[5, "retry"],
	[105, "retry"],
	[106, "retry"],
	[1, "terminal"],
	[2, "terminal"],
	[4, "terminal"],
	[8, "terminal"],
	[10, "terminal"],
	[11, "terminal"],
	[98, "terminal"],
	[99, "terminal"],
];

describe("ADR-07's table, code by code", () => {
	for (const [code, kind] of TABLE) {
		it(`classifies ${code ?? "success"} as ${kind}`, () => {
			expect(classifyAdd(code).kind).toBe(kind);
		});
	}
});

describe("the inverted default -- the 2022 bug, refused", () => {
	it("treats every unrecognized code as terminal", () => {
		// Sweeps the whole plausible space, including codes Flickr has not
		// invented. An unknown failure is the one MOST likely to be permanent,
		// and in the old design it was the one guaranteed to repeat.
		const known = new Set([3, 5, 6, 7, 105, 106]);

		for (let code = 0; code < 1000; code++) {
			if (known.has(code)) continue;
			expect(classifyAdd(code).kind).toBe("terminal");
		}
	});

	it("never marks an unknown code retryable", () => {
		for (const code of [12, 13, 42, 100, 107, 200, 404, 500, 999, -1]) {
			expect(classifyAdd(code).kind).not.toBe("retry");
		}
	});

	it("has exactly three retryable codes, and they are 5, 105 and 106", () => {
		// Locked deliberately. Widening this set is the single most dangerous
		// edit in the codebase: every code added here becomes something FGA will
		// resubmit, and resubmitting into a moderation queue is the one failure
		// this project will not ship.
		const retryable = [];
		for (let code = -100; code < 2000; code++) {
			if (classifyAdd(code).kind === "retry") retryable.push(code);
		}
		expect(retryable).toEqual([5, 105, 106]);
	});
});

describe("ADR-08, the moderator-protection rule", () => {
	it("makes 6 and 7 terminal, never retryable", () => {
		// A resubmission does not look like a retry to Flickr. It looks like a
		// brand-new submission, and the same volunteer sees the same photo again.
		for (const code of [6, 7]) {
			const disposition = classifyAdd(code);
			expect(disposition.kind).toBe("moderated");
			expect(disposition.kind).not.toBe("retry");
		}
	});

	it("distinguishes moderated from both success and failure", () => {
		// It is neither. Collapsing it into "failed" would make the user think
		// something went wrong; collapsing it into "succeeded" would claim the
		// photo is in the pool when a person has not yet decided.
		const disposition = classifyAdd(6);
		expect(disposition.kind).not.toBe("resolved");
		expect(disposition.kind).not.toBe("terminal");
	});

	it("flags exactly 6 and 7 for the permanent record", () => {
		// ADR-11 keeps code 8 out: a policy rejection means nobody reviewed it,
		// and a warning that fires on ordinary errors is a warning nobody reads.
		expect(reachedAModerator(classifyAdd(6))).toBe(true);
		expect(reachedAModerator(classifyAdd(7))).toBe(true);

		for (const code of [null, 1, 2, 3, 4, 5, 8, 10, 11, 98, 99, 105, 106, 42]) {
			expect(reachedAModerator(classifyAdd(code))).toBe(false);
		}
	});
});

describe("auth failures", () => {
	it("asks for a re-link on 98 and 99, and only those", () => {
		for (const code of [98, 99]) {
			const disposition = classifyAdd(code);
			expect(disposition).toEqual({ kind: "terminal", code, relink: true });
		}

		for (const code of [1, 2, 4, 8, 10, 11, 42]) {
			const disposition = classifyAdd(code);
			expect(disposition).toEqual({ kind: "terminal", code, relink: false });
		}
	});
});

describe("an unanswered call, ADR-08 at the transport layer", () => {
	it("is terminal, never retryable", () => {
		// A request that timed out may still have been processed. If the pool was
		// moderated, the photo could be in front of a volunteer right now, and a
		// retry would show it to them a second time.
		const disposition = classifyResult({
			kind: "unreachable",
			detail: "connection reset",
		});

		expect(disposition.kind).toBe("unconfirmed");
		expect(disposition.kind).not.toBe("retry");
		expect(outcomeColumn(disposition)).toBe("failed");
	});

	it("stays distinct from a Flickr-reported failure", () => {
		// Same behavior, different reason, and the user is owed a different
		// sentence: "we could not confirm this" is not "Flickr said no".
		expect(classifyResult({ kind: "unreachable", detail: "x" }).kind).toBe(
			"unconfirmed",
		);
		expect(classifyResult({ kind: "error", code: 8, message: "" }).kind).toBe(
			"terminal",
		);
	});

	it("keeps Flickr's own transient codes retryable", () => {
		// The asymmetry is deliberate. With 105 and 106 Flickr is TELLING us the
		// write did not happen; with a dead socket nobody is telling us anything.
		for (const code of [105, 106]) {
			expect(classifyResult({ kind: "error", code, message: "" }).kind).toBe(
				"retry",
			);
		}
	});

	it("treats a successful call as success", () => {
		expect(classifyResult({ kind: "ok", body: { stat: "ok" } }).kind).toBe(
			"resolved",
		);
	});
});

describe("outcomeColumn", () => {
	it("maps each disposition to a value the schema accepts", () => {
		expect(outcomeColumn(classifyAdd(null))).toBe("succeeded");
		expect(outcomeColumn(classifyAdd(3))).toBe("already_in_pool");
		expect(outcomeColumn(classifyAdd(6))).toBe("queued_for_moderator");
		expect(outcomeColumn(classifyAdd(7))).toBe("queued_for_moderator");
		expect(outcomeColumn(classifyAdd(8))).toBe("failed");
		expect(outcomeColumn(classifyAdd(42))).toBe("failed");
	});

	it("returns null for a retryable outcome, which stays pending", () => {
		// The schema's CHECK ties state to outcome: a pending row MUST have a null
		// outcome, so this is what keeps the request in its queue.
		for (const code of [5, 105, 106]) {
			expect(outcomeColumn(classifyAdd(code))).toBeNull();
		}
	});

	it("has no value meaning a moderator rejected the photo", () => {
		// No such signal exists in the Flickr API. Every disposition maps to one of
		// the four documented values or to null.
		const permitted = new Set([
			"succeeded",
			"already_in_pool",
			"queued_for_moderator",
			"failed",
			null,
		]);

		for (let code = -10; code < 300; code++) {
			expect(permitted.has(outcomeColumn(classifyAdd(code)))).toBe(true);
		}
	});
});
