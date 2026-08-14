import { Hono } from "hono";
import { cors } from "hono/cors";
import { createAttempt } from "./adds/attempt.js";
import { apiRoutes } from "./routes/api.js";
import { oauthRoutes } from "./routes/oauth.js";
import { sweep } from "./sweep.js";

export { OAuthLoginAttempt } from "./oauth/login-attempt.js";

const app = new Hono<{ Bindings: Env }>();

/**
 * ADR-12's CORS contract, and the one place in this codebase where a two-line
 * shortcut is catastrophic.
 *
 * The permitted origin is compared against the configured allowlist and the
 * response echoes OUR OWN constant, never the request's `Origin` header.
 * Reflecting the header instead -- which is what makes the error go away during
 * development -- combined with `credentials: true` means any website on the
 * internet can make authenticated calls as a logged-in FGA user and read the
 * replies.
 *
 * `Access-Control-Allow-Origin: *` is not an option either: browsers refuse a
 * wildcard whenever credentials are included.
 */
app.use("/v001/*", (c, next) =>
	cors({
		origin: (origin) => (origin === c.env.UI_ORIGIN ? c.env.UI_ORIGIN : null),
		credentials: true,
		allowMethods: ["GET", "POST", "DELETE", "OPTIONS"],
		allowHeaders: ["Content-Type"],
		maxAge: 86400,
	})(c, next),
);

app.route("/", oauthRoutes);
app.route("/", apiRoutes);

app.get("/health", (c) => c.json({ status: "ok" }));

export default {
	fetch: app.fetch,

	/**
	 * ADR-04's nightly work engine.
	 *
	 * The report is logged as structured JSON rather than prose so a bad night is
	 * queryable rather than readable-if-you-happen-to-look. `stoppedOnThrottle`
	 * is expected and is not an error -- it is the product working.
	 */
	async scheduled(
		_controller: ScheduledController,
		env: Env,
		_ctx: ExecutionContext,
	): Promise<void> {
		const report = await sweep(env.DB, createAttempt(env));
		console.log(JSON.stringify({ event: "nightly_sweep", ...report }));
	},
} satisfies ExportedHandler<Env>;
