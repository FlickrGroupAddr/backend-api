import type { Disposition } from "../adds/classify.js";
import { outcomeColumn, reachedAModerator } from "../adds/classify.js";

/**
 * The add-request queues, per ADR-10.
 *
 * "Queue" is a view over the `requests` table rather than a table of its own: a
 * queue is every pending row sharing an `(nsid, group_id)`, ordered by `id`.
 * There is no queue object to keep in step with the rows.
 */

export interface QueueHead {
	readonly id: number;
	readonly nsid: string;
	readonly photoId: string;
	readonly groupId: string;
}

/**
 * The head of every queue that currently has pending work.
 *
 * Written as a correlated subquery rather than leaning on SQLite's bare-column
 * behavior with `MIN()`. That shortcut works and is documented, but this form
 * is obviously correct to a reader who does not know the shortcut, and it uses
 * the partial index directly.
 *
 * **Users flagged `needs_relink` are excluded here rather than skipped later.**
 * ADR-07 makes the request that met code 98 or 99 terminal, and after that the
 * user's stored token is known bad -- every further attempt would burn a Flickr
 * call to rediscover the same thing. Filtering at the query means their queues
 * simply sit still, intact, and resume when they log in again. Failing those
 * requests instead would silently empty a user's queue while they were unaware
 * anything was wrong.
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

/** The next pending request behind a resolved head, if the queue has one. */
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

/**
 * ADR-05's cheap first-pass guard: has this pair already succeeded?
 *
 * The authoritative check is `flickr.photos.getAllContexts`, which also sees
 * adds FGA did not make. This one costs no network call and catches the common
 * case -- an overlapping or re-run sweep.
 */
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

/** Records that an attempt happened, whatever it produced. */
export async function recordAttempt(db: D1Database, id: number): Promise<void> {
	await db
		.prepare(
			"UPDATE requests SET attempts = attempts + 1, last_attempt_at = ? WHERE id = ?",
		)
		.bind(Date.now(), id)
		.run();
}

/**
 * Resolves a request and, where ADR-11 requires it, writes the permanent
 * moderated-pair record.
 *
 * Both writes happen in one batch so a request cannot be marked resolved
 * without the record that a person saw it. Losing that pairing is exactly the
 * failure ADR-11 exists to prevent -- the request row is transient and the
 * moderated record is not.
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

	// Only these two dispositions carry a Flickr code. `retry` does too, but it
	// never reaches here -- the guard above rejects it, since a retryable outcome
	// leaves the request pending rather than resolving it.
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

/** Adds a request to the back of its queue. ADR-10. */
export async function enqueue(
	db: D1Database,
	nsid: string,
	photoId: string,
	groupId: string,
): Promise<number> {
	const row = await db
		.prepare(
			`INSERT INTO requests (nsid, photo_id, group_id, created_at)
       VALUES (?, ?, ?, ?)
       RETURNING id`,
		)
		.bind(nsid, photoId, groupId, Date.now())
		.first<{ id: number }>();

	if (row === null) throw new Error("Enqueue returned no row");
	return row.id;
}

/**
 * How many pending requests sit in a queue.
 *
 * ADR-10 lets the API Worker attempt a new request immediately only when it is
 * the SOLE unresolved request in its queue -- a queue of length one is the only
 * case where an immediate attempt cannot take an allowance slot from something
 * that has been waiting longer.
 */
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

/** ADR-11: has this pair already been in front of a moderator? */
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
