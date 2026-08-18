import { Hono } from "hono";
// JavaScript has no built-in HTML escape, and `hono/html` is already a dependency --
// ADR-14. Every interpolation below is escaped by the tag.
import { html } from "hono/html";
import { z } from "zod";
import {
	codeHash,
	looksLikeUserCode,
	newCode,
	newUserCode,
	normalizeUserCode,
} from "../device/codes.js";
import {
	requireBrowserSession,
	requireSession,
	type SessionVariables,
} from "../middleware/session.js";
import { mintSession, readSessionCookie, verifySession } from "../session.js";

/**
 * **The one place this path is spelled**, because it appears in four: the route, the
 * `returnTo` the login carries, the allow-list in `src/oauth/return-to.ts`, and the
 * `verificationUri` handed to the plug-in. Three of those are strings in different
 * files, and a rename that missed one would break the flow at a different step each
 * time.
 */
const ENTER_USER_CODE_PATH = "/auth/device-link/enter-user-code";

/**
 * The device link flow: how a Lightroom plug-in gets a credential without ever
 * holding a Flickr one.
 *
 * **This is Adobe's frob dance with FGA one hop over.** Adobe's own Flickr
 * plug-in asks Flickr for a frob, opens a browser at Flickr's auth URL carrying
 * it, and trades the frob for a durable token afterwards. It talks to Flickr
 * directly **because Adobe has no server.** FGA has one, so the frob equivalent
 * is `POST /auth/device-link/start` and the plug-in makes zero Flickr calls.
 *
 * ## Two codes, and neither can do the other's job
 *
 * | | Held by | Travels | Proves |
 * |---|---|---|---|
 * | `deviceCode` | The plug-in, only | **Never in a URL** | The poller started this flow |
 * | `userCode` | Shown on screen | Typed, or prefilled in a link | One screen matches the other |
 *
 * **The earlier draft of this design put the polling credential in the URL**, and
 * `docs/LRC-CLIENT-NOTES.md` records the correction. RFC 8628 keeps `device_code`
 * out of every URL and puts `user_code` in front of the human; this does the same.
 *
 * ## Why start and poll are UNAUTHENTICATED, and why that is not a hole
 *
 * At `start` nobody has authorized anything, so there is no session to require --
 * the whole point of the flow is obtaining one. `poll` is authenticated by
 * `deviceCode`, which is 32 bytes from `crypto.getRandomValues` and is compared
 * with `timingSafeEqual` against a stored hash.
 *
 * **They are therefore mounted OUTSIDE `/api/v001/*`'s blanket `requireSession`**
 * -- see `src/index.ts`. Registering them inside it and relying on handler
 * ordering to skip the middleware would work and would be the kind of subtlety
 * this codebase keeps warning about.
 *
 * ## Approval is BROWSER-ONLY, and that is a deliberate second rule
 *
 * `restrictPluginScope` already refuses these routes to a plug-in token, because
 * they are not on its allow-list. `requireBrowserSession` says it again, out
 * loud, because the consequence is severe enough to deserve a named rule:
 * **a plug-in token that could approve a device link could mint another plug-in
 * token, and a 90-day credential on a stolen laptop would become permanent.**
 */

export const deviceRoutes = new Hono<{
	Bindings: Env;
	Variables: SessionVariables;
}>();

/**
 * ADR-12's `no-store`, RESTATED HERE, and the restatement is the bug fix.
 *
 * **`apiRoutes` puts `Cache-Control: private, no-store` on `/api/v001/*`, and these
 * routes never see it.** They no longer live under that prefix at all -- see the
 * mount note in `src/index.ts` -- so nothing upstream applies it for them.
 *
 * That matters more here than on the rest of the API. **Every reply from these
 * four routes carries a bearer credential in its body** -- `deviceCode` from
 * `start`, the session token from `poll`. A cached copy is a credential sitting
 * in a store nobody is watching.
 *
 * **Found by re-reading the file after it passed 24 tests**, and the header was
 * `null`. A skipped middleware leaves no trace: nothing errors, nothing warns,
 * and the only symptom is an absent header nobody asserted on.
 *
 * **The pattern MUST track the route prefix, and a literal rename cannot see a
 * wildcard.** The 2026-08-18 move to `/auth/device-link/*` rewrote every exact
 * path in this file and left this glob pointing at the old prefix, which would
 * have dropped the header from all four replies while every test still passed.
 */
deviceRoutes.use("/auth/device-link/*", async (c, next) => {
	await next();
	c.header("Cache-Control", "private, no-store");
});

