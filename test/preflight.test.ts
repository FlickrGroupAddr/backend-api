import { env, SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { encryptToken } from "../src/crypto/tokens.js";
import { mintSession, SESSION_COOKIE } from "../src/session.js";

/** ADR-20. The batch preflight, so ADR-04's warning arrives BEFORE the commitment. */

const NSID = "12345678@N00";
const OTHER = "87654321@N00";
const API = "https://flickrgroupaddr.com";

type Group = {
	groupId: string;
	status: string;
	reachedAModerator: { flickrCode: number; stillPending: boolean } | null;
};
type Reply = { photoId: string; poolsKnown: boolean; groups: Group[] };

async function check(
	photoId: string,
	groupIds: string[],
	nsid = NSID,
): Promise<Response> {
	return await SELF.fetch(`${API}/api/v001/photos/${photoId}/preflight`, {
		method: "POST",
		headers: {
			Cookie: `${SESSION_COOKIE}=${await mintSession(env.DB, nsid, env.SESSION_KEY)}`,
			"Content-Type": "application/json",
		},
		body: JSON.stringify({ groupIds }),
	});
}

const statuses = async (r: Response): Promise<Record<string, string>> => {
	const body = (await r.json()) as Reply;
	return Object.fromEntries(body.groups.map((g) => [g.groupId, g.status]));
};

async function addUser(nsid: string): Promise<void> {
	await env.DB.prepare(
		`INSERT INTO users (nsid, access_token_encrypted, access_token_secret_encrypted, created_at, updated_at)
     VALUES (?, ?, ?, 0, 0)`,
	)
		.bind(
			nsid,
			await encryptToken("access-token", nsid, env.TOKEN_KEY),
			await encryptToken("access-secret", nsid, env.TOKEN_KEY),
		)
		.run();
}

beforeEach(async () => {
	await env.DB.exec("DELETE FROM requests");
	await env.DB.exec("DELETE FROM moderated_pairs");
	await env.DB.exec("DELETE FROM users");
	await addUser(NSID);
	await addUser(OTHER);
});

describe("ADR-20, the batch preflight", () => {
	it("answers many groups in ONE request", async () => {
		const ids = Array.from({ length: 40 }, (_, i) => `g${i}`);
		const found = await statuses(await check("p1", ids));
		expect(Object.keys(found)).toHaveLength(40);
		expect(new Set(Object.values(found))).toEqual(new Set(["ready"]));
	});

	it("reports a pair that reached a moderator, WITHOUT submitting anything", async () => {
		// The whole point. Before this endpoint the only way to learn about a warning
		// was to POST and read the 409 -- which meant the warning arrived after the
		// commitment, backwards for a rule about informed consent.
		await env.DB.prepare(
			`INSERT INTO moderated_pairs (nsid, photo_id, group_id, flickr_code, first_seen_at, last_seen_at)
       VALUES (?, 'p1', 'g1', 7, 0, 0)`,
		)
			.bind(NSID)
			.run();

		const body = (await (await check("p1", ["g1", "g2"])).json()) as Reply;
		expect(await statusOf(body, "g1")).toBe("needs_acknowledgement");
		expect(await statusOf(body, "g2")).toBe("ready");

		const warned = body.groups.find((g) => g.groupId === "g1");
		// Code 7 means the ORIGINAL is still undecided, which reads differently.
		expect(warned?.reachedAModerator).toMatchObject({
			flickrCode: 7,
			stillPending: true,
		});

		const count = await env.DB.prepare(
			"SELECT COUNT(*) AS n FROM requests",
		).first<{ n: number }>();
		expect(count?.n).toBe(0);
	});

	it("reports a pair that is already queued", async () => {
		await env.DB.prepare(
			`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at)
       VALUES ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', ?, 'p1', 'g1', 0)`,
		)
			.bind(NSID)
			.run();

		expect(await statuses(await check("p1", ["g1"]))).toEqual({
			g1: "already_queued",
		});
	});

	it("reports a pair that already succeeded, per ADR-05", async () => {
		await env.DB.prepare(
			`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at, state, outcome, resolved_at)
       VALUES ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', ?, 'p1', 'g1', 0, 'resolved', 'succeeded', 1)`,
		)
			.bind(NSID)
			.run();

		expect(await statuses(await check("p1", ["g1"]))).toEqual({
			g1: "already_in_pool",
		});
	});

	it("lets pool membership OVERRIDE a moderation record", async () => {
		// ADR-04: presence in the pool proves approval, the one direction an invisible
		// decision becomes visible. Warning about an accepted photo spends exactly the
		// credibility the real warning needs.
		await env.DB.prepare(
			`INSERT INTO moderated_pairs (nsid, photo_id, group_id, flickr_code, first_seen_at, last_seen_at)
       VALUES (?, 'in-pool', 'g-already-in', 6, 0, 0)`,
		)
			.bind(NSID)
			.run();

		expect(await statuses(await check("in-pool", ["g-already-in"]))).toEqual({
			"g-already-in": "already_in_pool",
		});
	});

	it("says when the pool lookup is UNKNOWN rather than implying an empty pool", async () => {
		// A failed getAllContexts is not "in no pools". ADR-04: presence proves
		// approval, absence proves nothing. Reporting unknown as clean would suppress
		// a warning the server then raises at submit time.
		const body = (await (await check("p1", ["g1"])).json()) as Reply;
		expect(body.poolsKnown).toBe(true);
	});

	it("scopes to the caller, so one user cannot probe another's history", async () => {
		await env.DB.prepare(
			`INSERT INTO moderated_pairs (nsid, photo_id, group_id, flickr_code, first_seen_at, last_seen_at)
       VALUES (?, 'p1', 'g1', 6, 0, 0)`,
		)
			.bind(OTHER)
			.run();

		expect(await statuses(await check("p1", ["g1"], NSID))).toEqual({
			g1: "ready",
		});
	});

	it("collapses duplicate group ids rather than repeating them", async () => {
		const body = (await (
			await check("p1", ["g1", "g1", "g1"])
		).json()) as Reply;
		expect(body.groups).toHaveLength(1);
	});

	it("caps the list, and rejects an empty one", async () => {
		const tooMany = Array.from({ length: 201 }, (_, i) => `g${i}`);
		expect((await check("p1", tooMany)).status).toBe(400);
		expect((await check("p1", [])).status).toBe(400);
	});

	it("requires a session", async () => {
		const response = await SELF.fetch(`${API}/api/v001/photos/p1/preflight`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ groupIds: ["g1"] }),
		});
		expect(response.status).toBe(401);
	});

	it("is ADVISORY -- POST /requests still refuses on its own", async () => {
		// The one property that makes a "check first" endpoint safe to build. A caller
		// that skips preflight, or forges its result, gains nothing.
		await env.DB.prepare(
			`INSERT INTO moderated_pairs (nsid, photo_id, group_id, flickr_code, first_seen_at, last_seen_at)
       VALUES (?, 'p1', 'g1', 6, 0, 0)`,
		)
			.bind(NSID)
			.run();

		const submitted = await SELF.fetch(`${API}/api/v001/requests`, {
			method: "POST",
			headers: {
				Cookie: `${SESSION_COOKIE}=${await mintSession(env.DB, NSID, env.SESSION_KEY)}`,
				"Content-Type": "application/json",
			},
			body: JSON.stringify({ photoId: "p1", groupId: "g1" }),
		});
		expect(submitted.status).toBe(409);
	});
});

async function statusOf(body: Reply, groupId: string): Promise<string> {
	return body.groups.find((g) => g.groupId === groupId)?.status ?? "missing";
}
