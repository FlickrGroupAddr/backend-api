import { Hono } from "hono";
import { z } from "zod";
import { createAttempt } from "../adds/attempt.js";
import { outcomeColumn } from "../adds/classify.js";
import {
	enqueue,
	pairReachedAModerator,
	pendingCount,
	resolveRequest,
} from "../db/requests.js";
import { getFlickrTokens } from "../db/users.js";
import { getGroupInfo, getPhotoPools, getUserGroups } from "../flickr/api.js";
import {
	requireSession,
	type SessionVariables,
} from "../middleware/session.js";

/**
 * The authenticated REST surface, under `/v001/*`.
 *
 * The version is zero-padded to match the ADR labels -- `v001` sorts correctly
 * past nine and cannot be retrofitted cheaply once anything cites it.
 */

export const apiRoutes = new Hono<{
	Bindings: Env;
	Variables: SessionVariables;
}>();

apiRoutes.use("/v001/*", requireSession);

/** Flickr IDs are opaque strings. Validated for shape, never interpreted. */
const submission = z.object({
	photoId: z.string().min(1).max(64),
	groupId: z.string().min(1).max(64),
	/** ADR-11: the user has seen the moderation warning and chosen to proceed. */
	acknowledgedModeration: z.boolean().optional(),
});

apiRoutes.get("/v001/me", (c) => c.json({ nsid: c.get("nsid") }));

/**
 * Queues an add request.
 *
 * Three rules meet here, in this order: ADR-11's warning, ADR-10's ordering, and
 * ADR-10's narrow permission to attempt immediately.
 */
apiRoutes.post("/v001/requests", async (c) => {
	const parsed = submission.safeParse(await c.req.json().catch(() => null));
	if (!parsed.success) {
		return c.json({ error: "invalid_request" }, 400);
	}

	const { photoId, groupId, acknowledgedModeration } = parsed.data;
	const nsid = c.get("nsid");

	// ADR-11. A pair that already reached a moderator gets a warning BEFORE it is
	// queued -- but the user is never blocked. The warning informs; they decide.
	const priorModeration = await pairReachedAModerator(
		c.env.DB,
		nsid,
		photoId,
		groupId,
	);

	if (priorModeration !== null && acknowledgedModeration !== true) {
		// ADR-11: presence in the pool proves approval after the fact, and this is
		// the one direction the invisible decision becomes visible. Warning about a
		// photo the moderator accepted would spend exactly the credibility the real
		// warning needs.
		const tokens = await getFlickrTokens(c.env.DB, nsid, c.env.TOKEN_KEY);
		const pools =
			tokens === null
				? null
				: await getPhotoPools(photoId, {
						consumerKey: c.env.FLICKR_CONSUMER_KEY,
						consumerSecret: c.env.FLICKR_CONSUMER_SECRET,
						token: tokens.token,
						tokenSecret: tokens.tokenSecret,
					});

		// A failed lookup is not an approval. `?? false` keeps this a boolean and
		// makes the safe reading the default: if we cannot confirm the photo is in
		// the pool, the user still gets the warning.
		const alreadyApproved = pools?.includes(groupId) ?? false;

		if (!alreadyApproved) {
			return c.json(
				{
					status: "needs_acknowledgement",
					reason: "reached_a_moderator",
					// Named for what is KNOWN. No rejection signal exists in the Flickr
					// API, so the copy must not imply one.
					flickrCode: priorModeration.code,
					firstSeenAt: priorModeration.firstSeenAt,
					stillPending: priorModeration.code === 7,
				},
				409,
			);
		}
	}

	const id = await enqueue(c.env.DB, nsid, photoId, groupId);

	// ADR-10: attempt immediately if, and only if, this is the SOLE unresolved
	// request in its queue. A queue of length one is the only case where an
	// immediate attempt cannot take an allowance slot from something that has
	// been waiting longer.
	if ((await pendingCount(c.env.DB, nsid, groupId)) === 1) {
		const head = { id, nsid, photoId, groupId };
		const disposition = await createAttempt(c.env)(head);

		if (outcomeColumn(disposition) !== null) {
			await resolveRequest(c.env.DB, head, disposition);
			return c.json({ status: "resolved", id, disposition: disposition.kind });
		}
	}

	return c.json({ status: "queued", id }, 202);
});

