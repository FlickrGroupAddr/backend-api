import { Hono } from "hono";
import { cors } from "hono/cors";
// JavaScript has no built-in HTML escape. `hono/html` was already a dependency --
// ADR-14, found only after hand-writing one.
import { html } from "hono/html";
import { createAttempt } from "./adds/attempt.js";
import { getUsername } from "./db/users.js";
import { apiRoutes } from "./routes/api.js";
import { deviceRoutes } from "./routes/device.js";
import { oauthRoutes } from "./routes/oauth.js";
import { readSessionCookie, verifySession } from "./session.js";
import { sweep } from "./sweep.js";

export { DeviceLinkAttempt } from "./device/link-attempt.js";
export { OAuthLoginAttempt } from "./oauth/login-attempt.js";

const app = new Hono<{ Bindings: Env }>();

/**
 * A `www` guard. **It does NOT currently handle `www` traffic, and that is not a bug in
 * this function.**
 *
 * `www.flickrgroupaddr.com` is not routed to this Worker — see the note in
 * `wrangler.jsonc`. Routing it here was tried on 2026-08-14 and failed in production:
 * `not_found_handling: "single-page-application"` serves `index.html` before the Worker
 * is invoked for any path outside `run_worker_first`, so this middleware never ran and
 * `www` served the whole application on a second hostname. **The redirect belongs in a
 * Cloudflare Redirect Rule**, which runs at the edge ahead of both Workers and assets.
 *
 * **It stays as a guard against that exact mistake being repeated.** If anything ever
 * routes a `www` hostname here again, this bounces it instead of serving it.
 *
 * **Registered FIRST, before CORS and before any route.** A `www` request must never
 * reach session handling, because anything that set a cookie there would set it on a
 * hostname the rest of the system does not consider its own.
 *
 * **301, not 302.** The apex is the permanent home and browsers may cache that forever,
 * which is the intent. A 302 would ask every visitor to make the round trip again.
 *
 * **The path and query survive**, so a deep link to `www.flickrgroupaddr.com/queue`
 * lands on `flickrgroupaddr.com/queue` rather than the front page. A redirect that
 * silently drops where you were going is worse than no redirect.
 *
 * **Matched on the `www.` prefix rather than against `UI_ORIGIN`**, so this keeps
 * working if the apex ever changes, and so it cannot accidentally redirect the apex to
 * itself and loop.
 */
app.use("*", async (c, next) => {
	const url = new URL(c.req.url);

	if (url.hostname.startsWith("www.")) {
		url.hostname = url.hostname.slice(4);
		return c.redirect(url.toString(), 301);
	}

	await next();
});

/**
 * ADR-11's CORS contract, and **the one place in this codebase where a two-line shortcut
 * is catastrophic.**
 *
 * The response echoes OUR OWN configured constant, never the request's `Origin` header.
 * Reflecting the header instead -- which is what makes the error go away during
 * development -- combined with `credentials: true` lets **any website on the internet
 * make authenticated calls as a logged-in FGA user and read the replies.**
 *
 * A wildcard is not an option either: browsers refuse one when credentials are included.
 *
 * **ADR-18 makes the UI same-origin, which makes this middleware inert rather than
 * unnecessary.** A same-origin request sends no `Origin` header worth checking, so this
 * never fires in normal use. It stays for two reasons: the reflection prohibition MUST
 * survive any future second origin, and a control that is deleted because it is
 * currently unreachable is a control nobody restores when it becomes reachable again.
 */
app.use("/api/v001/*", (c, next) =>
	cors({
		origin: (origin) => (origin === c.env.UI_ORIGIN ? c.env.UI_ORIGIN : null),
		credentials: true,
		allowMethods: ["GET", "POST", "DELETE", "OPTIONS"],
		allowHeaders: ["Content-Type"],
		maxAge: 86400,
	})(c, next),
);

