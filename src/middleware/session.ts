import { createMiddleware } from "hono/factory";
import { readSessionCookie, verifySession } from "../session.js";

/** Sessions are opaque handles, so verification is a signature check AND a D1 read.
 *  The HMAC runs first: a forger spraying random cookies never reaches the database. */
export type SessionVariables = { nsid: string };

export const requireSession = createMiddleware<{
	Bindings: Env;
	Variables: SessionVariables;
}>(async (c, next) => {
	const cookie = readSessionCookie(c);

	if (cookie === undefined) {
		return c.json({ error: "not_authenticated" }, 401);
	}

	const nsid = await verifySession(c.env.DB, cookie, c.env.SESSION_KEY);
	if (nsid === null) {
		// Tampered, expired, revoked, wrong key, malformed, unknown -- one answer for
		// all six. Telling them apart tells an attacker which lever to pull.
		return c.json({ error: "not_authenticated" }, 401);
	}

	c.set("nsid", nsid);
	await next();
	return undefined;
});
