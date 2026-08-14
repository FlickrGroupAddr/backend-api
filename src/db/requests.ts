import type { Disposition } from "../adds/classify.js";
import { outcomeColumn, reachedAModerator } from "../adds/classify.js";

/**
 * ADR-10's queues.
 *
 * **A "queue" is a VIEW over the `requests` table, not a table of its own:** every
 * pending row sharing an `(nsid, group_id)`, ordered by `id`. There is no queue object to
 * keep in step with the rows.
 */

export interface QueueHead {
	readonly id: number;
	readonly nsid: string;
	readonly photoId: string;
	readonly groupId: string;
}

/**
 * The head of every queue with pending work.
 *
 * **Users flagged `needs_relink` are excluded HERE rather than skipped later.** Their
 * stored token is known bad, so every attempt would burn a Flickr call to rediscover the
 * same thing. Filtering leaves their queues intact and resuming on next login; failing
 * those requests would silently empty a queue while the user knew nothing.
 */
export async function queueHeads(db: D1Database): Promise<QueueHead[]> {
	const { results } = await db
		.prepare(
			// The alias is `q`, not `inner` -- INNER is a SQLite keyword and using it
			// here is a bare syntax error rather than anything subtle.
			`SELECT r.id, r.nsid, r.photo_id, r.group_id
       FROM requests r
       JOIN users u ON u.nsid = r.nsid
       WHERE r.state = 'pending'
         AND u.needs_relink = 0
         AND r.id = (
           SELECT MIN(q.id) FROM requests q
           WHERE q.state = 'pending'
             AND q.nsid = r.nsid
             AND q.group_id = r.group_id
         )
       ORDER BY r.id`,
		)
		.all<{
			id: number;
			nsid: string;
			photo_id: string;
			group_id: string;
		}>();

	return results.map((row) => ({
		id: row.id,
		nsid: row.nsid,
		photoId: row.photo_id,
		groupId: row.group_id,
	}));
}

export async function nextInQueue(
	db: D1Database,
	nsid: string,
	groupId: string,
): Promise<QueueHead | null> {
	const row = await db
		.prepare(
			`SELECT id, nsid, photo_id, group_id
       FROM requests
       WHERE state = 'pending' AND nsid = ? AND group_id = ?
       ORDER BY id
       LIMIT 1`,
		)
		.bind(nsid, groupId)
		.first<{ id: number; nsid: string; photo_id: string; group_id: string }>();

	return row === null
		? null
		: {
				id: row.id,
				nsid: row.nsid,
				photoId: row.photo_id,
				groupId: row.group_id,
			};
}

/** ADR-05's cheap first pass. No network. The authoritative check is
 *  `flickr.photos.getAllContexts`, which also sees adds FGA did not make. */
export async function alreadySucceeded(
	db: D1Database,
	nsid: string,
	photoId: string,
	groupId: string,
): Promise<boolean> {
	const row = await db
		.prepare(
			`SELECT 1 AS hit FROM requests
       WHERE nsid = ? AND photo_id = ? AND group_id = ?
         AND state = 'resolved'
         AND outcome IN ('succeeded', 'already_in_pool')
       LIMIT 1`,
		)
		.bind(nsid, photoId, groupId)
		.first<{ hit: number }>();

	return row !== null;
}

export async function recordAttempt(db: D1Database, id: number): Promise<void> {
	await db
		.prepare(
			"UPDATE requests SET attempts = attempts + 1, last_attempt_at = ? WHERE id = ?",
		)
		.bind(Date.now(), id)
		.run();
}

/**
 * **Both writes go in one batch so a request cannot be marked resolved without the record
 * that a person saw it.** The request row is transient and the moderated record is not,
 * so losing that pairing is exactly the failure ADR-11 exists to prevent.
 */
export async function resolveRequest(
	db: D1Database,
	head: QueueHead,
	disposition: Disposition,
): Promise<void> {
	const outcome = outcomeColumn(disposition);
	if (outcome === null) {
		throw new Error("A retryable disposition does not resolve its request");
	}

	const code =
		disposition.kind === "moderated" || disposition.kind === "terminal"
			? disposition.code
			: null;

	const now = Date.now();

	const statements = [
		db
			.prepare(
				`UPDATE requests
         SET state = 'resolved', outcome = ?, flickr_code = ?, resolved_at = ?
         WHERE id = ?`,
			)
			.bind(outcome, code, now, head.id),
	];

	if (reachedAModerator(disposition)) {
		statements.push(
			db
				.prepare(
					`INSERT INTO moderated_pairs
             (nsid, photo_id, group_id, flickr_code, first_seen_at, last_seen_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT (nsid, photo_id, group_id) DO UPDATE SET
             flickr_code  = excluded.flickr_code,
             last_seen_at = excluded.last_seen_at`,
				)
				.bind(
					head.nsid,
					head.photoId,
					head.groupId,
					disposition.code,
					now,
					now,
				),
		);
	}

	await db.batch(statements);
}

