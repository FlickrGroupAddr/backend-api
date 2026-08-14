import {
	type Param,
	percentEncode,
	signatureBaseString,
	signHmacSha1,
} from "../oauth/signature.js";

/**
 * Flickr's three-leg OAuth 1.0a login. Signing lives in ../oauth/signature.ts.
 *
 * Everything except the two `fetch` calls is pure, so the assembly tests without a
 * network and without a Flickr account.
 */

const REQUEST_TOKEN_URL = "https://www.flickr.com/services/oauth/request_token";
const AUTHORIZE_URL = "https://www.flickr.com/services/oauth/authorize";
const ACCESS_TOKEN_URL = "https://www.flickr.com/services/oauth/access_token";

/** ADR-07: Flickr offers only read, write or delete. **`write` is the narrowest that can
 *  do the job**, and it grants far more than FGA uses. */
const PERMS = "write";

export interface TemporaryCredentials {
	readonly token: string;
	readonly tokenSecret: string;
}

export interface AccessCredentials {
	readonly token: string;
	readonly tokenSecret: string;
	readonly nsid: string;
	readonly username: string;
}

/** The nonce comes from `crypto.getRandomValues`, never `Math.random()` -- a predictable
 *  nonce lets an observer replay a captured request. */
export function protocolParams(consumerKey: string): Param[] {
	const nonce = [...crypto.getRandomValues(new Uint8Array(16))]
		.map((byte) => byte.toString(16).padStart(2, "0"))
		.join("");

	return [
		["oauth_consumer_key", consumerKey],
		["oauth_nonce", nonce],
		["oauth_signature_method", "HMAC-SHA1"],
		["oauth_timestamp", String(Math.floor(Date.now() / 1000))],
		["oauth_version", "1.0"],
	];
}

/** Only `oauth_*` fields appear in the header. Non-protocol parameters still contribute
 *  to the signature -- they are in `params` -- but travel in the query or body, which is
 *  why the two lists differ. */
export async function authorizationHeader(
	method: string,
	url: URL,
	params: readonly Param[],
	consumerSecret: string,
	tokenSecret = "",
): Promise<string> {
	const signature = await signHmacSha1(
		signatureBaseString(method, url, params),
		consumerSecret,
		tokenSecret,
	);

	const fields: Param[] = [
		...params.filter(([name]) => name.startsWith("oauth_")),
		["oauth_signature", signature],
	];

	const rendered = fields
		.map(([name, value]) => `${percentEncode(name)}="${percentEncode(value)}"`)
		.join(", ");

	return `OAuth ${rendered}`;
}

/** `URLSearchParams` handles `+` as space, which a hand-rolled split would get wrong. */
export function parseFormResponse(body: string): Record<string, string> {
	return Object.fromEntries(new URLSearchParams(body));
}

/** Leg 1. **This call is itself signed, with an EMPTY token secret** -- OAuth 1.0a has no
 *  unauthenticated leg. That empty half is what makes it look anonymous when it is not. */
export async function fetchRequestToken(
	consumerKey: string,
	consumerSecret: string,
	callbackUrl: string,
): Promise<TemporaryCredentials> {
	const url = new URL(REQUEST_TOKEN_URL);
	const params: Param[] = [
		...protocolParams(consumerKey),
		["oauth_callback", callbackUrl],
	];

	const response = await fetch(url, {
		headers: {
			Authorization: await authorizationHeader(
				"GET",
				url,
				params,
				consumerSecret,
			),
		},
	});

	if (!response.ok) {
		throw new Error(`Flickr request_token failed: HTTP ${response.status}`);
	}

	const fields = parseFormResponse(await response.text());

	// Flickr signals success by echoing this. Its absence means an error page that
	// happened to arrive with a 200.
	if (fields.oauth_callback_confirmed !== "true") {
		throw new Error("Flickr did not confirm the OAuth callback");
	}

	const token = fields.oauth_token;
	const tokenSecret = fields.oauth_token_secret;
	if (token === undefined || tokenSecret === undefined) {
		throw new Error("Flickr request_token reply was missing the credentials");
	}

	return { token, tokenSecret };
}

/** Leg 2. No signing -- the user does this part. */
export function buildAuthorizeUrl(requestToken: string): string {
	const url = new URL(AUTHORIZE_URL);
	url.searchParams.set("oauth_token", requestToken);
	url.searchParams.set("perms", PERMS);
	return url.toString();
}

/** Leg 3. **Signed with the REQUEST token secret** -- the value ADR-08's Durable Object
 *  exists to carry across the redirect. The consumer secret alone produces a
 *  valid-looking request that Flickr rejects opaquely. */
export async function exchangeAccessToken(
	consumerKey: string,
	consumerSecret: string,
	requestToken: string,
	requestTokenSecret: string,
	verifier: string,
): Promise<AccessCredentials> {
	const url = new URL(ACCESS_TOKEN_URL);
	const params: Param[] = [
		...protocolParams(consumerKey),
		["oauth_token", requestToken],
		["oauth_verifier", verifier],
	];

	const response = await fetch(url, {
		headers: {
			Authorization: await authorizationHeader(
				"GET",
				url,
				params,
				consumerSecret,
				requestTokenSecret,
			),
		},
	});

	if (!response.ok) {
		throw new Error(`Flickr access_token failed: HTTP ${response.status}`);
	}

	const fields = parseFormResponse(await response.text());

	const token = fields.oauth_token;
	const tokenSecret = fields.oauth_token_secret;
	const nsid = fields.user_nsid;

	if (token === undefined || tokenSecret === undefined || nsid === undefined) {
		throw new Error("Flickr access_token reply was missing the credentials");
	}

	return { token, tokenSecret, nsid, username: fields.username ?? "" };
}
