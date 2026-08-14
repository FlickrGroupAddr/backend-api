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

/**
 * A landing page, for local development and for confirming a deploy.
 *
 * In production the real UI lives on a different origin (ADR-12), so nothing
 * routes here. During local development the OAuth callback redirects to
 * `UI_ORIGIN`, which is localhost -- and landing on a bare 404 after a
 * successful login is a confusing way to discover that it worked.
 *
 * It reports the two configured origins deliberately. Neither is a secret --
 * both are committed in `wrangler.jsonc` -- and seeing which values the Worker
 * actually resolved is the quickest way to catch a callback pointing at the
 * wrong host, which otherwise fails inside Flickr's redirect with nothing
 * useful to read.
 */
app.get("/", (c) => {
	const outcome = c.req.query("login");

	const banner =
		outcome === "ok"
			? "<p><strong>Logged in.</strong> The session cookie is set.</p>"
			: outcome === "expired"
				? "<p><strong>That login attempt expired or was already used.</strong> Start again.</p>"
				: outcome === "invalid"
					? "<p><strong>Flickr sent back an incomplete callback.</strong> Start again.</p>"
					: "";

	return c.html(
		`<!doctype html><meta charset="utf-8">
<title>FlickrGroupAddr API</title>
<style>body{font:16px/1.5 system-ui,sans-serif;margin:3rem auto;max-width:40rem;padding:0 1rem}
code{background:#f4f4f5;padding:.1em .35em;border-radius:3px}</style>
<h1>FlickrGroupAddr API</h1>
${banner}
<ul>
  <li><a href="/oauth/login">Log in with Flickr</a></li>
  <li><a href="/v001/groups">Your groups, with throttle and moderation info</a></li>
  <li><a href="/v001/queue">Your queue</a></li>
  <li><a href="/health">Health</a></li>
</ul>
<p>API base <code>${c.env.API_BASE_URL}</code><br>
UI origin <code>${c.env.UI_ORIGIN}</code></p>`,
	);
});

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
