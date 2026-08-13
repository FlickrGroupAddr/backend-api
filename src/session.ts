import { jwtVerify, SignJWT } from "jose";

/**
 * The session cookie, per ADR-06 and ADR-12.
 *
 * ADR-06 specifies an HMAC-SHA256-signed token carrying the NSID. This is that,
 * as a JWS with `HS256` -- which IS HMAC-SHA256, so the decision is unchanged.
 * ADR-14 moved it to `jose` rather than hand-writing it, because the hand-written
 * version is roughly forty lines in which every plausible bug is a security bug:
 * a non-constant-time comparison leaks the signature through timing, a missing
 * expiry check makes sessions immortal, and a missing algorithm check invites
 * algorithm confusion.
 *
 * The Flickr token MUST NOT appear here, or anywhere else the browser can see.
 */

const ISSUER = "fga";
const AUDIENCE = "fga-api";

/**
 * Thirty days. ADR-06 accepts that there is no instant revocation, so this
 * number is the real exposure window for a stolen cookie, and it is a deliberate
 * trade rather than a default: a photo tool people use occasionally is hostile
 * if it logs them out weekly, and the cookie grants no more than the ability to
 * queue that user's own photos. Shorten it here if that calculus ever changes;
 * nothing else needs to move.
 */
const SESSION_LIFETIME = "30d";

/** The name is short and unremarkable on purpose -- it advertises nothing. */
export const SESSION_COOKIE = "fga_session";

/**
 * ADR-03 keeps the session-signing key separate from the token-encryption key.
 * Passing the key in rather than reading a binding keeps this module pure and
 * makes the separation visible at every call site.
 */
function keyBytes(signingKey: string): Uint8Array {
	return new TextEncoder().encode(signingKey);
}

/** Mints the cookie value. Called once, after the Flickr callback succeeds. */
export async function mintSession(
	nsid: string,
	signingKey: string,
): Promise<string> {
	return await new SignJWT({})
		.setProtectedHeader({ alg: "HS256" })
		.setSubject(nsid)
		.setIssuer(ISSUER)
		.setAudience(AUDIENCE)
		.setIssuedAt()
		.setExpirationTime(SESSION_LIFETIME)
		.sign(keyBytes(signingKey));
}

/**
 * Returns the NSID a valid cookie carries, or null for any invalid one.
 *
 * Every failure -- tampered, expired, wrong key, wrong algorithm, malformed --
 * collapses to null deliberately. The caller's only correct response to any of
 * them is to treat the request as unauthenticated, and distinguishing them in a
 * response body tells an attacker which lever to pull next.
 */
export async function verifySession(
	token: string,
	signingKey: string,
): Promise<string | null> {
	try {
		const { payload } = await jwtVerify(token, keyBytes(signingKey), {
			// Pinning the algorithm is what closes algorithm confusion, where a
			// token declaring "alg":"none" or a different family is accepted because
			// the verifier trusted the header it was handed.
			algorithms: ["HS256"],
			issuer: ISSUER,
			audience: AUDIENCE,
		});

		return payload.sub ?? null;
	} catch {
		return null;
	}
}

/**
 * The cookie attributes ADR-12 settles, in one place so they cannot drift.
 *
 * No `Domain`: the cookie is minted by and returned to api.flickrgroupaddr.com
 * and never needs to reach the apex. Host-only is both the narrower and the
 * correct choice, and it is easy to get wrong in the safe-looking direction.
 */
export function sessionCookieAttributes(): string {
	return "HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=2592000";
}
