import { Hono } from "hono";
import { getCookie } from "hono/cookie";
import { cors } from "hono/cors";
// Hono's escaping tagged template. JavaScript has no built-in HTML escape, but
// this dependency was already here -- ADR-14, found only after hand-writing one.
import { html } from "hono/html";
import { createAttempt } from "./adds/attempt.js";
import { getUsername } from "./db/users.js";
import { apiRoutes } from "./routes/api.js";
import { oauthRoutes } from "./routes/oauth.js";
import { SESSION_COOKIE, verifySession } from "./session.js";
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
 * ADR-12 puts the real UI on a different origin, at which point nothing routes
 * here. Until the domain lands, `UI_ORIGIN` is this same host, so the OAuth
 * callback comes back to this page -- and a bare 404 is a confusing way to
 * discover that a login worked.
 *
 * **It reports the SESSION, never the redirect.** `?login=ok` only means the
 * callback believed it succeeded; a verified cookie means the browser actually
 * kept what it was handed. Those two agree right up until something is wrong,
 * which is the only moment anyone reads this page carefully.
 *
 * It also prints the two configured origins deliberately. Neither is a secret --
 * both are committed in `wrangler.jsonc` -- and seeing which values the Worker
 * actually resolved is the quickest way to catch a callback pointing at the
 * wrong host, which otherwise fails inside Flickr's redirect with nothing
 * useful to read.
 */
app.get("/", async (c) => {
	const outcome = c.req.query("login");

	// The NSID is free here: it is the `sub` claim of the cookie the Worker just
	// verified, so showing it costs no database read. It is also not a secret --
	// every Flickr NSID is public -- and the signature is what makes it
	// trustworthy rather than the value itself.
	const cookie = getCookie(c, SESSION_COOKIE);
	const nsid =
		cookie === undefined
			? null
			: await verifySession(cookie, c.env.SESSION_KEY);

	// The display name is the one value here that costs a database read, and the
	// only one FGA does not control -- Flickr does. It falls back to the NSID
	// alone rather than failing, because a missing name is cosmetic while the
	// identity is the point.
	//
	// Note this stays a PLAIN string. Every `html` interpolation below is escaped
	// by Hono, so pre-escaping here would double-encode it.
	const username = nsid === null ? null : await getUsername(c.env.DB, nsid);
	const who =
		username === null ? (nsid ?? "") : `${username} (NSID: ${nsid ?? ""})`;

	// Report the SESSION, not the redirect. `?login=ok` only says the callback
	// believed it succeeded; a valid cookie says the browser actually kept what
	// it was given. Those come apart when a cookie fails to stick, and a page
	// that trusted the query string would cheerfully claim success anyway.
	const session =
		nsid !== null
			? html`<p><strong>Signed in as <code>${who}</code></strong><br>
<small>Read from the session cookie and signature-verified just now, not from the redirect.</small></p>`
			: outcome === "ok"
				? html`<p><strong>The callback reported success, but no valid session cookie came back.</strong><br>
<small>That is a cookie problem rather than a login problem -- check that the browser is not blocking it.</small></p>`
				: html`<p>Not signed in.</p>`;

	const banner =
		outcome === "expired"
			? html`<p><strong>That login attempt expired or was already used.</strong> Start again.</p>`
			: outcome === "invalid"
				? html`<p><strong>Flickr sent back an incomplete callback.</strong> Start again.</p>`
				: "";

	// `html` escapes every interpolated value, and leaves nested `html` results
	// alone because they are already marked escaped. That is the whole reason
	// `session` and `banner` are built with it too.
	return c.html(
		html`<!doctype html><meta charset="utf-8">
<title>FlickrGroupAddr API</title>
<style>body{font:16px/1.5 system-ui,sans-serif;margin:3rem auto;max-width:40rem;padding:0 1rem}
code{background:#f4f4f5;padding:.1em .35em;border-radius:3px}</style>
<h1>FlickrGroupAddr API</h1>
${session}
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
