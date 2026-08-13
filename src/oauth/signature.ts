/**
 * OAuth 1.0a request signing, per RFC 5849.
 *
 * ADR-14 says take a dependency wherever one exists. This is the documented
 * exception: every OAuth 1.0a package on npm is unmaintained, Node-only, or
 * wraps an HTTP client we do not use, and the crypto underneath is native here.
 * The survey is in docs/architecture/DECISIONS.md.
 *
 * Because it is hand-written, it is held to a higher bar than "Flickr accepted
 * it": every function below is pure and is tested against the worked example in
 * RFC 5849 section 3.4.1. A signature Flickr rejects tells you nothing about
 * which of the four layers -- encoding, normalization, base string, or key
 * construction -- was actually wrong.
 */

/** A single OAuth or request parameter. Duplicates are legal and are preserved. */
export type Param = readonly [name: string, value: string];

/**
 * Percent-encoding per RFC 5849 section 3.6.
 *
 * Unreserved characters are ALPHA, DIGIT, "-", ".", "_", and "~". Everything
 * else is encoded, with uppercase hex digits.
 *
 * `encodeURIComponent` is close but not correct: it leaves `!`, `'`, `(`, `)`
 * and `*` alone, and all five are reserved here. That gap is the single most
 * common OAuth 1.0a bug, and it stays invisible until a value happens to
 * contain one of them.
 */
export function percentEncode(value: string): string {
	return encodeURIComponent(value).replace(
		/[!'()*]/g,
		(char) => `%${char.charCodeAt(0).toString(16).toUpperCase()}`,
	);
}

/**
 * The base string URI, per RFC 5849 section 3.4.1.2.
 *
 * Scheme and host lowercased, default ports omitted, query and fragment
 * dropped -- the query parameters are not lost, they travel through the
 * normalized parameter string instead.
 */
export function baseStringUri(url: URL): string {
	const scheme = url.protocol.slice(0, -1).toLowerCase();
	const host = url.hostname.toLowerCase();

	const isDefaultPort =
		url.port === "" ||
		(scheme === "http" && url.port === "80") ||
		(scheme === "https" && url.port === "443");

	return `${scheme}://${host}${isDefaultPort ? "" : `:${url.port}`}${url.pathname}`;
}

/**
 * Normalized parameter string, per RFC 5849 section 3.4.1.3.2.
 *
 * Both halves of every pair are encoded first, then pairs are sorted by encoded
 * name and -- for duplicate names -- by encoded value. Sorting before encoding
 * gives a different order for some inputs, which is why the order here is not
 * an implementation detail.
 */
export function normalizeParameters(params: readonly Param[]): string {
	return (
		params
			.map(
				([name, value]): Param => [percentEncode(name), percentEncode(value)],
			)
			// Ascending BYTE value, per the RFC -- not locale collation. Everything is
			// ASCII after encoding, so JavaScript's code-unit comparison is exactly
			// byte order. `localeCompare` would be wrong here: collation treats
			// punctuation as variable-weight, and `c%40` must sort before `c2`
			// because `%` is 0x25 and `2` is 0x32.
			.sort(([leftName, leftValue], [rightName, rightValue]) => {
				if (leftName !== rightName) return leftName < rightName ? -1 : 1;
				if (leftValue !== rightValue) return leftValue < rightValue ? -1 : 1;
				return 0;
			})
			.map(([name, value]) => `${name}=${value}`)
			.join("&")
	);
}

/**
 * The signature base string, per RFC 5849 section 3.4.1.1.
 *
 * Note the double encoding: the normalized parameter string is percent-encoded
 * as a whole after its own components were already encoded. That is correct and
 * is why the RFC's example contains sequences like `%25253D`.
 */
export function signatureBaseString(
	method: string,
	url: URL,
	params: readonly Param[],
): string {
	return [
		method.toUpperCase(),
		percentEncode(baseStringUri(url)),
		percentEncode(normalizeParameters(params)),
	].join("&");
}

/**
 * The signing key, per RFC 5849 section 3.4.2.
 *
 * The trailing "&" is present even when there is no token secret, which is the
 * case for the temporary-credentials request that opens a login. Omitting it
 * produces a key one byte short and a signature that fails for no visible
 * reason.
 */
export function signingKey(consumerSecret: string, tokenSecret = ""): string {
	return `${percentEncode(consumerSecret)}&${percentEncode(tokenSecret)}`;
}

/** HMAC-SHA1 over the base string, base64-encoded. RFC 5849 section 3.4.2. */
export async function signHmacSha1(
	baseString: string,
	consumerSecret: string,
	tokenSecret = "",
): Promise<string> {
	const encoder = new TextEncoder();

	const key = await crypto.subtle.importKey(
		"raw",
		encoder.encode(signingKey(consumerSecret, tokenSecret)),
		{ name: "HMAC", hash: "SHA-1" },
		false,
		["sign"],
	);

	const signature = await crypto.subtle.sign(
		"HMAC",
		key,
		encoder.encode(baseString),
	);

	return btoa(String.fromCharCode(...new Uint8Array(signature)));
}
