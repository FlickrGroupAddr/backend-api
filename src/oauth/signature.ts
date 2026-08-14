/**
 * OAuth 1.0a signing, RFC 5849. ADR-14's documented exception -- every package on npm is
 * unmaintained, Node-only, or wraps an HTTP client this project does not use.
 *
 * **Because it is hand-written it is held above "Flickr accepted it".** Every function
 * here is pure and tested against the RFC's own worked example. A signature Flickr
 * rejects tells you nothing about which of the four layers was wrong.
 */

/** Duplicates are legal and preserved. */
export type Param = readonly [name: string, value: string];

/** **`encodeURIComponent` is close and wrong.** It leaves `!`, `'`, `(`, `)` and `*`
 *  alone, and all five are reserved here. That gap is the classic OAuth 1.0a bug, and it
 *  stays invisible until a value happens to contain one. */
export function percentEncode(value: string): string {
	return encodeURIComponent(value).replace(
		/[!'()*]/g,
		(char) => `%${char.charCodeAt(0).toString(16).toUpperCase()}`,
	);
}

/** Query and fragment are dropped here, not lost -- they travel through the normalized
 *  parameter string instead. */
export function baseStringUri(url: URL): string {
	const scheme = url.protocol.slice(0, -1).toLowerCase();
	const host = url.hostname.toLowerCase();

	const isDefaultPort =
		url.port === "" ||
		(scheme === "http" && url.port === "80") ||
		(scheme === "https" && url.port === "443");

	return `${scheme}://${host}${isDefaultPort ? "" : `:${url.port}`}${url.pathname}`;
}

/** **Encode first, then sort.** Sorting before encoding gives a different order for some
 *  inputs, so this order is specification, not style. */
export function normalizeParameters(params: readonly Param[]): string {
	return (
		params
			.map(
				([name, value]): Param => [percentEncode(name), percentEncode(value)],
			)
			// Ascending BYTE value per the RFC, which is what JavaScript's code-unit
			// comparison already is on ASCII. `localeCompare` would be wrong: collation
			// treats punctuation as variable-weight, and `c%40` MUST precede `c2`.
			.sort(([leftName, leftValue], [rightName, rightValue]) => {
				if (leftName !== rightName) return leftName < rightName ? -1 : 1;
				if (leftValue !== rightValue) return leftValue < rightValue ? -1 : 1;
				return 0;
			})
			.map(([name, value]) => `${name}=${value}`)
			.join("&")
	);
}

/** The double encoding is correct: the normalized string is encoded again as a whole,
 *  which is why the RFC's own example contains sequences like `%25253D`. */
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

/** **The trailing `&` stays even with no token secret**, which is the case for the
 *  request-token call. Omitting it makes a key one byte short and a signature that fails
 *  for no visible reason. */
export function signingKey(consumerSecret: string, tokenSecret = ""): string {
	return `${percentEncode(consumerSecret)}&${percentEncode(tokenSecret)}`;
}

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
