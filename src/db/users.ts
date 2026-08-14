import { decryptToken, encryptToken } from "../crypto/tokens.js";

/** ADR-01 and ADR-03. **Encryption lives here, not at the call sites**, so there is
 *  exactly one path by which a Flickr token reaches D1 and no way to write one in
 *  plaintext by forgetting a step. */

export interface FlickrTokens {
	readonly token: string;
	readonly tokenSecret: string;
}

/** Idempotent by NSID. Clearing `needs_relink` is the point of doing it on every login:
 *  ADR-07 sets that flag on code 98 or 99, and a completed login is what resolves it. */
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

/** Null means no such user. **Decryption failure is NOT null -- it throws.** A row that
 *  exists but will not decrypt means a wrong key or a tampered ciphertext, and neither
 *  may be papered over by behaving as though the user were merely absent. */
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

/** Separate from `getFlickrTokens` so a page that only wants a name never touches key
 *  material. **The value is controlled by Flickr, so anything rendering it MUST escape.** */
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

/** ADR-07: Flickr answered 98 or 99, so the stored token is dead until the user re-links. */
export async function markNeedsRelink(
	db: D1Database,
	nsid: string,
): Promise<void> {
	await db
		.prepare("UPDATE users SET needs_relink = 1, updated_at = ? WHERE nsid = ?")
		.bind(Date.now(), nsid)
		.run();
}
