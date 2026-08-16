import { Hono } from "hono";
import { upsertUser } from "../db/users.js";
import {
	buildAuthorizeUrl,
	exchangeAccessToken,
	fetchRequestToken,
} from "../flickr/oauth.js";
import { safeReturnPath } from "../oauth/return-to.js";
import {
	clearSessionCookie,
	mintSession,
	readSessionCookie,
	revokeSession,
	setSessionCookie,
} from "../session.js";

/** The three legs of the Flickr login. **The order below is load-bearing.** */

export const oauthRoutes = new Hono<{ Bindings: Env }>();

/**
 * Where the browser lands when the login finishes.
 *
 * **`returnPath` is composed here rather than trusted from anywhere**, and it has already
 * passed `safeReturnPath`. Building it against `UI_ORIGIN` means even a wrong validator
 * cannot produce an off-site destination.
 */
function uiUrl(env: Env, outcome: string, returnPath?: string): string {
	const url =
		returnPath === undefined
			? new URL(env.UI_ORIGIN)
			: new URL(returnPath, env.UI_ORIGIN);
	url.searchParams.set("login", outcome);
	return url.toString();
}

oauthRoutes.get("/oauth/login", async (c) => {
	const callbackUrl = `${c.env.API_BASE_URL}/oauth/callback`;

	// ADR-11. Validated HERE, at the edge, so nothing downstream handles a raw value.
	// Null means "no usable destination", which uiUrl reads as the app root.
	const returnPath =
		safeReturnPath(c.req.query("returnTo"), c.env.UI_ORIGIN) ?? undefined;

	const temporary = await fetchRequestToken(
		c.env.FLICKR_CONSUMER_KEY,
		c.env.FLICKR_CONSUMER_SECRET,
		callbackUrl,
	);

	// ADR-08. Addressed by the request token, the only identifier that exists yet.
	const stub = c.env.OAUTH_LOGIN.get(
		c.env.OAUTH_LOGIN.idFromName(temporary.token),
	);

	// MUST complete before the redirect. If the browser reached Flickr and came back
	// faster than this write, the callback would find nothing -- rare, real, and
	// near-impossible to reproduce.
	await stub.start(temporary.token, temporary.tokenSecret, returnPath);

	return c.redirect(buildAuthorizeUrl(temporary.token), 302);
});

/** Every failure redirects rather than renders: a browser navigation lands here, so the
 *  response is a page a person sees, not an API reply anything parses. */
oauthRoutes.get("/oauth/callback", async (c) => {
	const requestToken = c.req.query("oauth_token");
	const verifier = c.req.query("oauth_verifier");

	if (requestToken === undefined || verifier === undefined) {
		return c.redirect(uiUrl(c.env, "invalid"), 302);
	}

	const stub = c.env.OAUTH_LOGIN.get(
		c.env.OAUTH_LOGIN.idFromName(requestToken),
	);

	// Null covers unknown, already-consumed and expired. All three mean "start over".
	const attempt = await stub.consume(requestToken);
	if (attempt === null) {
		return c.redirect(uiUrl(c.env, "expired"), 302);
	}

	const access = await exchangeAccessToken(
		c.env.FLICKR_CONSUMER_KEY,
		c.env.FLICKR_CONSUMER_SECRET,
		requestToken,
		attempt.requestTokenSecret,
		verifier,
	);

	// Store BEFORE minting the session. A cookie handed to a user whose tokens failed to
	// persist is a session that can never do anything, and it fails somewhere unrelated.
	await upsertUser(
		c.env.DB,
		access.nsid,
		access.username,
		{ token: access.token, tokenSecret: access.tokenSecret },
		c.env.TOKEN_KEY,
	);

	setSessionCookie(
		c,
		await mintSession(c.env.DB, access.nsid, c.env.SESSION_KEY),
	);

	// **The destination comes out of the Durable Object, never out of this request.**
	// Flickr chose the query string that reached us; it did not choose where the user
	// goes next. Before 2026-08-16 this always landed on the app root, which stranded
	// any flow that began somewhere else -- the device-link page most of all, because a
	// user who signed in mid-link arrived home with their code gone.
	return c.redirect(uiUrl(c.env, "ok", attempt.returnPath), 302);
});

/**
 * Ends the session, **on the server as well as in the browser.**
 *
 * **This is what opaque sessions bought.** The stateless cookie could only be dropped
 * from the browser; whoever else held a copy kept a working credential until it
 * expired. Deleting the row kills it for everyone at once.
 *
 * **The row is deleted BEFORE the cookie is cleared.** Reversed, a failure between the
 * two leaves a user who believes they signed out and a session that still works.
 *
 * The Flickr token deliberately survives -- cutting FGA off entirely happens at
 * Flickr, which is both more thorough and outside our control.
 */
oauthRoutes.post("/oauth/logout", async (c) => {
	const cookie = readSessionCookie(c);
	if (cookie !== undefined) await revokeSession(c.env.DB, cookie);

	clearSessionCookie(c);
	return c.json({ status: "ok" });
});
