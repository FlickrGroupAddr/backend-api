import type { Context } from "hono";
import { deleteCookie, getCookie, setCookie } from "hono/cookie";
import type { CookieOptions } from "hono/utils/cookie";
import { jwtVerify, SignJWT } from "jose";

/** The session cookie. ADR-06 and ADR-12. A JWS with HS256 IS HMAC-SHA256. */

const ISSUER = "fga";
const AUDIENCE = "fga-api";

/** Drives BOTH the token's `exp` and the cookie's `Max-Age`. Keep it one constant:
 *  a token outliving its cookie stays valid after the browser stops sending it. */
const SESSION_LIFETIME_SECONDS = 60 * 60 * 24 * 30;

const SESSION_COOKIE_NAME = "fga_session";

/** The name on the wire. The `__Host-` prefix is browser-enforced: without it, anything
 *  able to set cookies on the parent domain can plant a same-named cookie that shadows
 *  ours, and `Domain` is not sent back, so the API cannot tell them apart. */
export const SESSION_COOKIE = `__Host-${SESSION_COOKIE_NAME}`;

function keyBytes(signingKey: string): Uint8Array {
	return new TextEncoder().encode(signingKey);
}

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

/** Null for every invalid cookie. Distinguishing tampered from expired would tell an
 *  attacker which lever to pull. `algorithms` pinning closes algorithm confusion. */
export async function verifySession(
	token: string,
	signingKey: string,
): Promise<string | null> {
	try {
		const { payload } = await jwtVerify(token, keyBytes(signingKey), {
			algorithms: ["HS256"],
			issuer: ISSUER,
			audience: AUDIENCE,
		});

		return payload.sub ?? null;
	} catch {
		return null;
	}
}

/** `prefix: "host"` is why this is safe from a careless edit. Hono forces `Path=/`,
 *  `Secure` and no `Domain` AFTER spreading these options, so the three attributes the
 *  `__Host-` prefix requires cannot be broken from here.
 *
 *  `SameSite=Lax` is the CSRF control, and it works only because the UI and API share a
 *  registrable domain. Moving the UI elsewhere forces `SameSite=None`, and CSRF tokens
 *  MUST land in the same commit. */
const SESSION_COOKIE_OPTIONS = {
	prefix: "host",
	httpOnly: true,
	secure: true,
	sameSite: "Lax",
	path: "/",
	maxAge: SESSION_LIFETIME_SECONDS,
} as const satisfies CookieOptions;

export function setSessionCookie(c: Context, token: string): void {
	setCookie(c, SESSION_COOKIE_NAME, token, SESSION_COOKIE_OPTIONS);
}

/** The prefix MUST be passed here too. Omit it and every request looks logged out. */
export function readSessionCookie(c: Context): string | undefined {
	return getCookie(c, SESSION_COOKIE_NAME, "host");
}

/** Attributes MUST match the ones it was set with, or the browser treats it as a
 *  different cookie and the deletion silently does nothing. */
export function clearSessionCookie(c: Context): void {
	deleteCookie(c, SESSION_COOKIE_NAME, SESSION_COOKIE_OPTIONS);
}
