import { classifyAdd } from "../adds/classify.js";

/**
 * The admin surface, built as FINDINGS rather than as a wall of counters.
 *
 * **This follows the toolchain-check doctrine: volume tracks actionability, not
 * importance.** A dashboard that always shows twelve numbers teaches its reader to skim,
 * and then the one evening a number matters they scroll past it. So this reports things
 * an admin can DO something about -- even if the action is only "read the logs" -- and
 * says "nothing needs you" when that is the truth.
 *
 * Three severities, and the middle one MUST NOT be collapsed into either neighbor:
 *
 *   act    Confirmed, and something can be done about it right now.
 *   watch  Real, worth knowing, nothing to do this minute.
 *   info   We cannot currently tell. Naming the blindness beats implying health.
 *
 * **What is deliberately NOT a finding: a long queue, or a high attempt count.** Waiting
 * is this product working. ADR-02 makes code 5 retryable exactly so FGA can sit out a
 * daily cap, and `docs/FLICKR.md` measured throttle modes of `day`, `week` and `month` --
 * a month-throttled group with forty requests ahead of you legitimately takes years.
 * Nothing in the schema records a group's throttle mode, so a stuck queue and a patient
 * one are identical from here. Alerting on either would be a warning that fires when
 * nobody can act, which is the fastest way to make every warning worthless. It is
 * reported once, as an `info` finding that names the missing input.
 *
 * **Reads only.** ADR-12 puts D1 writes at roughly 1,000x the cost of reads, so a
 * dashboard that recorded its own visits would cost more than the thing it measures.
 */

const DAY_MS = 86_400_000;

/**
 * How long a queue HEAD may go un-attempted before it is a finding.
 *
 * Two missed nights, not one. The sweep runs at 00:15 UTC, so a single miss is a
 * transient and alerting on it would fire on any one-off blip -- which is how a warning
 * stops being read.
 */
const HEAD_STALE_HOURS = 48;

/** Below this an unrecognized code is noise; at or above it, it is a pattern. */
const UNRECOGNIZED_CODE_FLOOR = 3;

export type Severity = "act" | "watch" | "info";

export type Finding = {
	readonly id: string;
	readonly severity: Severity;
	readonly headline: string;
	readonly detail: string;
	/** What to do. Never empty for `act`. */
	readonly action: string;
};

/** Raw figures, for when a finding prompts a closer look. Not the headline. */
export type Context = {
	readonly windowDays: number;
	readonly pendingTotal: number;
	readonly resolvedLast24h: number;
	readonly resolvedInWindow: number;
	readonly lastResolvedAt: number | null;
	readonly usersTotal: number;
	readonly usersNeedingRelink: number;
	/**
	 * Queue heads the sweep has not touched in HEAD_STALE_HOURS.
	 *
	 * **This is the load-bearing sweep check, and it is stronger than watching
	 * `resolved_at`.** A sweep can run correctly and resolve nothing -- every queue
	 * throttled is the product working, and `stoppedOnThrottle` is an expected outcome.
	 * So silence in resolutions proves nothing. An ATTEMPT is recorded before the call
	 * regardless of how it turns out, so a head that has not been attempted means the
	 * sweep did not reach it.
	 */
	readonly stalledHeads: number;
	readonly oldestHeadTouchedAt: number | null;
	readonly moderatedPairsTotal: number;
	readonly moderatedPairsInWindow: number;
	readonly reachedModeratorTwice: number;
	readonly codes: readonly CodeCount[];
};

export type CodeCount = {
	readonly code: number | null;
	readonly count: number;
	/** What `src/adds/classify.ts` does with this code today. */
	readonly disposition: string;
	readonly unrecognized: boolean;
};

export type Overview = {
	readonly generatedAt: number;
	readonly findings: readonly Finding[];
	readonly context: Context;
};

type Totals = {
	pending_total: number;
	last_24h: number;
	in_window: number;
	last_resolved: number | null;
};

