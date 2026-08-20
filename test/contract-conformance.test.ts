import { env, SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { encryptToken } from "../src/crypto/tokens.js";
import { mintSession, SESSION_COOKIE } from "../src/session.js";
import * as contract from "../web/src/lib/contract.js";

/**
 * The browser's copy of the API contract, parsed against what the Worker really answers.
 *
 * `web/src/lib/contract.ts` opens by saying these schemas **MUST stay in step with
 * `src/routes/api.ts`**, and that a generated client was rejected on purpose: it would
 * add a build step and a dependency to restate 120 lines that change about once a month.
 * **That trade is defensible and it was completely unenforced.** Nothing compared the two
 * copies, so a renamed field would have shipped, and the symptom would be a zod error in
 * the browser rather than a red gate.
 *
 * **This is the cheap half of a generated client.** It does not keep the schemas in step;
 * it refuses to let them drift apart silently.
 *
 * **`parse` is the right instrument and its blind spot is deliberate.** Zod strips
 * unknown keys rather than rejecting them, so a field the server ADDS does not fail here
 * -- correctly, because the browser ignores it. A field that is renamed, removed, or
 * changes type does fail, and those are the three that break the UI.
 */

const NSID = "12345678@N00";
const API = "https://flickrgroupaddr.com";

const UUID = `lower(
  hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' ||
  substr(hex(randomblob(2)), 2) || '-' ||
  substr('89ab', 1 + (abs(random()) % 4), 1) ||
  substr(hex(randomblob(2)), 2) || '-' || hex(randomblob(6))
)`;

async function authed(
	path: string,
	init: RequestInit = {},
	nsid = NSID,
): Promise<Response> {
	const cookie = `${SESSION_COOKIE}=${await mintSession(env.DB, nsid, env.SESSION_KEY)}`;
	return await SELF.fetch(`${API}${path}`, {
		...init,
		headers: {
			...(init.headers ?? {}),
			Cookie: cookie,
			"Content-Type": "application/json",
		},
	});
}

async function addUser(nsid: string): Promise<void> {
	await env.DB.prepare(
		`INSERT INTO users
       (nsid, access_token_encrypted, access_token_secret_encrypted, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?)`,
	)
		.bind(
			nsid,
			await encryptToken("access-token", nsid, env.TOKEN_KEY),
			await encryptToken("access-secret", nsid, env.TOKEN_KEY),
			0,
			0,
		)
		.run();
}

async function seed(
	photoId: string,
	groupId: string,
	resolved?: { outcome: string; code?: number },
): Promise<string> {
	const row = await env.DB.prepare(
		`INSERT INTO requests
       (public_id, nsid, photo_id, group_id, created_at, state, outcome, flickr_code, resolved_at)
     VALUES (${UUID}, ?, ?, ?, 0, ?, ?, ?, ?)
     RETURNING public_id`,
	)
		.bind(
			NSID,
			photoId,
			groupId,
			resolved ? "resolved" : "pending",
			resolved?.outcome ?? null,
			resolved?.code ?? null,
			resolved ? 1 : null,
		)
		.first<{ public_id: string }>();
	return row?.public_id ?? "";
}

beforeEach(async () => {
	await env.DB.exec("DELETE FROM requests");
	await env.DB.exec("DELETE FROM moderated_pairs");
	await env.DB.exec("DELETE FROM users");
	await addUser(NSID);
});

describe("the browser contract still parses the Worker's replies", () => {
	/*
	 * TRACE-EXEMPT: drift insurance for a duplication the project chose on purpose, not
	 * the verification of a decision. `contract.ts` restates the route shapes by hand
	 * because a generated client was rejected; this block is what makes that safe. Linking
	 * it to the nearest ADR would be the forced link scripts/traceability.py exists to
	 * refuse.
	 */

	it("me", async () => {
		const response = await authed("/api/v001/me");
		expect(response.status).toBe(200);
		contract.me.parse(await response.json());
	});

	it("groupList", async () => {
		const response = await authed("/api/v001/groups");
		expect(response.status).toBe(200);
		contract.groupList.parse(await response.json());
	});

	it("submitted, on the ordinary path", async () => {
		const response = await authed("/api/v001/requests", {
			method: "POST",
			body: JSON.stringify({ photoId: "53912345678", groupId: "g1" }),
		});
		expect([200, 202]).toContain(response.status);
		contract.submitted.parse(await response.json());
	});

	/**
	 * **ADR-04's 409 is a RESULT, not a failure**, and `api.ts` reads the status before
	 * deciding for exactly this reason. So the 409 body has to satisfy the same schema as
	 * a success, or the warning renders as a crash.
	 */
	it("submitted, on ADR-04's 409", async () => {
		await env.DB.prepare(
			`INSERT INTO moderated_pairs
         (nsid, photo_id, group_id, flickr_code, first_seen_at, last_seen_at)
       VALUES (?, '53912345678', 'g1', 6, 0, 0)`,
		)
			.bind(NSID)
			.run();

		const response = await authed("/api/v001/requests", {
			method: "POST",
			body: JSON.stringify({ photoId: "53912345678", groupId: "g1" }),
		});
		expect(response.status).toBe(409);
		const parsed = contract.submitted.parse(await response.json());
		expect(parsed.status).toBe("needs_acknowledgement");
	});

	/**
	 * Both request shapes in one page. A pending row carries a `position` and a null
	 * `outcome`; a resolved row is the other way round, and `explain` branches on exactly
	 * that pair.
	 */
	it("queuePage, with a pending and a resolved request", async () => {
		await seed("53912345678", "g1");
		await seed("53912345679", "g1", {
			outcome: "queued_for_moderator",
			code: 6,
		});

		const response = await authed("/api/v001/queue?state=all&limit=50");
		expect(response.status).toBe(200);
		const page = contract.queuePage.parse(await response.json());

		const requests = page.queues.flatMap((queue) => queue.requests);
		expect(requests).toHaveLength(2);
		expect(requests.some((r) => r.state === "pending")).toBe(true);
		expect(requests.some((r) => r.state === "resolved")).toBe(true);
	});

	/** ADR-20. The whole selection in one call, so the warning precedes the decision. */
	it("preflight", async () => {
		const response = await authed("/api/v001/photos/53912345678/preflight", {
			method: "POST",
			body: JSON.stringify({ groupIds: ["g1", "g2"] }),
		});
		expect(response.status).toBe(200);
		contract.preflight.parse(await response.json());
	});

	it("withdrawn", async () => {
		const publicId = await seed("53912345678", "g1");
		const response = await authed(`/api/v001/requests/${publicId}/withdraw`, {
			method: "POST",
		});
		expect(response.status).toBe(200);
		contract.withdrawn.parse(await response.json());
	});

	/** ADR-19. `NSID` is on the allowlist in `vitest.config.ts`. */
	it("adminOverview", async () => {
		const response = await authed("/api/v001/admin/overview?days=7");
		expect(response.status).toBe(200);
		contract.adminOverview.parse(await response.json());
	});

	/**
	 * **The instrument has to be able to fail, and a schema is easy to get wrong in the
	 * permissive direction.** This pins that `parse` rejects a renamed field, which is the
	 * drift the whole block exists to catch.
	 */
	it("would notice a renamed field", () => {
		expect(() =>
			contract.me.parse({ nsidRenamed: "12345678@N00", admin: false }),
		).toThrow();
	});
});