/**
 * **Registered BEFORE the handlers, because Hono composes middleware in
 * registration order and a handler registered first would short-circuit it.**
 *
 * That ordering mistake is the dangerous direction: the routes would keep working,
 * approval would silently need no session, and nothing would fail. `requireAdmin`
 * carries the same warning in `src/routes/api.ts` for the same reason.
 *
 * `start` and `poll` are deliberately absent -- see the header comment.
 */
deviceRoutes.use(
	"/auth/device-link/approve",
	requireSession,
	requireBrowserSession,
);
deviceRoutes.use(
	"/auth/device-link/deny",
	requireSession,
	requireBrowserSession,
);

/** What a well-behaved plug-in waits between polls. Seconds, as RFC 8628 sends it. */
const POLL_AFTER_SECONDS = 5;

/** RFC 8628's remedy for a client that polled too fast: raise its interval. */
const SLOW_DOWN_EXTRA_SECONDS = 5;

const pollBody = z.object({
	userCode: z.string().min(1).max(64),
	deviceCode: z.string().min(1).max(512),
});

const decisionBody = z.object({
	userCode: z.string().min(1).max(64),
});

/**
 * Begin a link. No credential of any kind is required or accepted.
 *
 * **The response is the ONLY time `deviceCode` exists in transit from us.** It is
 * hashed before storage, exactly as `src/session.ts` never stores a session id.
 */
deviceRoutes.post("/auth/device-link/start", async (c) => {
	// **No body is read at all.** A plug-in sending `{}`, sending nothing, or
	// sending junk MUST behave identically -- there is nothing here to configure,
	// so validating a body would only invent a way to fail. `LrHttp.post` always
	// sends something, and Lightroom attaches its own Content-Type unless told not
	// to, so a strict parse here would reject the very client this exists for.
	const deviceCode = newCode();
	const userCode = newUserCode();

	// Addressed by userCode, so the browser can reach the attempt with nothing but
	// the string on the Lightroom screen. The typed path is the real path; the
	// link is a convenience.
	const stub = c.env.DEVICE_LINK.get(c.env.DEVICE_LINK.idFromName(userCode));
	const { expiresAt } = await stub.start(await codeHash(deviceCode));

	return c.json({
		deviceCode,
		userCode,
		expiresAt,
		pollAfter: POLL_AFTER_SECONDS,
		// Built from our own config rather than the request, so a plug-in
		// cannot be pointed at somebody else's approval page by a crafted
		// call.
		//
		// **It pointed at `/link` on UI_ORIGIN until 2026-08-18, and that page
		// did not exist.** `parse()` in `web/src/lib/router.ts` resolves
		// exactly `/`, `/queue` and `/admin`; everything else is `notFound`.
		// So the plug-in told people to visit a page that said there was no
		// such page, and device linking could not complete. **The page is a
		// Worker route now**, which is why the base moved with it.
		verificationUri: new URL(
			ENTER_USER_CODE_PATH,
			c.env.API_BASE_URL,
		).toString(),
	});
});

/**
 * The plug-in's half. **`deviceCode` is the credential**, so this needs no session.
 *
 * **`approved` is single-use.** The attempt is erased the moment a token is
 * collected, so a replay finds `expired`.
 */
deviceRoutes.post("/auth/device-link/poll", async (c) => {
	const parsed = pollBody.safeParse(await c.req.json().catch(() => null));
	if (!parsed.success) return c.json({ error: "invalid_body" }, 400);

	const userCode = normalizeUserCode(parsed.data.userCode);
	if (!looksLikeUserCode(userCode)) {
		// Shape is checked before the Durable Object is touched, so garbage never
		// creates an object. `expired` rather than a distinct error, for the same
		// reason the class collapses unknown, expired and consumed into one answer.
		return c.json({ status: "expired" });
	}

	const stub = c.env.DEVICE_LINK.get(c.env.DEVICE_LINK.idFromName(userCode));
	const state = await stub.poll(await codeHash(parsed.data.deviceCode));

	if (state.kind !== "approved") {
		/**
		 * **A throttled client is told to wait LONGER, per RFC 8628.** Returning the
		 * same interval it just violated would leave a misbehaving plug-in in a tight
		 * loop forever, being refused at exactly the rate it was already polling.
		 */
		const pollAfter =
			state.kind === "slow_down"
				? POLL_AFTER_SECONDS + SLOW_DOWN_EXTRA_SECONDS
				: POLL_AFTER_SECONDS;
		return c.json({ status: state.kind, pollAfter });
	}

	/**
	 * **The token is minted HERE, at collection, not at approval.** An approved
	 * link the plug-in never collects therefore mints nothing -- no credential
	 * exists for a flow that was abandoned after the browser said yes.
	 */
	const token = await mintSession(
		c.env.DB,
		state.nsid,
		c.env.SESSION_KEY,
		"lrc15_plugin",
	);

	return c.json({ status: "approved", token });
});

