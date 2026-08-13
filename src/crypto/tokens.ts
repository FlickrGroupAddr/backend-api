/**
 * Encryption of per-user Flickr tokens at rest, per ADR-03.
 *
 * ADR-14's "is the platform already doing it?" test answers yes here: WebCrypto
 * does AES-GCM natively, so a crypto library would add bundle and supply-chain
 * surface while removing an audited implementation.
 *
 * The threat this addresses is narrow and worth stating so the protection is
 * not mistaken for more than it is: it protects the tokens if the D1 contents
 * leak without the Worker secret leaking too. It does nothing about a
 * compromised Worker, which by definition holds the key.
 */

/** AES-GCM's standard nonce length. 96 bits is the size the mode is built for. */
const IV_BYTES = 12;

/** AES-256. The key material must be exactly this long after base64 decoding. */
const KEY_BYTES = 32;

/**
 * Decodes the base64 key from the Worker secret.
 *
 * Requiring exactly 32 raw bytes rather than hashing whatever string arrives is
 * deliberate. Hashing accepts a weak passphrase silently and turns it into a
 * key-shaped thing; this refuses to start instead. Generate one with:
 *
 *   openssl rand -base64 32
 */
async function importKey(base64Key: string): Promise<CryptoKey> {
	let raw: Uint8Array;
	try {
		raw = Uint8Array.from(atob(base64Key), (char) => char.charCodeAt(0));
	} catch {
		throw new Error("Token key is not valid base64");
	}

	if (raw.length !== KEY_BYTES) {
		throw new Error(
			`Token key must decode to ${KEY_BYTES} bytes, got ${raw.length}`,
		);
	}

	return await crypto.subtle.importKey("raw", raw, { name: "AES-GCM" }, false, [
		"encrypt",
		"decrypt",
	]);
}

/**
 * The NSID is bound into the ciphertext as additional authenticated data.
 *
 * It is not secret -- it is the row's own primary key. Binding it means a token
 * blob only decrypts in the row it belongs to, so moving one user's ciphertext
 * into another user's row fails authentication rather than silently granting
 * the wrong person's Flickr access. Costs nothing and closes a real hole for
 * anyone who gains write access to D1 but not the key.
 */
function aad(nsid: string): Uint8Array {
	return new TextEncoder().encode(nsid);
}

/**
 * Encrypts one token value. The 12-byte IV is prepended to the ciphertext, so a
 * value and the nonce that decrypts it cannot be separated by accident.
 *
 * A fresh random IV per call is required, not merely advisable: reusing a nonce
 * under the same key breaks AES-GCM catastrophically, leaking the keystream and
 * ultimately the authentication key.
 */
export async function encryptToken(
	plaintext: string,
	nsid: string,
	base64Key: string,
): Promise<Uint8Array> {
	const key = await importKey(base64Key);
	const iv = crypto.getRandomValues(new Uint8Array(IV_BYTES));

	const ciphertext = await crypto.subtle.encrypt(
		{ name: "AES-GCM", iv, additionalData: aad(nsid) },
		key,
		new TextEncoder().encode(plaintext),
	);

	const packed = new Uint8Array(IV_BYTES + ciphertext.byteLength);
	packed.set(iv, 0);
	packed.set(new Uint8Array(ciphertext), IV_BYTES);
	return packed;
}

/**
 * Decrypts one token value.
 *
 * Throws on any failure -- wrong key, wrong NSID, truncated input, tampered
 * ciphertext. There is deliberately no null-returning variant: a caller that
 * cannot decrypt a token cannot act for that user, and swallowing the failure
 * would turn a detected tamper into a confusing downstream error.
 */
export async function decryptToken(
	packed: Uint8Array,
	nsid: string,
	base64Key: string,
): Promise<string> {
	if (packed.length <= IV_BYTES) {
		throw new Error("Ciphertext is too short to contain an IV and a payload");
	}

	const key = await importKey(base64Key);
	const iv = packed.subarray(0, IV_BYTES);
	const ciphertext = packed.subarray(IV_BYTES);

	const plaintext = await crypto.subtle.decrypt(
		{ name: "AES-GCM", iv, additionalData: aad(nsid) },
		key,
		ciphertext,
	);

	return new TextDecoder().decode(plaintext);
}
