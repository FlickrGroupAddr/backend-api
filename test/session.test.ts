import { env, SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import { mintSession, SESSION_COOKIE, verifySession } from "../src/session.js";

/**
 * ADR-10 and ADR-11.
 *
 * **The attribute tests read the real `Set-Cookie` from a real login.** They once read a
 * helper that returned a hardcoded string and that the Worker never called, so five tests
 * described a cookie nothing issued while logout had silently lost `HttpOnly`. Driving a
 * login is the only version of this test that can fail for the right reason.
 */

const BASE = "https://api.flickrgroupaddr.com";
const NSID = "12345678@N00";

/** A full login against the stubbed Flickr. Returns its `Set-Cookie`. */
async function loginSetCookie(): Promise<string> {
	const login = await SELF.fetch(`${BASE}/oauth/login`, { redirect: "manual" });
	expect(login.status).toBe(302);

	const authorize = new URL(login.headers.get("Location") ?? "");
	const requestToken = authorize.searchParams.get("oauth_token");
	expect(requestToken).not.toBeNull();

	const callback = await SELF.fetch(
		`${BASE}/oauth/callback?oauth_token=${requestToken}&oauth_verifier=test-verifier`,
		{ redirect: "manual" },
	);
	return callback.headers.get("Set-Cookie") ?? "";
}

describe("mint and verify", () => {
	it("round-trips the NSID", async () => {
		const token = await mintSession(NSID, env.SESSION_KEY);
		expect(await verifySession(token, env.SESSION_KEY)).toBe(NSID);
	});

	it.each([
		["a token signed with a different key", "signed-elsewhere"],
		["a tampered payload", "tampered"],
		["malformed input", "malformed"],
		["a wrong audience", "audience"],
		["an expired token", "expired"],
	])("rejects %s", async (_name, kind) => {
		let token: string;
		switch (kind) {
			case "signed-elsewhere":
				token = await mintSession(NSID, "a-completely-different-key-32b!!");
				break;
			case "tampered": {
				const parts = (await mintSession(NSID, env.SESSION_KEY)).split(".");
				token = `${parts[0]}.${parts[1]}x.${parts[2]}`;
				break;
			}
			case "malformed":
				token = "not.a.jwt";
				break;
			case "audience":
				token = await new (await import("jose")).SignJWT({})
					.setProtectedHeader({ alg: "HS256" })
					.setSubject(NSID)
					.setIssuer("fga")
					.setAudience("someone-else")
					.setExpirationTime("1h")
					.sign(new TextEncoder().encode(env.SESSION_KEY));
				break;
			default:
				token = await new (await import("jose")).SignJWT({})
					.setProtectedHeader({ alg: "HS256" })
					.setSubject(NSID)
					.setIssuer("fga")
					.setAudience("fga-api")
					.setExpirationTime(Math.floor(Date.now() / 1000) - 60)
					.sign(new TextEncoder().encode(env.SESSION_KEY));
		}
		expect(await verifySession(token, env.SESSION_KEY)).toBeNull();
	});
});

describe("cookie attributes on a real login", () => {
	it.each([
		["HttpOnly", /HttpOnly/i],
		["Secure", /Secure/i],
		["SameSite=Lax", /SameSite=Lax/i],
		["the __Host- prefix", new RegExp(SESSION_COOKIE)],
		["Path=/", /Path=\//i],
	])("carries %s", async (_name, pattern) => {
		expect(await loginSetCookie()).toMatch(pattern);
	});

	it("carries NO Domain attribute, so the cookie stays host-only", async () => {
		expect(await loginSetCookie()).not.toMatch(/Domain=/i);
	});

	it("is not SameSite=None", async () => {
		expect(await loginSetCookie()).not.toMatch(/SameSite=None/i);
	});

	it("expires with the token rather than on its own schedule", async () => {
		// Drift is silent, and a token outliving its cookie is the dangerous direction.
		const maxAge = /Max-Age=(\d+)/.exec(await loginSetCookie())?.[1];
		expect(Number(maxAge)).toBe(60 * 60 * 24 * 30);
	});
});

it("clears with attributes that match, or the deletion is a no-op", async () => {
	const cleared = await SELF.fetch(`${BASE}/oauth/logout`, { method: "POST" });
	const header = cleared.headers.get("Set-Cookie") ?? "";
	expect(header).toMatch(new RegExp(SESSION_COOKIE));
	expect(header).toMatch(/HttpOnly/i);
	expect(header).toMatch(/Path=\//i);
	expect(header).not.toMatch(/Domain=/i);
});
