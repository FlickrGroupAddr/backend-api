import type { Context } from "hono";
import { deleteCookie, getCookie, setCookie } from "hono/cookie";
import type { CookieOptions } from "hono/utils/cookie";

/**
 * The session cookie: an OPAQUE, signed, revocable handle. ADR-11 for the cookie
 * attributes; this file replaces ADR-10's stateless JWS.
 *
 * **Cookie value is `<id>.<hmac>`**, and neither half says anything about the user.
 * The old value was a JWS whose payload anyone holding the cookie could decode --
 * `sub` was the Flickr NSID in plaintext.
 *
 * **THE ADVERSARY IS WHATEVER STEALS THE COOKIE JAR, never the user.** They already
 * know their own NSID. This defends against an infostealer reading the browser's
 * cookie database off disk, a synced profile, or a backup. `HttpOnly` does not help
 * there -- it stops JavaScript, not a native process opening the store directly.
 *
 * **The win is that a session is revocable and an NSID is not.** A thief now holds a
 * bearer token that dies at logout, at expiry, or on demand. They no longer also hold
 * a permanent identifier tying the loot to a real Flickr account.
 *
 * **VERIFY IN THIS ORDER: HMAC first, then the database.** An attacker spraying
 * random cookies is rejected on CPU alone and never costs a D1 read.
 *
 * **Rotating `SESSION_KEY` invalidates every live session**, because the HMAC is
 * checked under the current key. That is the temporal blast-radius control, and it
 * needs no schema support. A keyring accepting the previous key would make rotation
 * graceful rather than abrupt -- see `docs/architecture/KEY-ROTATION-NOTES.md`.
 */

/** Drives BOTH the row's `expires_at` and the cookie's `Max-Age`. Keep it one
 *  constant: a row outliving its cookie is a session the browser stops sending and
 *  the database keeps honoring. */
const SESSION_LIFETIME_SECONDS = 60 * 60 * 24 * 30;

const SESSION_COOKIE_NAME = "fga_session";

/** The name on the wire. The `__Host-` prefix is browser-enforced: without it, anything
 *  able to set cookies on the parent domain can plant a same-named cookie that shadows
 *  ours, and `Domain` is not sent back, so the API cannot tell them apart. */
export const SESSION_COOKIE = `__Host-${SESSION_COOKIE_NAME}`;

/** 256 bits. `KEY-ROTATION-NOTES.md` records that 122 would have been overwhelmingly
 *  sufficient and that the extra costs about 100 nanoseconds, because 16 and 32 bytes
 *  both fit in one SHA-256 compression block. */
const ID_BYTES = 32;

const encoder = new TextEncoder();

/** Base64url, unpadded. The cookie value must survive a `Set-Cookie` header without
 *  quoting, so `+`, `/` and `=` are all out. */
