import type { Param } from "../oauth/signature.js";
import { authorizationHeader, protocolParams } from "./oauth.js";

/**
 * The authenticated Flickr REST calls FGA makes.
 *
 * Six calls total across the whole product, three of them here -- the surface
 * was read out of the 2022 code, which is working precedent rather than a guess.
 */

const REST_URL = "https://api.flickr.com/services/rest/";

export interface UserCredentials {
	readonly consumerKey: string;
	readonly consumerSecret: string;
	readonly token: string;
	readonly tokenSecret: string;
}

/**
 * The result of one call, with the distinction that matters most kept explicit.
 *
 * `unreachable` is NOT the same as a Flickr error, and collapsing the two would
 * be the most dangerous simplification available here. When Flickr answers 105
 * or 106 it is telling us the write did not happen; when the request never
 * completes we do not know whether it happened, and ADR-08 says an outcome that
 * could mean a person saw something is terminal.
 */
export type FlickrResult =
	| { readonly kind: "ok"; readonly body: Record<string, unknown> }
	| { readonly kind: "error"; readonly code: number; readonly message: string }
	| { readonly kind: "unreachable"; readonly detail: string };

/**
 * Signs and issues one call.
 *
 * Method arguments travel in the POST body and the protocol parameters in the
 * Authorization header, but BOTH are signed -- RFC 5849 folds form-encoded body
 * parameters into the signature base string, and omitting them produces a
 * signature Flickr rejects without saying why.
 */
export async function callFlickr(
	method: string,
	args: Readonly<Record<string, string>>,
	credentials: UserCredentials,
): Promise<FlickrResult> {
	const url = new URL(REST_URL);

	const bodyParams: Param[] = [
		["method", method],
		["format", "json"],
		// Without this Flickr wraps the JSON in a callback function and the reply
		// is not parseable JSON at all.
		["nojsoncallback", "1"],
		...Object.entries(args),
	];

	const params: Param[] = [
		...protocolParams(credentials.consumerKey),
		["oauth_token", credentials.token],
		...bodyParams,
	];

	const header = await authorizationHeader(
		"POST",
		url,
		params,
		credentials.consumerSecret,
		credentials.tokenSecret,
	);

	let response: Response;
	try {
		response = await fetch(url, {
			method: "POST",
			headers: {
				Authorization: header,
				"Content-Type": "application/x-www-form-urlencoded",
			},
			body: new URLSearchParams(bodyParams.map(([k, v]) => [k, v])).toString(),
		});
	} catch (cause) {
		return {
			kind: "unreachable",
			detail: cause instanceof Error ? cause.message : "fetch failed",
		};
	}

	if (!response.ok) {
		return { kind: "unreachable", detail: `HTTP ${response.status}` };
	}

	let body: Record<string, unknown>;
	try {
		body = (await response.json()) as Record<string, unknown>;
	} catch {
		return { kind: "unreachable", detail: "reply was not JSON" };
	}

	if (body.stat === "fail") {
		return {
			kind: "error",
			code: typeof body.code === "number" ? body.code : -1,
			message: typeof body.message === "string" ? body.message : "",
		};
	}

	return { kind: "ok", body };
}

/**
 * `flickr.groups.pools.add`. The call the whole product exists to make.
 *
 * Returns the raw result; classification is ADR-07's job and lives in
 * ../adds/classify.ts, deliberately apart from the transport.
 */
export async function addPhotoToGroup(
	photoId: string,
	groupId: string,
	credentials: UserCredentials,
): Promise<FlickrResult> {
	return await callFlickr(
		"flickr.groups.pools.add",
		{ photo_id: photoId, group_id: groupId },
		credentials,
	);
}

/**
 * `flickr.photos.getAllContexts`. ADR-05's authoritative idempotency check.
 *
 * Beats the local D1 guard because it also sees adds FGA did not make -- the
 * user adding a photo by hand, or a second FGA session. Returns the pool IDs the
 * photo currently belongs to.
 *
 * **Absence is not evidence of rejection.** A photo sitting in a moderation
 * queue is not in the pool either, and no call distinguishes those two.
 */
export async function getPhotoPools(
	photoId: string,
	credentials: UserCredentials,
): Promise<readonly string[] | null> {
	const result = await callFlickr(
		"flickr.photos.getAllContexts",
		{ photo_id: photoId },
		credentials,
	);

	if (result.kind !== "ok") return null;

	const pools = result.body.pool;
	if (!Array.isArray(pools)) return [];

	return pools
		.map((pool) =>
			typeof pool === "object" && pool !== null && "id" in pool
				? String((pool as { id: unknown }).id)
				: null,
		)
		.filter((id): id is string => id !== null);
}

/** `flickr.groups.pools.getGroups`. The groups a user may post to. */
export async function getUserGroups(
	credentials: UserCredentials,
): Promise<FlickrResult> {
	return await callFlickr("flickr.groups.pools.getGroups", {}, credentials);
}
