import { env } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { classifyAdd } from "../src/adds/classify.js";
import { enqueue, pairReachedAModerator } from "../src/db/requests.js";
import { type AttemptFn, sweep } from "../src/sweep.js";

/** ADR-06's nightly engine and ADR-03's walking rules, against real D1.
 *
 *  The attempt is scripted, so these test the RULES rather than Flickr -- and the rules
 *  are where an error is expensive. Jumping a queue spends an allowance belonging to a
 *  request that waited longer. Continuing past a moderated result shows a volunteer the
 *  same photo twice. */

const USER = "12345678@N00";
const OTHER = "87654321@N00";

/** Scripts an outcome per photo id and records the order attempts happened in. */
function scripted(byPhoto: Record<string, number | null>): {
	attempt: AttemptFn;
	order: string[];
} {
	const order: string[] = [];
	// biome-ignore lint/suspicious/useAwait: AttemptFn returns a Promise by contract, so async is the signature rather than an oversight.
	const attempt: AttemptFn = async (head) => {
		order.push(head.photoId);
		return classifyAdd(byPhoto[head.photoId] ?? null);
	};
	return { attempt, order };
}

async function addUser(nsid: string): Promise<void> {
	await env.DB.prepare(
		`INSERT INTO users
       (nsid, access_token_encrypted, access_token_secret_encrypted, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?)`,
	)
		.bind(nsid, new Uint8Array([1]), new Uint8Array([2]), 0, 0)
		.run();
}

async function stateOf(photoId: string) {
	return await env.DB.prepare(
		"SELECT state, outcome, attempts FROM requests WHERE photo_id = ?",
	)
		.bind(photoId)
		.first<{ state: string; outcome: string | null; attempts: number }>();
}

beforeEach(async () => {
	await env.DB.exec("DELETE FROM requests");
	await env.DB.exec("DELETE FROM moderated_pairs");
	await env.DB.exec("DELETE FROM users");
	await addUser(USER);
	await addUser(OTHER);
});

describe("the queue is never jumped", () => {
	it("attempts in append order and STOPS at the first throttle", async () => {
		for (const photo of ["p1", "p2", "p3"]) {
			await enqueue(env.DB, USER, photo, "g1");
		}

		// p1 succeeds, p2 is throttled. p3 MUST NOT be touched: it is blocked by the
		// same daily cap, so trying it would spend an allowance p2 has waited for.
		const { attempt, order } = scripted({ p1: null, p2: 5 });
		const report = await sweep(env.DB, attempt);

		expect(order).toEqual(["p1", "p2"]);
		expect(report.stoppedOnThrottle).toBe(1);
		expect((await stateOf("p2"))?.state).toBe("pending");
		expect((await stateOf("p3"))?.state).toBe("pending");
	});

	it("keeps walking past a terminal or moderated result", async () => {
		for (const photo of ["p1", "p2", "p3"]) {
			await enqueue(env.DB, USER, photo, "g1");
		}

		const { attempt, order } = scripted({ p1: 1, p2: 6, p3: null });
		await sweep(env.DB, attempt);

		expect(order).toEqual(["p1", "p2", "p3"]);
	});
});

describe("queues are independent", () => {
	it("does not let one queue's throttle stop another", async () => {
		await enqueue(env.DB, USER, "p1", "g1");
		await enqueue(env.DB, OTHER, "p2", "g1");
		await enqueue(env.DB, USER, "p3", "g2");

		const { attempt, order } = scripted({ p1: 5 });
		await sweep(env.DB, attempt);

		expect([...order].sort((a, b) => a.localeCompare(b))).toEqual([
			"p1",
			"p2",
			"p3",
		]);
	});

	it("survives one queue throwing, reports it, and leaves that request pending", async () => {
		await enqueue(env.DB, USER, "boom", "g1");
		await enqueue(env.DB, OTHER, "p2", "g1");

		// biome-ignore lint/suspicious/useAwait: AttemptFn returns a Promise by contract, so async is the signature rather than an oversight.
		const attempt: AttemptFn = async (head) => {
			if (head.photoId === "boom") throw new Error("network gone");
			return classifyAdd(null);
		};
		const report = await sweep(env.DB, attempt);

		expect(report.errors).toHaveLength(1);
		expect((await stateOf("p2"))?.state).toBe("resolved");
		// ADR-01: we do not know what happened, so it MUST NOT resolve.
		expect((await stateOf("boom"))?.state).toBe("pending");
	});

	/**
	 * **The same promise, for the WRITE half, which went unguarded for months.**
	 *
	 * `sweep`'s own comment says one queue failing MUST NOT abandon the others, and the
	 * `catch` above only ever covered the attempt. A D1 error in `resolveRequest` escaped
	 * `sweep` entirely -- so every queue behind it was skipped, and `scheduled` never
	 * reached the `console.log` that makes a night queryable. **ADR-06 built that log for
	 * bad nights, and it was the bad nights it lost.**
	 *
	 * `db.batch` is what `resolveRequest` calls and nothing else in this path does, so
	 * failing it targets exactly the write.
	 */
	it("survives a FAILED WRITE, keeps walking, and still returns a report", async () => {
		await enqueue(env.DB, USER, "p1", "g1");
		await enqueue(env.DB, OTHER, "p2", "g1");

		let batches = 0;
		const flaky = new Proxy(env.DB, {
			get(target, property, receiver) {
				if (property === "batch") {
					return async (statements: D1PreparedStatement[]) => {
						batches++;
						if (batches === 1) throw new Error("D1_ERROR: storage");
						return await target.batch(statements);
					};
				}
				return Reflect.get(target, property, receiver);
			},
		});

		const { attempt } = scripted({ p1: null, p2: null });
		const report = await sweep(flaky, attempt);

		// It RETURNED. Before the fix this threw, and the caller logged nothing at all.
		expect(report.errors).toHaveLength(1);
		expect(report.errors[0]).toContain("D1_ERROR");

		// The queue behind the failure was still walked.
		expect(report.resolved).toBe(1);
		expect((await stateOf("p2"))?.state).toBe("resolved");

		// ADR-01. A write that failed is an unknown outcome, so the row stays pending
		// and gets attempted again rather than resolved on a guess.
		expect((await stateOf("p1"))?.state).toBe("pending");
	});
});

describe("ADR-04, the permanent record", () => {
	it.each([
		[6, true],
		[7, true],
		[3, false],
		[8, false],
		[5, false],
	])("code %s writes a moderated_pairs row: %s", async (code, expected) => {
		await enqueue(env.DB, USER, "p1", "g1");
		const { attempt } = scripted({ p1: code });
		await sweep(env.DB, attempt);

		const pair = await pairReachedAModerator(env.DB, USER, "p1", "g1");
		expect(pair !== null).toBe(expected);
	});

	it("records the attempt count and resolution on the request row", async () => {
		await enqueue(env.DB, USER, "p1", "g1");
		await sweep(env.DB, scripted({ p1: 6 }).attempt);

		const row = await stateOf("p1");
		expect(row).toMatchObject({
			state: "resolved",
			outcome: "queued_for_moderator",
			attempts: 1,
		});
	});
});

it("does nothing on an empty night, and says so", async () => {
	const report = await sweep(env.DB, scripted({}).attempt);
	expect(report).toMatchObject({ queuesWalked: 0, attempted: 0, resolved: 0 });
});
