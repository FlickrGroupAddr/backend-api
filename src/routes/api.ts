import { Hono } from "hono";
import { z } from "zod";
import { createAttempt } from "../adds/attempt.js";
import { outcomeColumn } from "../adds/classify.js";
import {
	enqueue,
	pairReachedAModerator,
	pendingCount,
	recordAttempt,
	resolveRequest,
	withdrawRequest,
} from "../db/requests.js";
import { getFlickrTokens } from "../db/users.js";
import { getGroupInfo, getPhotoPools, getUserGroups } from "../flickr/api.js";
import {
	requireSession,
	type SessionVariables,
} from "../middleware/session.js";

/** The authenticated surface, `/v001/*`. */

export const apiRoutes = new Hono<{
	Bindings: Env;
	Variables: SessionVariables;
}>();

/**
 * ADR-12. **Registered BEFORE `requireSession` deliberately:** a middleware that rejects
 * never calls `next()`, so registering this second would leave exactly the 401s uncovered.
 *
 * `no-store` goes beyond ADR-12's `private` because the queue view changes the instant a
 * user withdraws something, and a browser reusing its own cached copy would still show it.
 */
apiRoutes.use("/v001/*", async (c, next) => {
	await next();
	c.header("Cache-Control", "private, no-store");
});

apiRoutes.use("/v001/*", requireSession);

/** Flickr IDs are opaque strings. Validated for shape, never interpreted. */
const submission = z.object({
	photoId: z.string().min(1).max(64),
	groupId: z.string().min(1).max(64),
	acknowledgedModeration: z.boolean().optional(),
});

/** ADR-17. **`limit` is capped, not merely defaulted** -- an uncapped `?limit=` is the
 *  same unbounded query with the caller holding the trigger. `state` defaults to pending
 *  because that is the question this page answers. */
const queueQuery = z.object({
	limit: z.coerce.number().int().min(1).max(200).default(50),
	after: z.uuidv4().optional(),
	state: z.enum(["pending", "all"]).default("pending"),
});

apiRoutes.get("/v001/me", (c) => c.json({ nsid: c.get("nsid") }));

/** Three rules meet here in order: ADR-04's warning, ADR-03's ordering, then ADR-03's
 *  narrow permission to attempt immediately. */
apiRoutes.post("/v001/requests", async (c) => {
	const parsed = submission.safeParse(await c.req.json().catch(() => null));
	if (!parsed.success) {
		return c.json({ error: "invalid_request" }, 400);
	}

	const { photoId, groupId, acknowledgedModeration } = parsed.data;
	const nsid = c.get("nsid");

	const priorModeration = await pairReachedAModerator(
		c.env.DB,
		nsid,
		photoId,
		groupId,
	);

	if (priorModeration !== null && acknowledgedModeration !== true) {
		// ADR-04: presence in the pool proves approval, the one direction the invisible
		// decision becomes visible. Warning about an accepted photo spends exactly the
		// credibility the real warning needs.
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

		// `?? false` keeps the safe reading as the default: a failed lookup is not an
		// approval, so the user still gets the warning.
		const alreadyApproved = pools?.includes(groupId) ?? false;

		if (!alreadyApproved) {
			return c.json(
				{
					status: "needs_acknowledgement",
					reason: "reached_a_moderator",
					flickrCode: priorModeration.code,
					firstSeenAt: priorModeration.firstSeenAt,
					stillPending: priorModeration.code === 7,
				},
				409,
			);
		}
	}

	const { id, publicId } = await enqueue(c.env.DB, nsid, photoId, groupId);

	if ((await pendingCount(c.env.DB, nsid, groupId)) === 1) {
		const head = { id, nsid, photoId, groupId };

		// BEFORE the attempt, matching the sweep. An attempt that throws still happened,
		// and ADR-01 turns on not losing that: a dead socket may have left a photo in
		// front of a moderator, so the record MUST NOT depend on getting a reply.
		await recordAttempt(c.env.DB, id);

		const disposition = await createAttempt(c.env)(head);

		if (outcomeColumn(disposition) !== null) {
			await resolveRequest(c.env.DB, head, disposition);
			return c.json({
				status: "resolved",
				publicId,
				disposition: disposition.kind,
			});
		}
	}

	return c.json({ status: "queued", publicId }, 202);
});

