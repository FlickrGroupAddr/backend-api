import { Hono } from "hono";
import { upsertUser } from "../db/users.js";
import {
	buildAuthorizeUrl,
	exchangeAccessToken,
	fetchRequestToken,
} from "../flickr/oauth.js";
import {
	clearSessionCookie,
	mintSession,
	setSessionCookie,
} from "../session.js";

/**
 * The three legs of the Flickr login, wired together.
 *
 * This is the only place ADR-02's Durable Object, ADR-03's encryption and
 * ADR-06's session cookie all meet, and the order they happen in is
 * load-bearing rather than incidental.
 */

export const oauthRoutes = new Hono<{ Bindings: Env }>();

/** Where the browser is sent once a login finishes, succeed or fail. */
function uiUrl(env: Env, outcome: string): string {
	const url = new URL(env.UI_ORIGIN);
	url.searchParams.set("login", outcome);
	return url.toString();
}

/**
 * Leg 1 and 2. Gets temporary credentials, parks the secret, sends the user to
 * Flickr.
 */
oauthRoutes.get("/oauth/login", async (c) => {
	const callbackUrl = `${c.env.API_BASE_URL}/oauth/callback`;

	const temporary = await fetchRequestToken(
		c.env.FLICKR_CONSUMER_KEY,
		c.env.FLICKR_CONSUMER_SECRET,
		callbackUrl,
	);

	// ADR-02. The object is addressed by the request token, which is the only
	// identifier that exists at this point -- the user has authorized nothing, so
	// FGA holds no identity for them yet.
	const stub = c.env.OAUTH_LOGIN.get(
		c.env.OAUTH_LOGIN.idFromName(temporary.token),
	);

	// MUST complete before the redirect. If the browser reached Flickr first and
	// came back faster than this write, the callback would find nothing -- a race
	// that would be rare, real, and near-impossible to reproduce.
	await stub.start(temporary.token, temporary.tokenSecret);

	return c.redirect(buildAuthorizeUrl(temporary.token), 302);
});

/**
 * Leg 3. Flickr sends the user back here with a verifier.
 *
 * Every failure path redirects to the UI with an outcome rather than rendering
 * an error: this endpoint is reached by a browser navigation, so its response is
 * a page the user sees, not an API reply anything parses.
 */
oauthRoutes.get("/oauth/callback", async (c) => {
	const requestToken = c.req.query("oauth_token");
	const verifier = c.req.query("oauth_verifier");

	if (requestToken === undefined || verifier === undefined) {
		return c.redirect(uiUrl(c.env, "invalid"), 302);
	}

	const stub = c.env.OAUTH_LOGIN.get(
		c.env.OAUTH_LOGIN.idFromName(requestToken),
	);

	// Single-use by construction. Null covers unknown, already-consumed and
	// expired, and the correct response to all three is the same: start over.
	// Telling them apart would only help someone probing the endpoint.
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

	// Store before minting the session. A cookie handed out for a user whose
	// tokens failed to persist would be a session that can never do anything,
	// and the failure would surface later and somewhere unrelated.
	await upsertUser(
		c.env.DB,
		access.nsid,
		access.username,
		{ token: access.token, tokenSecret: access.tokenSecret },
		c.env.TOKEN_KEY,
	);

	// ADR-12's attributes live in session.ts, which is the only place that knows
	// them. They used to be spelled out here AND described by a helper nothing
	// called, so the tests asserted on the helper and could not have noticed this
	// copy losing an attribute.
	setSessionCookie(c, await mintSession(access.nsid, c.env.SESSION_KEY));

	return c.redirect(uiUrl(c.env, "ok"), 302);
});

/**
 * Clears the session cookie.
 *
 * This ends the browser's session and nothing else. ADR-06 accepts that there
 * is no server-side revocation, and the Flickr token deliberately survives --
 * a user who wants to cut FGA off entirely does that at Flickr, which is both
 * more thorough and outside FGA's control.
 */
oauthRoutes.post("/oauth/logout", (c) => {
	clearSessionCookie(c);
	return c.json({ status: "ok" });
});