/**
 * ADR-24's confirmation page, as HTML.
 *
 * **The wording is the security control, not decoration.** A device flow is phished
 * by getting somebody to approve a code that is on the ATTACKER'S screen, so the
 * page's whole job is to make "does this match Lightroom" the question being
 * answered. `src/lib/outcomes.ts` holds the same principle for the other surfaces.
 *
 * **ADR-01 is why this matters more here than in most flows.** A request that
 * reached a moderator is terminal, so a phished token pushes a stranger's photos
 * into volunteer queues and revoking it afterwards takes none of that back.
 */
function enterUserCodePage(prefill: string): ReturnType<typeof html> {
	return html`<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Link Lightroom to FlickrGroupAddr</title>
<style>
body { font: 16px/1.5 system-ui, sans-serif; margin: 3rem auto; max-width: 32rem;
       padding: 0 1rem; color: #172B4D; }
h1 { font-size: 1.35rem; }
input { font: 600 1.5rem/1 ui-monospace, Consolas, monospace; letter-spacing: .18em;
        padding: .6rem .7rem; width: 100%; box-sizing: border-box; text-align: center;
        text-transform: uppercase; border: 1px solid #DFE1E6; border-radius: 6px; }
button { font: 600 1rem/1 system-ui, sans-serif; padding: .7rem 1.2rem;
         border: 0; border-radius: 6px; cursor: pointer; }
#approve { background: #216E4E; color: #fff; }
#deny { background: transparent; color: #5E6C84; text-decoration: underline; }
.row { display: flex; gap: .75rem; align-items: center; margin-top: 1.25rem; }
.check { background: #FFF7D6; border: 1px solid #F5CD47; border-radius: 6px;
         padding: .8rem 1rem; margin: 1.25rem 0; }
#said { margin-top: 1.25rem; font-weight: 600; }
</style>
<h1>Link Lightroom to FlickrGroupAddr</h1>
<p>Lightroom is showing a code. Type it here to finish linking.</p>
<input id="code" value="${prefill}" autocomplete="off" autocapitalize="characters"
       spellcheck="false" aria-label="User code from Lightroom">
<div class="check">
  <strong>Check the code matches your Lightroom screen.</strong>
  Approving links whatever device is showing this code to your Flickr account. If a
  code arrived by email or message, do not approve it.
</div>
<div class="row">
  <button id="approve">Approve</button>
  <button id="deny">Not mine &mdash; deny</button>
</div>
<p id="said"></p>
<script>
// **JSON, not a form post, and that is a CSRF defense.** A urlencoded form submit is
// a simple request: no preflight, sent cross-origin with cookies. Requiring JSON
// forces a preflight that ADR-11's CORS rule refuses.
async function decide(path) {
  const said = document.getElementById('said');
  const userCode = document.getElementById('code').value.trim();
  if (!userCode) { said.textContent = 'Enter the code Lightroom is showing.'; return; }
  said.textContent = 'Working...';
  try {
    const res = await fetch(path, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({userCode: userCode}),
    });
    const out = await res.json();
    if (res.ok) {
      said.textContent = out.status === 'denied'
        ? 'Denied. Lightroom will stop waiting.'
        : 'Linked. You can go back to Lightroom.';
      return;
    }
    // **404 covers unknown, expired and already-used alike**, deliberately, so a
    // signed-in person probing codes learns nothing about which ones are live. The
    // wording here MUST stay equally uninformative.
    said.textContent = res.status === 404
      ? 'That code is not valid. Check Lightroom and try again.'
      : 'Something went wrong. Try again.';
  } catch (e) {
    said.textContent = 'Could not reach the server. Try again.';
  }
}
document.getElementById('approve').addEventListener(
  'click', () => decide('/auth/device-link/approve'));
document.getElementById('deny').addEventListener(
  'click', () => decide('/auth/device-link/deny'));
</script>`;
}

