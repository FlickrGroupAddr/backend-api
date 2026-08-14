import type { Context } from "hono";
import { deleteCookie, getCookie, setCookie } from "hono/cookie";
import type { CookieOptions } from "hono/utils/cookie";
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
 *
 * **One constant drives both the token's `exp` and the cookie's `Max-Age`.**
 * They were separate literals -- "30d" and 60*60*24*30 -- which is two places to
 * change and no way to notice. Drift there is not loud: a cookie outliving its
 * token logs people out early, and a token outliving its cookie is worse,
 * because the credential stays valid after the browser stops presenting it.
 */
const SESSION_LIFETIME_SECONDS = 60 * 60 * 24 * 30;

/**
 * The bare cookie name. On the wire it gains the `__Host-` prefix, so anything
 * matching against a raw header wants `SESSION_COOKIE` below.
 */
const SESSION_COOKIE_NAME = "fga_session";

/**
 * The name as the browser sees it.
 *
 * **The `__Host-` prefix is a contract the browser enforces**: it will refuse
 * this cookie unless it is `Secure`, has `Path=/`, and carries no `Domain`. The
 * attack it closes is session fixation from a neighbour -- without the prefix,
 * anything able to set cookies for the parent domain (a sibling subdomain, an
 * XSS anywhere under it, a stray CNAME) can plant `Domain=flickrgroupaddr.com;
 * fga_session=<attacker value>` that shadows ours, and the API cannot tell the
 * two apart because `Domain` is not sent back with a cookie.
 *
 * ADR-12 already required host-only, no `Domain`, `Path=/` and `Secure`, so this
 * costs nothing: it asks the browser to enforce what the code already intended.
 */
export const SESSION_COOKIE = `__Host-${SESSION_COOKIE_NAME}`;

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
		.setExpirationTime(`${SESSION_LIFETIME_SECONDS}s`)
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
 * The cookie attributes ADR-12 settles.
 *
 * `prefix: "host"` is what makes this real rather than aspirational. Hono
 * prepends `__Host-` and then forces `Path=/`, `Secure` and no `Domain`
 * AFTER spreading these options, so the three attributes the prefix depends on
 * cannot be broken from here even by a careless edit. That is the whole reason
 * to use the library's prefix support instead of writing `__Host-` into the
 * name by hand: hand-written, the name and the attributes are two facts that
 * must agree, and the browser silently drops the cookie when they stop
 * agreeing.
 *
 * `SameSite=Lax` is doing the CSRF work. It is sufficient because ADR-12 puts
 * the UI and the API on the same site -- flickrgroupaddr.com and
 * api.flickrgroupaddr.com share a registrable domain, and SameSite is about
 * site, not origin -- so the UI's authenticated calls still carry the cookie
 * while a genuine cross-site POST does not. **Moving the UI to a different
 * registrable domain would force `SameSite=None`, and CSRF tokens MUST land in
 * the same commit if that ever happens.**
 */
const SESSION_COOKIE_OPTIONS = {
	prefix: "host",
	httpOnly: true,
	secure: true,
	sameSite: "Lax",
	path: "/",
	maxAge: SESSION_LIFETIME_SECONDS,
} as const satisfies CookieOptions;

/** Issues the session cookie. Called once, after the Flickr callback succeeds. */
export function setSessionCookie(c: Context, token: string): void {
	setCookie(c, SESSION_COOKIE_NAME, token, SESSION_COOKIE_OPTIONS);
}

/**
 * The raw cookie value the browser sent, or undefined.
 *
 * The prefix MUST be passed here too -- `getCookie` looks for the prefixed name
 * only when told to, so a read that omits it silently finds nothing and every
 * request looks logged out.
 */
export function readSessionCookie(c: Context): string | undefined {
	return getCookie(c, SESSION_COOKIE_NAME, "host");
}

/**
 * Clears the session cookie.
 *
 * The attributes MUST match the ones it was set with, or the browser treats it
 * as a different cookie and the deletion silently does nothing.
 */
export function clearSessionCookie(c: Context): void {
	deleteCookie(c, SESSION_COOKIE_NAME, SESSION_COOKIE_OPTIONS);
}
