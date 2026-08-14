import { createMiddleware } from "hono/factory";
import { readSessionCookie, verifySession } from "../session.js";

/**
 * Requires a valid session cookie and puts the NSID on the context.
 *
 * ADR-06's session is stateless, so this costs no database read -- verifying the
 * signature IS the lookup.
 */
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
		// Tampered, expired, wrong key, malformed -- all the same answer. Telling
		// them apart would only help someone probing the endpoint.
		return c.json({ error: "not_authenticated" }, 401);
	}

	c.set("nsid", nsid);
	await next();
	return undefined;
});
