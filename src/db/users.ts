import { decryptToken, encryptToken } from "../crypto/tokens.js";

/**
 * The users table, per ADR-01 and ADR-03.
 *
 * Encryption lives here rather than at the call sites so there is exactly one
 * path by which a Flickr token reaches D1, and it is not possible to write one
 * in plaintext by forgetting a step.
 */

export interface FlickrTokens {
	readonly token: string;
	readonly tokenSecret: string;
}

/**
 * Records a successful login. Idempotent by NSID -- logging in again replaces
 * the stored credentials rather than creating a second row.
 *
 * Re-linking clears `needs_relink`: ADR-07 sets that flag when Flickr answers
 * 98 or 99, and a completed login is precisely the thing that resolves it.
 */
export async function upsertUser(
	db: D1Database,
	nsid: string,
	username: string,
	tokens: FlickrTokens,
	tokenKey: string,
): Promise<void> {
	const [encryptedToken, encryptedSecret] = await Promise.all([
		encryptToken(tokens.token, nsid, tokenKey),
		encryptToken(tokens.tokenSecret, nsid, tokenKey),
	]);

	const now = Date.now();

	await db
		.prepare(
			`INSERT INTO users
         (nsid, flickr_username, access_token_encrypted,
          access_token_secret_encrypted, needs_relink, created_at, updated_at)
       VALUES (?, ?, ?, ?, 0, ?, ?)
       ON CONFLICT (nsid) DO UPDATE SET
         flickr_username               = excluded.flickr_username,
         access_token_encrypted        = excluded.access_token_encrypted,
         access_token_secret_encrypted = excluded.access_token_secret_encrypted,
         needs_relink                  = 0,
         updated_at                    = excluded.updated_at`,
		)
		.bind(nsid, username, encryptedToken, encryptedSecret, now, now)
		.run();
}

/**
 * Returns a user's decrypted Flickr credentials, or null if there is no such
 * user.
 *
 * Decryption failure is NOT null -- it throws. A row that exists but cannot be
 * decrypted means the key is wrong or the ciphertext was tampered with, and
 * both are conditions the caller must not paper over by behaving as though the
 * user were merely absent.
 */
export async function getFlickrTokens(
	db: D1Database,
	nsid: string,
	tokenKey: string,
): Promise<FlickrTokens | null> {
	const row = await db
		.prepare(
			`SELECT access_token_encrypted, access_token_secret_encrypted
       FROM users WHERE nsid = ?`,
		)
		.bind(nsid)
		.first<{
			access_token_encrypted: ArrayBuffer;
			access_token_secret_encrypted: ArrayBuffer;
		}>();

	if (row === null) return null;

	const [token, tokenSecret] = await Promise.all([
		decryptToken(new Uint8Array(row.access_token_encrypted), nsid, tokenKey),
		decryptToken(
			new Uint8Array(row.access_token_secret_encrypted),
			nsid,
			tokenKey,
		),
	]);

	return { token, tokenSecret };
}

/**
 * A user's Flickr display name, or null if there is no such user.
 *
 * Separate from `getFlickrTokens` on purpose: this reads one column and does no
 * decryption, so a page that only wants a name never touches key material.
 *
 * **The value is controlled by Flickr, not by FGA.** Anything rendering it into
 * markup MUST escape it — see the landing page.
 */
export async function getUsername(
	db: D1Database,
	nsid: string,
): Promise<string | null> {
	const row = await db
		.prepare("SELECT flickr_username FROM users WHERE nsid = ?")
		.bind(nsid)
		.first<{ flickr_username: string | null }>();

	return row?.flickr_username ?? null;
}

/** ADR-07: Flickr answered 98 or 99, so the user must re-link before FGA can act. */
export async function markNeedsRelink(
	db: D1Database,
	nsid: string,
): Promise<void> {
	await db
		.prepare("UPDATE users SET needs_relink = 1, updated_at = ? WHERE nsid = ?")
		.bind(Date.now(), nsid)
		.run();
}
