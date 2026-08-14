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

/** The three legs of the Flickr login. **The order below is load-bearing.** */

export const oauthRoutes = new Hono<{ Bindings: Env }>();

function uiUrl(env: Env, outcome: string): string {
	const url = new URL(env.UI_ORIGIN);
	url.searchParams.set("login", outcome);
	return url.toString();
}

oauthRoutes.get("/oauth/login", async (c) => {
	const callbackUrl = `${c.env.API_BASE_URL}/oauth/callback`;

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
	await stub.start(temporary.token, temporary.tokenSecret);

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

	setSessionCookie(c, await mintSession(access.nsid, c.env.SESSION_KEY));

	return c.redirect(uiUrl(c.env, "ok"), 302);
});

/** Ends the browser session and nothing else. ADR-10 accepts no server-side revocation,
 *  and the Flickr token deliberately survives -- cutting FGA off entirely happens at
 *  Flickr, which is both more thorough and outside our control. */
oauthRoutes.post("/oauth/logout", (c) => {
	clearSessionCookie(c);
	return c.json({ status: "ok" });
});
