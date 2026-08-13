import { env } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";

/**
 * The schema's constraints, tested against real D1 running in workerd.
 *
 * These exist because an untested CHECK constraint is a comment. Each one below
 * enforces a rule from DECISIONS.md, and a schema change that quietly drops one
 * should fail here rather than surface as a behavior nobody notices.
 */

const NOW = 1_770_000_000_000;

async function insertUser(nsid = "99999999@N00"): Promise<void> {
	await env.DB.prepare(
		`INSERT INTO users
       (nsid, access_token_encrypted, access_token_secret_encrypted, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?)`,
	)
		.bind(nsid, new Uint8Array([1, 2, 3]), new Uint8Array([4, 5, 6]), NOW, NOW)
		.run();
}

async function insertRequest(
	photoId: string,
	groupId: string,
	nsid = "99999999@N00",
): Promise<number> {
	const row = await env.DB.prepare(
		`INSERT INTO requests (nsid, photo_id, group_id, created_at)
     VALUES (?, ?, ?, ?)
     RETURNING id`,
	)
		.bind(nsid, photoId, groupId, NOW)
		.first<{ id: number }>();

	if (row === null) throw new Error("insert returned no row");
	return row.id;
}

beforeEach(async () => {
	// Storage is isolated per test file, not per test.
	await env.DB.exec("DELETE FROM requests");
	await env.DB.exec("DELETE FROM moderated_pairs");
	await env.DB.exec("DELETE FROM users");
	await insertUser();
});

describe("requests, ADR-10 ordering", () => {
	it("hands out ids in append order, which IS the queue order", async () => {
		const first = await insertRequest("photo-a", "group-1");
		const second = await insertRequest("photo-b", "group-1");
		expect(second).toBeGreaterThan(first);
	});

	it("does not reuse the id of a deleted row", async () => {
		// AUTOINCREMENT. Without it SQLite reuses rowids, and a new request could
		// land at the head of a queue it should have joined the back of.
		const first = await insertRequest("photo-a", "group-1");
		await env.DB.prepare("DELETE FROM requests WHERE id = ?").bind(first).run();

		const next = await insertRequest("photo-c", "group-1");
		expect(next).toBeGreaterThan(first);
	});
});

describe("requests, resolution invariant", () => {
	it("rejects a resolved row with no outcome", async () => {
		const id = await insertRequest("photo-a", "group-1");

		await expect(
			env.DB.prepare(
				"UPDATE requests SET state = 'resolved', resolved_at = ? WHERE id = ?",
			)
				.bind(NOW, id)
				.run(),
		).rejects.toThrow();
	});

	it("rejects a pending row that carries an outcome", async () => {
		const id = await insertRequest("photo-a", "group-1");

		await expect(
			env.DB.prepare("UPDATE requests SET outcome = 'succeeded' WHERE id = ?")
				.bind(id)
				.run(),
		).rejects.toThrow();
	});

	it("accepts a fully resolved row", async () => {
		const id = await insertRequest("photo-a", "group-1");

		await env.DB.prepare(
			`UPDATE requests
         SET state = 'resolved', outcome = 'succeeded', flickr_code = NULL, resolved_at = ?
       WHERE id = ?`,
		)
			.bind(NOW, id)
			.run();

		const row = await env.DB.prepare(
			"SELECT state, outcome FROM requests WHERE id = ?",
		)
			.bind(id)
			.first<{ state: string; outcome: string }>();

		expect(row).toEqual({ state: "resolved", outcome: "succeeded" });
	});

	it("rejects an outcome outside the documented set", async () => {
		const id = await insertRequest("photo-a", "group-1");

		await expect(
			env.DB.prepare(
				`UPDATE requests SET state = 'resolved', outcome = 'rejected_by_moderator', resolved_at = ?
         WHERE id = ?`,
			)
				.bind(NOW, id)
				.run(),
		).rejects.toThrow();
		// "rejected_by_moderator" is deliberately not a valid outcome: the Flickr
		// API never reports one. ADR-11 names things for what is known.
	});
});

describe("requests, one outstanding request per pair", () => {
	it("refuses a second pending request for the same pair", async () => {
		await insertRequest("photo-a", "group-1");

		await expect(insertRequest("photo-a", "group-1")).rejects.toThrow();
	});

	it("allows a resubmission once the first has resolved", async () => {
		// ADR-11 permits resubmitting a pair that reached a moderator. The unique
		// index constrains concurrency, not history.
		const id = await insertRequest("photo-a", "group-1");
		await env.DB.prepare(
			`UPDATE requests
         SET state = 'resolved', outcome = 'queued_for_moderator', flickr_code = 6, resolved_at = ?
       WHERE id = ?`,
		)
			.bind(NOW, id)
			.run();

		await expect(insertRequest("photo-a", "group-1")).resolves.toBeGreaterThan(
			id,
		);
	});

	it("does not conflate different groups or different photos", async () => {
		await insertRequest("photo-a", "group-1");
		await expect(insertRequest("photo-a", "group-2")).resolves.toBeDefined();
		await expect(insertRequest("photo-b", "group-1")).resolves.toBeDefined();
	});
});

describe("moderated_pairs, ADR-11", () => {
	it("accepts only codes 6 and 7", async () => {
		const insert = (code: number) =>
			env.DB.prepare(
				`INSERT INTO moderated_pairs
           (nsid, photo_id, group_id, flickr_code, first_seen_at, last_seen_at)
         VALUES (?, ?, ?, ?, ?, ?)`,
			)
				.bind("99999999@N00", `photo-${code}`, "group-1", code, NOW, NOW)
				.run();

		await expect(insert(6)).resolves.toBeDefined();
		await expect(insert(7)).resolves.toBeDefined();

		// Code 8 is "content not allowed" -- a policy rejection, not a queue. ADR-11
		// keeps it out so the warning only fires when a human really saw something.
		await expect(insert(8)).rejects.toThrow();
	});

	it("survives deletion of the user's requests", async () => {
		// ADR-11: the record MUST outlive the request row, the queue, and any
		// later cleanup.
		await insertRequest("photo-a", "group-1");
		await env.DB.prepare(
			`INSERT INTO moderated_pairs
         (nsid, photo_id, group_id, flickr_code, first_seen_at, last_seen_at)
       VALUES (?, ?, ?, ?, ?, ?)`,
		)
			.bind("99999999@N00", "photo-a", "group-1", 6, NOW, NOW)
			.run();

		await env.DB.exec("DELETE FROM requests");

		const remaining = await env.DB.prepare(
			"SELECT COUNT(*) AS n FROM moderated_pairs",
		).first<{ n: number }>();

		expect(remaining?.n).toBe(1);
	});
});

describe("users", () => {
	it("constrains needs_relink to a boolean", async () => {
		await expect(
			env.DB.prepare("UPDATE users SET needs_relink = 2 WHERE nsid = ?")
				.bind("99999999@N00")
				.run(),
		).rejects.toThrow();
	});

	it("rejects a text token where a blob belongs, because the table is STRICT", async () => {
		await expect(
			env.DB.prepare(
				`INSERT INTO users
           (nsid, access_token_encrypted, access_token_secret_encrypted, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?)`,
			)
				.bind("11111111@N00", "not-a-blob", "also-not", NOW, NOW)
				.run(),
		).rejects.toThrow();
	});
});