/**
 * **"Withdraw", not "cancel" or "delete", and the word is doing work.** Delete is wrong:
 * the row survives, resolved as `withdrawn`, so the user's history still accounts for
 * something they caused. Cancel suggests stopping something in motion, which this cannot
 * do -- Flickr offers no call to pull a photo back out of a moderation queue.
 *
 * POST rather than DELETE for the same reason: this is a state transition, not a removal.
 */
apiRoutes.post("/v001/requests/:publicId/withdraw", async (c) => {
	// Not a security control -- `withdrawRequest` conditions on `nsid` and that is what
	// makes it safe. This just turns a malformed id into a clean 400 rather than a 404
	// that reads as "your request vanished".
	const parsed = z.uuidv4().safeParse(c.req.param("publicId"));
	if (!parsed.success) {
		return c.json({ error: "invalid_request" }, 400);
	}

	const publicId = parsed.data;
	const result = await withdrawRequest(c.env.DB, c.get("nsid"), publicId);

	switch (result.kind) {
		case "withdrawn":
			return c.json({ status: "withdrawn", publicId });

		case "not_found":
			return c.json({ error: "not_found" }, 404);

		case "already_resolved":
			// 409, not 400: the request is fine, the state is not.
			return c.json(
				{
					error: "already_resolved",
					publicId,
					outcome: result.outcome,
					reachedAModerator: result.outcome === "queued_for_moderator",
				},
				409,
			);
	}
});

/** One Flickr call whatever the group count. `poolModerated` and `inviteOnly` come free
 *  in this reply. **The throttle does not** -- it needs `groups.getInfo` per group, which
 *  is the sibling route below and is why this one does not fetch it. */
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

	// This JSON shape is documented loosely, so read it defensively rather than trusting
	// a path.
	const container = listed.body.groups;
	const rawGroups =
		typeof container === "object" &&
		container !== null &&
		Array.isArray((container as { group?: unknown }).group)
			? ((container as { group: unknown[] }).group as Record<string, unknown>[])
			: [];

	// Only what a picker needs. The raw reply carries every group's full description and
	// rules -- 979 KB on a real account -- and none of it is useful here.
	return c.json({
		groups: rawGroups
			.map((group) => ({
				id:
					typeof group.nsid === "string" ? group.nsid : String(group.id ?? ""),
				name: typeof group.name === "string" ? group.name : null,
				photos: Number(group.photos ?? 0),
				members: Number(group.member_count ?? 0),
				poolModerated: Number(group.ispoolmoderated ?? 0) === 1,
				inviteOnly: Number(group.invitation_only ?? 0) === 1,
			}))
			.filter((group) => group.id !== ""),
	});
});

/**
 * Split out from the list deliberately. The first version fetched this inline for every
 * group, reasoning that parallel calls would be rude to Flickr. **That was right about
 * the rudeness and wrong about the scale:** 330 groups meant 331 sequential calls and
 * 53 seconds. **The fix was not concurrency. It was not making the calls.**
 */
apiRoutes.get("/v001/groups/:groupId", async (c) => {
	const nsid = c.get("nsid");
	const groupId = c.req.param("groupId");

	const tokens = await getFlickrTokens(c.env.DB, nsid, c.env.TOKEN_KEY);
	if (tokens === null) {
		return c.json({ error: "no_flickr_credentials" }, 409);
	}

	const info = await getGroupInfo(groupId, {
		consumerKey: c.env.FLICKR_CONSUMER_KEY,
		consumerSecret: c.env.FLICKR_CONSUMER_SECRET,
		token: tokens.token,
		tokenSecret: tokens.tokenSecret,
	});

	return info === null
		? c.json({ error: "flickr_unavailable" }, 502)
		: c.json(info);
});

/**
 * **Where ADR-01 becomes visible.** Every other decision implements the stopping. This is
 * the only place the user finds out, and without it fail-polite is a promise the product
 * never keeps.
 */
