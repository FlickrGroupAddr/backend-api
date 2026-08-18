import { env, SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import {
	mintSession,
	revokeSession,
	SESSION_COOKIE,
	verifySession,
} from "../src/session.js";

/**
 * ADR-10's opaque signed handle, and ADR-11's cookie attributes. ADR-10 used to be a
 * stateless JWS; the decision was replaced in place rather than renumbered.
 *
 * **The attribute tests read the real `Set-Cookie` from a real login.** They once read a
 * helper that returned a hardcoded string and that the Worker never called, so five tests
 * described a cookie nothing issued while logout had silently lost `HttpOnly`. Driving a
 * login is the only version of this test that can fail for the right reason.
 */

const BASE = "https://api.flickrgroupaddr.com";
const NSID = "12345678@N00";

/** The session row references `users`, so a user has to exist before one is minted.
 *  That constraint is the point: a handle MUST NOT outlive the account it names. */
async function addUser(nsid: string): Promise<void> {
	await env.DB.prepare(
		`INSERT INTO users
       (nsid, access_token_encrypted, access_token_secret_encrypted, created_at, updated_at)
     VALUES (?, ?, ?, 0, 0)`,
	)
		.bind(nsid, new Uint8Array([1]), new Uint8Array([2]))
		.run();
}

/** A full login against the stubbed Flickr. Returns its `Set-Cookie`. */
async function loginSetCookie(): Promise<string> {
	const login = await SELF.fetch(`${BASE}/auth/flickr/login`, {
		redirect: "manual",
	});
	expect(login.status).toBe(302);

	const authorize = new URL(login.headers.get("Location") ?? "");
	const requestToken = authorize.searchParams.get("oauth_token");
	expect(requestToken).not.toBeNull();

	const callback = await SELF.fetch(
		`${BASE}/auth/flickr/callback?oauth_token=${requestToken}&oauth_verifier=test-verifier`,
		{ redirect: "manual" },
	);
	return callback.headers.get("Set-Cookie") ?? "";
}

beforeEach(async () => {
	await env.DB.exec("DELETE FROM sessions");
	await env.DB.exec("DELETE FROM users");
	await addUser(NSID);
});

describe("mint and verify", () => {
	it("round-trips the NSID", async () => {
		const token = await mintSession(env.DB, NSID, env.SESSION_KEY);
		expect(await verifySession(env.DB, token, env.SESSION_KEY)).toEqual({
			nsid: NSID,
			clientType: "browser",
		});
	});

	it("CARRIES NOTHING about the user, which is the whole point", async () => {
		// The old JWS put the NSID in a base64url payload anyone holding the cookie
		// could decode. An infostealer reading the cookie jar got a permanent Flickr
		// identifier for free; nobody can rotate an NSID.
		const token = await mintSession(env.DB, NSID, env.SESSION_KEY);
		expect(token).not.toContain(NSID);

		// And not merely absent as a literal -- not recoverable by decoding either half.
		for (const half of token.split(".")) {
			const decoded = atob(half.replace(/-/g, "+").replace(/_/g, "/"));
			expect(decoded).not.toContain("@N00");
		}
	});

	it("stores a HASH, so a database leak yields no usable tokens", async () => {
		const token = await mintSession(env.DB, NSID, env.SESSION_KEY);
		const id = token.slice(0, token.indexOf("."));

		const rows = await env.DB.prepare("SELECT id_hash FROM sessions").all<{
			id_hash: string;
		}>();
		expect(rows.results).toHaveLength(1);
		// Same reasoning as never storing a password.
		expect(rows.results[0]?.id_hash).not.toBe(id);
	});

	it("issues a different handle every time", async () => {
		const a = await mintSession(env.DB, NSID, env.SESSION_KEY);
		const b = await mintSession(env.DB, NSID, env.SESSION_KEY);
		expect(a).not.toBe(b);
	});

	it.each([
		["a handle signed with a different key", "signed-elsewhere"],
		["a tampered signature", "tampered"],
		["a tampered id", "tampered-id"],
		["malformed input", "malformed"],
		["no separator at all", "no-separator"],
		["a well-formed handle with no row", "unknown"],
	])("rejects %s", async (_name, kind) => {
		let token: string;
		switch (kind) {
			case "signed-elsewhere":
				// Rotating SESSION_KEY produces exactly this, which is why rotation is
				// the temporal blast-radius control.
				token = await mintSession(
					env.DB,
					NSID,
					"a-completely-different-key-32b!!",
				);
				break;
			case "tampered": {
				const minted = await mintSession(env.DB, NSID, env.SESSION_KEY);
				const cut = minted.indexOf(".");
				token = `${minted.slice(0, cut)}.${minted.slice(cut + 2)}`;
				break;
			}
			case "tampered-id": {
				const minted = await mintSession(env.DB, NSID, env.SESSION_KEY);
				const cut = minted.indexOf(".");
				// **Pick a character that CANNOT equal the one being replaced.** A fixed
				// substitute silently no-ops whenever the id already starts with it --
				// base64url has 64 symbols, so that flaked about one run in sixty-four,
				// and it did on the second run of this suite.
				const flipped = minted[0] === "A" ? "B" : "A";
				token = `${flipped}${minted.slice(1, cut)}.${minted.slice(cut + 1)}`;
				break;
			}
			case "malformed":
				token = "not-a-handle";
				break;
			case "no-separator":
				token = "abcdef";
				break;
			default: {
				// Signed correctly and never issued: passes the HMAC gate, fails the
				// lookup. This is the case a signature alone could not catch, and the
				// reason signing SURVIVES the move to opaque.
				const minted = await mintSession(env.DB, NSID, env.SESSION_KEY);
				await env.DB.exec("DELETE FROM sessions");
				token = minted;
			}
		}
		expect(await verifySession(env.DB, token, env.SESSION_KEY)).toBeNull();
	});

	it("rejects an expired handle without deleting it", async () => {
		const token = await mintSession(env.DB, NSID, env.SESSION_KEY);
		await env.DB.exec("UPDATE sessions SET expires_at = 1, created_at = 0");
		expect(await verifySession(env.DB, token, env.SESSION_KEY)).toBeNull();

		// Expiry is checked on the row already fetched, so an unswept table stays
		// correct and merely grows. Verification MUST NOT depend on a cleanup job.
		const rows = await env.DB.prepare("SELECT id_hash FROM sessions").all();
		expect(rows.results).toHaveLength(1);
	});
});

describe("revocation, which ADR-10 could not do", () => {
	it("kills the handle for everyone holding it", async () => {
		const token = await mintSession(env.DB, NSID, env.SESSION_KEY);
		expect(await verifySession(env.DB, token, env.SESSION_KEY)).toEqual({
			nsid: NSID,
			clientType: "browser",
		});

		await revokeSession(env.DB, token);
		expect(await verifySession(env.DB, token, env.SESSION_KEY)).toBeNull();
	});

	it("leaves other sessions of the same user alone", async () => {
		const first = await mintSession(env.DB, NSID, env.SESSION_KEY);
		const second = await mintSession(env.DB, NSID, env.SESSION_KEY);

		await revokeSession(env.DB, first);
		expect(await verifySession(env.DB, second, env.SESSION_KEY)).toEqual({
			nsid: NSID,
			clientType: "browser",
		});
	});

	it("dies with the user row, rather than outliving the account", async () => {
		const token = await mintSession(env.DB, NSID, env.SESSION_KEY);
		await env.DB.exec("DELETE FROM users");
		expect(await verifySession(env.DB, token, env.SESSION_KEY)).toBeNull();
	});

	it("logout revokes on the SERVER, not just in the browser", async () => {
		// The cookie being cleared proves nothing about whoever else holds a copy.
		const setCookie = await loginSetCookie();
		const token = /__Host-fga_session=([^;]+)/.exec(setCookie)?.[1] ?? "";
		expect(token).not.toBe("");
		expect(await verifySession(env.DB, token, env.SESSION_KEY)).not.toBeNull();

		await SELF.fetch(`${BASE}/auth/flickr/logout`, {
			method: "POST",
			headers: { Cookie: `${SESSION_COOKIE}=${token}` },
		});

		expect(await verifySession(env.DB, token, env.SESSION_KEY)).toBeNull();
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

	it("expires with the row rather than on its own schedule", async () => {
		// Drift is silent, and a row outliving its cookie is the dangerous direction:
		// the browser stops sending a handle the database still honors.
		const maxAge = /Max-Age=(\d+)/.exec(await loginSetCookie())?.[1];
		expect(Number(maxAge)).toBe(60 * 60 * 24 * 30);
	});
});

it("clears with attributes that match, or the deletion is a no-op", async () => {
	const cleared = await SELF.fetch(`${BASE}/auth/flickr/logout`, {
		method: "POST",
	});
	const header = cleared.headers.get("Set-Cookie") ?? "";
	expect(header).toMatch(new RegExp(SESSION_COOKIE));
	expect(header).toMatch(/HttpOnly/i);
	expect(header).toMatch(/Path=\//i);
	expect(header).not.toMatch(/Domain=/i);
});
