import { z } from "zod";

/**
 * The API contract, as parsers rather than as types.
 *
 * **This is the reason the UI shares a language with the Worker.** A `type` describes
 * what the server promised; a schema checks what it actually sent. The second one
 * catches a rename that the first one would let through silently, and Terry cannot
 * review TypeScript, so the check has to be mechanical rather than a reading.
 *
 * **These MUST stay in step with `src/routes/api.ts`.** They are deliberately written
 * against the JSON that route returns, field for field, so a diff between the two is
 * readable. A generated client was rejected: it would add a build step and a dependency
 * to restate 120 lines that change about once a month.
 */

/** ADR-04. Flickr reports no rejection, so 6 and 7 are all that is knowable. */
export const moderationCode = z.union([z.literal(6), z.literal(7)]);

/** `GET /api/v001/me` */
export const me = z.object({ nsid: z.string() });

/**
 * `GET /api/v001/groups`
 *
 * `poolModerated` is the field that matters to a person: it means an add goes to a
 * volunteer rather than straight into the pool. `throttle` is deliberately absent --
 * it needs one `groups.getInfo` call per group, and 372 groups took 53 seconds.
 */
export const group = z.object({
	id: z.string(),
	name: z.string().nullable(),
	photos: z.number(),
	members: z.number(),
	poolModerated: z.boolean(),
	inviteOnly: z.boolean(),
});

export const groupList = z.object({ groups: z.array(group) });

/** `GET /api/v001/groups/:groupId`. Shape is Flickr's, so it is read loosely. */
export const groupInfo = z.looseObject({});

/**
 * `POST /api/v001/requests`, and it has three shapes rather than one.
 *
 * **The 409 is not an error and MUST NOT be rendered as one.** It is ADR-04 asking a
 * question: this photo already reached a moderator, submit anyway? Treating it as a
 * failure is how the warning gets styled in red and ignored.
 */
export const submitted = z.discriminatedUnion("status", [
	z.object({
		status: z.literal("queued"),
		publicId: z.uuidv4(),
	}),
	z.object({
		status: z.literal("resolved"),
		publicId: z.uuidv4(),
		disposition: z.string(),
	}),
	z.object({
		status: z.literal("needs_acknowledgement"),
		reason: z.literal("reached_a_moderator"),
		flickrCode: moderationCode,
		firstSeenAt: z.number(),
		/** Code 7 means the ORIGINAL submission is still undecided. */
		stillPending: z.boolean(),
	}),
]);

/**
 * `GET /api/v001/queue`
 *
 * Grouped, never one flat list. A flat list reads as a single queue when there are
 * many, which makes correct ADR-03 ordering look like a bug the first time a later
 * request lands ahead of an earlier one somewhere else.
 */
export const queuedRequest = z.object({
	publicId: z.uuidv4(),
	photoId: z.string(),
	state: z.enum(["pending", "resolved"]),
	outcome: z
		.enum([
			"succeeded",
			"already_in_pool",
			"queued_for_moderator",
			"failed",
			"withdrawn",
		])
		.nullable(),
	flickrCode: z.number().nullable(),
	attempts: z.number(),
	queuedAt: z.number(),
	lastAttemptAt: z.number().nullable(),
	resolvedAt: z.number().nullable(),
	/** Null on a resolved request. 1-based position within its own queue. */
	position: z.number().nullable(),
});

export const queuePage = z.object({
	queues: z.array(
		z.object({ groupId: z.string(), requests: z.array(queuedRequest) }),
	),
	/**
	 * ADR-17. **Null means the end, stated by the server.** Inferring it from a short
	 * page is wrong exactly when the last page is exactly `limit` long.
	 */
	nextCursor: z.uuidv4().nullable(),
});

export const withdrawn = z.object({
	status: z.literal("withdrawn"),
	publicId: z.uuidv4(),
});

export type Group = z.infer<typeof group>;
export type Submitted = z.infer<typeof submitted>;
export type QueuedRequest = z.infer<typeof queuedRequest>;
export type QueuePage = z.infer<typeof queuePage>;
