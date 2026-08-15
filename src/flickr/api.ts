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
 * the write did not happen. A dead socket means we do not know, and ADR-01 says an
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

/** The call the whole product exists to make. Classification is ADR-02's job and lives
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

/**
 * ADR-17. **The group list is bounded by Flickr, not by FGA**, so this pages to the end
 * and refuses to return a partial list as though it were complete.
 *
 * **The defect this replaces shipped silently.** The old body was
 * `callFlickr("flickr.groups.pools.getGroups", {}, credentials)` -- no `page`, no
 * `per_page` -- and the caller read only `groups.group`, never `pages` or `total`. So FGA
 * took Flickr's default page size and returned page one as the whole answer. **Nothing in
 * the code could produce a symptom**, and the owner was at 372 groups with the default
 * undocumented.
 *
 * **Asking for a large `per_page` is safe precisely BECAUSE this loops.** Flickr clamps an
 * over-large page size silently rather than erroring, and a clamp only changes how many
 * iterations run. **A single call with a big `per_page` and no loop would inherit that
 * clamp as fresh silent truncation**, which is the trap this function exists to close.
 *
 * **`too-many` is a REFUSAL, not a failure.** Under ADR-01 an answer that could mean
 * "there are groups you cannot see" MUST NOT render as a clean complete list -- a picker
 * would show a filtered wall with entries missing and no way to tell.
 */
export const GROUPS_PER_PAGE = 500;

/** Terry was at 372 on 2026-08-15. This is headroom, not a prediction. */
export const MAX_USER_GROUPS = 5000;

export type UserGroupsResult =
	| { readonly kind: "ok"; readonly groups: readonly Record<string, unknown>[] }
	| {
			readonly kind: "too-many";
			readonly total: number;
			readonly ceiling: number;
	  }
	| { readonly kind: "error"; readonly code: number; readonly message: string }
	| { readonly kind: "unreachable"; readonly detail: string };

export async function getUserGroups(
	credentials: UserCredentials,
): Promise<UserGroupsResult> {
	const collected: Record<string, unknown>[] = [];

	// `pages` is read from the FIRST reply and re-read on every one, because a list that
	// grows mid-walk changes it. The loop bound is recomputed rather than captured.
	for (let page = 1; ; page++) {
		const result = await callFlickr(
			"flickr.groups.pools.getGroups",
			{ page: String(page), per_page: String(GROUPS_PER_PAGE) },
			credentials,
		);

		if (result.kind === "error") {
			return { kind: "error", code: result.code, message: result.message };
		}
		if (result.kind === "unreachable") {
			return { kind: "unreachable", detail: result.detail };
		}

		const container = result.body.groups;
		if (typeof container !== "object" || container === null) {
			// Not the shape we expect. Treat it as unreachable rather than as an empty
			// list -- "no groups" and "no idea" MUST NOT collapse into the same answer.
			return { kind: "unreachable", detail: "reply had no groups container" };
		}

		const fields = container as Record<string, unknown>;

		// Refuse BEFORE collecting, so a pathological account costs one call, not many.
		const total = asNumber(fields.total);
		if (total !== null && total > MAX_USER_GROUPS) {
			return { kind: "too-many", total, ceiling: MAX_USER_GROUPS };
		}

		const batch = fields.group;
		if (Array.isArray(batch)) {
			collected.push(...(batch as Record<string, unknown>[]));
		}

		if (collected.length > MAX_USER_GROUPS) {
			return {
				kind: "too-many",
				total: collected.length,
				ceiling: MAX_USER_GROUPS,
			};
		}

		// **A short page MUST NOT be read as the end** -- ADR-17 says the end is a fact the
		// server states, and that is wrong exactly when the last page is exactly full.
		const pages = asNumber(fields.pages);
		if (pages === null) {
			// Flickr did not say how many pages exist. Stopping here would be a guess, and
			// continuing forever is worse, so stop only when this page added nothing.
			if (!Array.isArray(batch) || batch.length === 0) {
				return { kind: "ok", groups: collected };
			}
			continue;
		}

		if (page >= pages) return { kind: "ok", groups: collected };
	}
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
