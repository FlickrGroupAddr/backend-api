import type { z } from "zod";
import * as contract from "./contract.js";

/**
 * The only place that talks to the Worker.
 *
 * **Same origin, so the paths are relative and there is no base URL to configure.**
 * That is ADR-18 paying out: no `VITE_API_URL`, no environment file, and no chance of
 * a production build pointing at localhost.
 *
 * **`credentials` is deliberately absent.** A same-origin `fetch` sends cookies by
 * default. Writing `credentials: "include"` here would work today and would quietly
 * become the thing that makes a future cross-origin move appear to succeed while
 * bypassing the check ADR-11 exists to make.
 */

/** Thrown for anything the caller cannot treat as data. */
export class ApiError extends Error {
	constructor(
		readonly status: number,
		readonly code: string,
	) {
		super(`${status} ${code}`);
		this.name = "ApiError";
	}
}

/** A 401 is not an error to show. It means "sign in", and the shell handles it. */
export class NotAuthenticated extends ApiError {
	constructor() {
		super(401, "not_authenticated");
		this.name = "NotAuthenticated";
	}
}

async function errorCode(response: Response): Promise<string> {
	try {
		const body = (await response.json()) as { error?: unknown };
		return typeof body.error === "string" ? body.error : "unknown";
	} catch {
		return "unparseable";
	}
}

/**
 * One request, parsed through its schema.
 *
 * **The schema runs on every response, including in production.** Skipping it there is
 * the usual optimization and it is wrong here: a server that starts returning a
 * differently shaped queue would otherwise render as an empty page rather than an
 * error, and an empty queue is a lie ADR-01 cannot afford.
 */
async function call<T extends z.ZodType>(
	schema: T,
	path: string,
	init?: RequestInit,
): Promise<z.infer<T>> {
	const response = await fetch(path, {
		...init,
		headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
	});

	if (response.status === 401) throw new NotAuthenticated();
	if (!response.ok)
		throw new ApiError(response.status, await errorCode(response));

	return schema.parse(await response.json());
}

export const api = {
	me: () => call(contract.me, "/api/v001/me"),

	groups: () => call(contract.groupList, "/api/v001/groups"),

	/**
	 * ADR-04's 409 is a RESULT, not a failure, so this one route reads the status
	 * before deciding. Every other route can let `call` throw.
	 */
	submit: async (
		photoId: string,
		groupId: string,
		acknowledgedModeration = false,
	): Promise<contract.Submitted> => {
		const response = await fetch("/api/v001/requests", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ photoId, groupId, acknowledgedModeration }),
		});

		if (response.status === 401) throw new NotAuthenticated();
		if (!response.ok && response.status !== 409) {
			throw new ApiError(response.status, await errorCode(response));
		}

		return contract.submitted.parse(await response.json());
	},

	queue: (cursor: string | null = null, state: "pending" | "all" = "pending") =>
		call(
			contract.queuePage,
			`/api/v001/queue?state=${state}&limit=50${cursor ? `&after=${cursor}` : ""}`,
		),

	/**
	 * ADR-20. One call for the whole selection, so the ADR-04 warning can be shown
	 * before the person commits rather than discovered afterwards.
	 */
	preflight: (photoId: string, groupIds: readonly string[]) =>
		call(contract.preflight, `/api/v001/photos/${photoId}/preflight`, {
			method: "POST",
			body: JSON.stringify({ groupIds }),
		}),

	/** ADR-19. 404 for a non-admin, which the caller shows as "no such page". */
	adminOverview: (days = 7) =>
		call(contract.adminOverview, `/api/v001/admin/overview?days=${days}`),

	withdraw: (publicId: string) =>
		call(contract.withdrawn, `/api/v001/requests/${publicId}/withdraw`, {
			method: "POST",
		}),

	/** POST, not GET. It changes state, and a link prefetcher MUST NOT log anyone out. */
	logout: () => fetch("/oauth/logout", { method: "POST" }),
};

/** A full navigation, not a fetch -- the OAuth leg ends in a redirect chain. */
export function beginLogin(): void {
	window.location.href = "/oauth/login";
}