/**
 * The page a person lands on, and the only route here that serves HTML.
 *
 * **It closes a live defect rather than adding a feature.** Until 2026-08-18 `start`
 * handed the plug-in `new URL("/link", UI_ORIGIN)`, and `/link` did not exist --
 * `parse()` in `web/src/lib/router.ts` resolves exactly `/`, `/queue` and `/admin`
 * and calls everything else `notFound`. **So the plug-in told people to visit a page
 * that said there was no such page, and device linking could not complete.**
 *
 * **Terry ruled the page belongs to the Worker**, and the reason is the redirect
 * below: the session cookie is `HttpOnly`, so a static SPA page cannot see whether
 * you are signed in. Only the server can, and journey step 9 requires it to answer
 * with a redirect rather than a blank screen.
 *
 * ## Why this route cannot use `requireSession`
 *
 * **That middleware answers `401` with JSON**, which is right for an API and useless
 * to a person in a browser. This checks the cookie itself and REDIRECTS to
 * `/auth/flickr/login`, carrying `returnTo` so the callback comes back here. It is
 * the one place in the codebase where an absent session is not an error.
 *
 * **A BEARER TOKEN IS DELIBERATELY NOT ACCEPTED.** `presentedToken` in the session
 * middleware falls back to `Authorization`, which is how the plug-in authenticates.
 * **A plug-in MUST NOT be able to drive its own approval page**, so this reads the
 * cookie and nothing else -- `requireBrowserSession` says the same thing one layer
 * up, and this route needs the rule before that layer would run.
 *
 * ## The form posts JSON, and that is a CSRF defense rather than a style choice
 *
 * **`approve` takes `application/json` and MUST keep taking only that.** A plain
 * `<form method=post>` sends `application/x-www-form-urlencoded`, which browsers
 * treat as a SIMPLE REQUEST -- no preflight, sent cross-origin with cookies
 * attached. **Any website could then approve a device link on a signed-in user's
 * behalf.** Requiring JSON forces a preflight that ADR-11's CORS rule refuses.
 *
 * So the page ships a small `fetch` rather than a form submit. That is the whole
 * reason, and a future "simplification" back to a native form would hand away the
 * protection silently.
 */
deviceRoutes.get("/auth/device-link/enter-user-code", async (c) => {
	const cookie = readSessionCookie(c);
	const session =
		cookie === undefined
			? null
			: await verifySession(c.env.DB, cookie, c.env.SESSION_KEY);

	if (session === null) {
		// Journey step 9. **Built from our own config, never from the request**, so
		// the destination cannot be chosen by whoever sent the person here.
		const login = new URL("/auth/flickr/login", c.env.API_BASE_URL);
		login.searchParams.set("returnTo", ENTER_USER_CODE_PATH);
		return c.redirect(login.toString(), 302);
	}

	if (session.clientType !== "browser") {
		// A plug-in token in a cookie should be impossible. Saying so out loud costs
		// one branch and removes the need for anyone to reason about whether it is.
		return c.text("This page needs a browser sign-in.", 403);
	}

	// **Prefilled, never auto-submitted.** ADR-24: the confirmation page is the only
	// defense against device-flow phishing, so the person MUST see the code and
	// press the button. A link that approved on load would be the attack.
	const prefill = c.req.query("code") ?? "";

	return c.html(enterUserCodePage(prefill));
});

/**
 * The browser's half. **Signed in, and browser-only.**
 *
 * **The page MUST have shown the `userCode` and asked the person to confirm it
 * matches their Lightroom screen before calling this.** That confirmation is the
 * only defense against device-flow phishing, and it matters more here than in
 * most flows: under ADR-01 a request that reached a moderator is terminal, so a
 * phished token can push a stranger's photos into volunteer queues and revoking
 * it afterwards takes none of that back.
 *
 * **Prefilling the code from the query string is fine. Auto-approving from it is
 * not**, and no route here will do it -- approval is always a POST a person had
 * to cause.
 */
deviceRoutes.post("/auth/device-link/approve", async (c) => {
	const parsed = decisionBody.safeParse(await c.req.json().catch(() => null));
	if (!parsed.success) return c.json({ error: "invalid_body" }, 400);

	const userCode = normalizeUserCode(parsed.data.userCode);
	if (!looksLikeUserCode(userCode)) {
		return c.json({ error: "unknown_code" }, 404);
	}

	const stub = c.env.DEVICE_LINK.get(c.env.DEVICE_LINK.idFromName(userCode));
	const ok = await stub.approve(c.get("nsid"));

	// 404 for unknown and expired alike. A signed-in user probing codes learns
	// nothing about which ones are live.
	return ok
		? c.json({ status: "approved" })
		: c.json({ error: "unknown_code" }, 404);
});

/**
 * The person said no.
 *
 * **Recorded rather than deleted**, so the waiting plug-in can say "you declined"
 * instead of timing out. That is ADR-01's habit pointed at a different surface:
 * **a refusal MUST NOT look like a failure.**
 */
deviceRoutes.post("/auth/device-link/deny", async (c) => {
	const parsed = decisionBody.safeParse(await c.req.json().catch(() => null));
	if (!parsed.success) return c.json({ error: "invalid_body" }, 400);

	const userCode = normalizeUserCode(parsed.data.userCode);
	if (!looksLikeUserCode(userCode)) {
		return c.json({ error: "unknown_code" }, 404);
	}

	const stub = c.env.DEVICE_LINK.get(c.env.DEVICE_LINK.idFromName(userCode));
	const ok = await stub.deny();

	return ok
		? c.json({ status: "denied" })
		: c.json({ error: "unknown_code" }, 404);
});
