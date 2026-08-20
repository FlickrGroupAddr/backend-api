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

	/**
	 * **Every interpolated value is encoded, and today not one of them needs it.**
	 *
	 * The cursor is a request's `publicId`, and `enqueue` mints that with
	 * `crypto.randomUUID()` -- `[0-9a-f-]` only. So this is insurance, not a fix.
	 *
	 * **ADR-16 calls `publicId` the OPAQUE handle that appears in URLs, and opaque means
	 * the format is free to change.** Move it to base64url and a `+` in a query string
	 * decodes to a SPACE on the server, so the cursor arrives corrupted and the route
	 * answers `unknown_cursor`. **That reads as an expired page rather than as a bug**,
	 * which is the kind of failure nobody traces back to a template literal.
	 */
	queue: (cursor: string | null = null, state: "pending" | "all" = "pending") =>
		call(
			contract.queuePage,
			`/api/v001/queue?state=${state}&limit=50${
				cursor ? `&after=${encodeURIComponent(cursor)}` : ""
			}`,
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

	/** Encoded for the same reason as the cursor above: the handle is opaque. */
	withdraw: (publicId: string) =>
		call(
			contract.withdrawn,
			`/api/v001/requests/${encodeURIComponent(publicId)}/withdraw`,
			{ method: "POST" },
		),

	/** POST, not GET. It changes state, and a link prefetcher MUST NOT log anyone out. */
	logout: () => fetch("/auth/flickr/logout", { method: "POST" }),
};

/**
 * **`beginLogin` moved to `./navigate.js` on 2026-08-19, and it MUST NOT come back.**
 *
 * It was the only line in this file that touched `window`, and that one reference made
 * the module unloadable from a Worker-side test -- `tsc --noEmit` reported
 * `Cannot find name 'window'` as soon as a test imported `ApiError`. Everything else
 * here uses `fetch`, `Response` and `RequestInit`, which both runtimes have.
 *
 * **So this file is now environment-neutral, and that is what made
 * `test/outcomes.test.ts` possible at all.**
 */
