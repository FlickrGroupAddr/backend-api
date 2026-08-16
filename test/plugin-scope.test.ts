import { env, SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { encryptToken } from "../src/crypto/tokens.js";
import { mintSession, SESSION_COOKIE } from "../src/session.js";

/**
 * ADR-17 and ADR-19. What a Lightroom plug-in token may reach, as an ALLOW-LIST.
 *
 * **The polarity is the thing being tested.** A deny-list would leave every endpoint
 * added later reachable by a 90-day credential on a laptop, unless whoever added it
 * remembered to guard it. Security that depends on remembering is security that lapses.
 *
 * So the interesting test is not that the allowed routes work — it is that an UNLISTED
 * route is refused, and that adding a route to the API does not quietly widen what a
 * stolen plug-in token can do.
 */

const NSID = "12345678@N00";
const API = "https://flickrgroupaddr.com";

async function addUser(nsid: string): Promise<void> {
	await env.DB.prepare(
		`INSERT INTO users (nsid, access_token_encrypted, access_token_secret_encrypted, created_at, updated_at)
     VALUES (?, ?, ?, 0, 0)`,
	)
		.bind(
			nsid,
			await encryptToken("access-token", nsid, env.TOKEN_KEY),
			await encryptToken("access-secret", nsid, env.TOKEN_KEY),
		)
		.run();
}

/** The plug-in sends a bearer header; it has no browser and no cookie jar. */
async function asPlugin(
	path: string,
	init: RequestInit = {},
): Promise<Response> {
	const token = await mintSession(
		env.DB,
		NSID,
		env.SESSION_KEY,
		"lrc15_plugin",
	);
	return await SELF.fetch(`${API}${path}`, {
		...init,
		headers: {
			...(init.headers ?? {}),
			Authorization: `Bearer ${token}`,
		},
	});
}

async function asBrowser(
	path: string,
	init: RequestInit = {},
): Promise<Response> {
	const token = await mintSession(env.DB, NSID, env.SESSION_KEY);
	return await SELF.fetch(`${API}${path}`, {
		...init,
		headers: { ...(init.headers ?? {}), Cookie: `${SESSION_COOKIE}=${token}` },
	});
}

beforeEach(async () => {
	await env.DB.exec("DELETE FROM sessions");
	await env.DB.exec("DELETE FROM requests");
	await env.DB.exec("DELETE FROM users");
	await addUser(NSID);
});

describe("ADR-19, a plug-in token reaches only its allow-list", () => {
	it("accepts a bearer token where a cookie would also work", async () => {
		const response = await asPlugin("/api/v001/me");
		expect(response.status).toBe(200);
		expect((await response.json()) as { nsid: string }).toMatchObject({
			nsid: NSID,
		});
	});

	/**
	 * **The load-bearing test.** `POST /api/v001/requests` is not in the allow-list,
	 * because the batch endpoint is the sanctioned path and one door is easier to reason
	 * about than two. A browser reaches it; a plug-in must not.
	 */
	it("REFUSES an unlisted route that a browser may use", async () => {
		const body = JSON.stringify({ photoId: "p1", groupId: "g1" });
		const headers = { "Content-Type": "application/json" };

		const plugin = await asPlugin("/api/v001/requests", {
			method: "POST",
			body,
			headers,
		});
		expect(plugin.status).toBe(403);
		expect(await plugin.json()).toEqual({ error: "not_allowed_for_plugin" });

		// The same call from a browser is not refused for scope reasons.
		const browser = await asBrowser("/api/v001/requests", {
			method: "POST",
			body,
			headers,
		});
		expect(browser.status).not.toBe(403);
	});

	/**
	 * **403 rather than 401, deliberately.** The caller IS authenticated and holds the
	 * wrong CLIENT TYPE. A 401 would send the plug-in into a re-login loop that
	 * could never succeed, because the credential it would obtain is the one refused.
	 */
	it("answers 403 rather than 401, so a plug-in does not re-login forever", async () => {
		const response = await asPlugin("/api/v001/admin/overview");
		expect(response.status).toBe(403);
	});

	it("refuses the admin surface even to an allowlisted NSID", async () => {
		// ADR-19's allowlist and this are different questions: is this person an admin,
		// versus is this credential one we let act as an admin. A stolen laptop MUST NOT
		// be an admin console.
		const response = await asPlugin("/api/v001/admin/overview");
		expect(response.status).toBe(403);
		expect(await response.json()).toEqual({ error: "not_allowed_for_plugin" });
	});

	it("allows the routes the picker actually needs", async () => {
		for (const path of [
			"/api/v001/me",
			"/api/v001/groups",
			"/api/v001/queue",
			"/api/v001/photos/in-pool/groups",
		]) {
			const response = await asPlugin(path);
			expect(response.status, `${path} must not be refused for scope`).not.toBe(
				403,
			);
		}
	});

	/**
	 * **The METHOD is part of the rule, not only the path.** `/api/v001/groups` is a
	 * legitimate read, and that MUST NOT imply a write to the same path is allowed.
	 */
	it("matches on method as well as path", async () => {
		const response = await asPlugin("/api/v001/groups", { method: "POST" });
		expect(response.status).toBe(403);
	});
});
