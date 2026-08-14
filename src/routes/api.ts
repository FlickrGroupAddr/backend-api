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

/**
 * ADR-09: nothing behind a session may reach a shared cache.
 *
 * **Registered BEFORE `requireSession` deliberately.** A middleware that
 * rejects a request never calls `next()`, so anything registered after it does
 * not run on that path -- putting this second would have left exactly the 401s
 * uncovered. Sitting first, it sets the header on the way back out and covers
 * every response the group can produce.
 *
 * ADR-09 specifies `private`; this adds `no-store`, and the extra word earns its
 * place twice. Correctness: the queue view changes the instant a user withdraws
 * something, and a browser reusing its own cached copy would show the request
 * still sitting there. Safety: `private` asks shared caches not to store, while
 * `no-store` asks everything not to, and the difference costs nothing on
 * responses this small.
 *
 * **The risk today is latent rather than live** — Cloudflare does not cache JSON
 * from a Worker by default, so nothing is leaking now. It becomes real the day
 * somebody adds a Cache Rule or "Cache Everything", which is exactly the change
 * that gets made without auditing what is already behind a session.
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
	/** ADR-11: the user has seen the moderation warning and chosen to proceed. */
	acknowledgedModeration: z.boolean().optional(),
});

/**
 * The queue view's paging and filter parameters.
 *
 * `limit` is capped rather than merely defaulted. An uncapped `?limit=` is the
 * same unbounded query this pagination exists to remove, just with the caller
 * holding the trigger.
 *
 * `state` defaults to `pending`, because that is the question this page answers
 * -- "what is FGA still going to do for me". History is available with
 * `state=all` and is the rarer ask, so it is the one that pays for itself.
 */
