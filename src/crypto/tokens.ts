/**
 * ADR-09. AES-GCM at rest for Flickr tokens.
 *
 * **Scope of the protection:** it covers a D1 leak that does not also leak the Worker
 * secret. It does nothing about a compromised Worker, which holds the key by definition.
 */

const IV_BYTES = 12;
const KEY_BYTES = 32;

/** Requires exactly 32 raw bytes rather than hashing whatever arrives. Hashing accepts a
 *  weak passphrase silently; this refuses to start. Generate: `openssl rand -base64 32`. */
async function importKey(base64Key: string): Promise<CryptoKey> {
	let raw: Uint8Array;
	try {
		raw = Uint8Array.from(atob(base64Key), (char) => char.charCodeAt(0));
	} catch (error) {
		throw new Error("Token key is not valid base64", { cause: error });
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

/** The NSID is the row's own primary key, not a secret. Binding it as additional
 *  authenticated data means a blob only decrypts in the row it belongs to, so moving one
 *  user's ciphertext into another's row fails instead of granting the wrong access. */
function aad(nsid: string): Uint8Array {
	return new TextEncoder().encode(nsid);
}

/** The IV is prepended, so a value and the nonce that decrypts it cannot be separated.
 *  **A fresh random IV per call is required, not advisable:** reusing a nonce under one
 *  key breaks AES-GCM catastrophically and leaks the authentication key. */
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

/** Throws on every failure, and there is deliberately no null-returning variant: a caller
 *  that cannot decrypt cannot act for that user, and swallowing it turns a detected
 *  tamper into a confusing error somewhere else. */
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
