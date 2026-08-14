import { env } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";

/** The schema carries the rules, so these test the CONSTRAINTS rather than any code. */

const NSID = "12345678@N00";
const UUID = `lower(
  hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' ||
  substr(hex(randomblob(2)), 2) || '-' ||
  substr('89ab', 1 + (abs(random()) % 4), 1) ||
  substr(hex(randomblob(2)), 2) || '-' || hex(randomblob(6))
)`;

async function insertRequest(sql: string, binds: unknown[] = []) {
	return await env.DB.prepare(sql)
		.bind(...binds)
		.run();
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
		.bind(NSID, new Uint8Array([1]), new Uint8Array([2]), 0, 0)
		.run();
});

describe("ADR-03 and ADR-16, requests: ordering", () => {
	it("hands out ids in append order, and never reuses a deleted one", async () => {
		// AUTOINCREMENT matters: a reused id would put a new request at the head of a
		// queue it should have joined the back of.
		for (const photo of ["p1", "p2"]) {
			await insertRequest(
				`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at)
         VALUES (${UUID}, ?, ?, 'g1', 0)`,
				[NSID, photo],
			);
		}
		const { results } = await env.DB.prepare(
			"SELECT id, photo_id FROM requests ORDER BY id",
		).all<{ id: number; photo_id: string }>();
		expect(results.map((r) => r.photo_id)).toEqual(["p1", "p2"]);

		const highest = results[1]?.id ?? 0;
		await env.DB.exec("DELETE FROM requests");
		await insertRequest(
			`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at)
       VALUES (${UUID}, ?, 'p3', 'g1', 0)`,
			[NSID],
		);
		const fresh = await env.DB.prepare("SELECT id FROM requests").first<{
			id: number;
		}>();
		expect(fresh?.id).toBeGreaterThan(highest);
	});
});

describe("ADR-02, requests: the resolution invariant", () => {
	it.each([
		["resolved with no outcome", "'resolved', NULL, 1"],
		["resolved with no resolved_at", "'resolved', 'succeeded', NULL"],
		["pending carrying an outcome", "'pending', 'succeeded', NULL"],
		["an outcome outside the set", "'resolved', 'rejected', 1"],
	])("rejects %s", async (_name, values) => {
		await expect(
			insertRequest(
				`INSERT INTO requests
           (public_id, nsid, photo_id, group_id, created_at, state, outcome, resolved_at)
         VALUES (${UUID}, ?, 'p1', 'g1', 0, ${values})`,
				[NSID],
			),
		).rejects.toThrow();
	});

	it("accepts a fully resolved row", async () => {
		await expect(
			insertRequest(
				`INSERT INTO requests
           (public_id, nsid, photo_id, group_id, created_at, state, outcome, resolved_at)
         VALUES (${UUID}, ?, 'p1', 'g1', 0, 'resolved', 'succeeded', 1)`,
				[NSID],
			),
		).resolves.toBeDefined();
	});
});

describe("ADR-04, requests: one outstanding request per pair", () => {
	const pending = (photo: string, group: string) =>
		insertRequest(
			`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at)
       VALUES (${UUID}, ?, ?, ?, 0)`,
			[NSID, photo, group],
		);

	it("refuses a second pending request for the same pair", async () => {
		await pending("p1", "g1");
		await expect(pending("p1", "g1")).rejects.toThrow();
	});

	it("allows the same photo in a different group", async () => {
		await pending("p1", "g1");
		await expect(pending("p1", "g2")).resolves.toBeDefined();
	});

	it("allows a resubmission once the first has resolved", async () => {
		await pending("p1", "g1");
		await env.DB.exec(
			"UPDATE requests SET state='resolved', outcome='failed', resolved_at=1",
		);
		await expect(pending("p1", "g1")).resolves.toBeDefined();
	});
});

describe("moderated_pairs", () => {
	const pair = (code: number) =>
		env.DB.prepare(
			`INSERT INTO moderated_pairs
         (nsid, photo_id, group_id, flickr_code, first_seen_at, last_seen_at)
       VALUES (?, 'p1', 'g1', ?, 0, 0)`,
		)
			.bind(NSID, code)
			.run();

	it.each([6, 7])("accepts code %s", async (code) => {
		await expect(pair(code)).resolves.toBeDefined();
	});

	it.each([3, 8, 0])("refuses code %s", async (code) => {
		await expect(pair(code)).rejects.toThrow();
	});

	it("outlives the user's requests", async () => {
		// ADR-04: deliberately not a foreign key. A cascade would delete the history the
		// warning depends on.
		await pair(6);
		await env.DB.exec("DELETE FROM requests");
		const row = await env.DB.prepare(
			"SELECT flickr_code FROM moderated_pairs",
		).first();
		expect(row).not.toBeNull();
	});
});

describe("ADR-07 and ADR-09, users", () => {
	it("constrains needs_relink to a boolean", async () => {
		await expect(
			env.DB.prepare("UPDATE users SET needs_relink = 2").run(),
		).rejects.toThrow();
	});

	it("rejects text where a blob belongs, because the table is STRICT", async () => {
		await expect(
			env.DB.prepare(
				"UPDATE users SET access_token_encrypted = 'plaintext'",
			).run(),
		).rejects.toThrow();
	});
});
