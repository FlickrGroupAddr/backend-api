import { env } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { classifyAdd } from "../src/adds/classify.js";
import { enqueue, pairReachedAModerator } from "../src/db/requests.js";
import { type AttemptFn, sweep } from "../src/sweep.js";

/**
 * ADR-10's queue discipline, against real D1 in workerd.
 *
 * The attempt function is scripted, so these test the WALKING RULES rather than
 * Flickr. Those rules are where a subtle error is expensive: jumping a queue
 * spends an allowance slot belonging to a request that has waited longer, and
 * continuing past a moderated result shows a volunteer the same photo twice.
 */

const USER = "12345678@N00";
const OTHER = "87654321@N00";

/** Scripts outcomes by photo id, and records the order attempts happened in. */
function scripted(byPhoto: Record<string, number | null>): {
	attempt: AttemptFn;
	order: string[];
} {
	const order: string[] = [];
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

beforeEach(async () => {
	await env.DB.exec("DELETE FROM requests");
	await env.DB.exec("DELETE FROM moderated_pairs");
	await env.DB.exec("DELETE FROM users");
	await addUser(USER);
	await addUser(OTHER);
});

describe("ADR-10, the queue is never jumped", () => {
	it("attempts a queue strictly in append order", async () => {
		await enqueue(env.DB, USER, "photo-1", "group-a");
		await enqueue(env.DB, USER, "photo-2", "group-a");
		await enqueue(env.DB, USER, "photo-3", "group-a");

		const { attempt, order } = scripted({});
		await sweep(env.DB, attempt);

		expect(order).toEqual(["photo-1", "photo-2", "photo-3"]);
	});

	it("STOPS a queue at the first retryable failure", async () => {
		// Code 5 is the per-group throttle. Everything behind the head keeps its
		// place -- attempting photo-3 here would hand a later request an allowance
		// slot that belonged to photo-2.
		await enqueue(env.DB, USER, "photo-1", "group-a");
		await enqueue(env.DB, USER, "photo-2", "group-a");
		await enqueue(env.DB, USER, "photo-3", "group-a");

		const { attempt, order } = scripted({ "photo-2": 5 });
		const report = await sweep(env.DB, attempt);

		expect(order).toEqual(["photo-1", "photo-2"]);
		expect(report.stoppedOnThrottle).toBe(1);
	});

	it("leaves a throttled request pending, at the head", async () => {
		await enqueue(env.DB, USER, "photo-1", "group-a");
		await enqueue(env.DB, USER, "photo-2", "group-a");

		const { attempt } = scripted({ "photo-1": 5 });
		await sweep(env.DB, attempt);

		const rows = await env.DB.prepare(
			"SELECT photo_id, state FROM requests ORDER BY id",
		).all<{ photo_id: string; state: string }>();

		expect(rows.results).toEqual([
			{ photo_id: "photo-1", state: "pending" },
			{ photo_id: "photo-2", state: "pending" },
		]);
	});

	it("keeps walking past a terminal failure", async () => {
		// A terminal failure RESOLVES and leaves the queue, so it must not block
		// the requests behind it. ADR-10 says so explicitly, and it is the reason
		// being polite to a moderator never holds a queue up.
		await enqueue(env.DB, USER, "photo-1", "group-a");
		await enqueue(env.DB, USER, "photo-2", "group-a");

		const { attempt, order } = scripted({ "photo-1": 1 });
		await sweep(env.DB, attempt);

		expect(order).toEqual(["photo-1", "photo-2"]);
	});

	it("keeps walking past a moderated result", async () => {
		// Code 6 is terminal for THAT PAIR but resolves it, so the queue moves on.
		await enqueue(env.DB, USER, "photo-1", "group-a");
		await enqueue(env.DB, USER, "photo-2", "group-a");

		const { attempt, order } = scripted({ "photo-1": 6 });
		await sweep(env.DB, attempt);

		expect(order).toEqual(["photo-1", "photo-2"]);
	});

	it("never re-attempts a pair that reached a moderator", async () => {
		// The rule the whole project is shaped around. Once code 6 comes back, FGA
		// is done with that pair -- a resubmission looks like a brand-new
		// submission to Flickr and the same volunteer reviews it again.
		await enqueue(env.DB, USER, "photo-1", "group-a");

		const { attempt, order } = scripted({ "photo-1": 6 });
		await sweep(env.DB, attempt);
		await sweep(env.DB, attempt);
		await sweep(env.DB, attempt);

		expect(order).toEqual(["photo-1"]);
	});
});

describe("queues are independent", () => {
	it("does not let one user's throttle stop another user", async () => {
		await enqueue(env.DB, USER, "photo-1", "group-a");
		await enqueue(env.DB, OTHER, "photo-2", "group-a");

		const { attempt, order } = scripted({ "photo-1": 5 });
		const report = await sweep(env.DB, attempt);

		expect(order).toContain("photo-2");
		expect(report.queuesWalked).toBe(2);
	});

	it("does not let one group's throttle stop another group", async () => {
		// The queue key is (user, group), not user and not group alone.
		await enqueue(env.DB, USER, "photo-1", "group-a");
		await enqueue(env.DB, USER, "photo-2", "group-b");

		const { attempt, order } = scripted({ "photo-1": 5 });
		await sweep(env.DB, attempt);

		expect(order).toContain("photo-2");
	});

	it("survives one queue throwing, and reports it", async () => {
		await enqueue(env.DB, USER, "photo-boom", "group-a");
		await enqueue(env.DB, OTHER, "photo-fine", "group-a");

		const order: string[] = [];
		const attempt: AttemptFn = async (head) => {
			order.push(head.photoId);
			if (head.photoId === "photo-boom")
				throw new Error("token decrypt failed");
			return classifyAdd(null);
		};

		const report = await sweep(env.DB, attempt);

		expect(order).toContain("photo-fine");
		expect(report.errors).toHaveLength(1);
		expect(report.errors[0]).toContain("token decrypt failed");
	});

	it("does not resolve a request whose attempt threw", async () => {
		// We do not know what happened, so the row stays pending rather than being
		// marked failed. It also is not retried within this sweep.
		await enqueue(env.DB, USER, "photo-boom", "group-a");

		const attempt: AttemptFn = async () => {
			throw new Error("network gone");
		};
		await sweep(env.DB, attempt);

		const row = await env.DB.prepare(
			"SELECT state, attempts FROM requests",
		).first<{ state: string; attempts: number }>();

		expect(row?.state).toBe("pending");
		expect(row?.attempts).toBe(1);
	});
});

describe("ADR-11, the permanent record", () => {
	it("writes the pair when the add reaches a moderation queue", async () => {
		await enqueue(env.DB, USER, "photo-1", "group-a");

		const { attempt } = scripted({ "photo-1": 6 });
		await sweep(env.DB, attempt);

		expect(
			await pairReachedAModerator(env.DB, USER, "photo-1", "group-a"),
		).toMatchObject({ code: 6 });
	});

	it("records code 7 as well as code 6", async () => {
		await enqueue(env.DB, USER, "photo-7", "group-a");

		const { attempt } = scripted({ "photo-7": 7 });
		await sweep(env.DB, attempt);

		expect(
			await pairReachedAModerator(env.DB, USER, "photo-7", "group-a"),
		).toMatchObject({ code: 7 });
	});

	it("writes NOTHING for any other outcome", async () => {
		// Code 8 is a policy rejection with no human involved. A warning that
		// fires on ordinary errors is a warning nobody reads.
		for (const code of [null, 1, 2, 3, 4, 8, 10, 11, 42]) {
			await env.DB.exec("DELETE FROM requests");
			await env.DB.exec("DELETE FROM moderated_pairs");
			await enqueue(env.DB, USER, "photo-x", "group-a");

			const { attempt } = scripted({ "photo-x": code });
			await sweep(env.DB, attempt);

			expect(
				await pairReachedAModerator(env.DB, USER, "photo-x", "group-a"),
			).toBeNull();
		}
	});

	it("records the attempt count and resolution on the request row", async () => {
		await enqueue(env.DB, USER, "photo-1", "group-a");

		const { attempt } = scripted({ "photo-1": 6 });
		await sweep(env.DB, attempt);

		const row = await env.DB.prepare(
			"SELECT state, outcome, flickr_code, attempts FROM requests",
		).first();

		expect(row).toMatchObject({
			state: "resolved",
			outcome: "queued_for_moderator",
			flickr_code: 6,
			attempts: 1,
		});
	});
});

describe("an empty night", () => {
	it("does nothing and says so", async () => {
		const { attempt, order } = scripted({});
		const report = await sweep(env.DB, attempt);

		expect(order).toEqual([]);
		expect(report).toMatchObject({
			queuesWalked: 0,
			attempted: 0,
			resolved: 0,
		});
	});
});