const queueQuery = z.object({
	limit: z.coerce.number().int().min(1).max(200).default(50),
	after: z.uuidv4().optional(),
	state: z.enum(["pending", "all"]).default("pending"),
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

	const { id, publicId } = await enqueue(c.env.DB, nsid, photoId, groupId);

	// ADR-10: attempt immediately if, and only if, this is the SOLE unresolved
	// request in its queue. A queue of length one is the only case where an
	// immediate attempt cannot take an allowance slot from something that has
	// been waiting longer.
	if ((await pendingCount(c.env.DB, nsid, groupId)) === 1) {
		const head = { id, nsid, photoId, groupId };

		// BEFORE the attempt, matching the sweep. An attempt that throws still
		// happened, and ADR-08 turns on not losing that: a dead socket may have
		// left a photo in front of a moderator, so the record of having tried
		// MUST NOT depend on getting a reply.
		//
		// This was missing until the first real add ran on 2026-08-13. The row
		// resolved correctly with Flickr's code, and reported `attempts: 0` --
		// the same event counted on one path and not the other.
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
 * Withdraws a pending request -- the user queued it and changed their mind.
 *
 * **Named "withdraw" rather than "cancel" or "delete", and the word is doing
 * work.** Delete would be wrong: the row survives, resolved as `withdrawn`, so
 * the user's history still accounts for something they caused. Cancel suggests
 * stopping something already in motion, which this cannot do -- see below.
 *
 * **POST rather than DELETE for the same reason.** This is a state transition on
 * a request, not the removal of one, and the response reports the transition.
 *
 * **It succeeds only while the request is pending, which is what makes it
 * honest.** Reaching a moderator resolves a request at that moment, so anything
 * still withdrawable has never been in front of a person. FGA cannot pull a
 * photo back out of a moderation queue -- Flickr offers no such call -- and a
 * feature that implied otherwise would be ADR-08 broken in the most direct way
 * available: telling someone a volunteer will not see their photo when one
 * already has.
 */
apiRoutes.post("/v001/requests/:publicId/withdraw", async (c) => {
	// Shape-checked before it reaches the database. This is not a security
	// control -- `withdrawRequest` conditions on `nsid` and that is what makes it
	// safe -- it just turns a malformed id into a clean 400 rather than a 404
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
			// 409 rather than 400: the request is fine, the state is not. The outcome
			// travels so the interface can say WHICH kind of too-late this was.
			return c.json(
				{
					error: "already_resolved",
					publicId,
					outcome: result.outcome,
					// The one outcome where the user should be told plainly that a person
					// is involved and FGA is out of the loop.
					reachedAModerator: result.outcome === "queued_for_moderator",
				},
				409,
			);
	}
});

/**
 * The groups this user may post to. One Flickr call, whatever the group count.
 *
 * `poolModerated` and `inviteOnly` come free in this reply. The add THROTTLE
 * does not -- it needs `groups.getInfo` per group, which is the sibling route
 * below and is why this one does not fetch it.
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

	// Only what a picker needs. The raw reply carries every group's full
	// description and rules -- HTML, award codes, decades of forum boilerplate --
	// which came to 979 KB on a real account. None of it is useful here.
	return c.json({
		groups: rawGroups
			.map((group) => ({
				id:
					typeof group.nsid === "string" ? group.nsid : String(group.id ?? ""),
				name: typeof group.name === "string" ? group.name : null,
				photos: Number(group.photos ?? 0),
				members: Number(group.member_count ?? 0),
				// Free signals already present in this reply. Fetching them here
				// costs nothing; fetching the THROTTLE would cost a call per group.
				poolModerated: Number(group.ispoolmoderated ?? 0) === 1,
				inviteOnly: Number(group.invitation_only ?? 0) === 1,
			}))
			.filter((group) => group.id !== ""),
	});
});

/**
 * One group's moderation status and add allowance.
 *
 * Split out from the list deliberately, and the reason is worth recording. The
 * first version fetched this inline for every group, reasoning that a burst of
 * parallel calls would be rude to Flickr. That was right about the rudeness and
 * wrong about the scale: the owner belongs to 330 groups, so it made 331
 * SEQUENTIAL calls and took 53 seconds.
 *
 * The fix is not concurrency, it is not making the calls. A list view does not
 * need throttle data for groups nobody is looking at.
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
 * The queue view -- where ADR-08's second half is delivered.
 *
 * Every decision in this project implements the STOPPING. This is the only place
 * the user finds out, and without it fail-polite is a promise the product never
 * keeps. A silent stop reads as a bug, and a user who thinks the tool is broken
 * goes and does the thing by hand, repeatedly, recreating the exact harm.
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

	// Keyset pagination on (group_id, id), which is exactly the sort order, so a
	// page boundary is a position in that order rather than a row count. Offset
	// paging would drift here: the sweep resolves rows every night, so the same
	// OFFSET returns a different window and requests slide across pages unseen.
	//
	// The cursor is a `public_id` the caller already holds. Resolving it back to
	// its (group_id, id) is one indexed lookup and keeps the internal id out of
	// the URL. Scoped by nsid, so a cursor from another account finds nothing.
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

	// One extra row, purely to learn whether another page exists. Cheaper and
	// more honest than a COUNT(*), which would be a second scan reporting a
	// total that is stale the moment the sweep runs.
	const probe = limit + 1;

	// **Position is computed in SQL, not while iterating**, because paging made
	// the old JS version wrong: a page starting mid-group restarted at 1.
	//
	// It is a correlated COUNT rather than a window function, and the difference
	// matters. A window function is evaluated AFTER the WHERE clause, so with the
	// cursor condition in there it would number only the rows on this page and
	// restart at 1 -- the exact bug, moved into SQL. The subquery is independent
	// of the page, and its cost is bounded by the PAGE size rather than by the
	// user's history: at most `limit` range-counts against the partial pending
	// index, and none at all for resolved rows.
	//
	// Ordered by `id` -- ADR-10's ordering key -- while only `public_id` is
	// selected, so the internal id orders the rows and never leaves the server.
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

	// Grouped by group, never one flat list. A flat list looks like a single
	// queue when there are many, which makes correct FIFO behavior read as a bug
	// the first time a later request lands ahead of an earlier one elsewhere.
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
			// Position within the whole group's pending queue, not within this
			// page. See the window function above.
			position: row.position,
		});
		queues.set(row.group_id, entries);
	}

	// The cursor is the last row of THIS page. Null means the end, and it says so
	// definitively rather than leaving the caller to infer it from a short page --
	// which would be wrong exactly when the last page is exactly `limit` long.
	const last = page.at(-1);

	return c.json({
		queues: [...queues].map(([groupId, requests]) => ({ groupId, requests })),
		nextCursor: hasMore && last !== undefined ? last.public_id : null,
	});
});