apiRoutes.get("/v001/queue", async (c) => {
	const nsid = c.get("nsid");

	const params = queueQuery.safeParse({
		limit: c.req.query("limit"),
		after: c.req.query("after"),
		state: c.req.query("state"),
	});

	if (!params.success) {
		return c.json({ error: "invalid_request" }, 400);
	}

	const { limit, after, state } = params.data;

	// ADR-17. Keyset on (group_id, id), which IS the sort order, so a page boundary is a
	// position rather than a row count. Offset paging drifts here: the sweep resolves
	// rows nightly, so the same OFFSET returns a different window and requests slide
	// across pages unseen.
	//
	// The cursor is a `public_id` the caller already holds, resolved back to its
	// (group_id, id). Scoped by nsid, so another account's cursor finds nothing.
	let cursor: { group_id: string; id: number } | null = null;
	if (after !== undefined) {
		cursor = await c.env.DB.prepare(
			"SELECT group_id, id FROM requests WHERE public_id = ? AND nsid = ?",
		)
			.bind(after, nsid)
			.first<{ group_id: string; id: number }>();

		if (cursor === null) {
			return c.json({ error: "unknown_cursor" }, 400);
		}
	}

	// One extra row, purely to learn whether another page exists. Cheaper and more honest
	// than a COUNT(*), which reports a total that is stale the moment the sweep runs.
	const probe = limit + 1;

	// **Position is a correlated COUNT, not a window function, and the difference is the
	// bug.** A window function is evaluated AFTER the WHERE clause, so with the cursor
	// condition in there it would number only this page and restart at 1. The subquery is
	// independent of the page, and its cost is bounded by page size rather than history.
	//
	// Ordered by `id` while only `public_id` is selected, so the internal id orders the
	// rows and never leaves the server.
	const { results } = await c.env.DB.prepare(
		`SELECT r.public_id, r.photo_id, r.group_id, r.state, r.outcome,
            r.flickr_code, r.attempts, r.created_at, r.last_attempt_at,
            r.resolved_at,
            CASE WHEN r.state = 'pending' THEN (
              SELECT COUNT(*) FROM requests q
              WHERE q.nsid     = r.nsid
                AND q.group_id = r.group_id
                AND q.state    = 'pending'
                AND q.id      <= r.id
            ) END AS position
     FROM requests r
     WHERE r.nsid = ?1
       AND (?4 = 'all' OR r.state = 'pending')
       AND (?2 IS NULL OR (r.group_id, r.id) > (?2, ?3))
     ORDER BY r.group_id, r.id
     LIMIT ?5`,
	)
		.bind(nsid, cursor?.group_id ?? null, cursor?.id ?? null, state, probe)
		.all<{
			public_id: string;
			photo_id: string;
			group_id: string;
			state: string;
			outcome: string | null;
			flickr_code: number | null;
			attempts: number;
			created_at: number;
			last_attempt_at: number | null;
			resolved_at: number | null;
			position: number | null;
		}>();

	const hasMore = results.length > limit;
	const page = hasMore ? results.slice(0, limit) : results;

	// Grouped, never one flat list. A flat list looks like a single queue when there are
	// many, which makes correct FIFO behavior read as a bug the first time a later
	// request lands ahead of an earlier one elsewhere.
	const queues = new Map<string, unknown[]>();

	for (const row of page) {
		const entries = queues.get(row.group_id) ?? [];

		entries.push({
			publicId: row.public_id,
			photoId: row.photo_id,
			state: row.state,
			outcome: row.outcome,
			flickrCode: row.flickr_code,
			attempts: row.attempts,
			queuedAt: row.created_at,
			lastAttemptAt: row.last_attempt_at,
			resolvedAt: row.resolved_at,
			position: row.position,
		});
		queues.set(row.group_id, entries);
	}

	// **Null means the end, stated rather than inferred.** Letting the caller infer it
	// from a short page is wrong exactly when the last page is exactly `limit` long.
	const last = page.at(-1);

	return c.json({
		queues: [...queues].map(([groupId, requests]) => ({ groupId, requests })),
		nextCursor: hasMore && last !== undefined ? last.public_id : null,
	});
});