function toBase64Url(bytes: ArrayBuffer | Uint8Array): string {
	const view = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
	let binary = "";
	for (const byte of view) binary += String.fromCharCode(byte);
	return btoa(binary)
		.replace(/\+/g, "-")
		.replace(/\//g, "_")
		.replace(/=+$/, "");
}

async function hmacKey(signingKey: string): Promise<CryptoKey> {
	return await crypto.subtle.importKey(
		"raw",
		encoder.encode(signingKey),
		{ name: "HMAC", hash: "SHA-256" },
		false,
		["sign"],
	);
}

async function sign(id: string, signingKey: string): Promise<string> {
	const mac = await crypto.subtle.sign(
		"HMAC",
		await hmacKey(signingKey),
		encoder.encode(id),
	);
	return toBase64Url(mac);
}

/** What goes in the database. The id itself is never stored, so a D1 leak yields
 *  hashes rather than usable bearer tokens -- the same reasoning as never storing a
 *  password. */
async function idHash(id: string): Promise<string> {
	return toBase64Url(await crypto.subtle.digest("SHA-256", encoder.encode(id)));
}

/**
 * Mints a session and records it. Returns the cookie value.
 *
 * **The row is written BEFORE the cookie reaches the user.** A cookie whose row failed
 * to persist is a session that can never authenticate, and it would fail somewhere
 * unrelated and much later.
 */
/**
 * The two credential classes, sharing one mechanism.
 *
 * **A separate table for plug-in tokens was the obvious alternative and it is the wrong
 * one.** It means a second minting path and a second verification path, and this file's
 * own history is the argument: the cookie's attributes were once duplicated and one copy
 * had silently lost `HttpOnly`. **Policy differs; mechanism MUST NOT.**
 */
export type SessionKind = "browser" | "plugin";

/**
 * A plug-in cannot ask its user to sign in again every day, and a browser can.
 *
 * **The plug-in's longer life is bought with a narrower reach, not given away.** See
 * `requireBrowserSession` -- a plug-in token is refused anywhere it could revoke another
 * credential or change the account, so a stolen laptop cannot lock the owner out.
 */
const LIFETIME_SECONDS: Record<SessionKind, number> = {
	browser: SESSION_LIFETIME_SECONDS,
	plugin: 90 * 24 * 60 * 60,
};

export async function mintSession(
	db: D1Database,
	nsid: string,
	signingKey: string,
	kind: SessionKind = "browser",
): Promise<string> {
	const id = toBase64Url(crypto.getRandomValues(new Uint8Array(ID_BYTES)));
	const now = Date.now();

	await db
		.prepare(
			`INSERT INTO sessions (id_hash, nsid, created_at, expires_at, kind)
       VALUES (?, ?, ?, ?, ?)`,
		)
		.bind(
			await idHash(id),
			nsid,
			now,
			now + LIFETIME_SECONDS[kind] * 1000,
			kind,
		)
		.run();

	return `${id}.${await sign(id, signingKey)}`;
}

/**
 * Null for every invalid cookie. **Distinguishing tampered from expired from unknown
 * would tell an attacker which lever to pull.**
 *
 * **`timingSafeEqual` is used rather than `===`.** Comparing MACs with string equality
 * leaks their contents through timing, one byte at a time. Cloudflare's runtime
 * provides it -- probed, not assumed.
 */
export type VerifiedSession = {
	readonly nsid: string;
	readonly kind: SessionKind;
};

export async function verifySession(
	db: D1Database,
	token: string,
	signingKey: string,
): Promise<VerifiedSession | null> {
	const separator = token.indexOf(".");
	if (separator <= 0) return null;

	const id = token.slice(0, separator);
	const presented = token.slice(separator + 1);

	const expected = await sign(id, signingKey);

	// Length differs -> not our MAC, and `timingSafeEqual` throws on mismatched sizes.
	if (presented.length !== expected.length) return null;
	if (
		!crypto.subtle.timingSafeEqual(
			encoder.encode(presented),
			encoder.encode(expected),
		)
	) {
		return null;
	}

	// Only now does a database read happen. A forger never gets this far.
	const row = await db
		.prepare("SELECT nsid, expires_at, kind FROM sessions WHERE id_hash = ?")
		.bind(await idHash(id))
		.first<{ nsid: string; expires_at: number; kind: string }>();

	if (row === null) return null;

	// Checked on the row already fetched, so an unswept table stays correct.
	if (row.expires_at <= Date.now()) return null;

	/**
	 * **The kind comes from the ROW, never from the caller.** A column read is the only
	 * honest source: the token itself carries nothing, deliberately, so there is no
	 * self-reported claim here to be wrong about or to forge.
	 */
	return {
		nsid: row.nsid,
		kind: row.kind === "plugin" ? "plugin" : "browser",
	};
}

/** Logout, and the reason this file exists. **Deleting the row is what ADR-10 could
 *  not do** -- a stateless token stayed valid until it expired, whoever held it. */
export async function revokeSession(
	db: D1Database,
	token: string,
): Promise<void> {
	const separator = token.indexOf(".");
	if (separator <= 0) return;

	// No signature check: this only ever DELETES, and the id is unguessable. Requiring a
	// valid MAC would mean a user whose key just rotated could not log out.
	await db
		.prepare("DELETE FROM sessions WHERE id_hash = ?")
		.bind(await idHash(token.slice(0, separator)))
		.run();
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
