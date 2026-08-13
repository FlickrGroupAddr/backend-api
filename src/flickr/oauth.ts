import {
	type Param,
	percentEncode,
	signatureBaseString,
	signHmacSha1,
} from "../oauth/signature.js";

/**
 * Flickr's OAuth 1.0a login, the three legs of it.
 *
 * The signing itself lives in ../oauth/signature.ts and is checked against RFC
 * 5849's published vectors. This module is the Flickr-specific half: endpoints,
 * parameter assembly, and reading the form-encoded replies.
 *
 * Everything except the two `fetch` calls is a pure function, so the assembly
 * can be tested without a network and without a Flickr account.
 */

const REQUEST_TOKEN_URL = "https://www.flickr.com/services/oauth/request_token";
const AUTHORIZE_URL = "https://www.flickr.com/services/oauth/authorize";
const ACCESS_TOKEN_URL = "https://www.flickr.com/services/oauth/access_token";

/**
 * ADR-01 records that Flickr offers only read, write, or delete -- there is no
 * scope for "add photos to groups" alone. `write` is the narrowest that can do
 * the job, and it grants far more than FGA uses.
 */
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

/**
 * The protocol parameters every signed call carries.
 *
 * The nonce is from `crypto.getRandomValues`, never `Math.random()` -- a
 * predictable nonce lets an observer replay a captured request.
 */
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

/**
 * Builds the `Authorization: OAuth ...` header, per RFC 5849 section 3.5.1.
 *
 * Only `oauth_*` parameters appear in the header. Any non-protocol parameters
 * still contribute to the signature -- they are in `params` -- but they travel
 * in the query string or body, which is why the two lists are not the same.
 */
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

/**
 * Parses Flickr's `application/x-www-form-urlencoded` replies.
 *
 * `URLSearchParams` handles the decoding, including `+` for space, which a
 * hand-rolled split on `&` and `=` would get wrong.
 */
export function parseFormResponse(body: string): Record<string, string> {
	return Object.fromEntries(new URLSearchParams(body));
}

/**
 * Leg 1. Obtains temporary credentials.
 *
 * Note this call is itself signed, with an EMPTY token secret -- there is no
 * unauthenticated leg anywhere in OAuth 1.0a. The trailing "&" that an empty
 * secret produces in the signing key is required, not incidental.
 */
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

	// Flickr signals success by echoing this. Its absence means the reply is an
	// error page that happened to arrive with a 200.
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

/** Leg 2. Where the browser gets sent. No signing -- the user does this part. */
export function buildAuthorizeUrl(requestToken: string): string {
	const url = new URL(AUTHORIZE_URL);
	url.searchParams.set("oauth_token", requestToken);
	url.searchParams.set("perms", PERMS);
	return url.toString();
}

/**
 * Leg 3. Exchanges the verifier for long-lived access credentials.
 *
 * This is signed with the REQUEST token secret -- the value ADR-02's Durable
 * Object exists to carry across the redirect. Signing with the consumer secret
 * alone produces a valid-looking request that Flickr rejects opaquely.
 */
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
