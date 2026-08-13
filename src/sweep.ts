import type { Disposition } from "./adds/classify.js";
import {
	nextInQueue,
	type QueueHead,
	queueHeads,
	recordAttempt,
	resolveRequest,
} from "./db/requests.js";

/**
 * ADR-04's nightly sweep, and ADR-10's queue discipline.
 *
 * The attempt itself is injected rather than imported. That keeps the walking
 * rules -- which are the part that can be subtly, expensively wrong -- testable
 * against scripted outcomes, with no network and no Flickr account. The
 * production wiring supplies a function that decrypts the user's token and
 * calls `flickr.groups.pools.add`.
 */

/** Attempts one add and classifies the result. Injected for testability. */
export type AttemptFn = (head: QueueHead) => Promise<Disposition>;

export interface SweepReport {
	readonly queuesWalked: number;
	readonly attempted: number;
	readonly resolved: number;
	/** Queues stopped by a retryable failure. Expected, not an error. */
	readonly stoppedOnThrottle: number;
	readonly errors: readonly string[];
}

/**
 * A guard, not a rule. ADR-10 permits continuing through a queue after each
 * resolution, and a queue of terminal failures would otherwise walk its whole
 * length in one night. Flickr's own throttle usually stops a queue long before
 * this does.
 */
const MAX_ATTEMPTS_PER_QUEUE = 25;

/**
 * Walks every queue with pending work.
 *
 * Queues are independent -- ADR-10 notes the sweep is embarrassingly parallel
 * across them -- but this runs them in sequence. Nothing here needs the
 * concurrency, and sequential execution keeps the Flickr call rate low and the
 * failure ordering easy to read in a log.
 */
export async function sweep(
	db: D1Database,
	attempt: AttemptFn,
): Promise<SweepReport> {
	const heads = await queueHeads(db);

	let attempted = 0;
	let resolved = 0;
	let stoppedOnThrottle = 0;
	const errors: string[] = [];

	for (const start of heads) {
		let head: QueueHead | null = start;

		for (let step = 0; step < MAX_ATTEMPTS_PER_QUEUE && head !== null; step++) {
			let disposition: Disposition;

			try {
				await recordAttempt(db, head.id);
				attempted++;
				disposition = await attempt(head);
			} catch (cause) {
				// One queue failing MUST NOT abandon the others. A thrown error is
				// also not a reason to retry this pair -- we do not know what
				// happened, and ADR-08 says an unknown outcome stops.
				errors.push(
					`${head.nsid}/${head.groupId}: ${
						cause instanceof Error ? cause.message : String(cause)
					}`,
				);
				break;
			}

			// ADR-10: a retryable failure ends this queue for the night. Nothing
			// behind the head may be attempted -- the request that has been waiting
			// longest keeps its place at the front.
			if (disposition.kind === "retry") {
				stoppedOnThrottle++;
				break;
			}

			await resolveRequest(db, head, disposition);
			resolved++;

			// The head resolved and left the queue, so whatever was behind it is now
			// the head and MAY be attempted in the same sweep.
			head = await nextInQueue(db, head.nsid, head.groupId);
		}
	}

	return {
		queuesWalked: heads.length,
		attempted,
		resolved,
		stoppedOnThrottle,
		errors,
	};
}
