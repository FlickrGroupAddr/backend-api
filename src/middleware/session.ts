import { createMiddleware } from "hono/factory";
import {
	readSessionCookie,
	type SessionClientType,
	verifySession,
} from "../session.js";

/** Sessions are opaque handles, so verification is a signature check AND a D1 read.
 *  The HMAC runs first: a forger spraying random cookies never reaches the database. */
export type SessionVariables = {
	nsid: string;
	sessionClientType: SessionClientType;
};

/**
 * **A cookie OR an `Authorization: Bearer` header, and the two are not interchangeable
 * by accident.**
 *
 * The browser sends a cookie because a cookie is what `HttpOnly` protects. The Lightroom
 * plug-in sends a header because it has no browser and no cookie jar. The credential
 * itself is identical -- ADR-10's opaque handle -- and only the envelope differs.
 *
 * **The cookie is read FIRST.** A browser that also somehow carried a bearer header
 * should behave as the browser it is, and preferring the header would make a header
 * injected by anything else outrank the browser's own protected credential.
 *
 * **CSRF applies to exactly one of these.** Nothing sends an `Authorization` header
 * automatically, so ADR-12's cross-origin rules exist for the cookie and do not need a
 * second version for the header.
 */
function presentedToken(c: {
	req: { header: (name: string) => string | undefined };
}): string | undefined {
	const cookie = readSessionCookie(c as never);
	if (cookie !== undefined) return cookie;

	const header = c.req.header("Authorization");
	if (header === undefined) return undefined;

	// Case-insensitive scheme, exactly one space, and nothing else accepted.
	const match = /^Bearer (\S+)$/i.exec(header.trim());
	return match?.[1];
}

export const requireSession = createMiddleware<{
	Bindings: Env;
	Variables: SessionVariables;
}>(async (c, next) => {
	const token = presentedToken(c);

	if (token === undefined) {
		return c.json({ error: "not_authenticated" }, 401);
	}

	const session = await verifySession(c.env.DB, token, c.env.SESSION_KEY);
	if (session === null) {
		// Tampered, expired, revoked, wrong key, malformed, unknown -- one answer for
		// all six. Telling them apart tells an attacker which lever to pull.
		return c.json({ error: "not_authenticated" }, 401);
	}

	c.set("nsid", session.nsid);
	c.set("sessionClientType", session.clientType);
	await next();
});

/**
 * **Refuses a plug-in token, and this is where the longer plug-in lifetime is paid for.**
 *
 * A plug-in token lives for 90 days on a laptop, protected by nothing but the filesystem.
 * **So it MUST NOT be able to revoke other credentials or change the account** — if it
 * could, whoever picks up that laptop can lock the real owner out of their own Flickr
 * queue, and the owner's remedy would be the very endpoint the thief just used.
 *
 * **Register it AFTER `requireSession`**, which is what puts `sessionClientType` on the
 * context. Registered before, this would read `undefined` and refuse everybody — a
 * failure that is at least loud. The reverse ordering mistake is the dangerous one, and
 * `requireAdmin` carries the same warning for the same reason.
 *
 * **403 rather than 401, deliberately.** The caller IS authenticated; it is the wrong
 * client type. Answering 401 would send a plug-in into a re-login loop that could
 * never succeed, because the credential it would obtain is the one being refused.
 */
export const requireBrowserSession = createMiddleware<{
	Bindings: Env;
	Variables: SessionVariables;
}>(async (c, next) => {
	if (c.get("sessionClientType") !== "browser") {
		return c.json({ error: "browser_session_required" }, 403);
	}
	await next();
});

/**
 * **What a plug-in token may reach, as an ALLOW-LIST.** Terry approved the polarity on
 * 2026-08-15, and the polarity is the whole point.
 *
 * A deny-list — "everything except the admin surface" — makes every endpoint added later
 * reachable by a 90-day credential sitting on a laptop, unless whoever adds it remembers
 * to guard it. **Security that depends on remembering is security that lapses.** This
 * repository has already been bitten by the same polarity mistake in `.gitignore`, where
 * a new top-level directory was invisible by default.
 *
 * So a route is refused unless it is named here, and **adding one is a deliberate act**.
 *
 * Deliberately ABSENT, each for a reason:
 *
 * | Route | Why not |
 * |---|---|
 * | `POST /api/v001/requests` | The batch endpoint is the sanctioned path. Same power, one door |
 * | `POST .../withdraw` | The plug-in's job is queueing, not queue management |
 * | `/api/v001/admin/*` | A stolen laptop MUST NOT be an admin console |
 */
const PLUGIN_ALLOWED: readonly { method: string; pattern: RegExp }[] = [
	// Identify itself, and learn whether the credential still works.
	{ method: "GET", pattern: /^\/api\/v001\/me$/ },
	// The candidate list the picker is built from.
	{ method: "GET", pattern: /^\/api\/v001\/groups$/ },
	{ method: "GET", pattern: /^\/api\/v001\/groups\/[^/]+$/ },
	// Which groups the photo is already in, so the picker can prune them.
	{ method: "GET", pattern: /^\/api\/v001\/photos\/[^/]+\/groups$/ },
	// ADR-20. The warning MUST arrive before the commitment, from every client.
	{ method: "POST", pattern: /^\/api\/v001\/photos\/[^/]+\/preflight$/ },
	// The commitment itself, and the reason the plug-in exists.
	{ method: "POST", pattern: /^\/api\/v001\/requests\/batch$/ },
	// Read-only, and the user's own rows. Lets the plug-in report what happened.
	{ method: "GET", pattern: /^\/api\/v001\/queue$/ },
];

/**
 * **403, not 401.** The caller IS authenticated and is holding the wrong CLIENT TYPE.
 * A 401 would send a plug-in into a re-login loop that could never succeed, because the
 * credential it would obtain is the one being refused.
 */
export const restrictPluginScope = createMiddleware<{
	Bindings: Env;
	Variables: SessionVariables;
}>(async (c, next) => {
	if (c.get("sessionClientType") === "lrc15_plugin") {
		const path = new URL(c.req.url).pathname;
		const allowed = PLUGIN_ALLOWED.some(
			(route) => route.method === c.req.method && route.pattern.test(path),
		);
		if (!allowed) {
			return c.json({ error: "not_allowed_for_plugin" }, 403);
		}
	}
	await next();
});