/**
 * **MOUNTED BEFORE `apiRoutes`, and the order is load-bearing.**
 *
 * `apiRoutes` registers `requireSession` on the blanket pattern `/api/v001/*`.
 * Hono merges every sub-app into one router and matches middleware by path, so a
 * device route registered after it would inherit that middleware -- and
 * `POST /api/v001/device/start` MUST be reachable with no credential at all,
 * because obtaining one is the entire point of the flow.
 *
 * **Mounting first is what keeps the blanket rule blanket.** The alternative --
 * narrowing `requireSession`'s pattern to spell out every authenticated route --
 * would turn a deny-by-default rule into a list somebody has to remember to
 * extend, which is the polarity mistake `restrictPluginScope` exists to avoid.
 *
 * `approve` and `deny` register their own `requireSession` inside `deviceRoutes`,
 * so nothing here is unauthenticated by accident.
 */
app.route("/", deviceRoutes);

app.route("/", oauthRoutes);
app.route("/", apiRoutes);

app.get("/health", (c) => c.json({ status: "ok" }));

/**
 * A diagnostic page, for local development and for confirming a deploy.
 *
 * **It reports the SESSION, never the redirect.** `?login=ok` only means the callback
 * believed it succeeded; a verified cookie means the browser actually kept what it was
 * handed. Those two agree right up until something is wrong, which is the only moment
 * anyone reads this page carefully.
 *
 * **It lives at `/api/debug` and NOT at `/`, because ADR-18 gives `/` to the Svelte app
 * shell.** A Worker route at `/` would shadow `index.html` for every visitor.
 */
app.get("/api/debug", async (c) => {
	const outcome = c.req.query("login");

	const cookie = readSessionCookie(c);
	const nsid =
		cookie === undefined
			? null
			: // `verifySession` now reports the CLIENT TYPE as well as the owner,
				// and this page only ever wanted the owner.
				((await verifySession(c.env.DB, cookie, c.env.SESSION_KEY))?.nsid ??
				null);

	// Stays a PLAIN string: every `html` interpolation below is escaped, so pre-escaping
	// here would double-encode it.
	const username = nsid === null ? null : await getUsername(c.env.DB, nsid);
	const who =
		username === null ? (nsid ?? "") : `${username} (NSID: ${nsid ?? ""})`;

	let session: ReturnType<typeof html> | string;
	if (nsid !== null) {
		session = html`<p><strong>Signed in as <code>${who}</code></strong><br>
<small>Read from the session cookie and signature-verified just now, not from the redirect.</small></p>`;
	} else if (outcome === "ok") {
		session = html`<p><strong>The callback reported success, but no valid session cookie came back.</strong><br>
<small>That is a cookie problem rather than a login problem -- check that the browser is not blocking it.</small></p>`;
	} else {
		session = html`<p>Not signed in.</p>`;
	}

	let banner: ReturnType<typeof html> | string = "";
	if (outcome === "expired") {
		banner = html`<p><strong>That login attempt expired or was already used.</strong> Start again.</p>`;
	} else if (outcome === "invalid") {
		banner = html`<p><strong>Flickr sent back an incomplete callback.</strong> Start again.</p>`;
	}

	return c.html(
		html`<!doctype html><meta charset="utf-8">
<title>FlickrGroupAddr API</title>
<style>body{font:16px/1.5 system-ui,sans-serif;margin:3rem auto;max-width:40rem;padding:0 1rem}
code{background:#f4f4f5;padding:.1em .35em;border-radius:3px}</style>
<h1>FlickrGroupAddr API</h1>
${session}
${banner}
<ul>
  <li><a href="/">The app</a></li>
  <li><a href="/oauth/login">Log in with Flickr</a></li>
  <li><a href="/api/v001/groups">Your groups, with throttle and moderation info</a></li>
  <li><a href="/api/v001/queue">Your queue</a></li>
  <li><a href="/health">Health</a></li>
</ul>
<p>API base <code>${c.env.API_BASE_URL}</code><br>
UI origin <code>${c.env.UI_ORIGIN}</code></p>`,
	);
});

export default {
	fetch: app.fetch,

	/** ADR-06. **Logged as structured JSON so a bad night is queryable**, rather than
	 *  readable-if-somebody-happens-to-look. `stoppedOnThrottle` is expected and is not
	 *  an error -- it is the product working. */
	async scheduled(
		_controller: ScheduledController,
		env: Env,
		_ctx: ExecutionContext,
	): Promise<void> {
		const report = await sweep(env.DB, createAttempt(env));
		console.log(JSON.stringify({ event: "nightly_sweep", ...report }));
	},
} satisfies ExportedHandler<Env>;
