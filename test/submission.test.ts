import { describe, expect, it } from "vitest";
import type { Submitted } from "../web/src/lib/contract.js";
import {
	awaitingAcknowledgement,
	type Batch,
	emptyBatch,
	photoIdFromUrl,
	runBatch,
	type SubmitFn,
} from "../web/src/lib/submission.js";

/**
 * ADR-01, ADR-03 and ADR-04, as the browser runs them.
 *
 * **Nothing under `web/src/lib/` was covered by any test until 2026-08-19**, and that is
 * 713 lines holding the rules a person actually meets. `runBatch` being sequential IS
 * ADR-01 at the client end -- forty parallel posts are forty simultaneous calls to Flickr
 * on one user's credentials, which is the same discourtesy in a performance costume.
 */

const QUEUED: Submitted = {
	status: "queued",
	publicId: "11111111-1111-4111-8111-111111111111",
};

function ack(stillPending: boolean): Submitted {
	return {
		status: "needs_acknowledgement",
		reason: "reached_a_moderator",
		flickrCode: 6,
		firstSeenAt: 1_700_000_000_000,
		stillPending,
	};
}

/**
 * The boring reply, as a resolved promise rather than an `async` stub.
 *
 * **A real `submit` is a `fetch`, so it MUST hand back a promise rather than throw
 * synchronously.** Biome's `useAwait` is what forces the distinction to be written down:
 * an `async` function with nothing to await hides which of the two a test is exercising.
 */
const alwaysQueued: SubmitFn = () => Promise.resolve(QUEUED);

describe("photoIdFromUrl", () => {
	it.each([
		["53912345678", "a bare id is a legitimate paste"],
		["https://www.flickr.com/photos/terry/53912345678", "the canonical URL"],
		["https://www.flickr.com/photos/terry/53912345678/", "a trailing slash"],
		[
			"https://www.flickr.com/photos/terry/53912345678/in/album-72177720316",
			"an /in/album suffix",
		],
		[
			"https://www.flickr.com/photos/terry/53912345678?foo=bar",
			"a query string",
		],
		["www.flickr.com/photos/terry/53912345678", "no protocol"],
		["  https://flickr.com/photos/terry/53912345678  ", "surrounding space"],
	])("takes the id out of %s -- %s", (input) => {
		expect(photoIdFromUrl(input)).toBe("53912345678");
	});

	it.each([
		["", "an empty field"],
		["   ", "only space"],
		["https://www.flickr.com/photos/terry", "a user page, not a photo"],
		["https://www.flickr.com/photos/terry/albums/72177720316", "an album page"],
		["https://www.flickr.com/groups/landscapes/pool", "a group pool"],
		["1234", "an id too short to be a Flickr photo"],
		["not a url at all", "prose"],
	])("returns null for %s -- %s", (input) => {
		expect(photoIdFromUrl(input)).toBeNull();
	});

	/**
	 * **A half-typed URL is the normal state of this field.** An exception per keystroke
	 * is not an error condition, so every rejection above has to be a null rather than a
	 * throw. This asserts the shape rather than trusting the ones above to have covered
	 * it.
	 */
	it("never throws, whatever is in the field", () => {
		for (const input of ["h", "ht", "http", "http:", "http://", "://", "%%%"]) {
			expect(() => photoIdFromUrl(input)).not.toThrow();
		}
	});
});

describe("emptyBatch", () => {
	it("starts every group waiting, in the order given", () => {
		const batch = emptyBatch(["b", "a", "c"]);
		expect([...batch.keys()]).toEqual(["b", "a", "c"]);
		expect([...batch.values()].every((s) => s.kind === "waiting")).toBe(true);
	});
});

