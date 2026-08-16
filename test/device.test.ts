import { env, runInDurableObject, SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { encryptToken } from "../src/crypto/tokens.js";
import { mintSession, SESSION_COOKIE } from "../src/session.js";

/**
 * ADR-24. The device link flow, end to end and at its edges.
 *
 * **The interesting tests here are the refusals**, not the happy path. A device
 * flow that works is table stakes; one that cannot be replayed, cannot be
 * approved by the credential it mints, and cannot be polled by somebody who did
 * not start it is the actual deliverable.
 */

const NSID = "12345678@N00";
const OTHER = "99999999@N00";
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

function post(path: string, body: unknown, init: RequestInit = {}) {
	return SELF.fetch(`${API}${path}`, {
		method: "POST",
		body: JSON.stringify(body),
		...init,
		headers: {
			"Content-Type": "application/json",
			...(init.headers ?? {}),
		},
	});
}

async function asBrowser(path: string, body: unknown, nsid = NSID) {
	const token = await mintSession(env.DB, nsid, env.SESSION_KEY);
	return await post(path, body, {
		headers: { Cookie: `${SESSION_COOKIE}=${token}` },
	});
}

type StartReply = {
	deviceCode: string;
	userCode: string;
	expiresAt: number;
	pollAfter: number;
	verificationUri: string;
};

async function start(): Promise<StartReply> {
	const response = await post("/api/v001/device/start", {});
	expect(response.status).toBe(200);
	return (await response.json()) as StartReply;
}

beforeEach(async () => {
	await env.DB.exec("DELETE FROM sessions");
	await env.DB.exec("DELETE FROM requests");
	await env.DB.exec("DELETE FROM users");
	await addUser(NSID);
	await addUser(OTHER);
});

describe("ADR-24: starting a link needs no credential", () => {
	it("issues two codes and a verification page, with no session at all", async () => {
		const reply = await start();

		expect(reply.userCode).toMatch(/^[2-9A-HJ-NP-TV-Z]{8}$/);
		expect(reply.deviceCode.length).toBeGreaterThan(32);
		expect(reply.pollAfter).toBeGreaterThan(0);
		expect(reply.expiresAt).toBeGreaterThan(Date.now());
	});

	it("builds the verification page from UI_ORIGIN, not from the request", async () => {
		// A crafted call MUST NOT be able to point a plug-in at somebody else's
		// approval page.
		const response = await SELF.fetch(
			"https://flickrgroupaddr.com/api/v001/device/start",
			{ method: "POST", headers: { Origin: "https://evil.com" } },
		);
		const reply = (await response.json()) as StartReply;
		expect(new URL(reply.verificationUri).origin).toBe(
			"https://flickrgroupaddr.com",
		);
	});

	it("NEVER puts the polling credential in the verification URL", async () => {
		// The correction recorded in docs/LRC-CLIENT-NOTES.md. RFC 8628 keeps
		// device_code out of every URL; a URL leaks to history, sync and proxy logs.
		const reply = await start();
		expect(reply.verificationUri).not.toContain(reply.deviceCode);
		expect(reply.verificationUri).not.toContain(reply.userCode);
	});

	/**
	 * **Every one of these responses carries a bearer credential in its body**, and
	 * mounting `deviceRoutes` ahead of `apiRoutes` means ADR-12's blanket
	 * `no-store` on `/api/v001/*` never runs for them. The same ordering that
	 * makes `start` unauthenticated also skipped the cache rule.
	 */
	it("marks credential-bearing replies no-store, which the mount order skipped", async () => {
		const started = await post("/api/v001/device/start", {});
		expect(started.headers.get("Cache-Control")).toContain("no-store");

		const reply = (await started.json()) as StartReply;
		const polled = await post("/api/v001/device/poll", {
			userCode: reply.userCode,
			deviceCode: reply.deviceCode,
		});
		expect(polled.headers.get("Cache-Control")).toContain("no-store");
	});

	it("gives every start a different pair", async () => {
		const a = await start();
		const b = await start();
		expect(a.userCode).not.toBe(b.userCode);
		expect(a.deviceCode).not.toBe(b.deviceCode);
	});
});

describe("ADR-24: the whole flow, and the token it mints", () => {
	it("start, approve, poll -- and the token reaches the plug-in's allow-list", async () => {
		const reply = await start();

		const approved = await asBrowser("/api/v001/device/approve", {
			userCode: reply.userCode,
		});
		expect(approved.status).toBe(200);

		const polled = await post("/api/v001/device/poll", {
			userCode: reply.userCode,
			deviceCode: reply.deviceCode,
		});
		expect(polled.status).toBe(200);
		const collected = (await polled.json()) as {
			status: string;
			token: string;
		};
		expect(collected.status).toBe("approved");

		// The credential works, and it works as a PLUG-IN credential.
		const me = await SELF.fetch(`${API}/api/v001/me`, {
			headers: { Authorization: `Bearer ${collected.token}` },
		});
		expect(me.status).toBe(200);
		expect(await me.json()).toMatchObject({ nsid: NSID });

		// And it is scoped: an unlisted route is refused, so the device flow cannot
		// be used to obtain a wider credential than the allow-list permits.
		const unlisted = await SELF.fetch(`${API}/api/v001/admin/overview`, {
			headers: { Authorization: `Bearer ${collected.token}` },
		});
		expect(unlisted.status).toBe(403);
	});

	it("mints the token for the APPROVER, never for whoever started the flow", async () => {
		const reply = await start();
		await asBrowser(
			"/api/v001/device/approve",
			{ userCode: reply.userCode },
			OTHER,
		);

		const polled = await post("/api/v001/device/poll", {
			userCode: reply.userCode,
			deviceCode: reply.deviceCode,
		});
		const collected = (await polled.json()) as { token: string };

		const me = await SELF.fetch(`${API}/api/v001/me`, {
			headers: { Authorization: `Bearer ${collected.token}` },
		});
		expect(await me.json()).toMatchObject({ nsid: OTHER });
	});

	it("gives the token a 90-day life, not a browser session's 30", async () => {
		const reply = await start();
		await asBrowser("/api/v001/device/approve", { userCode: reply.userCode });
		await post("/api/v001/device/poll", {
			userCode: reply.userCode,
			deviceCode: reply.deviceCode,
		});

		const row = await env.DB.prepare(
			"SELECT expires_at, created_at, client_type FROM sessions WHERE client_type = 'lrc15_plugin'",
		).first<{ expires_at: number; created_at: number; client_type: string }>();

		expect(row).not.toBeNull();
		const days = ((row?.expires_at ?? 0) - (row?.created_at ?? 0)) / 86_400_000;
		expect(Math.round(days)).toBe(90);
	});

	it("mints NOTHING until the plug-in collects", async () => {
		// An approved link nobody polls leaves no credential behind.
		const reply = await start();
		await asBrowser("/api/v001/device/approve", { userCode: reply.userCode });

		const count = await env.DB.prepare(
			"SELECT COUNT(*) AS n FROM sessions WHERE client_type = 'lrc15_plugin'",
		).first<{ n: number }>();
		expect(count?.n).toBe(0);
	});
});

describe("ADR-24: polling refuses everything it should", () => {
	it("answers pending before anyone approves", async () => {
		const reply = await start();
		const polled = await post("/api/v001/device/poll", {
			userCode: reply.userCode,
			deviceCode: reply.deviceCode,
		});
		expect(await polled.json()).toMatchObject({ status: "pending" });
	});

	it("is SINGLE USE -- a replayed poll finds nothing", async () => {
		const reply = await start();
		await asBrowser("/api/v001/device/approve", { userCode: reply.userCode });

		const first = await post("/api/v001/device/poll", {
			userCode: reply.userCode,
			deviceCode: reply.deviceCode,
		});
		expect((await first.json()) as { status: string }).toMatchObject({
			status: "approved",
		});

		const replay = await post("/api/v001/device/poll", {
			userCode: reply.userCode,
			deviceCode: reply.deviceCode,
		});
		expect(await replay.json()).toMatchObject({ status: "expired" });
	});

	/**
	 * **The load-bearing refusal.** Somebody who learns a `userCode` -- read off a
	 * screen, seen over a shoulder -- MUST NOT be able to collect the token. That
	 * is the whole reason `deviceCode` exists as a separate value.
	 */
	it("refuses a poll carrying the WRONG deviceCode", async () => {
		const reply = await start();
		await asBrowser("/api/v001/device/approve", { userCode: reply.userCode });

		const stolen = await post("/api/v001/device/poll", {
			userCode: reply.userCode,
			deviceCode: "not-the-right-code",
		});
		expect(await stolen.json()).toMatchObject({ status: "expired" });
	});

	/** A wrong poll MUST NOT destroy an attempt still in flight. */
	it("leaves the attempt intact after a wrong deviceCode", async () => {
		const reply = await start();
		await asBrowser("/api/v001/device/approve", { userCode: reply.userCode });

		await post("/api/v001/device/poll", {
			userCode: reply.userCode,
			deviceCode: "not-the-right-code",
		});

		const real = await post("/api/v001/device/poll", {
			userCode: reply.userCode,
			deviceCode: reply.deviceCode,
		});
		expect((await real.json()) as { status: string }).toMatchObject({
			status: "approved",
		});
	});

	it("answers expired for a code nobody ever started", async () => {
		const polled = await post("/api/v001/device/poll", {
			userCode: "ABCDEFGH",
			deviceCode: "whatever",
		});
		expect(await polled.json()).toMatchObject({ status: "expired" });
	});

	it("reports a denial as DENIED rather than letting it time out", async () => {
		// ADR-01's habit on a different surface: a refusal MUST NOT look like a failure.
		const reply = await start();
		const denied = await asBrowser("/api/v001/device/deny", {
			userCode: reply.userCode,
		});
		expect(denied.status).toBe(200);

		const polled = await post("/api/v001/device/poll", {
			userCode: reply.userCode,
			deviceCode: reply.deviceCode,
		});
		expect(await polled.json()).toMatchObject({ status: "denied" });
	});

	it("refuses a malformed body", async () => {
		const response = await post("/api/v001/device/poll", { nope: true });
		expect(response.status).toBe(400);
	});
});

describe("ADR-24: polling is throttled server-side, not on trust", () => {
	function poll(reply: StartReply, deviceCode = reply.deviceCode) {
		return post("/api/v001/device/poll", {
			userCode: reply.userCode,
			deviceCode,
		});
	}

	it("tells a hammering client to slow down, and to wait LONGER", async () => {
		const reply = await start();

		const first = await poll(reply);
		expect(await first.json()).toMatchObject({ status: "pending" });

		// Back to back, so comfortably inside the 2-second floor.
		const second = await poll(reply);
		const throttled = (await second.json()) as {
			status: string;
			pollAfter: number;
		};
		expect(throttled.status).toBe("slow_down");
		// Returning the interval it just violated would leave a tight loop looping.
		expect(throttled.pollAfter).toBeGreaterThan(reply.pollAfter);
	});

	it("does NOT push the window forward on a throttled poll", async () => {
		// A client in a tight loop must recover after one honest wait, rather than
		// holding itself out forever by resetting the clock on every refusal.
		const reply = await start();
		const stub = env.DEVICE_LINK.get(
			env.DEVICE_LINK.idFromName(reply.userCode),
		);

		const windowAfterFirstPoll = async () => {
			let seen = 0;
			await runInDurableObject(stub, async (_instance, state) => {
				const stored = await state.storage.get<{ lastPolledAt: number }>(
					"attempt",
				);
				seen = stored?.lastPolledAt ?? 0;
			});
			return seen;
		};

		await poll(reply);
		const opened = await windowAfterFirstPoll();
		expect(opened).toBeGreaterThan(0);

		// Three refusals in a row.
		await poll(reply);
		await poll(reply);
		await poll(reply);

		// **The exact same instant, not merely a recent one.** Asserting "recent"
		// would hold true whether or not the refusals wrote, which is an assertion
		// that proves nothing.
		expect(await windowAfterFirstPoll()).toBe(opened);
	});

	it("lets an honest client through once the interval has passed", async () => {
		const reply = await start();
		await poll(reply);

		// Rewind rather than sleep: the behavior under test is the interval, not
		// the suite's patience.
		const stub = env.DEVICE_LINK.get(
			env.DEVICE_LINK.idFromName(reply.userCode),
		);
		await runInDurableObject(stub, async (_instance, state) => {
			const stored =
				await state.storage.get<Record<string, unknown>>("attempt");
			await state.storage.put("attempt", {
				...stored,
				lastPolledAt: Date.now() - 60_000,
			});
		});

		expect(await (await poll(reply)).json()).toMatchObject({
			status: "pending",
		});
	});

	/**
	 * **The denial of service this ordering prevents.** Anybody who reads a
	 * `userCode` off a screen could otherwise hammer the object with a wrong
	 * `deviceCode` and hold the real plug-in in permanent `slow_down`.
	 */
	it("cannot be throttled by somebody polling with the WRONG deviceCode", async () => {
		const reply = await start();

		for (let i = 0; i < 5; i++) await poll(reply, "wrong-code");

		// The legitimate poller is unaffected, because a wrong code returns before
		// the throttle window is ever read or written.
		expect(await (await poll(reply)).json()).toMatchObject({
			status: "pending",
		});
	});
});

describe("ADR-24: approval is browser-only, and that stops escalation", () => {
	it("refuses an unauthenticated approval", async () => {
		const reply = await start();
		const response = await post("/api/v001/device/approve", {
			userCode: reply.userCode,
		});
		expect(response.status).toBe(401);
	});

	/**
	 * **The escalation this prevents.** If a plug-in token could approve a link, a
	 * 90-day credential on a stolen laptop could mint another one before the owner
	 * revoked it, and then another -- permanent access from a single theft.
	 */
	it("REFUSES a plug-in token, so a stolen token cannot mint a fresh one", async () => {
		const reply = await start();
		const pluginToken = await mintSession(
			env.DB,
			NSID,
			env.SESSION_KEY,
			"lrc15_plugin",
		);

		const response = await post(
			"/api/v001/device/approve",
			{ userCode: reply.userCode },
			{ headers: { Authorization: `Bearer ${pluginToken}` } },
		);
		expect(response.status).toBe(403);

		// And the attempt is untouched: still pending, not approved.
		const polled = await post("/api/v001/device/poll", {
			userCode: reply.userCode,
			deviceCode: reply.deviceCode,
		});
		expect(await polled.json()).toMatchObject({ status: "pending" });
	});

	it("refuses a plug-in token on deny as well", async () => {
		const reply = await start();
		const pluginToken = await mintSession(
			env.DB,
			NSID,
			env.SESSION_KEY,
			"lrc15_plugin",
		);
		const response = await post(
			"/api/v001/device/deny",
			{ userCode: reply.userCode },
			{ headers: { Authorization: `Bearer ${pluginToken}` } },
		);
		expect(response.status).toBe(403);
	});

	it("answers 404 for an unknown code, telling a prober nothing", async () => {
		const response = await asBrowser("/api/v001/device/approve", {
			userCode: "ABCDEFGH",
		});
		expect(response.status).toBe(404);
	});

	it("accepts a code the way a person actually types it", async () => {
		// Lower case, spaces and dashes all survive normalization. A code read off
		// one screen and typed into another is the real path, not the link.
		const reply = await start();
		const typed = `${reply.userCode.slice(0, 4).toLowerCase()}-${reply.userCode
			.slice(4)
			.toLowerCase()}`;

		const response = await asBrowser("/api/v001/device/approve", {
			userCode: typed,
		});
		expect(response.status).toBe(200);
	});
});
