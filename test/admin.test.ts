import { env, SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { checkAdmin } from "../src/admin/allowlist.js";
import { type Context, findingsFor } from "../src/db/metrics.js";
import { mintSession, SESSION_COOKIE } from "../src/session.js";

/** The admin surface. ADR-19. */

const ORIGIN = "https://flickrgroupaddr.com";
/** On the allowlist in vitest.config.ts. */
const ADMIN = "12345678@N00";
/** Signed in, and not on it. */
const OUTSIDER = "87654321@N00";

/** A session row references `users`, so being signed in means the row exists. That is
 *  reality rather than test scaffolding: a handle MUST NOT outlive its account. */
async function asUser(nsid: string, path: string): Promise<Response> {
	await env.DB.prepare(
		`INSERT OR IGNORE INTO users
       (nsid, access_token_encrypted, access_token_secret_encrypted, created_at, updated_at)
     VALUES (?, ?, ?, 0, 0)`,
	)
		.bind(nsid, new Uint8Array([1]), new Uint8Array([2]))
		.run();

	return await SELF.fetch(`${ORIGIN}${path}`, {
		headers: {
			Cookie: `${SESSION_COOKIE}=${await mintSession(env.DB, nsid, env.SESSION_KEY)}`,
		},
	});
}

beforeEach(async () => {
	await env.DB.exec("DELETE FROM requests");
	await env.DB.exec("DELETE FROM moderated_pairs");
	await env.DB.exec("DELETE FROM users");
});

describe("ADR-19, the admin gate", () => {
	it("answers 404 to a signed-in non-admin, NOT 403", async () => {
		// 403 would confirm the surface exists and that this account is merely not on
		// the list. That is worth nothing to the caller and something to a prober.
		const response = await asUser(OUTSIDER, "/api/v001/admin/overview");
		expect(response.status).toBe(404);
	});

	it("answers 401 with no session at all, before the allowlist is consulted", async () => {
		// requireSession runs first. If this ever returned 404 it would mean the admin
		// middleware was registered ahead of it, and `nsid` would be undefined.
		const response = await SELF.fetch(`${ORIGIN}/api/v001/admin/overview`);
		expect(response.status).toBe(401);
	});

	it("lets an allowlisted admin through", async () => {
		const response = await asUser(ADMIN, "/api/v001/admin/overview");
		expect(response.status).toBe(200);
	});

	it("carries ADR-12's no-store header, like every other /api/v001 response", async () => {
		// The admin routes hang off apiRoutes precisely so they inherit this. If the
		// header goes missing, somebody moved them to their own app.
		const response = await asUser(ADMIN, "/api/v001/admin/overview");
		expect(response.headers.get("Cache-Control")).toBe("private, no-store");
	});

	it("caps the window rather than only defaulting it", async () => {
		expect(
			(await asUser(ADMIN, "/api/v001/admin/overview?days=0")).status,
		).toBe(400);
		expect(
			(await asUser(ADMIN, "/api/v001/admin/overview?days=9999")).status,
		).toBe(400);
	});

	it("reports admin status on /me so the interface can hide the link", async () => {
		const mine = (await (await asUser(ADMIN, "/api/v001/me")).json()) as {
			admin: boolean;
		};
		const theirs = (await (await asUser(OUTSIDER, "/api/v001/me")).json()) as {
			admin: boolean;
		};
		expect(mine.admin).toBe(true);
		expect(theirs.admin).toBe(false);
	});
});

describe("ADR-19, the allowlist fails closed", () => {
	// The whole point. A config mistake must admit nobody, never everybody -- "no
	// allowlist" reading as "no restriction" is the failure this is built against.
	it.each([
		["undefined", undefined],
		["empty", ""],
		["whitespace", "   "],
		["not JSON", "12345678@N00"],
		["a bare string", '"12345678@N00"'],
		["an object", '{"nsid":"12345678@N00"}'],
		["an array of non-strings", "[123]"],
		["an array of malformed NSIDs", '["not-an-nsid"]'],
		["truncated JSON", '["12345678@N00"'],
	])("admits nobody when the secret is %s", (_name, secret) => {
		expect(checkAdmin(ADMIN, secret).admin).toBe(false);
	});

	it("reports WHY, so a dark dashboard is diagnosable", () => {
		expect(checkAdmin(ADMIN, undefined).configError).toMatch(/not set/);
		expect(checkAdmin(ADMIN, "nonsense").configError).toMatch(/valid JSON/);
		expect(checkAdmin(ADMIN, "[123]").configError).toMatch(/array of NSID/);
	});

	it("treats a well-formed empty list as a deliberate off switch, not an error", () => {
		const result = checkAdmin(ADMIN, "[]");
		expect(result.admin).toBe(false);
		expect(result.configError).toBeNull();
	});

	it("admits only exact matches", () => {
		const list = '["12345678@N00"]';
		expect(checkAdmin("12345678@N00", list).admin).toBe(true);
		expect(checkAdmin("12345678@N0", list).admin).toBe(false);
		expect(checkAdmin("112345678@N00", list).admin).toBe(false);
		expect(checkAdmin("12345678@N000", list).admin).toBe(false);
	});
});

/**
 * ADR-19's loudness rules, driven directly rather than through a seeded database.
 *
 * **Thresholds nobody tests are thresholds nobody trusts**, and shaping a database into
 * each of these states would take more fixture than assertion.
 */
describe("ADR-19, findings only appear when there is something to do", () => {
	const base: Context = {
		windowDays: 7,
		pendingTotal: 0,
		resolvedLast24h: 0,
		resolvedInWindow: 0,
		lastResolvedAt: null,
		usersTotal: 1,
		usersNeedingRelink: 0,
		stalledHeads: 0,
		oldestHeadTouchedAt: null,
		moderatedPairsTotal: 0,
		moderatedPairsInWindow: 0,
		reachedModeratorTwice: 0,
		codes: [],
	};

	const now = Date.now();
	const ids = (context: Context) => findingsFor(context, now).map((f) => f.id);

	it("says nothing at all when a healthy system has nothing waiting", () => {
		expect(findingsFor(base, now)).toEqual([]);
	});

	it("does NOT complain about a long queue that is being attempted", () => {
		// Waiting is the product working. Terry's instinct that queue length felt like
		// an alert and should not be one is encoded here.
		const busy = { ...base, pendingTotal: 400, stalledHeads: 0 };
		expect(ids(busy)).not.toContain("sweep-not-reaching-queues");
	});

	it("flags queue heads the sweep has not touched", () => {
		const stalled = {
			...base,
			pendingTotal: 12,
			stalledHeads: 3,
			oldestHeadTouchedAt: now - 5 * 86_400_000,
		};
		const found = findingsFor(stalled, now).find(
			(f) => f.id === "sweep-not-reaching-queues",
		);
		expect(found?.severity).toBe("act");
		expect(found?.action).toMatch(/log/i);
	});

	it("flags an unrecognized Flickr code only once it is a pattern", () => {
		const one = {
			...base,
			codes: [
				{ code: 42, count: 1, disposition: "terminal", unrecognized: true },
			],
		};
		const many = {
			...base,
			codes: [
				{ code: 42, count: 7, disposition: "terminal", unrecognized: true },
			],
		};
		expect(ids(one)).not.toContain("unknown-code-42");
		expect(ids(many)).toContain("unknown-code-42");
	});

	it("does not flag codes ADR-02 already recognizes", () => {
		const known = {
			...base,
			codes: [
				{ code: 5, count: 90, disposition: "retry", unrecognized: false },
				{ code: 98, count: 9, disposition: "terminal", unrecognized: false },
			],
		};
		expect(ids(known)).toEqual([]);
	});

	it("flags accounts that cannot be served, because nothing else will tell them", () => {
		const found = findingsFor({ ...base, usersNeedingRelink: 2 }, now).find(
			(f) => f.id === "users-need-relink",
		);
		expect(found?.severity).toBe("act");
	});

	it("treats a repeat moderator submission as watch, not act", () => {
		// ADR-04 permits a person to resubmit knowingly, so this is a number to watch
		// rather than a fault to fix. Calling it `act` would cry wolf.
		const found = findingsFor({ ...base, reachedModeratorTwice: 4 }, now).find(
			(f) => f.id === "moderator-twice",
		);
		expect(found?.severity).toBe("watch");
	});

	it("names the throttle blind spot as info, and only when work is waiting", () => {
		expect(ids(base)).not.toContain("throttle-mode-unknown");
		const found = findingsFor({ ...base, pendingTotal: 5 }, now).find(
			(f) => f.id === "throttle-mode-unknown",
		);
		expect(found?.severity).toBe("info");
	});

	it("gives every `act` finding something to actually do", () => {
		const loud: Context = {
			...base,
			pendingTotal: 9,
			stalledHeads: 2,
			oldestHeadTouchedAt: now - 3 * 86_400_000,
			usersNeedingRelink: 1,
			codes: [
				{ code: 77, count: 5, disposition: "terminal", unrecognized: true },
			],
		};
		const acts = findingsFor(loud, now).filter((f) => f.severity === "act");
		expect(acts.length).toBeGreaterThan(0);
		for (const finding of acts) {
			expect(finding.action.length).toBeGreaterThan(10);
		}
	});
});
