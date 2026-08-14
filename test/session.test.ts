import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import { mintSession, SESSION_COOKIE, verifySession } from "../src/session.js";

/**
 * The session cookie's security properties.
 *
 * ADR-14 chose `jose` over a hand-written signer precisely because these are the
 * failures that matter, so these tests check that the library is being USED
 * correctly -- pinned algorithm, checked expiry, checked issuer and audience.
 * A correct library called carelessly fails in exactly the same ways.
 */

const KEY = "a-signing-key-of-at-least-32-bytes-for-hs256";
const OTHER_KEY = "a-different-signing-key-also-32-bytes-long!!";
const NSID = "12345678@N00";

describe("mint and verify", () => {
	it("round-trips the NSID", async () => {
		const token = await mintSession(NSID, KEY);
		expect(await verifySession(token, KEY)).toBe(NSID);
	});

	it("never contains the NSID in a form that looks secret", async () => {
		// A JWS payload is base64url, NOT encrypted. This test documents that
		// rather than asserting privacy the format does not provide -- the NSID is
		// public data on Flickr, and the signature is what makes it trustworthy.
		const token = await mintSession(NSID, KEY);
		const payload = JSON.parse(
			atob((token.split(".")[1] ?? "").replace(/-/g, "+").replace(/_/g, "/")),
		);
		expect(payload.sub).toBe(NSID);
	});
});

describe("rejection", () => {
	it("rejects a token signed with a different key", async () => {
		const token = await mintSession(NSID, OTHER_KEY);
		expect(await verifySession(token, KEY)).toBeNull();
	});

	it("rejects a tampered payload", async () => {
		const token = await mintSession(NSID, KEY);
		const [header, , signature] = token.split(".");

		const forged = btoa(JSON.stringify({ sub: "99999999@N00" }))
			.replace(/\+/g, "-")
			.replace(/\//g, "_")
			.replace(/=+$/, "");

		expect(
			await verifySession(`${header}.${forged}.${signature}`, KEY),
		).toBeNull();
	});

	it('rejects an unsigned "alg":"none" token', async () => {
		// The classic JWT attack. Pinning algorithms: ["HS256"] is what stops it.
		const b64 = (value: object) =>
			btoa(JSON.stringify(value))
				.replace(/\+/g, "-")
				.replace(/\//g, "_")
				.replace(/=+$/, "");

		const unsigned = `${b64({ alg: "none", typ: "JWT" })}.${b64({
			sub: NSID,
			iss: "fga",
			aud: "fga-api",
		})}.`;

		expect(await verifySession(unsigned, KEY)).toBeNull();
	});

	it("rejects malformed input without throwing", async () => {
		for (const bad of ["", "not-a-token", "a.b.c", "....", "null"]) {
			expect(await verifySession(bad, KEY)).toBeNull();
		}
	});

	it("rejects a token minted for a different audience", async () => {
		// Guards against a token from some future sibling service being accepted
		// here just because it happens to share the signing key.
		const { SignJWT } = await import("jose");
		const foreign = await new SignJWT({})
			.setProtectedHeader({ alg: "HS256" })
			.setSubject(NSID)
			.setIssuer("fga")
			.setAudience("some-other-service")
			.setIssuedAt()
			.setExpirationTime("30d")
			.sign(new TextEncoder().encode(KEY));

		expect(await verifySession(foreign, KEY)).toBeNull();
	});

	it("rejects an expired token", async () => {
		const { SignJWT } = await import("jose");
		const expired = await new SignJWT({})
			.setProtectedHeader({ alg: "HS256" })
			.setSubject(NSID)
			.setIssuer("fga")
			.setAudience("fga-api")
			.setIssuedAt(Math.floor(Date.now() / 1000) - 7200)
			.setExpirationTime(Math.floor(Date.now() / 1000) - 3600)
			.sign(new TextEncoder().encode(KEY));

		expect(await verifySession(expired, KEY)).toBeNull();
	});
});

/**
 * The cookie attributes ADR-12 settles, asserted against the REAL `Set-Cookie`
 * header a real login emits.
 *
 * **These used to read a `sessionCookieAttributes()` helper that returned a
 * hardcoded string and that the Worker never called.** Five tests passed
 * describing a cookie nothing issued, while the live attributes sat in a
 * separate literal in the callback route. Their result was a function of one
 * string constant and could not have detected any change to the cookie actually
 * sent -- see [[assertions-that-pass-either-way]]. Driving a login and reading
 * the header is the only version of this test that can fail for the right
 * reason.
 */
const BASE = "https://api.flickrgroupaddr.com";

/** Runs a full login against the stubbed Flickr and returns its `Set-Cookie`. */
async function loginSetCookie(): Promise<string> {
	const login = await SELF.fetch(`${BASE}/oauth/login`, {
		redirect: "manual",
	});
	expect(login.status).toBe(302);

	const authorize = new URL(login.headers.get("Location") ?? "");
	const requestToken = authorize.searchParams.get("oauth_token");
	expect(requestToken).not.toBeNull();

	const callback = await SELF.fetch(
		`${BASE}/oauth/callback?oauth_token=${requestToken}&oauth_verifier=test-verifier`,
		{ redirect: "manual" },
	);
	expect(callback.status).toBe(302);

	const header = callback.headers.get("Set-Cookie");
	expect(header).not.toBeNull();
	return header ?? "";
}

describe("cookie attributes, ADR-12", () => {
	it("is HttpOnly, so script cannot read the session", async () => {
		expect(await loginSetCookie()).toContain("HttpOnly");
	});

	it("is Secure and SameSite=Lax", async () => {
		const header = await loginSetCookie();
		expect(header).toContain("Secure");
		expect(header).toContain("SameSite=Lax");
	});

	it("carries NO Domain attribute, so the cookie stays host-only", async () => {
		// ADR-12. Adding a Domain would widen it to every subdomain that will ever
		// exist, for no benefit. This is the mistake that looks like a fix.
		expect(await loginSetCookie()).not.toContain("Domain");
	});

	it("is not SameSite=None", async () => {
		// SameSite=Lax is doing the CSRF work, and it suffices only because ADR-12
		// keeps the UI and the API on the same registrable domain. Loosening this
		// makes CSRF tokens mandatory in the same commit.
		expect(await loginSetCookie()).not.toContain("SameSite=None");
	});

	it("carries the __Host- prefix, so a sibling subdomain cannot shadow it", async () => {
		// The prefix is a browser-enforced contract: Secure, Path=/, no Domain. It
		// closes session fixation from anything able to set cookies on the parent
		// domain, which a host-only cookie alone does NOT prevent -- the browser
		// does not report which host set a cookie it sends back.
		expect(await loginSetCookie()).toContain("__Host-fga_session=");
		expect(SESSION_COOKIE).toBe("__Host-fga_session");
	});

	it("expires with the token rather than on its own schedule", async () => {
		// One constant drives the JWT's `exp` and this `Max-Age`. A token that
		// outlives its cookie is the dangerous direction: the credential stays
		// valid after the browser stops presenting it.
		expect(await loginSetCookie()).toContain("Max-Age=2592000");
	});

	it("clears with attributes that match, or the deletion is a no-op", async () => {
		const header = (
			await SELF.fetch(`${BASE}/oauth/logout`, { method: "POST" })
		).headers.get("Set-Cookie");

		// A browser matches a deletion by name, path and domain. The logout route
		// used to spell its own attributes out and omitted HttpOnly entirely.
		expect(header).toContain("__Host-fga_session=");
		expect(header).toContain("Path=/");
		expect(header).toContain("Secure");
		expect(header).not.toContain("Domain");
	});
});
