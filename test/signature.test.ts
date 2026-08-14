import { describe, expect, it } from "vitest";
import {
	baseStringUri,
	normalizeParameters,
	type Param,
	percentEncode,
	signatureBaseString,
	signHmacSha1,
	signingKey,
} from "../src/oauth/signature.js";

/**
 * RFC 5849's own worked example, section 3.4.1, reproduced exactly.
 *
 * **These exist because of ADR-14.** That decision permits hand-written code only where
 * the spec is short, exact, and covered by published vectors -- and then requires the
 * vectors to be used. This file is the payment for that exception.
 *
 * The signer is hand-written, so "Flickr accepted it" is not good enough -- a rejected
 * signature tells you nothing about which of the four layers was wrong. The RFC example
 * is well chosen: duplicate parameter names, an empty value, a space, and a value that
 * arrives already percent-encoded.
 */

const REQUEST_URL = new URL(
	"http://example.com/request?b5=%3D%253D&a3=a&c%40=&a2=r%20b",
);

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

describe("percentEncode", () => {
	it("leaves the unreserved set alone", () => {
		const unreserved =
			"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~";
		expect(percentEncode(unreserved)).toBe(unreserved);
	});

	// The five encodeURIComponent misses. This gap is the classic OAuth 1.0a bug.
	it.each([
		["!", "%21"],
		["'", "%27"],
		["(", "%28"],
		[")", "%29"],
		["*", "%2A"],
		["@", "%40"],
		["r b", "r%20b"],
		["é", "%C3%A9"],
	])("encodes %s as %s", (input, expected) => {
		expect(percentEncode(input)).toBe(expected);
	});
});

describe("baseStringUri", () => {
	it.each([
		[REQUEST_URL.href, "http://example.com/request"],
		["HTTP://EXAMPLE.com/Path?a=1", "http://example.com/Path"],
		["http://example.com:80/x", "http://example.com/x"],
		["https://example.com:443/x", "https://example.com/x"],
		["https://example.com:8443/x", "https://example.com:8443/x"],
	])("%s -> %s", (input, expected) => {
		expect(baseStringUri(new URL(input))).toBe(expected);
	});
});

describe("normalizeParameters", () => {
	const EXPECTED =
		"a2=r%20b&a3=2%20q&a3=a&b5=%3D%253D&c%40=&c2=" +
		"&oauth_consumer_key=9djdj82h48djs9d2&oauth_nonce=7d8f3e4a" +
		"&oauth_signature_method=HMAC-SHA1&oauth_timestamp=137131201" +
		"&oauth_token=kkk9d7dh3k39sjv7";

	it("reproduces the RFC string exactly", () => {
		expect(normalizeParameters(PARAMS)).toBe(EXPECTED);
	});

	it("is insensitive to collection order", () => {
		expect(normalizeParameters([...PARAMS].reverse())).toBe(EXPECTED);
	});

	it("sorts by byte value, so c%40 precedes c2", () => {
		// localeCompare would get this wrong: it treats punctuation as variable-weight.
		expect(
			normalizeParameters([
				["c2", ""],
				["c@", ""],
			]),
		).toBe("c%40=&c2=");
	});
});

describe("signatureBaseString", () => {
	it("reproduces the RFC string exactly", () => {
		// Note %25253D: b5's value was already encoded once in the query, collection
		// decoded it, encoding put it back, and the base string encoded the whole
		// normalized string again.
		expect(signatureBaseString("POST", REQUEST_URL, PARAMS)).toBe(
			"POST&http%3A%2F%2Fexample.com%2Frequest" +
				"&a2%3Dr%2520b%26a3%3D2%2520q%26a3%3Da%26b5%3D%253D%25253D" +
				"%26c%2540%3D%26c2%3D%26oauth_consumer_key%3D9djdj82h48djs9d2" +
				"%26oauth_nonce%3D7d8f3e4a%26oauth_signature_method%3DHMAC-SHA1" +
				"%26oauth_timestamp%3D137131201%26oauth_token%3Dkkk9d7dh3k39sjv7",
		);
	});

	it("uppercases the method", () => {
		expect(signatureBaseString("post", REQUEST_URL, PARAMS)).toBe(
			signatureBaseString("POST", REQUEST_URL, PARAMS),
		);
	});
});

describe("signingKey", () => {
	it("keeps the trailing ampersand with no token secret", () => {
		// The request-token call has none. Dropping it makes the key one byte short and
		// the signature fail for no visible reason.
		expect(signingKey("secret")).toBe("secret&");
	});

	it("encodes both halves", () => {
		expect(signingKey("a b", "c@d")).toBe("a%20b&c%40d");
	});
});

describe("signHmacSha1", () => {
	it.each([
		["base strinh", "consumer", "token"],
		["base string", "consumeR", "token"],
		["base string", "consumer", "toked"],
	])("changes when any input changes (%s, %s, %s)", async (base, cs, ts) => {
		expect(await signHmacSha1(base, cs, ts)).not.toBe(
			await signHmacSha1("base string", "consumer", "token"),
		);
	});

	/** **The load-bearing platform assumption.** HMAC-SHA1 is deprecated and a modern
	 *  runtime could reasonably decline to ship it. Without it every Flickr call is
	 *  unsignable and Cloudflare Workers is off the table for this project. */
	it("matches RFC 2202 test case 1, proving workerd implements HMAC-SHA1", async () => {
		const key = await crypto.subtle.importKey(
			"raw",
			new Uint8Array(20).fill(0x0b),
			{ name: "HMAC", hash: "SHA-1" },
			false,
			["sign"],
		);
		const raw = await crypto.subtle.sign(
			"HMAC",
			key,
			new TextEncoder().encode("Hi There"),
		);
		const hex = [...new Uint8Array(raw)]
			.map((b) => b.toString(16).padStart(2, "0"))
			.join("");
		expect(hex).toBe("b617318655057264e28bc0b6fb378c8ef146be00");
	});
});
