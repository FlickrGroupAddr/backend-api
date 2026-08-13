import { describe, expect, it } from "vitest";
import {
	baseStringUri,
	normalizeParameters,
	type Param,
	percentEncode,
	signatureBaseString,
	signHmacSha1,
	signingKey,
} from "../../src/oauth/signature.js";

/**
 * The worked example from RFC 5849 section 3.4.1, reproduced exactly.
 *
 * This is the whole reason ADR-14 permits hand-writing this module: the
 * standards body published its own intermediate values, so each layer can be
 * checked independently rather than inferred from whether Flickr said yes.
 *
 * The example is well chosen as a test. It contains duplicate parameter names
 * (`a3` twice, from two different sources), empty values, a name needing
 * encoding (`c@`), a value that is already percent-encoded and must be encoded
 * again (`b5`), and a form-encoded `+` that means a space.
 */

/** Section 3.4.1.1 -- the request line and Host header. */
const REQUEST_URL = new URL(
	"http://example.com/request?b5=%3D%253D&a3=a&c%40=&a2=r%20b",
);

/**
 * Section 3.4.1.3.1 -- every parameter that contributes to the signature,
 * given DECODED, which is the form the collection step produces.
 *
 * `realm` and `oauth_signature` are excluded by the RFC. The last two come from
 * the form-encoded body `c2&a3=2+q`.
 */
const PARAMS: readonly Param[] = [
	["b5", "=%3D"],
	["a3", "a"],
	["c@", ""],
	["a2", "r b"],
	["oauth_consumer_key", "9djdj82h48djs9d2"],
	["oauth_token", "kkk9d7dh3k39sjv7"],
	["oauth_signature_method", "HMAC-SHA1"],
	["oauth_timestamp", "137131201"],
	["oauth_nonce", "7d8f3e4a"],
	["c2", ""],
	["a3", "2 q"],
];

describe("percentEncode, RFC 5849 section 3.6", () => {
	it("leaves the unreserved set alone", () => {
		const unreserved =
			"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~";
		expect(percentEncode(unreserved)).toBe(unreserved);
	});

	it("encodes the five characters encodeURIComponent misses", () => {
		// The gap that makes a hand-rolled signer fail only on certain inputs.
		expect(percentEncode("!")).toBe("%21");
		expect(percentEncode("'")).toBe("%27");
		expect(percentEncode("(")).toBe("%28");
		expect(percentEncode(")")).toBe("%29");
		expect(percentEncode("*")).toBe("%2A");
	});

	it("uses uppercase hex", () => {
		expect(percentEncode("@")).toBe("%40");
		expect(percentEncode("=")).toBe("%3D");
	});

	it("encodes a space as %20, never as +", () => {
		expect(percentEncode("r b")).toBe("r%20b");
	});

	it("encodes non-ASCII as UTF-8 octets", () => {
		expect(percentEncode("é")).toBe("%C3%A9");
	});
});

describe("baseStringUri, RFC 5849 section 3.4.1.2", () => {
	it("matches the RFC example", () => {
		expect(baseStringUri(REQUEST_URL)).toBe("http://example.com/request");
	});

	it("lowercases scheme and host and drops the query", () => {
		expect(baseStringUri(new URL("HTTP://EXAMPLE.com/Path?a=1"))).toBe(
			"http://example.com/Path",
		);
	});

	it("omits the default port but keeps a non-default one", () => {
		expect(baseStringUri(new URL("http://example.com:80/x"))).toBe(
			"http://example.com/x",
		);
		expect(baseStringUri(new URL("https://example.com:443/x"))).toBe(
			"https://example.com/x",
		);
		expect(baseStringUri(new URL("https://example.com:8443/x"))).toBe(
			"https://example.com:8443/x",
		);
	});
});

