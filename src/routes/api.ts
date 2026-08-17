import { Hono } from "hono";
import { z } from "zod";
import { createAttempt } from "../adds/attempt.js";
import { outcomeColumn } from "../adds/classify.js";
import { checkAdmin } from "../admin/allowlist.js";
import { overview } from "../db/metrics.js";
import {
	enqueue,
	enqueueMany,
	moderatedPairsFor,
	pairReachedAModerator,
	pendingCount,
	pendingPairsFor,
	recordAttempt,
	resolveRequest,
	succeededPairsFor,
	withdrawRequest,
} from "../db/requests.js";
import { getFlickrTokens } from "../db/users.js";
import {
	getGroupInfo,
	getPhotoPools,
	getPhotoPoolsDetailed,
	getUserGroups,
	MAX_PHOTO_POOLS,
} from "../flickr/api.js";
import { requireAdmin } from "../middleware/admin.js";
import {
	requireBrowserSession,
	requireSession,
	restrictPluginScope,
	type SessionVariables,
} from "../middleware/session.js";

/**
 * The authenticated surface, `/api/v001/*`.
 *
 * **The `/api` prefix exists because the UI and the API share one hostname.** Static
 * assets answer everything else, so the prefix is what tells the Worker apart from the
 * app shell -- it is `run_worker_first` in `wrangler.jsonc` that makes it load-bearing
 * rather than decorative.
 */

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
apiRoutes.use("/api/v001/*", async (c, next) => {
	await next();
	c.header("Cache-Control", "private, no-store");
});

apiRoutes.use("/api/v001/*", requireSession);

/**
 * **Registered immediately after `requireSession`**, which is what puts
 * `sessionClientType` on the context. It refuses a plug-in token anywhere outside its
 * allow-list, so a route added later is closed to that credential until somebody opens it
 * deliberately.
 */
apiRoutes.use("/api/v001/*", restrictPluginScope);

/**
 * ADR-19. **Registered on `apiRoutes` rather than as its own app, deliberately.**
 *
 * Mounted here it provably inherits the two middlewares above -- `requireSession`, which
 * is what puts `nsid` on the context for `requireAdmin` to read, and ADR-12's
 * `no-store`. A separate Hono app would have to restate both, and a restated security
 * rule is one that drifts.
 *
 * Order matters and is load-bearing: `requireAdmin` is registered AFTER `requireSession`
 * so the session is verified first. Swapped, `c.get("nsid")` would be undefined and the
 * allowlist would compare against nothing.
 */
/**
 * **The admin surface is browser-only, and that is a separate rule from the allowlist.**
 *
 * A plug-in token lives for 90 days on a laptop protected by nothing but the filesystem.
 * The allowlist asks *is this person an admin*; this asks *is this credential one I am
 * willing to let act as an admin*. An admin's stolen laptop MUST NOT be an admin console.
 *
 * Registered before `requireAdmin` so the cheaper, broader refusal runs first.
 */
apiRoutes.use("/api/v001/admin/*", requireBrowserSession);
apiRoutes.use("/api/v001/admin/*", requireAdmin);

/**
 * The admin surface is one endpoint on purpose.
 *
 * Four separate fetches would render four different instants and invite the reader to
 * compare numbers that were never simultaneously true. `generatedAt` stamps the set.
 */
apiRoutes.get("/api/v001/admin/overview", async (c) => {
	const days = z.coerce
		.number()
		.int()
		.min(1)
		.max(90)
		.default(7)
		.safeParse(c.req.query("days"));

	// ADR-17's reasoning applied to a window: capped, not merely defaulted. An
	// uncapped `?days=` is the same unbounded scan with the caller holding the trigger.
	if (!days.success) return c.json({ error: "invalid_request" }, 400);

	return c.json(await overview(c.env.DB, days.data));
});

/** Flickr IDs are opaque strings. Validated for shape, never interpreted. */
const submission = z.object({
	photoId: z.string().min(1).max(64),
	groupId: z.string().min(1).max(64),
	acknowledgedModeration: z.boolean().optional(),
});

/** One photo into many groups. **Capped like ADR-20's preflight, and for the same
 *  reason: the cap bounds the reply, not the work.** `acknowledgedModeration` is a LIST
 *  rather than a flag -- a blanket boolean would let one click acknowledge warnings the
 *  user never saw, which is precisely what ADR-20 exists to prevent. */
