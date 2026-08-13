import { Hono } from "hono";
import { cors } from "hono/cors";
import { oauthRoutes } from "./routes/oauth.js";

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

app.get("/health", (c) => c.json({ status: "ok" }));

export default {
	fetch: app.fetch,

	/**
	 * ADR-04: the nightly sweep is the v1 work engine. Not yet implemented --
	 * it needs the Flickr group-add call, which is the next piece of work.
	 */
	async scheduled(
		_controller: ScheduledController,
		_env: Env,
		_ctx: ExecutionContext,
	): Promise<void> {
		// Intentionally empty for now.
	},
} satisfies ExportedHandler<Env>;