describe("runBatch", () => {
	/**
	 * **ADR-01 at the client end.** The comment on `runBatch` says this MUST NOT be
	 * "optimized" into parallel requests, and nothing enforced it. A parallel rewrite
	 * still passes every other test in this file, so this is the one that would catch it:
	 * each call must complete before the next one starts.
	 */
	it("submits strictly one at a time", async () => {
		const events: string[] = [];
		const submit = async (
			_photoId: string,
			groupId: string,
		): Promise<Submitted> => {
			events.push(`start ${groupId}`);
			await Promise.resolve();
			events.push(`end ${groupId}`);
			return QUEUED;
		};

		await runBatch(submit, "53912345678", ["a", "b", "c"], new Set(), () => {});

		expect(events).toEqual([
			"start a",
			"end a",
			"start b",
			"end b",
			"start c",
			"end c",
		]);
	});

	it("reports before and after each group", async () => {
		const seen: Batch[] = [];
		await runBatch(
			alwaysQueued,
			"53912345678",
			["a", "b"],
			new Set(),
			(batch) => seen.push(batch),
		);

		// Two groups, two reports each.
		expect(seen).toHaveLength(4);
		expect(seen[0]?.get("a")?.kind).toBe("sending");
		expect(seen[1]?.get("a")?.kind).toBe("queued");
		expect(seen[1]?.get("b")?.kind).toBe("waiting");
		expect(seen[3]?.get("b")?.kind).toBe("queued");
	});

	/**
	 * **A failure MUST NOT abort the batch.** The groups after it are independent, and
	 * stopping would leave the person unable to tell which ones were even attempted --
	 * which is the state that sends somebody to Flickr to add photos by hand.
	 */
	it("keeps going after one group throws", async () => {
		const attempted: string[] = [];
		const submit: SubmitFn = (_photoId, groupId) => {
			attempted.push(groupId);
			// A rejected promise, because that is what a failed `fetch` hands back.
			if (groupId === "b") return Promise.reject(new Error("network"));
			return Promise.resolve(QUEUED);
		};

		const batch = await runBatch(
			submit,
			"53912345678",
			["a", "b", "c"],
			new Set(),
			() => {},
		);

		expect(attempted).toEqual(["a", "b", "c"]);
		expect(batch.get("a")?.kind).toBe("queued");
		expect(batch.get("b")?.kind).toBe("failed");
		expect(batch.get("c")?.kind).toBe("queued");
	});

	/** ADR-04. The acknowledgement is per group, not per batch. */
	it("passes the acknowledgement only for the groups that carry one", async () => {
		const flags: Array<[string, boolean]> = [];
		const submit: SubmitFn = (_photoId, groupId, acknowledged) => {
			flags.push([groupId, acknowledged]);
			return Promise.resolve(QUEUED);
		};

		await runBatch(
			submit,
			"53912345678",
			["a", "b", "c"],
			new Set(["b"]),
			() => {},
		);

		expect(flags).toEqual([
			["a", false],
			["b", true],
			["c", false],
		]);
	});

	it("carries the reply's own fields into the state", async () => {
		const batch = await runBatch(
			() => Promise.resolve(ack(true)),
			"53912345678",
			["a"],
			new Set(),
			() => {},
		);

		const state = batch.get("a");
		expect(state).toEqual({
			kind: "needsAcknowledgement",
			flickrCode: 6,
			firstSeenAt: 1_700_000_000_000,
			stillPending: true,
		});
	});

	/**
	 * **The reported batch MUST be a snapshot, not the live map.** Svelte's `$state`
	 * reassignment is what makes the results column update; handing out the same mutable
	 * object would make every earlier report retroactively show the final answer.
	 */
	it("reports a copy, so an earlier snapshot does not change under the caller", async () => {
		const seen: Batch[] = [];
		await runBatch(
			alwaysQueued,
			"53912345678",
			["a", "b"],
			new Set(),
			(batch) => seen.push(batch),
		);

		expect(seen[0]?.get("b")?.kind).toBe("waiting");
		expect(seen[0]).not.toBe(seen[3]);
	});
});

describe("awaitingAcknowledgement", () => {
	it("lists only the unanswered ADR-04 questions, in submission order", async () => {
		const submit: SubmitFn = (_photoId, groupId) =>
			Promise.resolve(groupId === "b" || groupId === "d" ? ack(false) : QUEUED);

		const batch = await runBatch(
			submit,
			"53912345678",
			["a", "b", "c", "d"],
			new Set(),
			() => {},
		);

		expect(awaitingAcknowledgement(batch)).toEqual(["b", "d"]);
	});

	it("is empty when nothing is waiting on the person", () => {
		expect(awaitingAcknowledgement(emptyBatch(["a", "b"]))).toEqual([]);
	});
});
