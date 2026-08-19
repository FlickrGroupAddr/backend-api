<script lang="ts">
import { api, ApiError } from "../lib/api.js";
import type { AdminOverview, Finding } from "../lib/contract.js";
import { ago, describeError } from "../lib/outcomes.js";

/*
 * ADR-19. Findings, not figures.
 *
 * **This page is SUPPOSED to be nearly empty.** A dashboard that always shows twelve
 * numbers teaches its reader to skim, and then the one night a number matters they
 * scroll past it. Silence here is the healthy state and says so in one line.
 *
 * The raw counts live behind a disclosure, because a finding sometimes prompts a closer
 * look and the numbers should be reachable without being the headline.
 */

let data = $state<AdminOverview | null>(null);
let loading = $state(true);
/** A non-admin gets 404 from the API. That is not an error to explain, it is a wall. */
let forbidden = $state(false);
let error = $state<string | null>(null);
let showNumbers = $state(false);

$effect(() => {
	void (async () => {
		try {
			data = await api.adminOverview();
		} catch (caught) {
			if (caught instanceof ApiError && caught.status === 404) {
				forbidden = true;
			} else {
				console.error("GET /api/v001/admin/overview failed", caught);
				error = describeError(caught, "loading the admin overview");
			}
		} finally {
			loading = false;
		}
	})();
});

/** Severity maps onto the same four state rails the rest of the product uses. */
function rail(severity: Finding["severity"]): string {
	if (severity === "act") return "s-stopped";
	if (severity === "watch") return "s-human";
	return "s-waiting";
}

const acts = $derived(
	data === null ? [] : data.findings.filter((f) => f.severity === "act"),
);
const others = $derived(
	data === null ? [] : data.findings.filter((f) => f.severity !== "act"),
);
</script>

{#if loading}
	<p class="small muted">Loading...</p>
{:else if forbidden}
	<h2>No such page</h2>
	<p class="muted">Nothing lives at <code>/admin</code>.</p>
{:else if error !== null}
	<div class="panel panel-quiet railed s-stopped">
		<p class="small" style="margin:0">{error}</p>
	</div>
{:else if data !== null}
	<div class="head">
		<h2>Health</h2>
		<span class="small muted">
			Last {data.context.windowDays} days · read {ago(data.generatedAt)}
		</span>
	</div>

	{#if data.findings.length === 0}
		<!-- The healthy state, and it is one line on purpose. -->
		<div class="panel panel-quiet railed s-good">
			<p class="small" style="margin:0">
				<strong>Nothing needs you.</strong> No stalled queues, no unrecognized Flickr
				codes, and no account locked out.
			</p>
		</div>
	{:else}
		{#each [...acts, ...others] as finding (finding.id)}
			<article class="finding railed {rail(finding.severity)}">
				<div class="finding-head">
					<strong>{finding.headline}</strong>
					<span class="sev sev-{finding.severity}">{finding.severity}</span>
				</div>
				<p class="small muted detail">{finding.detail}</p>
				<p class="small action">{finding.action}</p>
			</article>
		{/each}
	{/if}

	<!--
		The numbers are DELIBERATELY behind a click. They are for confirming a finding,
		not for scanning, and putting them on the page would rebuild the wall of
		counters this design exists to avoid.
	-->
	<details class="numbers" bind:open={showNumbers}>
		<summary class="small muted">The numbers behind this</summary>

		<dl class="grid small">
			<dt>Waiting</dt>
			<dd class="mono">{data.context.pendingTotal}</dd>
			<dt>Resolved, 24h</dt>
			<dd class="mono">{data.context.resolvedLast24h}</dd>
			<dt>Resolved, {data.context.windowDays}d</dt>
			<dd class="mono">{data.context.resolvedInWindow}</dd>
			<dt>Queue heads not attempted in 48h</dt>
			<dd class="mono">{data.context.stalledHeads}</dd>
			<dt>Accounts</dt>
			<dd class="mono">{data.context.usersTotal}</dd>
			<dt>Accounts needing re-link</dt>
			<dd class="mono">{data.context.usersNeedingRelink}</dd>
			<dt>Pairs a moderator has seen</dt>
			<dd class="mono">{data.context.moderatedPairsTotal}</dd>
			<dt>...seen more than once</dt>
			<dd class="mono">{data.context.reachedModeratorTwice}</dd>
		</dl>

		{#if data.context.codes.length > 0}
			<p class="eyebrow" style="margin-top:1rem">Flickr codes</p>
			<ul class="plain codes">
				{#each data.context.codes as entry (entry.code ?? "none")}
					<li class="code-row">
						<span class="mono">{entry.code ?? "—"}</span>
						<span class="small muted grow">
							{entry.disposition}{entry.unrecognized ? " · unrecognized" : ""}
						</span>
						<span class="mono">{entry.count}</span>
					</li>
				{/each}
			</ul>
		{/if}
	</details>
{/if}

<style>
	.head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1rem;
		flex-wrap: wrap;
		margin-bottom: 0.9rem;
	}

	.finding {
		border: 1px solid var(--rule);
		border-left-width: var(--rail);
		border-radius: var(--radius);
		padding: 0.7rem 0.9rem;
		margin-bottom: 0.6rem;
		max-width: 56rem;
	}

	.finding-head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.75rem;
	}

	.sev {
		font-size: var(--t-xs);
		text-transform: uppercase;
		letter-spacing: 0.07em;
		border-radius: 999px;
		padding: 0 0.4rem;
		border: 1px solid currentColor;
		flex: none;
	}

	.sev-act {
		color: var(--stop);
	}
	.sev-watch {
		color: var(--human);
	}
	.sev-info {
		color: var(--muted);
	}

	.detail {
		margin: 0.25rem 0 0.4rem;
	}

	/* The action is the reason the finding exists, so it is the only line in ink. */
	.action {
		margin: 0;
		color: var(--ink);
	}

	.numbers {
		margin-top: 1.75rem;
		max-width: 56rem;
	}

	.numbers summary {
		cursor: pointer;
	}

	.grid {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: 0.2rem 1rem;
		margin: 0.75rem 0 0;
	}

	.grid dt {
		color: var(--muted);
	}

	.grid dd {
		margin: 0;
		text-align: right;
	}

	.code-row {
		display: flex;
		gap: 0.75rem;
		align-items: baseline;
		padding: 0.15rem 0;
	}

	@media (max-width: 34rem) {
		.finding-head {
			flex-direction: column;
			gap: 0.2rem;
		}
	}
</style>
