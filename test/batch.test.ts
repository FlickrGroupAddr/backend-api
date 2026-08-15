import { env, SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { encryptToken } from "../src/crypto/tokens.js";
import { mintSession, SESSION_COOKIE } from "../src/session.js";

/**
 * `POST /api/v001/requests/batch` — one photo into many groups, in one round trip.
 *
 * **Built for the Lightroom Classic plug-in**, where forty groups meant forty POSTs and
 * roughly twelve seconds. The status vocabulary matches ADR-20's preflight exactly, so a
 * client renders one set of outcomes for both.
 */

const NSID = "12345678@N00";
const OTHER = "87654321@N00";
const API = "https://flickrgroupaddr.com";

type Entry = { groupId: string; status: string; publicId?: string };
type Reply = {
	photoId: string;
	poolsKnown: boolean;
	queuedCount: number;
	groups: Entry[];
};

async function addUser(nsid: string): Promise<void> {
	await env.DB.prepare(
		`INSERT INTO users
       (nsid, access_token_encrypted, access_token_secret_encrypted, created_at, updated_at)
     VALUES (?, ?, ?, 0, 0)`,
	)
		.bind(
			nsid,
			await encryptToken("access-token", nsid, env.TOKEN_KEY),
			await encryptToken("access-secret", nsid, env.TOKEN_KEY),
		)
		.run();
}

async function submit(body: unknown, nsid = NSID): Promise<Response> {
	return await SELF.fetch(`${API}/api/v001/requests/batch`, {
		method: "POST",
		headers: {
			Cookie: `${SESSION_COOKIE}=${await mintSession(env.DB, nsid, env.SESSION_KEY)}`,
			"Content-Type": "application/json",
		},
		body: JSON.stringify(body),
	});
}

const statusOf = (reply: Reply, groupId: string): string =>
	reply.groups.find((g) => g.groupId === groupId)?.status ?? "missing";

beforeEach(async () => {
	await env.DB.exec("DELETE FROM requests");
	await env.DB.exec("DELETE FROM moderated_pairs");
	await env.DB.exec("DELETE FROM sessions");
	await env.DB.exec("DELETE FROM users");
	await addUser(NSID);
	await addUser(OTHER);
});

describe("ADR-03, the batch endpoint does NOT attempt at batch scale", () => {
	it("queues every group without attempting any of them", async () => {
		/**
		 * **The load-bearing property of this endpoint.** ADR-03 lets the single POST
		 * attempt immediately when a request is alone in its queue. Applied to forty, one
		 * Worker invocation would make forty sequential `groups.pools.add` calls on one
		 * user's token — the same discourtesy wearing a performance costume.
		 */
		const groupIds = Array.from({ length: 40 }, (_, i) => `g${i}`);
		const response = await submit({ photoId: "p1", groupIds });
		expect(response.status).toBe(202);

		const reply = (await response.json()) as Reply;
		expect(reply.queuedCount).toBe(40);
		expect(new Set(reply.groups.map((g) => g.status))).toEqual(
			new Set(["queued"]),
		);

		// Nothing was attempted: every row is pending with zero attempts.
		const row = await env.DB.prepare(
			"SELECT COUNT(*) AS n FROM requests WHERE state = 'pending' AND attempts = 0",
		).first<{ n: number }>();
		expect(row?.n).toBe(40);
	});

	it("DOES attempt a batch of exactly one into an empty queue", async () => {
		// Indistinguishable from the single POST, so refusing would make the plug-in
		// slower than the web app at the one thing they do identically.
		const reply = (await (
			await submit({ photoId: "p1", groupIds: ["g1"] })
		).json()) as Reply;

		expect(statusOf(reply, "g1")).toBe("resolved");
		const row = await env.DB.prepare(
			"SELECT state, attempts FROM requests WHERE group_id = 'g1'",
		).first<{ state: string; attempts: number }>();
		expect(row).toMatchObject({ state: "resolved", attempts: 1 });
	});

	it("does NOT attempt a batch of one when something is already queued there", async () => {
		await submit({ photoId: "p0", groupIds: ["g1"] });
		await env.DB.exec(
			"UPDATE requests SET state='pending', outcome=NULL, resolved_at=NULL",
		);

		const reply = (await (
			await submit({ photoId: "p1", groupIds: ["g1"] })
		).json()) as Reply;
		expect(statusOf(reply, "g1")).toBe("queued");
	});
});

describe("ADR-20 and ADR-04, the batch endpoint refuses per group, not per batch", () => {
	it("queues the clean groups and reports the warned one, rather than rejecting all", async () => {
		/**
		 * **Rejecting all three because one carries a warning would hold two good ones
		 * hostage**, and the partial result is the safe direction anyway — nothing reaches
		 * a moderator unanswered.
		 */
		await env.DB.prepare(
			`INSERT INTO moderated_pairs (nsid, photo_id, group_id, flickr_code, first_seen_at, last_seen_at)
       VALUES (?, 'p1', 'g2', 6, 0, 0)`,
		)
			.bind(NSID)
			.run();

		const reply = (await (
			await submit({ photoId: "p1", groupIds: ["g1", "g2", "g3"] })
		).json()) as Reply;

		expect(statusOf(reply, "g2")).toBe("needs_acknowledgement");
		expect(statusOf(reply, "g1")).toBe("queued");
		expect(statusOf(reply, "g3")).toBe("queued");
		expect(reply.queuedCount).toBe(2);
	});

	it("acknowledges ONLY the groups named, never the whole batch", async () => {
		// A blanket boolean would let one click acknowledge warnings the user never saw,
		// which is precisely what ADR-20 exists to prevent.
		for (const groupId of ["g1", "g2"]) {
			await env.DB.prepare(
				`INSERT INTO moderated_pairs (nsid, photo_id, group_id, flickr_code, first_seen_at, last_seen_at)
         VALUES (?, 'p1', ?, 6, 0, 0)`,
			)
				.bind(NSID, groupId)
				.run();
		}

		const reply = (await (
			await submit({
				photoId: "p1",
				groupIds: ["g1", "g2"],
				acknowledgedModeration: ["g1"],
			})
		).json()) as Reply;

		expect(statusOf(reply, "g1")).toBe("queued");
		expect(statusOf(reply, "g2")).toBe("needs_acknowledgement");
	});

	it("reports a pair already in the pool without queueing it", async () => {
		// The stub in vitest.config.ts puts photo `in-pool` in group `g-already-in`.
		const reply = (await (
			await submit({ photoId: "in-pool", groupIds: ["g-already-in", "g1"] })
		).json()) as Reply;

		expect(statusOf(reply, "g-already-in")).toBe("already_in_pool");
		expect(statusOf(reply, "g1")).toBe("queued");
		expect(reply.queuedCount).toBe(1);
	});

	it("reports a pair that is already queued rather than duplicating it", async () => {
		await submit({ photoId: "p1", groupIds: ["g1", "g2"] });
		const reply = (await (
			await submit({ photoId: "p1", groupIds: ["g1", "g2"] })
		).json()) as Reply;

		expect(statusOf(reply, "g1")).toBe("already_queued");
		expect(statusOf(reply, "g2")).toBe("already_queued");
		expect(reply.queuedCount).toBe(0);
	});
});

describe("the batch endpoint's shape", () => {
	it("answers in the order asked, so a client can zip its own list", async () => {
		const groupIds = ["gc", "ga", "gb"];
		const reply = (await (
			await submit({ photoId: "p1", groupIds })
		).json()) as Reply;
		expect(reply.groups.map((g) => g.groupId)).toEqual(groupIds);
	});

	it("collapses duplicates rather than colliding on the pending-pair index", async () => {
		// `idx_requests_one_pending_per_pair` would reject the second insert inside the
		// same batch, taking the whole transaction with it.
		const reply = (await (
			await submit({ photoId: "p1", groupIds: ["g1", "g1", "g1"] })
		).json()) as Reply;
		expect(reply.groups).toHaveLength(1);
	});

	it.each([
		["an empty list", { photoId: "p1", groupIds: [] }],
		[
			"more than 200 groups",
			{
				photoId: "p1",
				groupIds: Array.from({ length: 201 }, (_, i) => `g${i}`),
			},
		],
		["a missing photoId", { groupIds: ["g1"] }],
	])("rejects %s", async (_name, body) => {
		expect((await submit(body)).status).toBe(400);
	});

	it("refuses without a session", async () => {
		const response = await SELF.fetch(`${API}/api/v001/requests/batch`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ photoId: "p1", groupIds: ["g1"] }),
		});
		expect(response.status).toBe(401);
	});

	it("writes rows for the acting user only", async () => {
		await submit({ photoId: "p1", groupIds: ["g1", "g2"] }, OTHER);
		const row = await env.DB.prepare(
			"SELECT COUNT(*) AS n FROM requests WHERE nsid = ?",
		)
			.bind(OTHER)
			.first<{ n: number }>();
		expect(row?.n).toBe(2);

		const mine = await env.DB.prepare(
			"SELECT COUNT(*) AS n FROM requests WHERE nsid = ?",
		)
			.bind(NSID)
			.first<{ n: number }>();
		expect(mine?.n).toBe(0);
	});
});
