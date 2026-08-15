import { env, SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { mintSession, SESSION_COOKIE } from "../src/session.js";

/** The unauthenticated surface: CORS, health, and the diagnostic page. */

/**
 * One origin serves the app shell, the API and the OAuth legs, so there is no second
 * hostname to name here.
 *
 * The CORS block below still earns its place. A same-origin browser sends no `Origin`
 * worth checking, so the middleware is inert in normal use -- but the prohibition on
 * reflecting the header MUST hold if a second origin ever appears, and a test deleted
 * because the code path is currently unreachable is a test nobody writes again.
 */
const ORIGIN = "https://flickrgroupaddr.com";
const NSID = "12345678@N00";

const originHeader = (origin: string) =>
	SELF.fetch(`${ORIGIN}/api/v001/me`, { headers: { Origin: origin } });

beforeEach(async () => {
	await env.DB.exec("DELETE FROM users");
});

describe("ADR-11, CORS", () => {
	it("allows the configured UI origin", async () => {
		// The positive case is the control: without it, the negative tests below would
		// pass just as well against middleware that never ran.
		const response = await originHeader(ORIGIN);
		expect(response.headers.get("Access-Control-Allow-Origin")).toBe(ORIGIN);
		expect(response.headers.get("Access-Control-Allow-Credentials")).toBe(
			"true",
		);
	});

	it.each([
		["an arbitrary origin", "https://evil.example"],
		["a prefix-matching lookalike", `${ORIGIN}.evil.example`],
		["a suffix lookalike", "https://evilflickrgroupaddr.com"],
	])("does NOT reflect %s", async (_name, origin) => {
		// Reflecting the header with credentials enabled lets any site on the internet
		// make authenticated calls as a logged-in user. Two lines, and it looks like the fix.
		const value = (await originHeader(origin)).headers.get(
			"Access-Control-Allow-Origin",
		);
		expect(value).not.toBe(origin);
		expect(value).not.toBe("*");
	});

	it("varies on Origin, so no cache serves one origin's decision to another", async () => {
		expect((await originHeader(ORIGIN)).headers.get("Vary")).toMatch(/Origin/);
	});

	it("answers a preflight from the UI origin", async () => {
		const response = await SELF.fetch(`${ORIGIN}/api/v001/requests`, {
			method: "OPTIONS",
			headers: {
				Origin: ORIGIN,
				"Access-Control-Request-Method": "POST",
				"Access-Control-Request-Headers": "Content-Type",
			},
		});
		expect(response.status).toBeLessThan(300);
		expect(response.headers.get("Access-Control-Allow-Origin")).toBe(ORIGIN);
	});
});

it("answers /health without a session", async () => {
	/* TRACE-EXEMPT: hygiene, not a decision. A health endpoint answers 200 because
	   that is what a health endpoint is for, and no ADR asked for it. */

	const response = await SELF.fetch(`${ORIGIN}/health`);
	expect(response.status).toBe(200);
	expect(await response.json()).toEqual({ status: "ok" });
});

/** ADR-14 chose `hono/html` over a hand-written escape, and ADR-07 makes the Flickr
 *  username the only identity there is to show. Both meet on this page. */
describe("ADR-14 and ADR-07, the diagnostic page", () => {
	const load = async (query = "", cookie?: string): Promise<string> =>
		await (
			await SELF.fetch(`${ORIGIN}/api/debug${query}`, {
				headers: cookie ? { Cookie: cookie } : {},
			})
		).text();

	async function signedIn(username: string): Promise<string> {
		await env.DB.prepare(
			`INSERT INTO users
         (nsid, flickr_username, access_token_encrypted,
          access_token_secret_encrypted, created_at, updated_at)
       VALUES (?, ?, ?, ?, 0, 0)`,
		)
			.bind(NSID, username, new Uint8Array([1]), new Uint8Array([2]))
			.run();
		return `${SESSION_COOKIE}=${await mintSession(NSID, env.SESSION_KEY)}`;
	}

	it("says so plainly when there is no session", async () => {
		expect(await load()).toMatch(/Not signed in/);
	});

	it("escapes a username containing markup", async () => {
		// A Flickr display name is third-party text rendered into a page served from the
		// origin that holds the session cookie.
		const cookie = await signedIn("<script>alert(1)</script>");
		const body = await load("", cookie);
		expect(body).not.toMatch(/<script>alert/);
		expect(body).toMatch(/&lt;script&gt;/);
	});

	it("escapes an ampersand without double-encoding the rest", async () => {
		const cookie = await signedIn("Salt & Pepper");
		const body = await load("", cookie);
		expect(body).toMatch(/Salt &amp; Pepper/);
		expect(body).not.toMatch(/&amp;amp;/);
	});

	it("reports the SESSION, not the redirect, in both directions", async () => {
		// `?login=ok` only means the callback believed it worked. These two agree right
		// up until something is wrong, which is when anyone reads this page carefully.
		expect(await load("?login=ok")).toMatch(/no valid session cookie/i);

		const cookie = await signedIn("TerryDOtt");
		expect(await load("", cookie)).toMatch(/Signed in as/);
	});

	it("does NOT claim a session for a cookie signed with the wrong key", async () => {
		const forged = await mintSession(NSID, "a-completely-different-key-32b!!");
		const body = await load("", `${SESSION_COOKIE}=${forged}`);
		expect(body).toMatch(/Not signed in/);
	});
});

/**
 * ADR-18. **The Worker MUST claim only the paths `run_worker_first` routes to it**, and
 * MUST leave everything else unclaimed so the static assets can answer.
 *
 * These assert the Worker HALF of that contract, which is the half that can regress in
 * source. The `assets` block in `wrangler.jsonc` is the other half and is verified by
 * inspection -- there is no asset binding in this pool to exercise.
 */
describe("ADR-18, one origin split by an /api prefix", () => {
	it("serves the API under /api/v001 and NOT at the bare /v001 it used to use", async () => {
		// The old path must be gone rather than quietly aliased. An alias would keep
		// working, which is exactly how a half-finished migration hides.
		expect((await SELF.fetch(`${ORIGIN}/api/v001/me`)).status).toBe(401);
		expect((await SELF.fetch(`${ORIGIN}/v001/me`)).status).toBe(404);
	});

	it("leaves / unclaimed, so index.html can answer it", async () => {
		// A Worker route at / would shadow the app shell for every visitor, and it would
		// do so only in production where the assets binding exists.
		expect((await SELF.fetch(`${ORIGIN}/`)).status).toBe(404);
	});

	it("bounces www to the apex, permanently, keeping the path and query", async () => {
		const response = await SELF.fetch(
			"https://www.flickrgroupaddr.com/queue?state=all",
			{ redirect: "manual" },
		);
		// 301 rather than 302: the apex is the permanent home, and a browser
		// caching that forever is the intent.
		expect(response.status).toBe(301);
		expect(response.headers.get("Location")).toBe(
			"https://flickrgroupaddr.com/queue?state=all",
		);
	});

	it("redirects www BEFORE any session handling", async () => {
		// A www request must never reach the session layer. If it did, anything
		// setting a cookie would set it on a hostname nothing else considers ours.
		const response = await SELF.fetch(
			"https://www.flickrgroupaddr.com/api/v001/me",
			{ redirect: "manual" },
		);
		expect(response.status).toBe(301);
		expect(response.headers.get("Set-Cookie")).toBeNull();
	});

	it("does NOT redirect the apex, so there is no loop", async () => {
		expect((await SELF.fetch(`${ORIGIN}/health`)).status).toBe(200);
	});

	it("keeps the worker-first paths answering", async () => {
		// Each of these is named in `run_worker_first`. If one stops answering here, the
		// config entry is pointing at nothing.
		expect((await SELF.fetch(`${ORIGIN}/health`)).status).toBe(200);
		expect((await SELF.fetch(`${ORIGIN}/api/debug`)).status).toBe(200);
	});
});