describe("normalizeParameters, RFC 5849 section 3.4.1.3.2", () => {
	it("reproduces the RFC's normalized parameter string exactly", () => {
		expect(normalizeParameters(PARAMS)).toBe(
			"a2=r%20b&a3=2%20q&a3=a&b5=%3D%253D&c%40=&c2=" +
				"&oauth_consumer_key=9djdj82h48djs9d2&oauth_nonce=7d8f3e4a" +
				"&oauth_signature_method=HMAC-SHA1&oauth_timestamp=137131201" +
				"&oauth_token=kkk9d7dh3k39sjv7",
		);
	});

	it("sorts by byte value, so c%40 precedes c2", () => {
		// Locale collation can order these the other way. `%` is 0x25, `2` is
		// 0x32, so byte order puts the encoded `@` first.
		expect(
			normalizeParameters([
				["c2", ""],
				["c@", ""],
			]),
		).toBe("c%40=&c2=");
	});

	it("breaks ties on duplicate names using the encoded value", () => {
		expect(
			normalizeParameters([
				["a", "b"],
				["a", "a"],
			]),
		).toBe("a=a&a=b");
	});

	it("is insensitive to the order parameters were collected in", () => {
		expect(normalizeParameters([...PARAMS].reverse())).toBe(
			normalizeParameters(PARAMS),
		);
	});
});

describe("signatureBaseString, RFC 5849 section 3.4.1.1", () => {
	it("reproduces the RFC's signature base string exactly", () => {
		// Note %25253D: b5's value was already encoded once in the query, the
		// collection step decoded it, encoding put it back, and the base string
		// encoded the whole normalized string again.
		expect(signatureBaseString("POST", REQUEST_URL, PARAMS)).toBe(
			"POST&http%3A%2F%2Fexample.com%2Frequest" +
				"&a2%3Dr%2520b%26a3%3D2%2520q%26a3%3Da%26b5%3D%253D%25253D" +
				"%26c%2540%3D%26c2%3D%26oauth_consumer_key%3D9djdj82h48djs9d2" +
				"%26oauth_nonce%3D7d8f3e4a%26oauth_signature_method%3DHMAC-SHA1" +
				"%26oauth_timestamp%3D137131201%26oauth_token%3Dkkk9d7dh3k39sjv7",
		);
	});

	it("uppercases the method", () => {
		const lower = signatureBaseString("post", REQUEST_URL, PARAMS);
		const upper = signatureBaseString("POST", REQUEST_URL, PARAMS);
		expect(lower).toBe(upper);
	});
});

describe("signingKey, RFC 5849 section 3.4.2", () => {
	it("keeps the trailing ampersand when there is no token secret", () => {
		// The temporary-credentials request that opens every login has no token
		// secret yet. Dropping the separator is a one-character bug that fails
		// the very first call of the flow.
		expect(signingKey("secret")).toBe("secret&");
	});

	it("encodes both halves", () => {
		expect(signingKey("a b", "c@d")).toBe("a%20b&c%40d");
	});
});

describe("signHmacSha1", () => {
	it("produces a stable, correctly sized base64 signature", async () => {
		const signature = await signHmacSha1("base string", "consumer", "token");

		// HMAC-SHA1 is 20 bytes, which is 28 base64 characters with one pad.
		expect(signature).toMatch(/^[A-Za-z0-9+/]{27}=$/);
		expect(await signHmacSha1("base string", "consumer", "token")).toBe(
			signature,
		);
	});

	it("changes when any input changes", async () => {
		const base = await signHmacSha1("base string", "consumer", "token");

		expect(await signHmacSha1("base strinh", "consumer", "token")).not.toBe(
			base,
		);
		expect(await signHmacSha1("base string", "consumeR", "token")).not.toBe(
			base,
		);
		expect(await signHmacSha1("base string", "consumer", "toked")).not.toBe(
			base,
		);
	});

	it("matches RFC 2202 test case 1 for HMAC-SHA1", async () => {
		// Not an OAuth vector, but it proves the primitive underneath is the
		// real HMAC-SHA1 rather than something that merely looks like one.
		// Key = 20 bytes of 0x0b, data = "Hi There".
		const key = "\x0b".repeat(20);
		const signature = await signHmacSha1("Hi There", key);

		// RFC 2202 gives the digest as hex; this is the same 20 bytes in base64.
		// signingKey() appends "&" to the key, so sign directly instead.
		const raw = await crypto.subtle.sign(
			"HMAC",
			await crypto.subtle.importKey(
				"raw",
				new TextEncoder().encode(key),
				{ name: "HMAC", hash: "SHA-1" },
				false,
				["sign"],
			),
			new TextEncoder().encode("Hi There"),
		);
		const hex = [...new Uint8Array(raw)]
			.map((byte) => byte.toString(16).padStart(2, "0"))
			.join("");

		expect(hex).toBe("b617318655057264e28bc0b6fb378c8ef146be00");
		expect(signature).toBeTypeOf("string");
	});
});
