<script lang="ts">
import { api } from "../lib/api.js";
import type { QueuePage } from "../lib/contract.js";
import { ago, explain } from "../lib/outcomes.js";

/*
 * The queue.
 *
 * **This is where ADR-01 becomes visible.** Every other part of the system implements
 * the stopping; without this screen, fail-polite is a promise the product never keeps.
 *
 * Grouped by group, never one flat list. A flat list reads as a single queue when
 * there are several, which makes correct FIFO ordering look like a bug the first time
 * a later request lands ahead of an earlier one somewhere else.
 */

let page = $state<QueuePage | null>(null);
let loading = $state(true);
let error = $state<string | null>(null);
let showAll = $state(false);
let busy = $state<string | null>(null);

async function load(): Promise<void> {
	loading = true;
	error = null;
	try {
		page = await api.queue(null, showAll ? "all" : "pending");
	} catch (caught) {
		error =
			caught instanceof Error ? caught.message : "Could not load your queue.";
	} finally {
		loading = false;
	}
}

async function loadMore(): Promise<void> {
	if (page === null || page.nextCursor === null) return;
	const next = await api.queue(page.nextCursor, showAll ? "all" : "pending");

	// Merge by group, so a group split across a page boundary stays one card.
	const merged = new Map(page.queues.map((q) => [q.groupId, [...q.requests]]));
	for (const queue of next.queues) {
		merged.set(queue.groupId, [
			...(merged.get(queue.groupId) ?? []),
			...queue.requests,
		]);
	}

	page = {
		queues: [...merged].map(([groupId, requests]) => ({ groupId, requests })),
		nextCursor: next.nextCursor,
	};
}

async function withdraw(publicId: string): Promise<void> {
	busy = publicId;
	try {
		await api.withdraw(publicId);
		await load();
	} catch (caught) {
		error =
			caught instanceof Error ? caught.message : "Could not withdraw that.";
	} finally {
		busy = null;
	}
}

$effect(() => {
	// Reads `showAll`, so flipping the toggle refetches. That is the dependency
	// doing real work rather than a change handler wired up by hand.
	void showAll;
	void load();
});

const total = $derived(
	page === null
		? 0
		: page.queues.reduce((sum, q) => sum + q.requests.length, 0),
);
</script>

<div class="head">
	<h2>Your queue</h2>
	<label class="small muted toggle">
		<input type="checkbox" bind:checked={showAll} />
		Include finished
	</label>
</div>

{#if loading && page === null}
	<p class="muted">Loading...</p>
{:else if error !== null}
	<p class="stop">{error}</p>
	<p><button onclick={load}>Try again</button></p>
{:else if total === 0}
	<p class="muted">
		{showAll
			? "Nothing here yet. Add a photo to a group and it will show up."
			: "Nothing waiting. Everything you have submitted has finished."}
	</p>
{:else}
	{#each page?.queues ?? [] as queue (queue.groupId)}
		<section class="card">
			<h3 class="truncate">{queue.groupId}</h3>

			<ul class="plain">
				{#each queue.requests as request (request.publicId)}
					{@const said = explain(request)}
					<li class="entry">
						<div class="entry-main">
							<span class="dot dot-{said.tone}" aria-hidden="true"></span>
							<div class="grow">
								<div class="entry-head">
									<strong>{said.headline}</strong>
									<span class="small muted">photo {request.photoId}</span>
									<span class="small muted">
										{ago(request.resolvedAt ?? request.queuedAt)}
									</span>
								</div>
								<p class="small detail">{said.detail}</p>
							</div>

							{#if request.state === "pending"}
								<button
									class="small"
									disabled={busy === request.publicId}
									onclick={() => withdraw(request.publicId)}
								>
									{busy === request.publicId ? "Withdrawing..." : "Withdraw"}
								</button>
							{/if}
						</div>
					</li>
				{/each}
			</ul>
		</section>
	{/each}

	{#if page?.nextCursor !== null}
		<p><button onclick={loadMore}>Load more</button></p>
	{/if}
{/if}

<style>
	.head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1rem;
		flex-wrap: wrap;
	}

	.toggle {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}

	.card {
		border: 1px solid var(--line);
		border-radius: var(--radius);
		padding: 0.75rem 1rem;
		margin: 0.75rem 0;
	}

	.card h3 {
		margin: 0 0 0.35rem;
		font-size: 0.95rem;
	}

	.entry {
		padding: 0.5rem 0;
		border-top: 1px solid var(--line);
	}

	.entry:first-child {
		border-top: 0;
	}

	.entry-main {
		display: flex;
		align-items: flex-start;
		gap: 0.65rem;
	}

	.entry-head {
		display: flex;
		gap: 0.6rem;
		align-items: baseline;
		flex-wrap: wrap;
	}

	.detail {
		margin: 0.15rem 0 0;
		color: var(--muted);
		max-width: 46rem;
	}

	/* A colored dot rather than a colored row. The status is scannable down the left
	   edge, and the sentence stays readable. */
	.dot {
		width: 0.6rem;
		height: 0.6rem;
		border-radius: 50%;
		margin-top: 0.45rem;
		flex: none;
	}

	.dot-waiting {
		background: var(--muted);
	}
	.dot-good {
		background: var(--ok);
	}
	.dot-human {
		background: var(--warn-line);
	}
	.dot-stopped {
		background: var(--stop);
	}
</style>