export async function overview(
	db: D1Database,
	windowDays = 7,
): Promise<Overview> {
	const now = Date.now();
	const since = now - windowDays * DAY_MS;

	const totals = await db
		.prepare(
			`SELECT
         COALESCE(SUM(state = 'pending'), 0) AS pending_total,
         COALESCE(SUM(resolved_at >= ?1), 0) AS last_24h,
         COALESCE(SUM(resolved_at >= ?2), 0) AS in_window,
         MAX(resolved_at)                    AS last_resolved
       FROM requests`,
		)
		.bind(now - DAY_MS, since)
		.first<Totals>();

	const users = await db
		.prepare(
			"SELECT COUNT(*) AS total, COALESCE(SUM(needs_relink), 0) AS relink FROM users",
		)
		.first<{ total: number; relink: number }>();

	const pairs = await db
		.prepare(
			`SELECT
         COUNT(*)                                         AS total,
         COALESCE(SUM(first_seen_at >= ?1), 0)            AS in_window,
         COALESCE(SUM(last_seen_at  >  first_seen_at), 0) AS twice
       FROM moderated_pairs`,
		)
		.bind(since)
		.first<{ total: number; in_window: number; twice: number }>();

	/*
	 * Queue heads the sweep should have touched and did not.
	 *
	 * Mirrors `queueHeads()` in db/requests.ts, including its `needs_relink = 0` join --
	 * those users are excluded from the sweep BY DESIGN, so their heads go stale
	 * legitimately and counting them here would double-report the relink finding as a
	 * sweep failure.
	 *
	 * `COALESCE(last_attempt_at, created_at)` so a request that has never been attempted
	 * is measured from when it was queued. Without it, a brand-new request would read as
	 * infinitely stale the moment it was created.
	 */
	const heads = await db
		.prepare(
			`SELECT COUNT(*) AS stalled, MIN(COALESCE(r.last_attempt_at, r.created_at)) AS oldest
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
         AND COALESCE(r.last_attempt_at, r.created_at) < ?1`,
		)
		.bind(now - HEAD_STALE_HOURS * 3_600_000)
		.first<{ stalled: number; oldest: number | null }>();

	const { results: codeRows } = await db
		.prepare(
			`SELECT flickr_code AS code, COUNT(*) AS n
       FROM requests
       WHERE state = 'resolved' AND resolved_at >= ?1
       GROUP BY flickr_code
       ORDER BY n DESC
       LIMIT 20`,
		)
		.bind(since)
		.all<{ code: number | null; n: number }>();

	const codes: CodeCount[] = codeRows.map((row) => {
		const disposition = classifyAdd(row.code);
		return {
			code: row.code,
			count: row.n,
			disposition: disposition.kind,
			// Fell through ADR-02's default: terminal, not an auth failure, and not the
			// recognized "already in pool" code 3.
			unrecognized:
				disposition.kind === "terminal" &&
				!disposition.relink &&
				row.code !== null &&
				row.code !== 3,
		};
	});

	const context: Context = {
		windowDays,
		pendingTotal: totals?.pending_total ?? 0,
		resolvedLast24h: totals?.last_24h ?? 0,
		resolvedInWindow: totals?.in_window ?? 0,
		lastResolvedAt: totals?.last_resolved ?? null,
		usersTotal: users?.total ?? 0,
		usersNeedingRelink: users?.relink ?? 0,
		stalledHeads: heads?.stalled ?? 0,
		oldestHeadTouchedAt: heads?.oldest ?? null,
		moderatedPairsTotal: pairs?.total ?? 0,
		moderatedPairsInWindow: pairs?.in_window ?? 0,
		reachedModeratorTwice: pairs?.twice ?? 0,
		codes,
	};

	return { generatedAt: now, findings: findingsFor(context, now), context };
}

/**
 * Turns the figures into things worth telling somebody.
 *
 * Exported so a test can drive it with a fabricated `Context` and assert on exactly
 * which findings appear -- otherwise the thresholds could only be exercised by seeding a
 * database into each shape, and thresholds nobody tests are thresholds nobody trusts.
 */
