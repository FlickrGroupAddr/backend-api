import { env, runInDurableObject, SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import {
	authorizationHeader,
	buildAuthorizeUrl,
	parseFormResponse,
	protocolParams,
} from "../src/flickr/oauth.js";
import { safeReturnPath } from "../src/oauth/return-to.js";
import type { Param } from "../src/oauth/signature.js";

/** The Flickr login: parameter assembly, and ADR-08's single-use secret store. */

const URL_UNDER_TEST = new URL(
	"https://www.flickr.com/services/oauth/request_token",
);

describe("protocolParams", () => {
	it("carries the five parameters every signed call needs", () => {
		const names = protocolParams("ck").map(([name]) => name);
		expect(names).toEqual([
			"oauth_consumer_key",
			"oauth_nonce",
			"oauth_signature_method",
			"oauth_timestamp",
			"oauth_version",
		]);
	});

	it("declares HMAC-SHA1 and version 1.0", () => {
		const params = new Map(protocolParams("ck"));
		expect(params.get("oauth_signature_method")).toBe("HMAC-SHA1");
		expect(params.get("oauth_version")).toBe("1.0");
	});

	it("produces a fresh 128-bit nonce every time", () => {
		// A predictable nonce lets an observer replay a captured request.
		const nonce = () => new Map(protocolParams("ck")).get("oauth_nonce") ?? "";
		expect(nonce()).toHaveLength(32);
		expect(nonce()).not.toBe(nonce());
	});
});

describe("authorizationHeader", () => {
	const base: Param[] = [
		["oauth_consumer_key", "ck"],
		["oauth_nonce", "n"],
		["oauth_signature_method", "HMAC-SHA1"],
		["oauth_timestamp", "1"],
		["oauth_version", "1.0"],
	];

	it("emits only oauth_ fields, plus the signature", async () => {
		const header = await authorizationHeader(
			"POST",
			URL_UNDER_TEST,
			[...base, ["method", "flickr.test.echo"]],
			"cs",
		);
		expect(header).toMatch(/^OAuth /);
		// Anchored to a field boundary: a loose /method=/ matches
		// oauth_signature_method and passes for the wrong reason.
		expect(header).not.toMatch(/(?:^OAuth |, )method="/);
		expect(header).toMatch(/oauth_signature="/);
	});

	it("changes the signature when a NON-header parameter changes", async () => {
		// Body parameters are signed even though they never appear in the header.
		// Omitting them yields a signature Flickr rejects without saying why.
		const sign = async (method: string) =>
			await authorizationHeader(
				"POST",
				URL_UNDER_TEST,
				[...base, ["method", method]],
				"cs",
			);
		expect(await sign("a")).not.toBe(await sign("b"));
	});

	it("differs with and without a token secret", async () => {
		expect(
			await authorizationHeader("POST", URL_UNDER_TEST, base, "cs"),
		).not.toBe(
			await authorizationHeader("POST", URL_UNDER_TEST, base, "cs", "ts"),
		);
	});
});

describe("buildAuthorizeUrl", () => {
	it("asks for write over HTTPS and carries no secret", () => {
		const url = new URL(buildAuthorizeUrl("request-token"));
		expect(url.protocol).toBe("https:");
		expect(url.host).toBe("www.flickr.com");
		// ADR-07: write is the narrowest scope Flickr offers that can do the job.
		expect(url.searchParams.get("perms")).toBe("write");
		expect(url.search).not.toMatch(/secret/i);
	});
});

describe("parseFormResponse", () => {
	it.each([
		["a=1&b=2", { a: "1", b: "2" }],
		["a=r%20b", { a: "r b" }],
		["a=r+b", { a: "r b" }],
		["", {}],
	])("parses %s", (body, expected) => {
		expect(parseFormResponse(body)).toEqual(expected);
	});
});

describe("the login attempt, ADR-08", () => {
	function stub(token: string) {
		return env.OAUTH_LOGIN.get(env.OAUTH_LOGIN.idFromName(token));
	}

	it("returns the secret exactly once", async () => {
		const s = stub("tok-once");
		await s.start("tok-once", "the-secret");
		expect(await s.consume("tok-once")).toEqual({
			requestTokenSecret: "the-secret",
		});
		// A replayed callback MUST find nothing.
		expect(await s.consume("tok-once")).toBeNull();
	});

	it("returns null for an attempt that was never started", async () => {
		expect(await stub("tok-unknown").consume("tok-unknown")).toBeNull();
	});

	it("refuses a mismatched token WITHOUT destroying the attempt", async () => {
		const s = stub("tok-keep");
		await s.start("tok-keep", "the-secret");
		expect(await s.consume("wrong-token")).toBeNull();
		expect(await s.consume("tok-keep")).toEqual({
			requestTokenSecret: "the-secret",
		});
	});

	it("arms a cleanup alarm as part of starting, and the alarm erases everything", async () => {
		const id = env.OAUTH_LOGIN.idFromName("tok-alarm");
		const s = env.OAUTH_LOGIN.get(id);
		await s.start("tok-alarm", "the-secret");

		await runInDurableObject(s, async (_instance, state) => {
			expect(await state.storage.getAlarm()).not.toBeNull();
		});

		await runInDurableObject(s, async (instance, state) => {
			await (instance as { alarm(): Promise<void> }).alarm();
			expect(await state.storage.get("attempt")).toBeUndefined();
		});
	});

	it("gives concurrent logins separate objects", () => {
		expect(env.OAUTH_LOGIN.idFromName("a").toString()).not.toBe(
			env.OAUTH_LOGIN.idFromName("b").toString(),
		);
	});
});

it("sends a login to Flickr carrying a request token", async () => {
	const response = await SELF.fetch(
		"https://api.flickrgroupaddr.com/oauth/login",
		{ redirect: "manual" },
	);
	expect(response.status).toBe(302);
	const location = new URL(response.headers.get("Location") ?? "");
	expect(location.host).toBe("www.flickr.com");
	expect(location.searchParams.get("oauth_token")).not.toBeNull();
});

describe("ADR-11: returnTo can never leave our origin", () => {
	const ORIGIN = "https://flickrgroupaddr.com";

	it("accepts the paths a login is allowed to finish on", () => {
		expect(safeReturnPath("/", ORIGIN)).toBe("/");
		expect(safeReturnPath("/link", ORIGIN)).toBe("/link");
		// The query survives, which is the whole point for the device flow.
		expect(safeReturnPath("/link?userCode=ABC123", ORIGIN)).toBe(
			"/link?userCode=ABC123",
		);
		// Absolute but same-origin resolves to its own path.
		expect(safeReturnPath(`${ORIGIN}/link`, ORIGIN)).toBe("/link");
	});

	it.each([
		["https://evil.com", "absolute off-site URL"],
		["https://evil.com/link", "off-site URL wearing an allowed path"],
		["//evil.com", "protocol-relative"],
		["//evil.com/link", "protocol-relative wearing an allowed path"],
		["/\\evil.com", "backslash, which WHATWG normalizes to a second slash"],
		["\\\\evil.com", "double backslash"],
		["http://flickrgroupaddr.com/link", "right host, WRONG SCHEME"],
		["https://flickrgroupaddr.com.evil.com/link", "suffix-confusion host"],
	])("refuses %s -- %s", (candidate) => {
		expect(safeReturnPath(candidate, ORIGIN)).toBeNull();
	});

	// Annotated because a bare array of mixed tuples makes TypeScript infer a UNION of
	// tuple types, which `it.each` cannot match to a single callback signature.
	const NOT_A_DESTINATION: ReadonlyArray<[string | null | undefined, string]> =
		[
			["/admin", "a real path that is not an allowed destination"],
			["/%2f%2fevil.com", "percent-encoded escape attempt"],
			["", "empty"],
			[null, "absent"],
			[undefined, "undefined"],
		];

	it.each(NOT_A_DESTINATION)("refuses %s -- %s", (candidate) => {
		expect(safeReturnPath(candidate, ORIGIN)).toBeNull();
	});

	it("returns a PATH, never anything carrying an origin", () => {
		// Defense in depth by return type: even a wrong check above cannot emit a host.
		for (const candidate of ["/", "/link", `${ORIGIN}/link`]) {
			const got = safeReturnPath(candidate, ORIGIN);
			expect(got).not.toBeNull();
			expect(got?.startsWith("/")).toBe(true);
			expect(got).not.toMatch(/^\/\//);
		}
	});
});

describe("ADR-11: the callback returns where the login STARTED", () => {
	/** Drives both legs. The outbound stub answers request_token and access_token. */
	async function login(query: string): Promise<URL> {
		const started = await SELF.fetch(
			`https://api.flickrgroupaddr.com/oauth/login${query}`,
			{ redirect: "manual" },
		);
		expect(started.status).toBe(302);

		const back = await SELF.fetch(
			"https://api.flickrgroupaddr.com/oauth/callback" +
				"?oauth_token=test-request-token&oauth_verifier=test-verifier",
			{ redirect: "manual" },
		);
		expect(back.status).toBe(302);
		return new URL(back.headers.get("Location") ?? "");
	}

	it("lands on the app root when no returnTo was given", async () => {
		const location = await login("");
		expect(location.origin).toBe("https://flickrgroupaddr.com");
		expect(location.pathname).toBe("/");
		expect(location.searchParams.get("login")).toBe("ok");
	});

	it("carries the device-link code through the whole Flickr round trip", async () => {
		// The defect this closes: before 2026-08-16 the callback always redirected to
		// the app root, so a user who signed in mid-link arrived home with the code
		// gone and the flow had no way to finish.
		const location = await login(
			`?returnTo=${encodeURIComponent("/link?userCode=ABC123")}`,
		);
		expect(location.origin).toBe("https://flickrgroupaddr.com");
		expect(location.pathname).toBe("/link");
		expect(location.searchParams.get("userCode")).toBe("ABC123");
		expect(location.searchParams.get("login")).toBe("ok");
	});

	it("ignores an off-site returnTo and still lands on our origin", async () => {
		// The open redirect. A victim clicking a crafted login link MUST end up here,
		// not on the attacker's site holding a fresh session cookie.
		const location = await login("?returnTo=https%3A%2F%2Fevil.com");
		expect(location.origin).toBe("https://flickrgroupaddr.com");
		expect(location.pathname).toBe("/");
	});

	it("keeps the destination out of the callback URL entirely", async () => {
		// Flickr controls the callback's query string. If the destination travelled
		// there, Flickr -- or anyone who could tamper with that redirect -- would be
		// choosing where an authenticated user lands. It lives in the Durable Object.
		await SELF.fetch(
			`https://api.flickrgroupaddr.com/oauth/login?returnTo=${encodeURIComponent("/link")}`,
			{ redirect: "manual" },
		);
		const stub = env.OAUTH_LOGIN.get(
			env.OAUTH_LOGIN.idFromName("test-request-token"),
		);
		expect(await stub.consume("test-request-token")).toEqual({
			requestTokenSecret: "test-request-token-secret",
			returnPath: "/link",
		});
	});
});
