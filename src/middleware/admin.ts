import { createMiddleware } from "hono/factory";
import { checkAdmin } from "../admin/allowlist.js";
import type { SessionVariables } from "./session.js";

/**
 * Gate for `/api/v001/admin/*`. **MUST run after `requireSession`**, which is what puts
 * `nsid` on the context.
 *
 * **A non-admin gets 404, not 403**, and the difference is the point. A 403 confirms the
 * admin surface exists and that this account simply is not on the list, which is a fact
 * worth nothing to the caller and worth something to anyone probing. A 404 says only that
 * there is no such route, which is exactly what a non-admin should believe.
 *
 * **A broken `ADMIN_NSIDS` denies everyone and logs.** The dashboard going dark is a
 * visible, cheap failure. The alternative -- treating an unparseable allowlist as "no
 * restriction" -- opens operational data to every signed-in user and reports nothing.
 */
export const requireAdmin = createMiddleware<{
	Bindings: Env;
	Variables: SessionVariables;
}>(async (c, next) => {
	const { admin, configError } = checkAdmin(c.get("nsid"), c.env.ADMIN_NSIDS);

	if (configError !== null) {
		// Structured, so a dark dashboard is diagnosable from logs rather than by
		// guessing. The NSID is not logged: it is the one piece of user identity this
		// project holds, and a config error is not a reason to start recording it.
		console.log(
			JSON.stringify({ event: "admin_config_error", detail: configError }),
		);
	}

	if (!admin) return c.json({ error: "not_found" }, 404);

	await next();
	return undefined;
});
