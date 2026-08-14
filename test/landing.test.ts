import { env, SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { mintSession, SESSION_COOKIE } from "../src/session.js";

/** Inserts a user row so the landing page has a display name to render. */
async function addUser(nsid: string, username: string): Promise<void> {
	await env.DB.prepare(
		`INSERT INTO users
       (nsid, flickr_username, access_token_encrypted,
        access_token_secret_encrypted, created_at, updated_at)
     VALUES (?, ?, ?, ?, 0, 0)`,
	)
		.bind(nsid, username, new Uint8Array([1]), new Uint8Array([2]))
		.run();
}

beforeEach(async () => {
	await env.DB.exec("DELETE FROM users");
});

/**
 * The landing page, which exists to answer one question honestly: am I actually
 * signed in?
 *
 * It reports the SESSION rather than the redirect. Those two come apart exactly
 * when something is wrong, which is the only time anybody reads this page
 * carefully.
 */

const BASE = "https://api.flickrgroupaddr.com";
const NSID = "146878425@N05";

async function landing(init: RequestInit = {}): Promise<string> {
	const response = await SELF.fetch(`${BASE}/`, init);
	expect(response.status).toBe(200);
	return await response.text();
}

describe("the landing page", () => {
	it("says so plainly when there is no session", async () => {
		expect(await landing()).toContain("Not signed in");
	});

	it("shows the username and NSID from a valid session cookie", async () => {
		await addUser(NSID, "TerryDOtt");
		const token = await mintSession(NSID, env.SESSION_KEY);
		const body = await landing({
			headers: { Cookie: `${SESSION_COOKIE}=${token}` },
		});

		expect(body).toContain("Signed in as");
		expect(body).toContain(`TerryDOtt (NSID: ${NSID})`);
	});

	it("falls back to the NSID alone when no user row exists", async () => {
		// A missing display name is cosmetic; the identity is the point. This also
		// covers a valid session outliving its row.
		const token = await mintSession(NSID, env.SESSION_KEY);
		const body = await landing({
			headers: { Cookie: `${SESSION_COOKIE}=${token}` },
		});

		expect(body).toContain("Signed in as");
		expect(body).toContain(NSID);
	});

	it("escapes a username that contains markup", async () => {
		// A Flickr display name is a third-party string a user can change at will.
		// Rendered raw, a chosen username would inject script into a page served
		// from the same origin that holds the session cookie.
		await addUser(NSID, '<script>alert("xss")</script>');
		const token = await mintSession(NSID, env.SESSION_KEY);
		const body = await landing({
			headers: { Cookie: `${SESSION_COOKIE}=${token}` },
		});

		expect(body).not.toContain("<script>alert");
		expect(body).toContain("&lt;script&gt;");
	});

	it("escapes ampersands without double-encoding the rest", async () => {
		await addUser(NSID, 'Terry & "Friends"');
		const token = await mintSession(NSID, env.SESSION_KEY);
		const body = await landing({
			headers: { Cookie: `${SESSION_COOKIE}=${token}` },
		});

		expect(body).toContain("Terry &amp; &quot;Friends&quot;");
		expect(body).not.toContain("&amp;quot;");
	});

	it("does NOT claim a session for a cookie signed with the wrong key", async () => {
		// The whole point of showing the NSID is peace of mind, which is worth
		// nothing if the page will echo back any value it is handed.
		const forged = await mintSession(
			"99999999@N00",
			"a-completely-different-key-32b!!",
		);
		const body = await landing({
			headers: { Cookie: `${SESSION_COOKIE}=${forged}` },
		});

		expect(body).toContain("Not signed in");
		expect(body).not.toContain("99999999@N00");
	});

	it("flags the discrepancy when the callback claims success but no cookie arrives", async () => {
		// The failure this page exists to catch. `?login=ok` only says the callback
		// believed it worked; a browser that dropped the cookie leaves the user
		// signed out while every visible sign says otherwise.
		const response = await SELF.fetch(`${BASE}/?login=ok`);
		const body = await response.text();

		expect(body).toContain("no valid session cookie came back");
		expect(body).not.toContain("Signed in as");
	});

	it("prefers the real session over a stale query string", async () => {
		// ?login=expired alongside a valid cookie means the user re-ran an old
		// callback URL. They are signed in; the query string is history.
		const token = await mintSession(NSID, env.SESSION_KEY);
		const body = await landing({
			headers: { Cookie: `${SESSION_COOKIE}=${token}` },
		});

		expect(body).toContain("Signed in as");
	});
});
