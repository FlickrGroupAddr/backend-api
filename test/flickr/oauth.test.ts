import { describe, expect, it } from "vitest";
import {
	authorizationHeader,
	buildAuthorizeUrl,
	parseFormResponse,
	protocolParams,
} from "../../src/flickr/oauth.js";
import type { Param } from "../../src/oauth/signature.js";

/**
 * The Flickr-specific assembly, tested without a network.
 *
 * Everything here is a pure function on purpose: the two calls that do reach
 * Flickr are thin wrappers over these, so the parts that can be wrong in silence
 * are the parts that can be checked offline.
 */

const CONSUMER_KEY = "consumer-key";
const CONSUMER_SECRET = "consumer-secret";

function fieldsOf(header: string): Map<string, string> {
	const fields = new Map<string, string>();
	for (const part of header.replace(/^OAuth /, "").split(", ")) {
		const [name, quoted] = part.split("=");
		if (name !== undefined && quoted !== undefined) {
			fields.set(name, decodeURIComponent(quoted.slice(1, -1)));
		}
	}
	return fields;
}

describe("protocolParams", () => {
	it("carries the five parameters every signed call needs", () => {
		const names = protocolParams(CONSUMER_KEY).map(([name]) => name);
		expect(names).toEqual([
			"oauth_consumer_key",
			"oauth_nonce",
			"oauth_signature_method",
			"oauth_timestamp",
			"oauth_version",
		]);
	});

	it("declares HMAC-SHA1 and version 1.0", () => {
		const params = new Map(protocolParams(CONSUMER_KEY));
		expect(params.get("oauth_signature_method")).toBe("HMAC-SHA1");
		expect(params.get("oauth_version")).toBe("1.0");
	});

	it("produces a fresh nonce every time", () => {
		// A predictable nonce lets an observer replay a captured request, which is
		// why this uses getRandomValues rather than Math.random.
		const nonces = new Set(
			Array.from({ length: 100 }, () => {
				const params = new Map(protocolParams(CONSUMER_KEY));
				return params.get("oauth_nonce");
			}),
		);
		expect(nonces.size).toBe(100);
	});

	it("uses a 128-bit nonce rendered as hex", () => {
		const params = new Map(protocolParams(CONSUMER_KEY));
		expect(params.get("oauth_nonce")).toMatch(/^[0-9a-f]{32}$/);
	});

	it("stamps a plausible unix timestamp in seconds", () => {
		const params = new Map(protocolParams(CONSUMER_KEY));
		const stamp = Number(params.get("oauth_timestamp"));
		expect(Math.abs(stamp - Math.floor(Date.now() / 1000))).toBeLessThan(5);
	});
});

