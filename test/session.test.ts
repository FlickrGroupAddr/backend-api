import { describe, expect, it } from "vitest";
import {
	mintSession,
	SESSION_COOKIE,
	sessionCookieAttributes,
	verifySession,
} from "../src/session.js";

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

describe("cookie attributes, ADR-12", () => {
	const attributes = sessionCookieAttributes();

	it("is HttpOnly, so script cannot read the session", () => {
		expect(attributes).toContain("HttpOnly");
	});

	it("is Secure and SameSite=Lax", () => {
		expect(attributes).toContain("Secure");
		expect(attributes).toContain("SameSite=Lax");
	});

	it("carries NO Domain attribute, so the cookie stays host-only", () => {
		// ADR-12. Adding a Domain would widen it to every subdomain that will ever
		// exist, for no benefit. This is the mistake that looks like a fix.
		expect(attributes).not.toContain("Domain");
	});

	it("is not SameSite=None", () => {
		// SameSite=Lax is doing the CSRF work. Loosening it makes CSRF tokens
		// mandatory in the same commit.
		expect(attributes).not.toContain("SameSite=None");
	});

	it("names the cookie without advertising what it is", () => {
		expect(SESSION_COOKIE).toBe("fga_session");
	});
});
