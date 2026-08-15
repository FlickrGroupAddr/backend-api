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
	await env.DB.exec("DELETE FROM sessions");
	await env.DB.exec("DELETE FROM users");
	await env.DB.prepare(
		`INSERT INTO users
       (nsid, access_token_encrypted, access_token_secret_encrypted, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?)`,
	)
		.bind(NSID, new Uint8Array([1]), new Uint8Array([2]), 0, 0)
		.run();
});

describe("ADR-22, STRICT tables refuse a wrong type", () => {
	/**
	 * **Without `STRICT` every one of these succeeds**, because SQLite's default is type
	 * affinity: a declared type is a hint about storage, not a rule. The write lands, the
	 * read lands, and the comparison quietly means something else much later.
	 */
	it.each([
		[
			"text into requests.created_at",
			`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at)
       VALUES (${UUID}, ?, 'p1', 'g1', 'not-a-number')`,
			[NSID],
		],
		[
			"text into sessions.expires_at",
			`INSERT INTO sessions (id_hash, nsid, created_at, expires_at)
       VALUES ('h1', ?, 0, 'whenever')`,
			[NSID],
		],
		[
			"text into requests.attempts",
			`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at, attempts)
       VALUES (${UUID}, ?, 'p2', 'g1', 0, 'many')`,
			[NSID],
		],
	])("rejects %s", async (_name, sql, binds) => {
		// **Asserted on the MESSAGE, not merely that something threw.** A foreign key
		// violation, a typo in the SQL and a STRICT rejection are all exceptions, and only
		// one of them proves what this test claims. Measured wording, 2026-08-15:
		// "cannot store TEXT value in INTEGER column requests.created_at".
		await expect(insertRequest(sql, binds)).rejects.toThrow(
			/cannot store TEXT value in INTEGER column/,
		);
	});

	it("still accepts the right types, so the check is not simply refusing everything", async () => {
		// The control. Without it, a table that rejected every insert would pass above.
		const now = Date.now();
		await insertRequest(
			`INSERT INTO sessions (id_hash, nsid, created_at, expires_at)
       VALUES ('h-ok', ?, ?, ?)`,
			[NSID, now, now + 1000],
		);
		const row = await env.DB.prepare(
			"SELECT expires_at FROM sessions WHERE id_hash = 'h-ok'",
		).first<{ expires_at: number }>();
		expect(row?.expires_at).toBe(now + 1000);
	});

	it.each([
		[
			"requests",
			`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at)
       VALUES (${UUID}, 'nobody@N00', 'p1', 'g1', 0)`,
		],
		[
			"sessions",
			`INSERT INTO sessions (id_hash, nsid, created_at, expires_at)
       VALUES ('h-orphan', 'nobody@N00', 0, 1)`,
		],
	])(
		"FOREIGN KEYS ARE ENFORCED: %s refuses an unknown nsid",
		async (_table, sql) => {
			// SQLite only enforces foreign keys when `PRAGMA foreign_keys = ON`, and it is
			// OFF by default. **This proves D1 turns it on** rather than assuming it.
			await expect(insertRequest(sql)).rejects.toThrow(
				/FOREIGN KEY constraint/,
			);
		},
	);

	it("cascades: deleting a user removes their requests and sessions", async () => {
		await insertRequest(
			`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at)
       VALUES (${UUID}, ?, 'p1', 'g1', 0)`,
			[NSID],
		);
		await insertRequest(
			`INSERT INTO sessions (id_hash, nsid, created_at, expires_at)
       VALUES ('h-cascade', ?, 0, 1)`,
			[NSID],
		);

		await env.DB.exec("DELETE FROM users");

		for (const table of ["requests", "sessions"]) {
			const row = await env.DB.prepare(
				`SELECT COUNT(*) AS n FROM ${table}`,
			).first<{ n: number }>();
			expect(row?.n).toBe(0);
		}
	});

	it("moderated_pairs SURVIVES the user, deliberately and by having no foreign key", async () => {
		/**
		 * **ADR-04 says a pair that reached a moderator is remembered FOREVER**, and ADR-07
		 * makes the Flickr NSID the identity — which is permanent and cannot be reissued.
		 * So a user who deletes their FGA account and later signs back in MUST still be
		 * warned before their photo returns to the same volunteer's queue.
		 *
		 * **A foreign key here could not express that.** Cascading would delete the history
		 * ADR-01 depends on, and restricting would make user deletion impossible. **No key
		 * is the only option that keeps both**, and the cost is no insert-time sanity check
		 * on this one table.
		 *
		 * The migration comment explains the absent link to `requests` and is silent about
		 * `users`; ADR-22 now carries this half.
		 */
		await insertRequest(
			`INSERT INTO moderated_pairs
         (nsid, photo_id, group_id, flickr_code, first_seen_at, last_seen_at)
       VALUES (?, 'p1', 'g1', 6, 0, 0)`,
			[NSID],
		);

		await env.DB.exec("DELETE FROM users");

		const row = await env.DB.prepare(
			"SELECT COUNT(*) AS n FROM moderated_pairs",
		).first<{ n: number }>();
		expect(row?.n).toBe(1);
	});

	it("enforces the sessions CHECK that expiry follows creation", async () => {
		// A handle that expired before it was minted is a bug in the minting path, and a
		// constraint is the only place that cannot be forgotten.
		await expect(
			insertRequest(
				`INSERT INTO sessions (id_hash, nsid, created_at, expires_at)
         VALUES ('h-backwards', ?, 100, 50)`,
				[NSID],
			),
		).rejects.toThrow(/CHECK constraint failed: expires_at > created_at/);
	});
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