/**
 * The groups this user may post to, with each one's moderation status and add
 * allowance.
 *
 * **This endpoint is also the diagnostic that closes three open questions**, and
 * the first authenticated call made against a real Flickr key will answer all of
 * them at once: whether Flickr accepts our OAuth 1.0a signature at all, what
 * values `throttle.mode` actually takes, and whether `remaining` is per-user or
 * per-group. `raw` carries the unparsed group list for exactly that reason and
 * SHOULD be dropped once the shapes are confirmed.
 */
apiRoutes.get("/v001/groups", async (c) => {
	const nsid = c.get("nsid");

	const tokens = await getFlickrTokens(c.env.DB, nsid, c.env.TOKEN_KEY);
	if (tokens === null) {
		return c.json({ error: "no_flickr_credentials" }, 409);
	}

	const credentials = {
		consumerKey: c.env.FLICKR_CONSUMER_KEY,
		consumerSecret: c.env.FLICKR_CONSUMER_SECRET,
		token: tokens.token,
		tokenSecret: tokens.tokenSecret,
	};

	const listed = await getUserGroups(credentials);
	if (listed.kind !== "ok") {
		return c.json(
			{
				error: "flickr_unavailable",
				detail: listed.kind === "error" ? listed.code : listed.detail,
			},
			502,
		);
	}

	// The JSON shape here is documented loosely and unconfirmed against a live
	// reply, so read it defensively rather than trusting a path.
	const container = listed.body.groups;
	const rawGroups =
		typeof container === "object" &&
		container !== null &&
		Array.isArray((container as { group?: unknown }).group)
			? ((container as { group: unknown[] }).group as Record<string, unknown>[])
			: [];

	const ids = rawGroups
		.map((group) => group.nsid ?? group.id)
		.filter((id): id is string => typeof id === "string");

	// Sequential rather than concurrent. This runs once when a user opens the
	// page, and a burst of parallel calls into an API this project depends on
	// staying friendly with is the wrong instinct.
	const groups = [];
	for (const id of ids) {
		groups.push((await getGroupInfo(id, credentials)) ?? { id, error: true });
	}

	return c.json({ groups, raw: rawGroups });
});

/**
 * The queue view -- where ADR-08's second half is delivered.
 *
 * Every decision in this project implements the STOPPING. This is the only place
 * the user finds out, and without it fail-polite is a promise the product never
 * keeps. A silent stop reads as a bug, and a user who thinks the tool is broken
 * goes and does the thing by hand, repeatedly, recreating the exact harm.
 */
apiRoutes.get("/v001/queue", async (c) => {
	const nsid = c.get("nsid");

	const { results } = await c.env.DB.prepare(
		`SELECT id, photo_id, group_id, state, outcome, flickr_code,
            attempts, created_at, last_attempt_at, resolved_at
     FROM requests
     WHERE nsid = ?
     ORDER BY group_id, id`,
	)
		.bind(nsid)
		.all<{
			id: number;
			photo_id: string;
			group_id: string;
			state: string;
			outcome: string | null;
			flickr_code: number | null;
			attempts: number;
			created_at: number;
			last_attempt_at: number | null;
			resolved_at: number | null;
		}>();

	// Grouped by group, never one flat list. A flat list looks like a single
	// queue when there are many, which makes correct FIFO behavior read as a bug
	// the first time a later request lands ahead of an earlier one elsewhere.
	const queues = new Map<string, unknown[]>();

	for (const row of results) {
		const entries = queues.get(row.group_id) ?? [];
		entries.push({
			id: row.id,
			photoId: row.photo_id,
			state: row.state,
			outcome: row.outcome,
			flickrCode: row.flickr_code,
			attempts: row.attempts,
			queuedAt: row.created_at,
			lastAttemptAt: row.last_attempt_at,
			resolvedAt: row.resolved_at,
			// Position is only meaningful while pending, and it is what tells a user
			// that nothing is wrong -- they are simply behind someone.
			position: row.state === "pending" ? entries.length + 1 : null,
		});
		queues.set(row.group_id, entries);
	}

	return c.json({
		queues: [...queues].map(([groupId, requests]) => ({ groupId, requests })),
	});
});
