import { env, SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { encryptToken } from "../src/crypto/tokens.js";
import { mintSession, SESSION_COOKIE } from "../src/session.js";

/**
 * ADR-17. `GET /api/v001/photos/:photoId/groups` -- which groups a photo is already in.
 *
 * **The Lightroom picker opens with this and cannot ask Flickr itself.** The plug-in holds
 * no Flickr credentials by design, so FGA proxies the question. Terry, 2026-08-15: *"we
 * made SURE we don't keep the user's long term flickr creds in the plugin ... I'm good
 * proxying that through our API as a middleman."*
 */

const NSID = "12345678@N00";
const API = "https://flickrgroupaddr.com";

type Reply = { groups: { id: string; title: string | null }[] };

async function cookie(nsid: string): Promise<string> {
	return `${SESSION_COOKIE}=${await mintSession(env.DB, nsid, env.SESSION_KEY)}`;
}

async function ask(photoId: string, nsid = NSID): Promise<Response> {
	return await SELF.fetch(`${API}/api/v001/photos/${photoId}/groups`, {
		headers: { Cookie: await cookie(nsid) },
	});
}

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

beforeEach(async () => {
	await env.DB.exec("DELETE FROM sessions");
	await env.DB.exec("DELETE FROM requests");
	await env.DB.exec("DELETE FROM users");
	await addUser(NSID);
});

describe("ADR-17, the groups a photo is already in", () => {
	it("returns the pools Flickr reports, with the title it already sent", async () => {
		const response = await ask("in-pool-titled");
		expect(response.status).toBe(200);

		const body = (await response.json()) as Reply;
		expect(body.groups).toEqual([
			{ id: "g-titled", title: "Canada Landscapes" },
			// **Null, not a guess.** Flickr MAY omit the title, and inventing one here
			// would put a name in the picker that does not match the group list.
			{ id: "g-untitled", title: null },
		]);
	});

	it("returns an empty list for a photo in no pools", async () => {
		const body = (await (await ask("lonely-photo")).json()) as Reply;
		expect(body.groups).toEqual([]);
	});

	/**
	 * **The `no_flickr_credentials` 409 branch is UNREACHABLE, and that is a schema fact
	 * rather than a gap in this file.** `users.access_token_encrypted` is NOT NULL and
	 * `sessions.nsid` carries a foreign key to `users`, so a valid session implies a user
	 * row implies tokens. The branch stays in the route because ADR-22's constraints are
	 * what make it unreachable, and a later migration that relaxed either one would make
	 * it live again -- deleting it would be trusting today's schema forever.
	 *
	 * **What the route MUST NOT do is collapse "Flickr did not answer" into "the photo is
	 * in no groups".** Those are different facts, and reporting the second would show the
	 * picker an empty right-hand list. The user would then queue adds for groups the photo
	 * is already in, and a duplicate add can reach a moderator. The route answers 502 for
	 * the unknown case; the stub always succeeds, so only inspection covers it.
	 */

	it("requires a session, like every other /api/v001 route", async () => {
		const response = await SELF.fetch(`${API}/api/v001/photos/in-pool/groups`);
		expect(response.status).toBe(401);
	});

	it("rejects a photo id past the length every other endpoint enforces", async () => {
		const response = await ask("x".repeat(65));
		expect(response.status).toBe(400);
	});

	/**
	 * ADR-12. The reply names a user's photo and its group memberships, so a shared cache
	 * would serve one person's memberships to another.
	 */
	it("is not cacheable", async () => {
		const response = await ask("in-pool");
		expect(response.headers.get("Cache-Control")).toContain("no-store");
	});
});
