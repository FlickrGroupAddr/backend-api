import { describe, expect, it } from "vitest";
import {
	classifyAdd,
	classifyResult,
	outcomeColumn,
} from "../src/adds/classify.js";

/** ADR-07 and ADR-08. Widening `RETRYABLE` is the most dangerous edit in the repo. */

type Kind = ReturnType<typeof classifyAdd>["kind"];

/** Every code Flickr documents, plus the success case. Pinning the whole table in one
 *  place is what stops a new code being quietly added to the retryable set. */
const TABLE: ReadonlyArray<[code: number | null, kind: Kind]> = [
	[null, "resolved"], // added
	[3, "resolved"], // already in pool
	[6, "moderated"], // in a human's queue
	[7, "moderated"],
	[5, "retry"], // the throttle FGA exists to wait out
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
	[4242, "terminal"], // a code Flickr has not invented yet
];

describe("classifyAdd", () => {
	it.each(TABLE)("code %s is %s", (code, kind) => {
		expect(classifyAdd(code).kind).toBe(kind);
	});

	it("has exactly three retryable codes", () => {
		const retryable = TABLE.filter(([, kind]) => kind === "retry").map(
			([code]) => code,
		);
		expect(retryable).toEqual([5, 105, 106]);
	});

	it("asks for a re-link on 98 and 99, and nowhere else", () => {
		const relinks = TABLE.filter(([code]) => code !== null)
			.map(([code]) => code as number)
			.filter((code) => {
				const d = classifyAdd(code);
				return d.kind === "terminal" && d.relink;
			});
		expect(relinks).toEqual([98, 99]);
	});
});

describe("classifyResult", () => {
	it("treats an unanswered call as terminal, never retryable", () => {
		const d = classifyResult({ kind: "unreachable", detail: "socket died" });
		expect(d.kind).toBe("unconfirmed");
		expect(outcomeColumn(d)).toBe("failed");
	});

	it("keeps an unanswered call distinct from a Flickr-reported failure", () => {
		expect(classifyResult({ kind: "unreachable", detail: "x" }).kind).not.toBe(
			classifyResult({ kind: "error", code: 1, message: "" }).kind,
		);
	});
});

describe("outcomeColumn", () => {
	it("leaves a retryable outcome pending", () => {
		expect(outcomeColumn({ kind: "retry", code: 5 })).toBeNull();
	});

	it("has no value meaning a moderator rejected the photo", () => {
		// Flickr reports no rejection, so naming one would make the schema dishonest.
		const values = TABLE.map(([code]) => outcomeColumn(classifyAdd(code)));
		expect(values).not.toContain("rejected");
		// null is the retry case, which stays pending rather than resolving.
		expect(new Set(values.filter((v) => v !== null))).toEqual(
			new Set([
				"succeeded",
				"already_in_pool",
				"queued_for_moderator",
				"failed",
			]),
		);
	});
});