const batchSubmission = z.object({
	photoId: z.string().min(1).max(64),
	groupIds: z.array(z.string().min(1).max(64)).min(1).max(200),
	acknowledgedModeration: z.array(z.string().min(1).max(64)).optional(),
});

/** ADR-17. **`limit` is capped, not merely defaulted** -- an uncapped `?limit=` is the
 *  same unbounded query with the caller holding the trigger. `state` defaults to pending
 *  because that is the question this page answers. */
const queueQuery = z.object({
	limit: z.coerce.number().int().min(1).max(200).default(50),
	after: z.uuidv4().optional(),
	state: z.enum(["pending", "all"]).default("pending"),
});

/**
 * **`admin` is a hint for the interface, never a gate.** It exists so the shell can
 * decide whether to render a link. Every admin route re-checks the allowlist itself, so
 * forging this field client-side buys nothing but a link that 404s.
 *
 * Telling a user their own admin status leaks nothing: it is a fact about them, and they
 * can already discover it by requesting the route.
 */
/**
 * **`clientType` is reported so a client can tell what it is holding.**
 *
 * The Lightroom plug-in ships a permanent diagnostic — Terry runs the latest GA
 * Lightroom Classic and takes every Adobe regression on day one, so re-proving the chain
 * after an update has to cost seconds. **"Am I authenticated" and "did I end up with the
 * credential I think I did" are different questions**, and before this the plug-in could
 * only answer the first. A device link that silently minted a browser session would have
 * looked identical to one that worked.
 *
 * **It reads from the verified session, never from the request.** `sessionClientType` is
 * set by `requireSession` out of the database row, so this cannot be a self-report.
 */
apiRoutes.get("/api/v001/me", (c) =>
	c.json({
		nsid: c.get("nsid"),
		clientType: c.get("sessionClientType"),
		admin: checkAdmin(c.get("nsid"), c.env.ADMIN_NSIDS).admin,
	}),
);

/** ADR-20. The picker asks about many groups; the cap bounds the reply, not the work. */
const preflight = z.object({
	groupIds: z.array(z.string().min(1).max(64)).min(1).max(200),
});

/**
 * ADR-20. **Answers ADR-04's question for many groups in ONE round trip.**
 *
 * Without this the picker learned about warnings by submitting: forty groups meant forty
 * POSTs, each returning `409 needs_acknowledgement`, each one a decision the user had
 * already made blind. The warning arrived after the commitment, which is precisely
 * backwards for a rule whose whole point is informed consent.
 *
 * **It costs ONE Flickr call regardless of how many groups are asked about**, because
 * `getAllContexts` is per-photo, not per-group. The three D1 reads are bounded by the
 * caller's list.
 *
 * **This is advisory and MUST NOT be treated as authorization.** `POST /requests`
 * re-checks everything itself. A caller that skipped preflight gets the same protection,
 * and a caller that forges a preflight result gains nothing — which is the only safe way
 * to build a "check first" endpoint.
 */
