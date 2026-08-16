import { createMiddleware } from "hono/factory";
import {
	readSessionCookie,
	type SessionKind,
	verifySession,
} from "../session.js";

/** Sessions are opaque handles, so verification is a signature check AND a D1 read.
 *  The HMAC runs first: a forger spraying random cookies never reaches the database. */
export type SessionVariables = { nsid: string; sessionKind: SessionKind };

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
	c.set("sessionKind", session.kind);
	await next();
	return undefined;
});

/**
 * **Refuses a plug-in token, and this is where the longer plug-in lifetime is paid for.**
 *
 * A plug-in token lives for 90 days on a laptop, protected by nothing but the filesystem.
 * **So it MUST NOT be able to revoke other credentials or change the account** — if it
 * could, whoever picks up that laptop can lock the real owner out of their own Flickr
 * queue, and the owner's remedy would be the very endpoint the thief just used.
 *
 * **Register it AFTER `requireSession`**, which is what puts `sessionKind` on the
 * context. Registered before, this would read `undefined` and refuse everybody — a
 * failure that is at least loud. The reverse ordering mistake is the dangerous one, and
 * `requireAdmin` carries the same warning for the same reason.
 *
 * **403 rather than 401, deliberately.** The caller IS authenticated; it is the wrong
 * kind of credential. Answering 401 would send a plug-in into a re-login loop that could
 * never succeed, because the credential it would obtain is the one being refused.
 */
export const requireBrowserSession = createMiddleware<{
	Bindings: Env;
	Variables: SessionVariables;
}>(async (c, next) => {
	if (c.get("sessionKind") !== "browser") {
		return c.json({ error: "browser_session_required" }, 403);
	}
	await next();
	return undefined;
});