export function findingsFor(context: Context, now: number): Finding[] {
	const findings: Finding[] = [];

	/*
	 * THE SWEEP WENT QUIET. The highest-value finding here, because it is the one
	 * failure that is completely invisible today: the cron stops firing, queues stop
	 * moving, and the product simply appears to be waiting -- which is what it always
	 * looks like.
	 *
	 * Conditioned on pending work existing. A silent sweep with an empty queue is a
	 * sweep with nothing to do, and alerting on it would fire on every quiet week.
	 */
	if (context.stalledHeads > 0) {
		const hours =
			context.oldestHeadTouchedAt === null
				? null
				: Math.floor((now - context.oldestHeadTouchedAt) / 3_600_000);

		findings.push({
			id: "sweep-not-reaching-queues",
			severity: "act",
			headline: `${context.stalledHeads} queue${context.stalledHeads === 1 ? "" : "s"} not attempted in over ${HEAD_STALE_HOURS} hours`,
			detail:
				`The sweep tries the head of every eligible queue each night and records the attempt before it calls Flickr, so a head this old was never reached.` +
				(hours === null ? "" : ` The oldest has waited ${hours} hours.`) +
				" Accounts flagged needs_relink are excluded, so this is not that.",
			action:
				"Read the nightly_sweep log lines for the last two nights, then confirm the Cron Trigger is still attached.",
		});
	}

	/*
	 * A CODE THIS PROJECT DOES NOT KNOW. ADR-02 makes an unrecognized code terminal,
	 * which is the safe default and a silent one -- a code Flickr shipped last month
	 * fails every request touching it and looks exactly like an ordinary refusal.
	 */
	const unknown = context.codes.filter(
		(c) => c.unrecognized && c.count >= UNRECOGNIZED_CODE_FLOOR,
	);
	for (const entry of unknown) {
		findings.push({
			id: `unknown-code-${entry.code}`,
			severity: "act",
			headline: `Flickr code ${entry.code} is not recognized (${entry.count} in ${context.windowDays}d)`,
			detail:
				"ADR-02 treats an unrecognized code as terminal, so every one of these stopped for good. That is the safe default, not necessarily the right one.",
			action:
				"Look the code up, add it to docs/FLICKR.md, and decide deliberately whether classify.ts should change. Widening the retryable set is the most dangerous edit here.",
		});
	}

	/*
	 * A USER CANNOT BE SERVED. `needs_relink` excludes them from queueHeads, so their
	 * queue freezes intact and silently. They will never be told by the sweep.
	 */
	if (context.usersNeedingRelink > 0) {
		findings.push({
			id: "users-need-relink",
			severity: "act",
			headline: `${context.usersNeedingRelink} account${context.usersNeedingRelink === 1 ? "" : "s"} need${context.usersNeedingRelink === 1 ? "s" : ""} to sign in again`,
			detail:
				"Flickr answered 98 or 99 for them. The sweep skips their queues entirely, so their requests sit untouched and nothing tells them.",
			action: "Sign in again to clear the flag. Nothing else unblocks it.",
		});
	}

	/*
	 * ATTENTION SPENT TWICE. Not a violation -- ADR-04 lets a person resubmit knowingly.
	 * It is `watch` because there is no immediate action, only a question worth asking
	 * if the number climbs.
	 */
	if (context.reachedModeratorTwice > 0) {
		findings.push({
			id: "moderator-twice",
			severity: "watch",
			headline: `${context.reachedModeratorTwice} photo/group pair${context.reachedModeratorTwice === 1 ? " has" : "s have"} reached a moderator more than once`,
			detail:
				"ADR-04 permits this when the person acknowledged the warning. It is also what a wrong pool lookup would produce, and the schema cannot tell those apart.",
			action:
				"No action unless this climbs. To make it decisive, persist acknowledgedModeration on the request row.",
		});
	}

	/*
	 * THE KNOWN BLIND SPOT, reported once and quietly.
	 *
	 * Terry's instinct was that long queues and high attempt counts felt like alerts and
	 * he was not convinced -- correctly. Without a group's throttle mode there is no way
	 * to tell a jammed queue from one patiently waiting out a monthly cap. Saying so is
	 * honest; alerting on it would cry wolf, and staying silent would imply health this
	 * cannot verify.
	 */
	if (context.pendingTotal > 0) {
		findings.push({
			id: "throttle-mode-unknown",
			severity: "info",
			headline: "Stuck queues cannot be detected yet",
			detail:
				"Telling a jammed queue from a patient one needs the group's throttle mode, which flickr.groups.getInfo returns and nothing stores. A month-throttled group can legitimately wait years.",
			action:
				"Persist throttle mode per group if this becomes worth alerting on. Until then, no queue length here means anything is wrong.",
		});
	}

	return findings;
}
