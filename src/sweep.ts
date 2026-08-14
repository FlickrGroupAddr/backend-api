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
				errors.push(
					`${head.nsid}/${head.groupId}: ${
						cause instanceof Error ? cause.message : String(cause)
					}`,
				);
				break;
			}

			// ADR-03. Everything behind the head is blocked by the same cap, so trying
			// the next one is the queue-jump this rule forbids, not an optimization.
			if (disposition.kind === "retry") {
				stoppedOnThrottle++;
				break;
			}

			await resolveRequest(db, head, disposition);
			resolved++;

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
