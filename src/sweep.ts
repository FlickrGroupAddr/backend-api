import type { Disposition } from "./adds/classify.js";
import {
	nextInQueue,
	type QueueHead,
	queueHeads,
	recordAttempt,
	resolveRequest,
} from "./db/requests.js";

/**
 * ADR-06's nightly engine and ADR-03's queue discipline.
 *
 * **`attempt` is injected, not imported.** The walking rules are the part that can be
 * subtly and expensively wrong, so they test against scripted outcomes with no network
 * and no Flickr account.
 */

export type AttemptFn = (head: QueueHead) => Promise<Disposition>;

export interface SweepReport {
	readonly queuesWalked: number;
	readonly attempted: number;
	readonly resolved: number;
	/** Expected, not an error. It is the product working. */
	readonly stoppedOnThrottle: number;
	readonly errors: readonly string[];
}

/** A guard, not a rule. ADR-03 permits continuing after each resolution, so a queue of
 *  terminal failures would otherwise walk its whole length in one night. */
const MAX_ATTEMPTS_PER_QUEUE = 25;

/** One queue's failure, as the line the report carries. Shared so both guards below
 *  record it identically -- an error whose shape depends on where it was caught is an
 *  error nobody can grep for. */
function describeFailure(head: QueueHead, cause: unknown): string {
	return `${head.nsid}/${head.groupId}: ${
		cause instanceof Error ? cause.message : String(cause)
	}`;
}

/** Queues are independent, so this MAY run them concurrently. It does not: nothing needs
 *  the speed, and sequential keeps the Flickr call rate low and the log readable. */
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
				// One queue failing MUST NOT abandon the others. A throw is also not a
				// reason to retry this pair -- we do not know what happened, and ADR-01
				// says an unknown outcome stops.
				errors.push(describeFailure(head, cause));
				break;
			}

			// ADR-03. Everything behind the head is blocked by the same cap, so trying
			// the next one is the queue-jump this rule forbids, not an optimization.
			if (disposition.kind === "retry") {
				stoppedOnThrottle++;
				break;
			}

			/**
			 * **THE WRITES NEED THE SAME GUARD, and for months they did not have it.**
			 *
			 * The `catch` above only ever covered the attempt, so a D1 error in
			 * `resolveRequest` or `nextInQueue` escaped `sweep` entirely -- abandoning
			 * every queue after this one, which is the exact thing the comment above
			 * forbids.
			 *
			 * **It also took the report with it.** `scheduled` logs the structured line
			 * AFTER `sweep` returns, so a throw here means the night is never logged.
			 * ADR-06 built that log so a BAD night is queryable, and it was the bad
			 * nights it lost.
			 *
			 * **A failed write leaves the request pending, which is the safe direction.**
			 * ADR-01 says an unknown outcome stops, and a pending row gets attempted
			 * again tomorrow rather than resolved on a guess.
			 */
			// **Bound before the try, because `head` is reassigned INSIDE it.** In the
			// catch, TypeScript can only assume the assignment may already have happened,
			// so `head` is `QueueHead | null` there and the error line would lose the pair
			// it is about. `tsc` refused the first version of this block for exactly that.
			const current = head;
			try {
				await resolveRequest(db, current, disposition);
				resolved++;
				head = await nextInQueue(db, current.nsid, current.groupId);
			} catch (cause) {
				errors.push(describeFailure(current, cause));
				break;
			}
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
