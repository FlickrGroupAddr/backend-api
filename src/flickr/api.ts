import type { Param } from "../oauth/signature.js";
import { authorizationHeader, protocolParams } from "./oauth.js";

/** The three authenticated Flickr calls FGA makes. See docs/FLICKR.md. */

const REST_URL = "https://api.flickr.com/services/rest/";

export interface UserCredentials {
	readonly consumerKey: string;
	readonly consumerSecret: string;
	readonly token: string;
	readonly tokenSecret: string;
}

/**
 * **`unreachable` is NOT a Flickr error, and collapsing the two would be the most
 * dangerous simplification available here.** Codes 105 and 106 mean Flickr is telling us
 * the write did not happen. A dead socket means we do not know, and ADR-08 says an
 * outcome that could mean a person saw something is terminal.
 */
export type FlickrResult =
	| { readonly kind: "ok"; readonly body: Record<string, unknown> }
	| { readonly kind: "error"; readonly code: number; readonly message: string }
	| { readonly kind: "unreachable"; readonly detail: string };

/** Method arguments travel in the body and protocol parameters in the header, but **both
 *  are signed** -- RFC 5849 folds form-encoded body parameters into the base string, and
 *  omitting them produces a signature Flickr rejects without saying why. */
export async function callFlickr(
	method: string,
	args: Readonly<Record<string, string>>,
	credentials: UserCredentials,
): Promise<FlickrResult> {
	const url = new URL(REST_URL);

	const bodyParams: Param[] = [
		["method", method],
		["format", "json"],
		// Without this Flickr wraps the JSON in a callback and it is not parseable JSON.
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

/** The call the whole product exists to make. Classification is ADR-07's job and lives
 *  in ../adds/classify.ts, deliberately apart from the transport. */
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

/** ADR-05's authoritative check. Beats the local guard because it also sees adds FGA did
 *  not make. **Absence is not evidence of rejection** -- a photo awaiting a moderator is
 *  not in the pool either, and no call distinguishes those two. */
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

export async function getUserGroups(
	credentials: UserCredentials,
): Promise<FlickrResult> {
	return await callFlickr("flickr.groups.pools.getGroups", {}, credentials);
}

/**
 * **The JSON form of this API wraps some values in `_content` and leaves others bare,
 * inconsistently**, so every access below is defensive and `null` means "not in the shape
 * we expected" rather than "absent from the group".
 */
export interface GroupInfo {
	readonly id: string;
	readonly name: string | null;
	/** Not `restrictions.moderate_ok`, which is about content ratings. See docs/FLICKR.md. */
	readonly poolModerated: boolean | null;
	readonly throttle: {
		readonly count: number | null;
		readonly mode: string | null;
		readonly remaining: number | null;
	} | null;
}

function asNumber(value: unknown): number | null {
	if (typeof value === "number") return value;
	if (typeof value === "string" && value.trim() !== "") {
		const parsed = Number(value);
		return Number.isFinite(parsed) ? parsed : null;
	}
	return null;
}

function asText(value: unknown): string | null {
	if (typeof value === "string") return value;
	if (typeof value === "object" && value !== null && "_content" in value) {
		const content = (value as { _content: unknown })._content;
		return typeof content === "string" ? content : null;
	}
	return null;
}

export async function getGroupInfo(
	groupId: string,
	credentials: UserCredentials,
): Promise<GroupInfo | null> {
	const result = await callFlickr(
		"flickr.groups.getInfo",
		{ group_id: groupId },
		credentials,
	);

	if (result.kind !== "ok") return null;

	const group = result.body.group;
	if (typeof group !== "object" || group === null) return null;

	const fields = group as Record<string, unknown>;
	const moderated = asNumber(fields.ispoolmoderated);

	const rawThrottle = fields.throttle;
	const throttle =
		typeof rawThrottle === "object" && rawThrottle !== null
			? (rawThrottle as Record<string, unknown>)
			: null;

	return {
		id: groupId,
		name: asText(fields.name),
		poolModerated: moderated === null ? null : moderated === 1,
		throttle:
			throttle === null
				? null
				: {
						count: asNumber(throttle.count),
						mode: asText(throttle.mode),
						remaining: asNumber(throttle.remaining),
					},
	};
}
