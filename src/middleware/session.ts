import { createMiddleware } from "hono/factory";
import { readSessionCookie, verifySession } from "../session.js";

/** ADR-10 sessions are stateless, so verifying the signature IS the lookup. No D1 read. */
export type SessionVariables = { nsid: string };

export const requireSession = createMiddleware<{
	Bindings: Env;
	Variables: SessionVariables;
}>(async (c, next) => {
	const cookie = readSessionCookie(c);

	if (cookie === undefined) {
		return c.json({ error: "not_authenticated" }, 401);
	}

	const nsid = await verifySession(cookie, c.env.SESSION_KEY);
	if (nsid === null) {
		// Tampered, expired, wrong key, malformed -- one answer for all four.
		return c.json({ error: "not_authenticated" }, 401);
	}

	c.set("nsid", nsid);
	await next();
	return undefined;
});