apiRoutes.post("/api/v001/photos/:photoId/preflight", async (c) => {
	const photoId = z.string().min(1).max(64).safeParse(c.req.param("photoId"));
	const body = preflight.safeParse(await c.req.json().catch(() => null));

	if (!photoId.success || !body.success) {
		return c.json({ error: "invalid_request" }, 400);
	}

	const nsid = c.get("nsid");
	// Duplicates would multiply the response without adding a question.
	const groupIds = [...new Set(body.data.groupIds)];

	const tokens = await getFlickrTokens(c.env.DB, nsid, c.env.TOKEN_KEY);
	if (tokens === null) return c.json({ error: "no_flickr_credentials" }, 409);

	const [moderated, pending, succeeded, pools] = await Promise.all([
		moderatedPairsFor(c.env.DB, nsid, photoId.data, groupIds),
		pendingPairsFor(c.env.DB, nsid, photoId.data, groupIds),
		succeededPairsFor(c.env.DB, nsid, photoId.data, groupIds),
		getPhotoPools(photoId.data, {
			consumerKey: c.env.FLICKR_CONSUMER_KEY,
			consumerSecret: c.env.FLICKR_CONSUMER_SECRET,
			token: tokens.token,
			tokenSecret: tokens.tokenSecret,
		}),
	]);

	/**
	 * **`poolsKnown` is reported, and the distinction is load-bearing.** A failed
	 * `getAllContexts` is not "the photo is in no pools" — ADR-04 says presence proves
	 * approval while absence proves nothing. Rendering an unknown as a clean "ready"
	 * would suppress warnings the server will then raise at submit time.
	 */
	const poolsKnown = pools !== null;
	const inPool = new Set(pools ?? []);

	return c.json({
		photoId: photoId.data,
		poolsKnown,
		groups: groupIds.map((groupId) => {
			const seen = moderated.get(groupId);

			// Order matters and mirrors POST /requests exactly. Pool membership beats a
			// moderation record, because a photo in the pool was approved -- that is the
			// one direction an invisible decision becomes visible.
			// A chain reads as a chain. The two "already_in_pool" arms merge,
			// which the nested ternary hid.
			let status:
				| "already_in_pool"
				| "already_queued"
				| "needs_acknowledgement"
				| "ready";
			if (inPool.has(groupId) || succeeded.has(groupId)) {
				status = "already_in_pool";
			} else if (pending.has(groupId)) {
				status = "already_queued";
			} else if (seen !== undefined) {
				status = "needs_acknowledgement";
			} else {
				status = "ready";
			}

			return {
				groupId,
				status,
				reachedAModerator:
					seen === undefined
						? null
						: {
								flickrCode: seen.code,
								firstSeenAt: seen.firstSeenAt,
								stillPending: seen.code === 7,
							},
			};
		}),
	});
});

/** Three rules meet here in order: ADR-04's warning, ADR-03's ordering, then ADR-03's
 *  narrow permission to attempt immediately. */
