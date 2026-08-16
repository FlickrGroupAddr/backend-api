/**
 * The two codes a device link uses, and why there are two.
 *
 * | | Held by | Travels | Purpose |
 * |---|---|---|---|
 * | `code` | The plug-in, only | Never in a URL | Proves the poller started this flow |
 * | `userCode` | Shown on screen | Typed, or prefilled in a link | Lets a human match one screen to the other |
 *
 * **One code could not do both jobs.** A secret long enough to resist guessing
 * is too long to read off a screen and retype, and a string short enough to
 * retype is too short to be a bearer credential.
 */

const encoder = new TextEncoder();

/** 32 bytes, matching `src/session.ts`. */
const CODE_BYTES = 32;

/** Eight characters from a 32-symbol alphabet is about 1.1e12 combinations. */
const USER_CODE_LENGTH = 8;

/**
 * **Crockford base32 minus the ambiguous glyphs.** No `I`, `L`, `O` or `U`, and
 * no `0` or `1`. A person reads this off one screen and types it into another,
 * so a character pair that looks alike at a glance is a support problem rather
 * than a security one — and `U` is out because removing it removes most
 * accidental profanity.
 */
const ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ";

function toBase64Url(bytes: ArrayBuffer): string {
	return btoa(String.fromCharCode(...new Uint8Array(bytes)))
		.replace(/\+/g, "-")
		.replace(/\//g, "_")
		.replace(/=+$/, "");
}

/** The polling secret. */
export function newCode(): string {
	return toBase64Url(crypto.getRandomValues(new Uint8Array(CODE_BYTES)).buffer);
}

/**
 * The human-readable half.
 *
 * **Rejection sampling, not modulo.** `byte % 30` maps 256 bytes onto 30
 * symbols unevenly, so the first 16 letters would appear about 12% more often
 * than the rest. The bias is small and it is free to avoid.
 */
export function newUserCode(): string {
	const out: string[] = [];
	const limit = 256 - (256 % ALPHABET.length);
	while (out.length < USER_CODE_LENGTH) {
		for (const byte of crypto.getRandomValues(new Uint8Array(16))) {
			if (byte >= limit) continue;
			out.push(ALPHABET[byte % ALPHABET.length] as string);
			if (out.length === USER_CODE_LENGTH) break;
		}
	}
	return out.join("");
}

/**
 * **Only the hash is stored**, so a leak of the Durable Object's storage yields
 * no usable polling credential. Same reasoning as `src/session.ts` never
 * storing a session id.
 */
export async function codeHash(code: string): Promise<string> {
	return toBase64Url(
		await crypto.subtle.digest("SHA-256", encoder.encode(code)),
	);
}

/**
 * **Typing is forgiving; matching is not.** A person reading a code aloud or
 * off a screen will lower-case it and may add a space or a dash. Normalizing on
 * the way in costs nothing and removes the most common failed attempt.
 *
 * It does NOT map look-alike characters back — `0` to `O` and so on. The
 * alphabet excludes both members of every confusable pair, so a `0` in the
 * input is a genuine mistake rather than an ambiguity to resolve.
 */
export function normalizeUserCode(input: string): string {
	return input.toUpperCase().replace(/[^0-9A-Z]/g, "");
}

/** Shape only. A well-formed code still has to exist and still has to be live. */
export function looksLikeUserCode(input: string): boolean {
	if (input.length !== USER_CODE_LENGTH) return false;
	return [...input].every((character) => ALPHABET.includes(character));
}
