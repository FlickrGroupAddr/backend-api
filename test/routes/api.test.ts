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

/**
 * A v4 UUID built by SQLite, for rows inserted straight into the table.
 *
 * Spliced into the SQL rather than bound, so adding the column to a fixture
 * costs no extra bind parameter. **Fixtures only** -- the Worker mints real ones
 * with `crypto.randomUUID()`, which is a CSPRNG where SQLite's `random()` is
 * not, and that difference is the entire point of the column.
 */
const SQL_UUID = `lower(
  hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' ||
  substr(hex(randomblob(2)), 2) || '-' ||
  substr('89ab', 1 + (abs(random()) % 4), 1) ||
  substr(hex(randomblob(2)), 2) || '-' || hex(randomblob(6))
)`;

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

describe("ADR-09, nothing behind a session reaches a shared cache", () => {
	it("marks an authenticated response private and no-store", async () => {
		const response = await authed("/v001/queue");
		expect(response.headers.get("Cache-Control")).toBe("private, no-store");
	});

	it("marks the 401 too, which is the one a middleware order gets wrong", async () => {
		// A rejecting middleware never calls next(), so anything registered after
		// it does not run on that path. This asserts the ordering, not the header.
		const response = await SELF.fetch(`${API}/v001/queue`);
		expect(response.status).toBe(401);
		expect(response.headers.get("Cache-Control")).toBe("private, no-store");
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

	it("records the attempt it just made", async () => {
		// Found by the first real add, 2026-08-13. The row resolved correctly with
		// Flickr's code and reported `attempts: 0`, because only the nightly sweep
		// called recordAttempt -- the same event counted on one path and not the
		// other. Every earlier test asserted on the RESPONSE, which is identical
		// either way.
		await authed("/v001/requests", {
			method: "POST",
			body: JSON.stringify({ photoId: "p1", groupId: "g1" }),
		});

		const row = await env.DB.prepare(
			"SELECT attempts, last_attempt_at FROM requests WHERE photo_id = 'p1'",
		).first<{ attempts: number; last_attempt_at: number | null }>();

		expect(row?.attempts).toBe(1);
		expect(row?.last_attempt_at).toBeGreaterThan(0);
	});

	it("does NOT record an attempt for a request it only queued", async () => {
		// The control for the test above. Without it, always writing attempts=1
		// would pass -- including on the path where ADR-10 forbids an attempt.
		await env.DB.prepare(
			`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at)
       VALUES (${SQL_UUID}, ?, 'waiting', 'g1', 0)`,
		)
			.bind(NSID)
			.run();

		await authed("/v001/requests", {
			method: "POST",
			body: JSON.stringify({ photoId: "p2", groupId: "g1" }),
		});

		const row = await env.DB.prepare(
			"SELECT attempts, last_attempt_at FROM requests WHERE photo_id = 'p2'",
		).first<{ attempts: number; last_attempt_at: number | null }>();

		expect(row?.attempts).toBe(0);
		expect(row?.last_attempt_at).toBeNull();
	});

	it("queues without attempting when something is already waiting", async () => {
		// ADR-10: a queue of length one is the ONLY case where an immediate
		// attempt cannot take an allowance slot from a request that has been
		// waiting longer.
		await env.DB.prepare(
			`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at)
       VALUES (${SQL_UUID}, ?, 'waiting', 'g1', 0)`,
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
				`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at) VALUES (${SQL_UUID}, ?, ?, ?, 0)`,
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
				`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at) VALUES (${SQL_UUID}, ?, ?, 'g1', 0)`,
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
         (public_id, nsid, photo_id, group_id, state, outcome, flickr_code, created_at, resolved_at)
       VALUES (${SQL_UUID}, ?, 'p1', 'g1', 'resolved', 'queued_for_moderator', 6, 0, 1)`,
		)
			.bind(NSID)
			.run();

		// `state=all` because the default is pending-only -- history is the rarer
		// question and the one that pays for itself.
		const body = (await (await authed("/v001/queue?state=all")).json()) as {
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
			`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at) VALUES (${SQL_UUID}, '99999999@N00', 'theirs', 'g1', 0)`,
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
	/** Queues a request directly and returns its PUBLIC id, which is what URLs use. */
	async function queue(photoId: string, groupId = "g1"): Promise<string> {
		const row = await env.DB.prepare(
			`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at)
       VALUES (${SQL_UUID}, ?, ?, ?, 0) RETURNING public_id`,
		)
			.bind(NSID, photoId, groupId)
			.first<{ public_id: string }>();

		return row?.public_id ?? "";
	}

	/** Queues a request that has already resolved with the given outcome. */
	async function resolved(photoId: string, outcome: string): Promise<string> {
		const row = await env.DB.prepare(
			`INSERT INTO requests
         (public_id, nsid, photo_id, group_id, state, outcome, resolved_at, created_at)
       VALUES (${SQL_UUID}, ?, ?, 'g1', 'resolved', ?, 1, 0) RETURNING public_id`,
		)
			.bind(NSID, photoId, outcome)
			.first<{ public_id: string }>();

		return row?.public_id ?? "";
	}

	function withdraw(publicId: string): Promise<Response> {
		return authed(`/v001/requests/${publicId}/withdraw`, { method: "POST" });
	}

	it("withdraws a pending request", async () => {
		const publicId = await queue("p1");
		const response = await withdraw(publicId);

		expect(response.status).toBe(200);
		expect(await response.json()).toMatchObject({
			status: "withdrawn",
			publicId,
		});
	});

	it("resolves the row as withdrawn rather than deleting it", async () => {
		// The user's history MUST still account for something they caused. A
		// deleted row leaves a silent gap where an explicable event belongs.
		const publicId = await queue("p1");
		await withdraw(publicId);

		const row = await env.DB.prepare(
			"SELECT state, outcome, resolved_at FROM requests WHERE public_id = ?",
		)
			.bind(publicId)
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
			`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at)
       VALUES (${SQL_UUID}, '99999999@N00', 'theirs', 'g1', 0) RETURNING public_id`,
		).first<{ public_id: string }>();

		// 404, not 403: a distinct answer would confirm the id exists, turning this
		// into a way to enumerate other people's requests. Note the caller here
		// KNOWS the id -- an unguessable public_id makes that unrealistic, and the
		// nsid condition is what makes it safe even when they do.
		expect((await withdraw(theirs?.public_id ?? "")).status).toBe(404);

		const still = await env.DB.prepare(
			"SELECT state FROM requests WHERE public_id = ?",
		)
			.bind(theirs?.public_id ?? "")
			.first<{ state: string }>();

		expect(still?.state).toBe("pending");
	});

	it("rejects an id that is not a v4 UUID", async () => {
		for (const bad of [
			"abc",
			"1",
			"",
			"not-a-uuid",
			// A syntactically valid UUID of the wrong version. Worth pinning: the
			// column holds v4 specifically, and a v7 here would mean something in
			// the system is minting the timestamp-leaking kind.
			"017f22e2-79b0-7cc3-98c4-dc0c0c07398f",
		]) {
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

describe("queue pagination", () => {
	/** Queues n requests in one group and returns their public ids in order. */
	async function queueMany(n: number, group = "g1"): Promise<string[]> {
		const ids: string[] = [];
		for (let i = 0; i < n; i++) {
			const row = await env.DB.prepare(
				`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at)
         VALUES (${SQL_UUID}, ?, ?, ?, 0) RETURNING public_id`,
			)
				.bind(NSID, `p${i}`, group)
				.first<{ public_id: string }>();
			ids.push(row?.public_id ?? "");
		}
		return ids;
	}

	type Page = {
		queues: { requests: { photoId: string; position: number | null }[] }[];
		nextCursor: string | null;
	};

	async function page(query: string): Promise<Page> {
		return (await (await authed(`/v001/queue${query}`)).json()) as Page;
	}

	it("returns at most `limit` requests and a cursor for the rest", async () => {
		await queueMany(5);
		const first = await page("?limit=2");

		expect(first.queues.flatMap((q) => q.requests)).toHaveLength(2);
		expect(first.nextCursor).not.toBeNull();
	});

	it("walks every request exactly once across pages", async () => {
		await queueMany(5);

		const seen: string[] = [];
		let cursor: string | null = null;
		for (let guard = 0; guard < 10; guard++) {
			const p: Page = await page(
				`?limit=2${cursor === null ? "" : `&after=${cursor}`}`,
			);
			seen.push(...p.queues.flatMap((q) => q.requests).map((r) => r.photoId));
			cursor = p.nextCursor;
			if (cursor === null) break;
		}

		// No duplicates, nothing skipped, original order preserved.
		expect(seen).toEqual(["p0", "p1", "p2", "p3", "p4"]);
	});

	it("reports no cursor on a final page that is exactly `limit` long", async () => {
		// The off-by-one an inferred cursor gets wrong. A caller that stops on a
		// SHORT page would ask for one more page here; a caller that trusts a null
		// cursor stops correctly. That is why the probe row exists.
		await queueMany(4);
		const p = await page("?limit=4");

		expect(p.queues.flatMap((q) => q.requests)).toHaveLength(4);
		expect(p.nextCursor).toBeNull();
	});

	it("keeps positions correct on a page that starts mid-queue", async () => {
		// The reason position moved into SQL. Computed while iterating a page, the
		// third request would report position 1 because the page began at it.
		await queueMany(4);
		const first = await page("?limit=2");
		const second = await page(`?limit=2&after=${first.nextCursor}`);

		expect(
			second.queues.flatMap((q) => q.requests).map((r) => r.position),
		).toEqual([3, 4]);
	});

	it("does not skip a request when an earlier one resolves between pages", async () => {
		// THE ARGUMENT FOR A CURSOR OVER A PAGE NUMBER. The nightly sweep resolves
		// rows constantly, so with `state=all` and OFFSET 2, deleting or filtering
		// out an earlier row shifts everything left and page 2 silently begins
		// after the row that moved into slot 2. A keyset cursor names a position in
		// the sort order, so it cannot drift.
		const ids = await queueMany(4);
		const first = await page("?limit=2");

		// p0 leaves the pending set while the caller holds a cursor pointing at p1.
		await authed(`/v001/requests/${ids[0]}/withdraw`, { method: "POST" });

		const second = await page(`?limit=2&after=${first.nextCursor}`);
		const photos = second.queues
			.flatMap((q) => q.requests)
			.map((r) => r.photoId);

		expect(photos).toEqual(["p2", "p3"]);
	});

	it("rejects a limit outside the permitted range", async () => {
		for (const bad of ["0", "-1", "201", "abc"]) {
			expect((await authed(`/v001/queue?limit=${bad}`)).status).toBe(400);
		}
	});

	it("refuses a cursor belonging to somebody else", async () => {
		await env.DB.prepare(
			`INSERT INTO users
         (nsid, access_token_encrypted, access_token_secret_encrypted, created_at, updated_at)
       VALUES ('99999999@N00', ?, ?, 0, 0)`,
		)
			.bind(new Uint8Array([1]), new Uint8Array([2]))
			.run();

		const theirs = await env.DB.prepare(
			`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at)
       VALUES (${SQL_UUID}, '99999999@N00', 'theirs', 'g1', 0) RETURNING public_id`,
		).first<{ public_id: string }>();

		const response = await authed(
			`/v001/queue?after=${theirs?.public_id ?? ""}`,
		);
		expect(response.status).toBe(400);
	});

	it("defaults to pending only, and shows history on request", async () => {
		await queueMany(2);
		await env.DB.prepare(
			`INSERT INTO requests
         (public_id, nsid, photo_id, group_id, state, outcome, resolved_at, created_at)
       VALUES (${SQL_UUID}, ?, 'old', 'g1', 'resolved', 'succeeded', 1, 0)`,
		)
			.bind(NSID)
			.run();

		const byDefault = await page("");
		expect(
			byDefault.queues.flatMap((q) => q.requests).map((r) => r.photoId),
		).not.toContain("old");

		const all = await page("?state=all");
		expect(
			all.queues.flatMap((q) => q.requests).map((r) => r.photoId),
		).toContain("old");
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
           (public_id, nsid, photo_id, group_id, state, outcome, resolved_at, created_at)
         VALUES (${SQL_UUID}, ?, ?, 'g1', 'resolved', 'succeeded', 1, 0)`,
			)
				.bind(NSID, photo)
				.run();
		}

		await env.DB.prepare(
			`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at) VALUES (${SQL_UUID}, ?, 'waiting', 'g1', 0)`,
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
		const publicIds: string[] = [];
		for (const photo of ["p1", "p2", "p3"]) {
			const row = await env.DB.prepare(
				`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at)
         VALUES (${SQL_UUID}, ?, ?, 'g1', 0) RETURNING public_id`,
			)
				.bind(NSID, photo)
				.first<{ public_id: string }>();
			publicIds.push(row?.public_id ?? "");
		}

		await authed(`/v001/requests/${publicIds[0]}/withdraw`, { method: "POST" });

		// `state=all` so the withdrawn row is visible and its null position can be
		// asserted rather than merely absent.
		const body = (await (await authed("/v001/queue?state=all")).json()) as {
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
