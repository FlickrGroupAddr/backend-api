import { Hono } from "hono";
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
import { mintSession } from "../session.js";

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
		// Built from UI_ORIGIN rather than the request, so a plug-in cannot be
		// pointed at somebody else's approval page by a crafted call.
		verificationUri: new URL("/link", c.env.UI_ORIGIN).toString(),
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
