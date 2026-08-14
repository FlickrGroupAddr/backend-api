import { env, SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { mintSession, SESSION_COOKIE } from "../src/session.js";

/** The unauthenticated surface: CORS, health, and the landing page. */

const API = "https://api.flickrgroupaddr.com";
const UI = "https://flickrgroupaddr.com";
const NSID = "12345678@N00";

const originHeader = (origin: string) =>
	SELF.fetch(`${API}/v001/me`, { headers: { Origin: origin } });

beforeEach(async () => {
	await env.DB.exec("DELETE FROM users");
});

describe("ADR-12, CORS", () => {
	it("allows the configured UI origin", async () => {
		// The positive case is the control: without it, the negative tests below would
		// pass just as well against middleware that never ran.
		const response = await originHeader(UI);
		expect(response.headers.get("Access-Control-Allow-Origin")).toBe(UI);
		expect(response.headers.get("Access-Control-Allow-Credentials")).toBe(
			"true",
		);
	});

	it.each([
		["an arbitrary origin", "https://evil.example"],
		["a prefix-matching lookalike", `${UI}.evil.example`],
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
		expect((await originHeader(UI)).headers.get("Vary")).toMatch(/Origin/);
	});

	it("answers a preflight from the UI origin", async () => {
		const response = await SELF.fetch(`${API}/v001/requests`, {
			method: "OPTIONS",
			headers: {
				Origin: UI,
				"Access-Control-Request-Method": "POST",
				"Access-Control-Request-Headers": "Content-Type",
			},
		});
		expect(response.status).toBeLessThan(300);
		expect(response.headers.get("Access-Control-Allow-Origin")).toBe(UI);
	});
});

it("answers /health without a session", async () => {
	const response = await SELF.fetch(`${API}/health`);
	expect(response.status).toBe(200);
	expect(await response.json()).toEqual({ status: "ok" });
});

describe("the landing page", () => {
	const load = async (query = "", cookie?: string): Promise<string> =>
		await (
			await SELF.fetch(`${API}/${query}`, {
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