/**
 * ADR-16. Two identifiers with different jobs: `id` orders and stays inside the server,
 * `publicId` is the opaque handle that appears in URLs.
 *
 * **v4, not v7.** This value exists to be unguessable, and v7 spends its first 48 bits on
 * a plaintext timestamp, republishing the request's creation time to anyone holding it.
 */
export async function enqueue(
	db: D1Database,
	nsid: string,
	photoId: string,
	groupId: string,
): Promise<{ id: number; publicId: string }> {
	const publicId = crypto.randomUUID();

	const row = await db
		.prepare(
			`INSERT INTO requests (public_id, nsid, photo_id, group_id, created_at)
       VALUES (?, ?, ?, ?, ?)
       RETURNING id`,
		)
		.bind(publicId, nsid, photoId, groupId, Date.now())
		.first<{ id: number }>();

	if (row === null) throw new Error("Enqueue returned no row");
	return { id: row.id, publicId };
}

/** ADR-10 lets the API attempt immediately only when a request is the SOLE unresolved one
 *  in its queue. A queue of length one is the only case where an immediate attempt cannot
 *  take an allowance slot from something that waited longer. */
export async function pendingCount(
	db: D1Database,
	nsid: string,
	groupId: string,
): Promise<number> {
	const row = await db
		.prepare(
			`SELECT COUNT(*) AS n FROM requests
       WHERE state = 'pending' AND nsid = ? AND group_id = ?`,
		)
		.bind(nsid, groupId)
		.first<{ n: number }>();

	return row?.n ?? 0;
}

/** `already_resolved` carries the outcome, because "it went to a moderator" and "it
 *  failed" are very different things to read. */
export type WithdrawResult =
	| { readonly kind: "withdrawn" }
	| { readonly kind: "not_found" }
	| { readonly kind: "already_resolved"; readonly outcome: string };

/**
 * **The `state = 'pending'` guard is IN the UPDATE, and that is the honesty of this
 * feature.** Reaching a moderator resolves a request at that instant, so anything still
 * pending has provably never been in front of a person.
 *
 * As a condition, the race with the nightly sweep becomes the database's problem: if the
 * sweep resolves this row first, the UPDATE matches nothing and the user is told it was
 * too late. **A read-then-write would report success for a request just submitted to a
 * human**, which is the one wrong answer this project is organized against.
 *
 * `nsid` is a condition for the same reason, and the follow-up lookup is scoped to the
 * caller too, so a miss cannot be used to probe which ids exist.
 */
export async function withdrawRequest(
	db: D1Database,
	nsid: string,
	publicId: string,
): Promise<WithdrawResult> {
	const withdrawn = await db
		.prepare(
			`UPDATE requests
       SET state = 'resolved', outcome = 'withdrawn', resolved_at = ?
       WHERE public_id = ? AND nsid = ? AND state = 'pending'
       RETURNING id`,
		)
		.bind(Date.now(), publicId, nsid)
		.first<{ id: number }>();

	if (withdrawn !== null) return { kind: "withdrawn" };

	const existing = await db
		.prepare("SELECT outcome FROM requests WHERE public_id = ? AND nsid = ?")
		.bind(publicId, nsid)
		.first<{ outcome: string | null }>();

	if (existing === null) return { kind: "not_found" };

	return {
		kind: "already_resolved",
		// 0001's CHECK makes a resolved row's outcome non-null. The fallback exists so a
		// future schema change cannot turn this into a crash.
		outcome: existing.outcome ?? "unknown",
	};
}

/** ADR-11. */
export async function pairReachedAModerator(
	db: D1Database,
	nsid: string,
	photoId: string,
	groupId: string,
): Promise<{ code: number; firstSeenAt: number } | null> {
	const row = await db
		.prepare(
			`SELECT flickr_code, first_seen_at FROM moderated_pairs
       WHERE nsid = ? AND photo_id = ? AND group_id = ?`,
		)
		.bind(nsid, photoId, groupId)
		.first<{ flickr_code: number; first_seen_at: number }>();

	return row === null
		? null
		: { code: row.flickr_code, firstSeenAt: row.first_seen_at };
}
