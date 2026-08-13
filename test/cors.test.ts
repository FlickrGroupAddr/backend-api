import { SELF } from "cloudflare:test";
import { describe, expect, it } from "vitest";

/**
 * ADR-12 calls the reflected-Origin mistake "the single highest-severity mistake
 * available in this design", so it gets tested against the real Worker rather
 * than reasoned about.
 *
 * The attack these guard against: reflect the request's Origin header while
 * also sending Access-Control-Allow-Credentials: true, and any website on the
 * internet can make authenticated calls as a logged-in FGA user and read the
 * replies. It is two lines, and it looks exactly like the fix.
 */

const UI = "https://flickrgroupaddr.com";
const EVIL = "https://flickrgroupaddr.com.attacker.example";

describe("CORS on the API surface", () => {
	it("allows the configured UI origin", async () => {
		const response = await SELF.fetch(
			"https://api.flickrgroupaddr.com/v001/anything",
			{ headers: { Origin: UI } },
		);

		expect(response.headers.get("Access-Control-Allow-Origin")).toBe(UI);
		expect(response.headers.get("Access-Control-Allow-Credentials")).toBe(
			"true",
		);
	});

	it("does NOT reflect an arbitrary origin", async () => {
		const response = await SELF.fetch(
			"https://api.flickrgroupaddr.com/v001/anything",
			{ headers: { Origin: EVIL } },
		);

		expect(response.headers.get("Access-Control-Allow-Origin")).not.toBe(EVIL);
	});

	it("does not fall for a prefix-matching lookalike origin", async () => {
		// A substring or startsWith check would pass this. The comparison is
		// equality against the configured value.
		for (const lookalike of [
			"https://flickrgroupaddr.com.attacker.example",
			"https://evil.com/?https://flickrgroupaddr.com",
			"http://flickrgroupaddr.com",
			"https://flickrgroupaddr.com:8443",
			"null",
		]) {
			const response = await SELF.fetch(
				"https://api.flickrgroupaddr.com/v001/anything",
				{ headers: { Origin: lookalike } },
			);
			expect(response.headers.get("Access-Control-Allow-Origin")).not.toBe(
				lookalike,
			);
		}
	});

	it("never answers with a wildcard", async () => {
		// Browsers refuse a wildcard whenever credentials are included, so a
		// wildcard here would mean the credentialed path is silently broken -- or
		// that credentials were dropped to make it work.
		const response = await SELF.fetch(
			"https://api.flickrgroupaddr.com/v001/anything",
			{ headers: { Origin: UI } },
		);
		expect(response.headers.get("Access-Control-Allow-Origin")).not.toBe("*");
	});

	it("varies on Origin, so no cache serves one origin's decision to another", async () => {
		const response = await SELF.fetch(
			"https://api.flickrgroupaddr.com/v001/anything",
			{ headers: { Origin: UI } },
		);
		expect(response.headers.get("Vary") ?? "").toContain("Origin");
	});

	it("answers a preflight from the UI origin", async () => {
		const response = await SELF.fetch(
			"https://api.flickrgroupaddr.com/v001/anything",
			{
				method: "OPTIONS",
				headers: {
					Origin: UI,
					"Access-Control-Request-Method": "POST",
					"Access-Control-Request-Headers": "Content-Type",
				},
			},
		);

		expect(response.headers.get("Access-Control-Allow-Origin")).toBe(UI);
		expect(response.headers.get("Access-Control-Allow-Methods")).toContain(
			"POST",
		);
		// ADR-12 SHOULDs this, so the browser stops asking on every call.
		expect(response.headers.get("Access-Control-Max-Age")).toBe("86400");
	});
});

describe("health", () => {
	it("answers without needing a session", async () => {
		const response = await SELF.fetch("https://api.flickrgroupaddr.com/health");
		expect(response.status).toBe(200);
		expect(await response.json()).toEqual({ status: "ok" });
	});
});