describe("authorizationHeader", () => {
	const url = new URL("https://www.flickr.com/services/oauth/request_token");

	it("emits only oauth_ fields, plus the signature", async () => {
		const params: Param[] = [
			["oauth_consumer_key", CONSUMER_KEY],
			["oauth_nonce", "abc123"],
			["oauth_signature_method", "HMAC-SHA1"],
			["oauth_timestamp", "1770000000"],
			["oauth_version", "1.0"],
			// A non-protocol parameter. It must contribute to the signature but MUST
			// NOT appear in the header -- it travels in the query or body instead.
			["perms", "write"],
		];

		const fields = fieldsOf(
			await authorizationHeader("GET", url, params, CONSUMER_SECRET),
		);

		expect(fields.has("perms")).toBe(false);
		expect(fields.has("oauth_signature")).toBe(true);
		expect(fields.get("oauth_consumer_key")).toBe(CONSUMER_KEY);
	});

	it("changes the signature when a non-header parameter changes", async () => {
		// Proves the excluded parameter really is being signed. If `perms` were
		// dropped before signing rather than before rendering, these would match
		// and Flickr would reject the request for reasons nothing here explains.
		const base: Param[] = [
			["oauth_consumer_key", CONSUMER_KEY],
			["oauth_nonce", "abc123"],
			["oauth_signature_method", "HMAC-SHA1"],
			["oauth_timestamp", "1770000000"],
			["oauth_version", "1.0"],
		];

		const withWrite = await authorizationHeader(
			"GET",
			url,
			[...base, ["perms", "write"]],
			CONSUMER_SECRET,
		);
		const withRead = await authorizationHeader(
			"GET",
			url,
			[...base, ["perms", "read"]],
			CONSUMER_SECRET,
		);

		expect(fieldsOf(withWrite).get("oauth_signature")).not.toBe(
			fieldsOf(withRead).get("oauth_signature"),
		);
	});

	it("differs with and without a token secret", async () => {
		// The trailing "&" in the signing key is load-bearing. Leg 1 signs with an
		// empty token secret; leg 3 signs with the request token secret.
		const params: Param[] = [
			["oauth_consumer_key", CONSUMER_KEY],
			["oauth_nonce", "abc123"],
			["oauth_signature_method", "HMAC-SHA1"],
			["oauth_timestamp", "1770000000"],
			["oauth_version", "1.0"],
		];

		const leg1 = await authorizationHeader("GET", url, params, CONSUMER_SECRET);
		const leg3 = await authorizationHeader(
			"GET",
			url,
			params,
			CONSUMER_SECRET,
			"request-token-secret",
		);

		expect(fieldsOf(leg1).get("oauth_signature")).not.toBe(
			fieldsOf(leg3).get("oauth_signature"),
		);
	});

	it("percent-encodes values inside the quotes", async () => {
		const params: Param[] = [
			["oauth_consumer_key", CONSUMER_KEY],
			["oauth_nonce", "abc123"],
			["oauth_signature_method", "HMAC-SHA1"],
			["oauth_timestamp", "1770000000"],
			["oauth_version", "1.0"],
			["oauth_callback", "https://api.flickrgroupaddr.com/oauth/callback"],
		];

		const header = await authorizationHeader(
			"GET",
			url,
			params,
			CONSUMER_SECRET,
		);

		// The raw header must not contain an unencoded separator, or a parser
		// splitting on ", " walks straight off the end of the field.
		expect(header).toContain("oauth_callback=");
		expect(header).toContain("%3A%2F%2F");
	});
});

describe("buildAuthorizeUrl", () => {
	it("asks for write, the narrowest scope that can do the job", () => {
		// ADR-01: Flickr offers only read, write, or delete. There is no scope for
		// "add to groups" alone, and write grants far more than FGA uses.
		const url = new URL(buildAuthorizeUrl("request-token"));
		expect(url.searchParams.get("perms")).toBe("write");
		expect(url.searchParams.get("oauth_token")).toBe("request-token");
	});

	it("points at flickr.com over HTTPS", () => {
		const url = new URL(buildAuthorizeUrl("t"));
		expect(url.protocol).toBe("https:");
		expect(url.hostname).toBe("www.flickr.com");
	});

	it("never carries a secret", () => {
		// Leg 2 happens in the user's browser. Anything here is visible to them,
		// to their history, and to anything watching the address bar.
		const url = buildAuthorizeUrl("request-token");
		expect(url).not.toContain("secret");
	});
});

describe("parseFormResponse", () => {
	it("reads Flickr's form-encoded reply", () => {
		expect(
			parseFormResponse(
				"oauth_callback_confirmed=true&oauth_token=72157&oauth_token_secret=abc",
			),
		).toEqual({
			oauth_callback_confirmed: "true",
			oauth_token: "72157",
			oauth_token_secret: "abc",
		});
	});

	it("decodes percent escapes and plus-as-space", () => {
		// A hand-rolled split on & and = gets the plus wrong, and usernames
		// containing spaces are common.
		expect(parseFormResponse("username=Terry+Ott&nsid=123%40N00")).toEqual({
			username: "Terry Ott",
			nsid: "123@N00",
		});
	});

	it("returns an empty object for an empty body", () => {
		expect(parseFormResponse("")).toEqual({});
	});
});
