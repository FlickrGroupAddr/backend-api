import { env, SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { encryptToken } from "../../src/crypto/tokens.js";
import { mintSession, SESSION_COOKIE } from "../../src/session.js";

/**
 * The authenticated REST surface, against the real Worker.
 *
 * Outbound Flickr calls are answered by the stub in vitest.config.ts, so these
 * exercise the real code path without the real API.
 */

const NSID = "12345678@N00";
const API = "https://api.flickrgroupaddr.com";

/** Matches the SESSION_KEY in .dev.vars, which the test Worker loads. */
async function sessionCookie(nsid = NSID): Promise<string> {
	const token = await mintSession(nsid, env.SESSION_KEY);
	return `${SESSION_COOKIE}=${token}`;
}

async function authed(path: string, init: RequestInit = {}): Promise<Response> {
	return await SELF.fetch(`${API}${path}`, {
		...init,
		headers: {
			...(init.headers ?? {}),
			Cookie: await sessionCookie(),
			"Content-Type": "application/json",
		},
	});
}

beforeEach(async () => {
	await env.DB.exec("DELETE FROM requests");
	await env.DB.exec("DELETE FROM moderated_pairs");
	await env.DB.exec("DELETE FROM users");

	await env.DB.prepare(
		`INSERT INTO users
       (nsid, access_token_encrypted, access_token_secret_encrypted, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?)`,
	)
		.bind(
			NSID,
			await encryptToken("access-token", NSID, env.TOKEN_KEY),
			await encryptToken("access-secret", NSID, env.TOKEN_KEY),
			0,
			0,
		)
		.run();
});

describe("authentication", () => {
	it("refuses a request with no cookie", async () => {
		const response = await SELF.fetch(`${API}/v001/me`);
		expect(response.status).toBe(401);
	});

	it("refuses a tampered cookie", async () => {
		const response = await SELF.fetch(`${API}/v001/me`, {
			headers: { Cookie: `${SESSION_COOKIE}=a.b.c` },
		});
		expect(response.status).toBe(401);
	});

	it("refuses a cookie signed with the wrong key", async () => {
		const forged = await mintSession(NSID, "a-completely-different-key-32b!!");
		const response = await SELF.fetch(`${API}/v001/me`, {
			headers: { Cookie: `${SESSION_COOKIE}=${forged}` },
		});
		expect(response.status).toBe(401);
	});

	it("accepts a valid session and reports the NSID", async () => {
		const response = await authed("/v001/me");
		expect(response.status).toBe(200);
		expect(await response.json()).toEqual({ nsid: NSID });
	});
});

describe("queueing a request", () => {
	it("rejects a malformed body", async () => {
		for (const body of ["{}", '{"photoId":""}', "not json", '{"photoId":1}']) {
			const response = await authed("/v001/requests", {
				method: "POST",
				body,
			});
			expect(response.status).toBe(400);
		}
	});

	it("attempts immediately when the queue is empty, per ADR-10", async () => {
		const response = await authed("/v001/requests", {
			method: "POST",
			body: JSON.stringify({ photoId: "p1", groupId: "g1" }),
		});

		expect(response.status).toBe(200);
		// `disposition: "resolved"` and not merely `status: "resolved"`. A failed
		// Flickr call produces "unconfirmed", which ALSO resolves the row and would
		// make a status-only assertion pass whether or not the call ever happened.
		// This can only pass if the outbound stub answered with stat=ok.
		expect(await response.json()).toMatchObject({
			status: "resolved",
			disposition: "resolved",
		});
	});

	it("queues without attempting when something is already waiting", async () => {
		// ADR-10: a queue of length one is the ONLY case where an immediate
		// attempt cannot take an allowance slot from a request that has been
		// waiting longer.
		await env.DB.prepare(
			`INSERT INTO requests (nsid, photo_id, group_id, created_at)
       VALUES (?, 'waiting', 'g1', 0)`,
		)
			.bind(NSID)
			.run();

		const response = await authed("/v001/requests", {
			method: "POST",
			body: JSON.stringify({ photoId: "p2", groupId: "g1" }),
		});

		expect(response.status).toBe(202);
		expect(await response.json()).toMatchObject({ status: "queued" });
	});
});

describe("ADR-11, the moderation warning", () => {
	beforeEach(async () => {
		await env.DB.prepare(
			`INSERT INTO moderated_pairs
         (nsid, photo_id, group_id, flickr_code, first_seen_at, last_seen_at)
       VALUES (?, 'seen', 'g1', 6, 100, 100)`,
		)
			.bind(NSID)
			.run();
	});

	it("warns instead of queueing when the pair already reached a moderator", async () => {
		const response = await authed("/v001/requests", {
			method: "POST",
			body: JSON.stringify({ photoId: "seen", groupId: "g1" }),
		});

		expect(response.status).toBe(409);
		expect(await response.json()).toMatchObject({
			status: "needs_acknowledgement",
			reason: "reached_a_moderator",
			flickrCode: 6,
		});
	});

	it("queues nothing while the warning is outstanding", async () => {
		await authed("/v001/requests", {
			method: "POST",
			body: JSON.stringify({ photoId: "seen", groupId: "g1" }),
		});

		const row = await env.DB.prepare(
			"SELECT COUNT(*) AS n FROM requests",
		).first<{ n: number }>();
		expect(row?.n).toBe(0);
	});

	it("does NOT block a user who acknowledges it", async () => {
		// ADR-11: the warning informs, the person decides. Terry's framing --
		// "we won't hard block them but are giving them the data to be a good
		// community member".
		const response = await authed("/v001/requests", {
			method: "POST",
			body: JSON.stringify({
				photoId: "seen",
				groupId: "g1",
				acknowledgedModeration: true,
			}),
		});

		expect([200, 202]).toContain(response.status);

		const row = await env.DB.prepare(
			"SELECT COUNT(*) AS n FROM requests",
		).first<{ n: number }>();
		expect(row?.n).toBe(1);
	});

	it("does not warn about a pair in a different group", async () => {
		const response = await authed("/v001/requests", {
			method: "POST",
			body: JSON.stringify({ photoId: "seen", groupId: "g2" }),
		});
		expect(response.status).not.toBe(409);
	});
});

describe("the queue view, where ADR-08 becomes visible", () => {
	it("groups requests by group rather than one flat list", async () => {
		// A flat list looks like a single queue when there are many, which makes
		// correct FIFO behavior read as a bug the first time a later request lands
		// ahead of an earlier one elsewhere.
		for (const [photo, group] of [
			["p1", "g1"],
			["p2", "g1"],
			["p3", "g2"],
		]) {
			await env.DB.prepare(
				"INSERT INTO requests (nsid, photo_id, group_id, created_at) VALUES (?, ?, ?, 0)",
			)
				.bind(NSID, photo, group)
				.run();
		}

		const body = (await (await authed("/v001/queue")).json()) as {
			queues: { groupId: string; requests: { position: number | null }[] }[];
		};

		expect(body.queues).toHaveLength(2);
		expect(body.queues[0]?.requests).toHaveLength(2);
		expect(body.queues[1]?.requests).toHaveLength(1);
	});

	it("numbers pending positions so waiting does not look like breakage", async () => {
		for (const photo of ["p1", "p2", "p3"]) {
			await env.DB.prepare(
				"INSERT INTO requests (nsid, photo_id, group_id, created_at) VALUES (?, ?, 'g1', 0)",
			)
				.bind(NSID, photo)
				.run();
		}

		const body = (await (await authed("/v001/queue")).json()) as {
			queues: { requests: { position: number | null }[] }[];
		};

		expect(body.queues[0]?.requests.map((r) => r.position)).toEqual([1, 2, 3]);
	});

	it("shows the outcome and Flickr code on a resolved request", async () => {
		// The honest report ADR-08 promises. "Queued for a moderator" is the whole
		// reason this view exists.
		await env.DB.prepare(
			`INSERT INTO requests
         (nsid, photo_id, group_id, state, outcome, flickr_code, created_at, resolved_at)
       VALUES (?, 'p1', 'g1', 'resolved', 'queued_for_moderator', 6, 0, 1)`,
		)
			.bind(NSID)
			.run();

		const body = (await (await authed("/v001/queue")).json()) as {
			queues: {
				requests: { outcome: string; flickrCode: number; position: null }[];
			}[];
		};

		expect(body.queues[0]?.requests[0]).toMatchObject({
			outcome: "queued_for_moderator",
			flickrCode: 6,
			position: null,
		});
	});

	it("shows one user nothing belonging to another", async () => {
		await env.DB.prepare(
			`INSERT INTO users
         (nsid, access_token_encrypted, access_token_secret_encrypted, created_at, updated_at)
       VALUES ('99999999@N00', ?, ?, 0, 0)`,
		)
			.bind(new Uint8Array([1]), new Uint8Array([2]))
			.run();

		await env.DB.prepare(
			"INSERT INTO requests (nsid, photo_id, group_id, created_at) VALUES ('99999999@N00', 'theirs', 'g1', 0)",
		).run();

		const body = (await (await authed("/v001/queue")).json()) as {
			queues: { requests: { photoId: string }[] }[];
		};

		const photos = body.queues.flatMap((q) => q.requests.map((r) => r.photoId));
		expect(photos).not.toContain("theirs");
	});
});

/**
 * Withdrawing a request -- the user queued it and changed their mind.
 *
 * The load-bearing property is that withdrawal is only possible while a request
 * is PENDING. Reaching a moderator resolves a request at that instant, so
 * anything withdrawable has provably never been in front of a person. FGA
 * cannot retract a photo from a moderation queue and MUST NOT imply it can.
 */
describe("withdrawing a request", () => {
	/** Queues a request directly and returns its id. */
	async function queue(photoId: string, groupId = "g1"): Promise<number> {
		const row = await env.DB.prepare(
			`INSERT INTO requests (nsid, photo_id, group_id, created_at)
       VALUES (?, ?, ?, 0) RETURNING id`,
		)
			.bind(NSID, photoId, groupId)
			.first<{ id: number }>();

		return row?.id ?? 0;
	}

	/** Queues a request that has already resolved with the given outcome. */
	async function resolved(photoId: string, outcome: string): Promise<number> {
		const row = await env.DB.prepare(
			`INSERT INTO requests
         (nsid, photo_id, group_id, state, outcome, resolved_at, created_at)
       VALUES (?, ?, 'g1', 'resolved', ?, 1, 0) RETURNING id`,
		)
			.bind(NSID, photoId, outcome)
			.first<{ id: number }>();

		return row?.id ?? 0;
	}

	function withdraw(id: number | string): Promise<Response> {
		return authed(`/v001/requests/${id}/withdraw`, { method: "POST" });
	}

	it("withdraws a pending request", async () => {
		const id = await queue("p1");
		const response = await withdraw(id);

		expect(response.status).toBe(200);
		expect(await response.json()).toMatchObject({ status: "withdrawn", id });
	});

	it("resolves the row as withdrawn rather than deleting it", async () => {
		// The user's history MUST still account for something they caused. A
		// deleted row leaves a silent gap where an explicable event belongs.
		const id = await queue("p1");
		await withdraw(id);

		const row = await env.DB.prepare(
			"SELECT state, outcome, resolved_at FROM requests WHERE id = ?",
		)
			.bind(id)
			.first<{ state: string; outcome: string; resolved_at: number }>();

		expect(row?.state).toBe("resolved");
		expect(row?.outcome).toBe("withdrawn");
		expect(row?.resolved_at).toBeGreaterThan(0);
	});

	it("refuses to withdraw a request that reached a moderator, and says so", async () => {
		// The honesty case. A volunteer has already seen this photo; nothing FGA
		// does can unsee it, so the reply MUST NOT read like a retraction.
		const id = await resolved("p1", "queued_for_moderator");
		const response = await withdraw(id);

		expect(response.status).toBe(409);
		expect(await response.json()).toMatchObject({
			error: "already_resolved",
			outcome: "queued_for_moderator",
			reachedAModerator: true,
		});
	});

	it("distinguishes an ordinary resolution from one a human saw", async () => {
		const id = await resolved("p1", "succeeded");
		const response = await withdraw(id);

		expect(response.status).toBe(409);
		expect(await response.json()).toMatchObject({
			outcome: "succeeded",
			reachedAModerator: false,
		});
	});

	it("will not withdraw another user's request, and does not reveal it exists", async () => {
		await env.DB.prepare(
			`INSERT INTO users
         (nsid, access_token_encrypted, access_token_secret_encrypted, created_at, updated_at)
       VALUES ('99999999@N00', ?, ?, 0, 0)`,
		)
			.bind(new Uint8Array([1]), new Uint8Array([2]))
			.run();

		const theirs = await env.DB.prepare(
			`INSERT INTO requests (nsid, photo_id, group_id, created_at)
       VALUES ('99999999@N00', 'theirs', 'g1', 0) RETURNING id`,
		).first<{ id: number }>();

		// 404, not 403: a distinct answer would confirm the id exists, turning this
		// into a way to enumerate other people's requests.
		expect((await withdraw(theirs?.id ?? 0)).status).toBe(404);

		const still = await env.DB.prepare(
			"SELECT state FROM requests WHERE id = ?",
		)
			.bind(theirs?.id ?? 0)
			.first<{ state: string }>();

		expect(still?.state).toBe("pending");
	});

	it("rejects an id that is not a positive integer", async () => {
		for (const bad of ["abc", "-1", "0", "1.5", "", "1e9999"]) {
			expect((await withdraw(bad)).status).not.toBe(200);
		}
	});

	it("frees the pair so the same photo can be queued again", async () => {
		// A unique partial index allows one PENDING request per pair. Withdrawing
		// resolves the row, so re-submitting must work -- changing your mind twice
		// is allowed.
		const id = await queue("p1");
		await withdraw(id);

		const again = await authed("/v001/requests", {
			method: "POST",
			body: JSON.stringify({ photoId: "p1", groupId: "g1" }),
		});

		expect([200, 202]).toContain(again.status);
	});

	it("takes the request out of its queue so the next one becomes head", async () => {
		const first = await queue("p1");
		await queue("p2");
		await withdraw(first);

		const body = (await (await authed("/v001/queue")).json()) as {
			queues: {
				groupId: string;
				requests: { photoId: string; state: string }[];
			}[];
		};

		const pending = body.queues
			.flatMap((q) => q.requests)
			.filter((r) => r.state === "pending");

		expect(pending.map((r) => r.photoId)).toEqual(["p2"]);
	});
});

describe("queue position", () => {
	it("counts only the pending requests ahead, not resolved ones", async () => {
		// A user whose earlier requests all succeeded is at the FRONT of their
		// queue, and MUST be told so. Counting resolved rows makes a first-in-line
		// request report position 3, which reads as a stall that is not happening.
		for (const photo of ["done1", "done2"]) {
			await env.DB.prepare(
				`INSERT INTO requests
           (nsid, photo_id, group_id, state, outcome, resolved_at, created_at)
         VALUES (?, ?, 'g1', 'resolved', 'succeeded', 1, 0)`,
			)
				.bind(NSID, photo)
				.run();
		}

		await env.DB.prepare(
			"INSERT INTO requests (nsid, photo_id, group_id, created_at) VALUES (?, 'waiting', 'g1', 0)",
		)
			.bind(NSID)
			.run();

		const body = (await (await authed("/v001/queue")).json()) as {
			queues: { requests: { photoId: string; position: number | null }[] }[];
		};

		const waiting = body.queues
			.flatMap((q) => q.requests)
			.find((r) => r.photoId === "waiting");

		expect(waiting?.position).toBe(1);
	});

	it("moves everyone up when a request ahead of them is withdrawn", async () => {
		// Withdrawal makes the bug above visible: withdraw the head and the rest
		// must advance. A queue whose numbers never move is a queue that looks
		// stuck, which is the opposite of what this view is for.
		const ids: number[] = [];
		for (const photo of ["p1", "p2", "p3"]) {
			const row = await env.DB.prepare(
				`INSERT INTO requests (nsid, photo_id, group_id, created_at)
         VALUES (?, ?, 'g1', 0) RETURNING id`,
			)
				.bind(NSID, photo)
				.first<{ id: number }>();
			ids.push(row?.id ?? 0);
		}

		await authed(`/v001/requests/${ids[0]}/withdraw`, { method: "POST" });

		const body = (await (await authed("/v001/queue")).json()) as {
			queues: { requests: { photoId: string; position: number | null }[] }[];
		};

		const positions = new Map(
			body.queues
				.flatMap((q) => q.requests)
				.map((r) => [r.photoId, r.position]),
		);

		expect(positions.get("p2")).toBe(1);
		expect(positions.get("p3")).toBe(2);
		expect(positions.get("p1")).toBeNull();
	});
});