apiRoutes.post("/api/v001/requests", async (c) => {
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
 * One photo into many groups, in one round trip. Built for the Lightroom Classic
 * plug-in, where forty groups meant forty POSTs and roughly twelve seconds.
 *
 * **IT MUST NOT INHERIT ADR-03's IMMEDIATE-ATTEMPT BEHAVIOR AT BATCH SCALE.** The single
 * POST above attempts straight away when a request is alone in its queue, which is right
 * for one photo into one group. Applied to forty, a single Worker invocation would make
 * forty sequential `groups.pools.add` calls on one user's token -- **the same discourtesy
 * wearing a performance costume.** This route enqueues and returns; ADR-06's nightly
 * sweep does the work.
 *
 * **The one exception is deliberate**: a batch naming exactly one eligible group, whose
 * queue is empty, is indistinguishable from the single POST and takes the same immediate
 * path. Refusing that would make the plug-in slower than the web app at the one thing
 * they do identically.
 *
 * **ATOMIC IN D1, NOT ATOMIC IN OUTCOME.** `enqueueMany` puts the inserts in one
 * transaction, and the reply is still per-group. **Rejecting all forty because three
 * carry a warning would hold thirty-seven good ones hostage**, and the partial result is
 * the safe direction anyway -- nothing reaches a moderator unanswered.
 *
 * **One Flickr call regardless of group count**, because `getAllContexts` is per-photo.
 * The status vocabulary matches ADR-20's preflight exactly, so a client renders one set
 * of outcomes for both.
 */
apiRoutes.post("/api/v001/requests/batch", async (c) => {
	const parsed = batchSubmission.safeParse(
		await c.req.json().catch(() => null),
	);
	if (!parsed.success) {
		return c.json({ error: "invalid_request" }, 400);
	}

	const { photoId } = parsed.data;
	const nsid = c.get("nsid");

	// Duplicates would multiply the reply without adding a request, and would collide on
	// `idx_requests_one_pending_per_pair` inside the batch.
	const groupIds = [...new Set(parsed.data.groupIds)];
	const acknowledged = new Set(parsed.data.acknowledgedModeration ?? []);

	const tokens = await getFlickrTokens(c.env.DB, nsid, c.env.TOKEN_KEY);
	if (tokens === null) return c.json({ error: "no_flickr_credentials" }, 409);

	const [moderated, pending, succeeded, pools] = await Promise.all([
		moderatedPairsFor(c.env.DB, nsid, photoId, groupIds),
		pendingPairsFor(c.env.DB, nsid, photoId, groupIds),
		succeededPairsFor(c.env.DB, nsid, photoId, groupIds),
		getPhotoPools(photoId, {
			consumerKey: c.env.FLICKR_CONSUMER_KEY,
			consumerSecret: c.env.FLICKR_CONSUMER_SECRET,
			token: tokens.token,
			tokenSecret: tokens.tokenSecret,
		}),
	]);

	/** A failed `getAllContexts` is NOT "the photo is in no pools". ADR-04: presence
	 *  proves approval, absence proves nothing. Reporting an unknown as a clean `ready`
	 *  would suppress warnings this route then raises anyway. */
	const poolsKnown = pools !== null;
	const inPool = new Set(pools ?? []);

	type Decision = { groupId: string; status: string; publicId?: string };
	const decided: Decision[] = [];
	const eligible: string[] = [];

	for (const groupId of groupIds) {
		const seen = moderated.get(groupId);

		// Order mirrors POST /requests and the preflight exactly. Pool membership beats a
		// moderation record, because a photo in the pool was approved -- the one direction
		// an invisible decision becomes visible.
		if (inPool.has(groupId) || succeeded.has(groupId)) {
			decided.push({ groupId, status: "already_in_pool" });
		} else if (pending.has(groupId)) {
			decided.push({ groupId, status: "already_queued" });
		} else if (seen !== undefined && !acknowledged.has(groupId)) {
			decided.push({ groupId, status: "needs_acknowledgement" });
		} else {
			eligible.push(groupId);
		}
	}

	const minted = await enqueueMany(c.env.DB, nsid, photoId, eligible);

	/**
	 * ADR-03's narrow permission, and ONLY at a scale where it still holds. One eligible
	 * group whose queue is empty is exactly the single-POST case.
	 */
	let attempted: Decision | null = null;

	/**
	 * **The caller must have ASKED for one group, not merely ended up with one eligible.**
	 *
	 * Keying off `minted.length === 1` was the first attempt and it is subtly wrong. A
	 * forty-group batch where thirty-nine are already queued would leave one eligible and
	 * take the immediate path — so identical requests would behave differently depending
	 * on state the caller cannot see. **Predictable beats marginally faster.**
	 *
	 * ADR-01's discourtesy argument is unaffected either way: one eligible group is one
	 * Flickr call. This is about a surprising API, not about volume.
	 */
	const only =
		groupIds.length === 1 && minted.length === 1 ? minted[0] : undefined;

	if (only !== undefined) {
		if ((await pendingCount(c.env.DB, nsid, only.groupId)) === 1) {
			const row = await c.env.DB.prepare(
				"SELECT id FROM requests WHERE public_id = ?",
			)
				.bind(only.publicId)
				.first<{ id: number }>();

			if (row !== null) {
				const head = { id: row.id, nsid, photoId, groupId: only.groupId };

				// BEFORE the attempt, matching the sweep and the single POST. A dead socket
				// may have left a photo in front of a moderator, and ADR-01 turns on not
				// losing that.
				await recordAttempt(c.env.DB, row.id);
				const disposition = await createAttempt(c.env)(head);

				if (outcomeColumn(disposition) !== null) {
					await resolveRequest(c.env.DB, head, disposition);
					attempted = {
						groupId: only.groupId,
						status: "resolved",
						publicId: only.publicId,
					};
				}
			}
		}
	}

	const queued: Decision[] = minted.map(({ groupId, publicId }) =>
		attempted !== null && attempted.groupId === groupId
			? attempted
			: { groupId, status: "queued", publicId },
	);

	// Answered in the order asked, so a client can zip the reply against its own list.
	const byGroup = new Map(
		[...decided, ...queued].map((entry) => [entry.groupId, entry]),
	);

	return c.json(
		{
			photoId,
			poolsKnown,
			queuedCount: eligible.length,
			groups: groupIds.map((groupId) => byGroup.get(groupId)),
		},
		202,
	);
});

/**
 * **"Withdraw", not "cancel" or "delete", and the word is doing work.** Delete is wrong:
 * the row survives, resolved as `withdrawn`, so the user's history still accounts for
 * something they caused. Cancel suggests stopping something in motion, which this cannot
 * do -- Flickr offers no call to pull a photo back out of a moderation queue.
 *
 * POST rather than DELETE for the same reason: this is a state transition, not a removal.
 */
apiRoutes.post("/api/v001/requests/:publicId/withdraw", async (c) => {
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

/** One Flickr call per PAGE of groups, and `getUserGroups` walks to the end -- ADR-17,
 *  because Flickr sets this list's size and FGA cannot bound it. At `GROUPS_PER_PAGE` of
 *  500 an ordinary account is still one call. `poolModerated` and `inviteOnly` come free
 *  in this reply. **The throttle does not** -- it needs `groups.getInfo` per group, which
 *  is the sibling route below and is why this one does not fetch it. */
apiRoutes.get("/api/v001/groups", async (c) => {
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

	/**
	 * ADR-17. **A refusal, and it MUST NOT be softened into a truncated list.** Returning
	 * the first 5000 with a flag invites a client to render them, and a picker showing
	 * most of a wall is the failure this whole change exists to prevent -- the user cannot
	 * see which entries are missing.
	 */
	if (listed.kind === "too-many") {
		return c.json(
			{
				error: "too_many_groups",
				total: listed.total,
				ceiling: listed.ceiling,
			},
			502,
		);
	}

	if (listed.kind !== "ok") {
		return c.json(
			{
				error: "flickr_unavailable",
				detail: listed.kind === "error" ? listed.code : listed.detail,
			},
			502,
		);
	}

	// Only what a picker needs. The raw reply carries every group's full description and
	// rules -- 979 KB on a real account -- and none of it is useful here.
	return c.json({
		groups: listed.groups
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
apiRoutes.get("/api/v001/groups/:groupId", async (c) => {
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
 * ADR-17. Which groups a photo is ALREADY in.
 *
 * **The Lightroom picker opens with this and cannot ask Flickr itself.** The plug-in holds
 * no Flickr credentials on purpose -- ADR-09 keeps the user's token encrypted in D1 and
 * the plug-in never sees it -- so FGA proxies the question. The proxy is a consequence of
 * the credential design rather than overhead.
 *
 * **Preflight does NOT answer this**, and the difference is not pedantic. Preflight asks
 * *what would happen if I submitted these groups*, which is the right question at commit
 * time. This asks *where is this photo now*, which is the right question when a picker
 * opens. Preflight also caps `groupIds` at 200 while Terry belongs to 372 groups, so
 * using it here would cost two round trips to learn something one call already knows --
 * `getAllContexts` is per-photo, not per-group.
 *
 * **ADR-17's second kind of list: FGA cannot bound this one.** Flickr decides how many
 * pools a photo sits in, so the ceiling is stated and a result past it is REFUSED rather
 * than truncated. Same reasoning as the group list -- a picker showing most of a photo's
 * memberships is worse than one that says it cannot show them, because the user cannot
 * see which are missing and would read the gap as "not in that group".
 */
apiRoutes.get("/api/v001/photos/:photoId/groups", async (c) => {
	const nsid = c.get("nsid");
	const photoId = z.string().min(1).max(64).safeParse(c.req.param("photoId"));
	if (!photoId.success) {
		return c.json({ error: "invalid_request" }, 400);
	}

	const tokens = await getFlickrTokens(c.env.DB, nsid, c.env.TOKEN_KEY);
	if (tokens === null) {
		return c.json({ error: "no_flickr_credentials" }, 409);
	}

	const pools = await getPhotoPoolsDetailed(photoId.data, {
		consumerKey: c.env.FLICKR_CONSUMER_KEY,
		consumerSecret: c.env.FLICKR_CONSUMER_SECRET,
		token: tokens.token,
		tokenSecret: tokens.tokenSecret,
	});

	// **Null is UNKNOWN, not empty.** Returning `[]` here would tell the picker the photo
	// is in no groups, and the user would then queue adds for groups it is already in --
	// straight into ADR-01's territory, since a duplicate add can reach a moderator.
	if (pools === null) {
		return c.json({ error: "flickr_unavailable" }, 502);
	}

	if (pools.length > MAX_PHOTO_POOLS) {
		return c.json(
			{
				error: "too_many_pools",
				total: pools.length,
				ceiling: MAX_PHOTO_POOLS,
			},
			502,
		);
	}

	return c.json({ groups: pools });
});

/**
 * **Where ADR-01 becomes visible.** Every other decision implements the stopping. This is
 * the only place the user finds out, and without it fail-polite is a promise the product
 * never keeps.
 */
apiRoutes.get("/api/v001/queue", async (c) => {
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
