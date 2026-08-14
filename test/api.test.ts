import { env, SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { encryptToken } from "../src/crypto/tokens.js";
import { mintSession, SESSION_COOKIE } from "../src/session.js";

/** The authenticated surface against the real Worker. Flickr is answered by the stub in
 *  vitest.config.ts, so these exercise the real path without the real API. */

const NSID = "12345678@N00";
const OTHER = "87654321@N00";
/** One origin. The `/api` prefix, not a hostname, separates the API from the app
 *  shell. */
const API = "https://flickrgroupaddr.com";

/** SQLite-side v4, for rows inserted straight into the table. **Fixtures only** -- the
 *  Worker mints real ones with `crypto.randomUUID()`, and that difference is the point. */
const UUID = `lower(
  hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' ||
  substr(hex(randomblob(2)), 2) || '-' ||
  substr('89ab', 1 + (abs(random()) % 4), 1) ||
  substr(hex(randomblob(2)), 2) || '-' || hex(randomblob(6))
)`;

async function cookieFor(nsid = NSID): Promise<string> {
	return `${SESSION_COOKIE}=${await mintSession(nsid, env.SESSION_KEY)}`;
}

async function authed(
	path: string,
	init: RequestInit = {},
	nsid = NSID,
): Promise<Response> {
	return await SELF.fetch(`${API}${path}`, {
		...init,
		headers: {
			...(init.headers ?? {}),
			Cookie: await cookieFor(nsid),
			"Content-Type": "application/json",
		},
	});
}

async function addUser(nsid: string): Promise<void> {
	await env.DB.prepare(
		`INSERT INTO users
       (nsid, access_token_encrypted, access_token_secret_encrypted, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?)`,
	)
		.bind(
			nsid,
			await encryptToken("access-token", nsid, env.TOKEN_KEY),
			await encryptToken("access-secret", nsid, env.TOKEN_KEY),
			0,
			0,
		)
		.run();
}

/** Inserts a row directly, bypassing the API, and returns its public_id. */
async function seed(
	nsid: string,
	photoId: string,
	groupId: string,
	resolved?: { outcome: string; code?: number },
): Promise<string> {
	const row = await env.DB.prepare(
		`INSERT INTO requests
       (public_id, nsid, photo_id, group_id, created_at, state, outcome, flickr_code, resolved_at)
     VALUES (${UUID}, ?, ?, ?, 0, ?, ?, ?, ?)
     RETURNING public_id`,
	)
		.bind(
			nsid,
			photoId,
			groupId,
			resolved ? "resolved" : "pending",
			resolved?.outcome ?? null,
			resolved?.code ?? null,
			resolved ? 1 : null,
		)
		.first<{ public_id: string }>();
	return row?.public_id ?? "";
}

beforeEach(async () => {
	await env.DB.exec("DELETE FROM requests");
	await env.DB.exec("DELETE FROM moderated_pairs");
	await env.DB.exec("DELETE FROM users");
	await addUser(NSID);
	await addUser(OTHER);
});

describe("ADR-10, authentication", () => {
	it.each([
		["no cookie", undefined],
		["a malformed cookie", `${SESSION_COOKIE}=a.b.c`],
	])("refuses %s", async (_name, cookie) => {
		const response = await SELF.fetch(`${API}/api/v001/me`, {
			headers: cookie ? { Cookie: cookie } : {},
		});
		expect(response.status).toBe(401);
	});

	it("refuses a cookie signed with the wrong key", async () => {
		const forged = await mintSession(NSID, "a-completely-different-key-32b!!");
		const response = await SELF.fetch(`${API}/api/v001/me`, {
			headers: { Cookie: `${SESSION_COOKIE}=${forged}` },
		});
		expect(response.status).toBe(401);
	});

	it("accepts a valid session and reports the NSID", async () => {
		const response = await authed("/api/v001/me");
		expect(response.status).toBe(200);
		// ADR-19 added `admin`. Kept as toEqual rather than toMatchObject so a future
		// field cannot be added to this response without somebody deciding to.
		expect(await response.json()).toEqual({ nsid: NSID, admin: true });
	});
});

describe("ADR-12, nothing behind a session reaches a shared cache", () => {
	it("marks the 200 AND the 401, which is what middleware order gets wrong", async () => {
		// A rejecting middleware never calls next(), so registering the cache header
		// after `requireSession` would leave exactly the 401s uncovered.
		const ok = await authed("/api/v001/me");
		const denied = await SELF.fetch(`${API}/api/v001/me`);
		for (const response of [ok, denied]) {
			expect(response.headers.get("Cache-Control")).toBe("private, no-store");
		}
	});
});

describe("ADR-03 and ADR-05, queueing a request", () => {
	const submit = (body: unknown) =>
		authed("/api/v001/requests", {
			method: "POST",
			body: JSON.stringify(body),
		});

	it("rejects a malformed body", async () => {
		expect((await submit({ photoId: "" })).status).toBe(400);
	});

	it("attempts immediately when the queue is empty, and RECORDS that attempt", async () => {
		// The attempt count is the part that regressed once: the response was correct
		// and complete while the row it wrote reported `attempts: 0`.
		const response = await submit({ photoId: "p1", groupId: "g1" });
		expect(await response.json()).toMatchObject({ status: "resolved" });

		const row = await env.DB.prepare(
			"SELECT state, attempts, last_attempt_at FROM requests WHERE photo_id='p1'",
		).first<{
			state: string;
			attempts: number;
			last_attempt_at: number | null;
		}>();
		expect(row).toMatchObject({ state: "resolved", attempts: 1 });
		expect(row?.last_attempt_at).not.toBeNull();
	});

	it("ADR-05: does not call Flickr for a pair that already succeeded", async () => {
		// The cheap local guard. `alreadySucceeded` resolves it without a network call.
		await seed(NSID, "p1", "g1", { outcome: "succeeded" });
		const response = await submit({ photoId: "p1", groupId: "g1" });
		expect(await response.json()).toMatchObject({
			status: "resolved",
			disposition: "resolved",
		});
		const row = await env.DB.prepare(
			"SELECT outcome FROM requests WHERE photo_id='p1' ORDER BY id DESC LIMIT 1",
		).first<{ outcome: string }>();
		expect(row?.outcome).toBe("already_in_pool");
	});

	it("queues without attempting when something is already waiting", async () => {
		await seed(NSID, "p0", "g1");
		const response = await submit({ photoId: "p1", groupId: "g1" });

		expect(response.status).toBe(202);
		expect(await response.json()).toMatchObject({ status: "queued" });
		const row = await env.DB.prepare(
			"SELECT attempts FROM requests WHERE photo_id='p1'",
		).first<{ attempts: number }>();
		expect(row?.attempts).toBe(0);
	});
});

describe("ADR-04, the moderation warning", () => {
	const submit = (body: unknown) =>
		authed("/api/v001/requests", {
			method: "POST",
			body: JSON.stringify(body),
		});

	beforeEach(async () => {
		await env.DB.prepare(
			`INSERT INTO moderated_pairs
         (nsid, photo_id, group_id, flickr_code, first_seen_at, last_seen_at)
       VALUES (?, 'p1', 'g1', 6, 0, 0)`,
		)
			.bind(NSID)
			.run();
	});

	it("warns instead of queueing, and queues nothing while the warning stands", async () => {
		const response = await submit({ photoId: "p1", groupId: "g1" });
		expect(response.status).toBe(409);
		expect(await response.json()).toMatchObject({
			status: "needs_acknowledgement",
			reason: "reached_a_moderator",
			flickrCode: 6,
		});

		const count = await env.DB.prepare(
			"SELECT COUNT(*) AS n FROM requests",
		).first<{ n: number }>();
		expect(count?.n).toBe(0);
	});

	it("does NOT block a user who acknowledges it", async () => {
		// The warning informs. The person decides.
		const response = await submit({
			photoId: "p1",
			groupId: "g1",
			acknowledgedModeration: true,
		});
		expect([200, 202]).toContain(response.status);
	});

	it("does not warn about the same photo in a different group", async () => {
		const response = await submit({ photoId: "p1", groupId: "g2" });
		expect(response.status).not.toBe(409);
	});
});

describe("withdrawing a request", () => {
	const withdraw = (id: string, nsid = NSID) =>
		authed(`/api/v001/requests/${id}/withdraw`, { method: "POST" }, nsid);

	it("withdraws a pending request and RESOLVES the row rather than deleting it", async () => {
		const id = await seed(NSID, "p1", "g1");
		expect((await withdraw(id)).status).toBe(200);

		const row = await env.DB.prepare(
			"SELECT state, outcome FROM requests WHERE public_id = ?",
		)
			.bind(id)
			.first();
		expect(row).toMatchObject({ state: "resolved", outcome: "withdrawn" });
	});

	it("refuses one that reached a moderator, and says a human is involved", async () => {
		// FGA cannot pull a photo back out of a moderation queue, so claiming otherwise
		// would be ADR-01 broken in the most direct way available.
		const id = await seed(NSID, "p1", "g1", {
			outcome: "queued_for_moderator",
		});
		const response = await withdraw(id);
		expect(response.status).toBe(409);
		expect(await response.json()).toMatchObject({ reachedAModerator: true });
	});

	it("distinguishes an ordinary resolution from one a human saw", async () => {
		const id = await seed(NSID, "p1", "g1", { outcome: "failed" });
		expect(await (await withdraw(id)).json()).toMatchObject({
			reachedAModerator: false,
		});
	});

	it("will not withdraw another user's request, and does not reveal it exists", async () => {
		const id = await seed(OTHER, "p1", "g1");
		expect((await withdraw(id, NSID)).status).toBe(404);

		const row = await env.DB.prepare(
			"SELECT state FROM requests WHERE public_id = ?",
		)
			.bind(id)
			.first<{ state: string }>();
		expect(row?.state).toBe("pending");
	});

	it("rejects an id that is not a v4 UUID", async () => {
		expect((await withdraw("1")).status).toBe(400);
	});

	it("frees the pair, so the same photo can be queued again", async () => {
		const id = await seed(NSID, "p1", "g1");
		await withdraw(id);
		const response = await authed("/api/v001/requests", {
			method: "POST",
			body: JSON.stringify({ photoId: "p1", groupId: "g1" }),
		});
		expect([200, 202]).toContain(response.status);
	});
});

describe("ADR-01, the queue view is where fail-polite becomes visible", () => {
	type Page = {
		queues: {
			groupId: string;
			requests: { publicId: string; position: number | null }[];
		}[];
		nextCursor: string | null;
	};

	const page = async (query = ""): Promise<Page> =>
		(await (await authed(`/api/v001/queue${query}`)).json()) as Page;

	it("groups by group rather than one flat list, and numbers pending positions", async () => {
		// A flat list looks like a single queue when there are many, which makes correct
		// FIFO behavior read as a bug.
		await seed(NSID, "p1", "g1");
		await seed(NSID, "p2", "g1");
		await seed(NSID, "p3", "g2");

		const body = await page();
		expect(body.queues.map((q) => q.groupId).sort()).toEqual(["g1", "g2"]);
		const g1 = body.queues.find((q) => q.groupId === "g1");
		expect(g1?.requests.map((r) => r.position)).toEqual([1, 2]);
	});

	it("shows one user nothing belonging to another", async () => {
		await seed(OTHER, "p1", "g1");
		expect((await page()).queues).toHaveLength(0);
	});

	it("defaults to pending, and shows history on request", async () => {
		await seed(NSID, "p1", "g1", { outcome: "failed", code: 8 });
		expect((await page()).queues).toHaveLength(0);

		const all = await page("?state=all");
		expect(all.queues[0]?.requests).toHaveLength(1);
	});

	it("counts only pending requests ahead, not resolved ones", async () => {
		await seed(NSID, "p0", "g1", { outcome: "failed" });
		await seed(NSID, "p1", "g1");
		const g1 = (await page()).queues[0];
		expect(g1?.requests[0]?.position).toBe(1);
	});
});

describe("ADR-17, pagination", () => {
	type Page = {
		queues: { groupId: string; requests: { publicId: string }[] }[];
		nextCursor: string | null;
	};

	const page = async (query: string): Promise<Page> =>
		(await (await authed(`/api/v001/queue${query}`)).json()) as Page;

	const idsOf = (body: Page) =>
		body.queues.flatMap((q) => q.requests.map((r) => r.publicId));

	it("walks every request exactly once across pages", async () => {
		for (let i = 0; i < 5; i++) await seed(NSID, `p${i}`, "g1");

		const seen: string[] = [];
		let cursor: string | null = null;
		for (let guard = 0; guard < 10; guard++) {
			const body: Page = await page(
				`?limit=2${cursor ? `&after=${cursor}` : ""}`,
			);
			seen.push(...idsOf(body));
			cursor = body.nextCursor;
			if (cursor === null) break;
		}

		expect(seen).toHaveLength(5);
		expect(new Set(seen).size).toBe(5);
	});

	it("does not skip a request when an earlier one resolves between pages", async () => {
		// The failure offset paging produces, and the whole reason for a keyset cursor.
		for (let i = 0; i < 4; i++) await seed(NSID, `p${i}`, "g1");

		const first = await page("?limit=2");
		const seen = idsOf(first);

		await env.DB.exec(
			"UPDATE requests SET state='resolved', outcome='failed', resolved_at=1 WHERE photo_id='p0'",
		);

		const second = await page(`?limit=2&after=${first.nextCursor}`);
		seen.push(...idsOf(second));

		expect(new Set(seen).size).toBe(seen.length);
		expect(seen).toHaveLength(4);
	});

	it("reports no cursor on a final page that is exactly `limit` long", async () => {
		// A short page is the wrong end-of-list signal exactly when the last page is full.
		await seed(NSID, "p1", "g1");
		await seed(NSID, "p2", "g1");
		expect((await page("?limit=2")).nextCursor).toBeNull();
	});

	it.each([0, 201])("rejects limit=%s", async (limit) => {
		expect((await authed(`/api/v001/queue?limit=${limit}`)).status).toBe(400);
	});

	it("refuses a cursor belonging to somebody else", async () => {
		const theirs = await seed(OTHER, "p1", "g1");
		expect((await authed(`/api/v001/queue?after=${theirs}`)).status).toBe(400);
	});
});
