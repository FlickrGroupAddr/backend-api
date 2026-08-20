<script lang="ts">
import { api } from "../lib/api.js";
import type { QueuePage } from "../lib/contract.js";
import { ago, describeError, explain, ticksFor, type Tone } from "../lib/outcomes.js";

/*
 * The queue. **This is where ADR-01 becomes visible.** Every other part of the system
 * implements the stopping; without this screen, fail-polite is a promise the product
 * never keeps.
 *
 * Grouped by group, never one flat list. A flat list reads as a single queue when there
 * are several, which makes correct FIFO ordering look like a bug the first time a later
 * request lands ahead of an earlier one somewhere else.
 */

let page = $state<QueuePage | null>(null);
let loading = $state(true);
let error = $state<string | null>(null);
let showAll = $state(false);
let busy = $state<string | null>(null);

/*
 * **LAST CALLER WINS, not last REPLY.**
 *
 * `load` is started from two places -- the `$effect` below on every `showAll` change,
 * and `withdraw` -- and nothing cancelled the previous one. Two calls in flight resolve
 * in whatever order the network decides, so toggling "Include finished" on and off
 * quickly could leave `page` holding the "all" reply while the checkbox reads unchecked.
 *
 * **That is worse than a stale spinner: the screen shows the wrong SET of requests and
 * says nothing about it.** This is the one screen where ADR-01 becomes visible, so a
 * quietly wrong list is exactly the thing it cannot afford.
 *
 * The counter is the whole fix. A stale call still completes -- there is no aborting a
 * `fetch` already sent -- it just declines to write anything, including `loading` and
 * `error`. Clearing `loading` from a superseded call is the same defect one step
 * quieter: the spinner would vanish while the real request was still out.
 */
let generation = 0;

async function load(): Promise<void> {
	const mine = ++generation;
	loading = true;
	error = null;
	try {
		const got = await api.queue(null, showAll ? "all" : "pending");
		if (mine !== generation) return;
		page = got;
	} catch (caught) {
		if (mine !== generation) return;
		console.error("GET /api/v001/queue failed", caught);
		error = describeError(caught, "loading your queue");
	} finally {
		if (mine === generation) loading = false;
	}
}

async function loadMore(): Promise<void> {
	if (page === null || page.nextCursor === null) return;

	// **Same guard, for the same reason.** A `load` that starts while this page is in
	// flight bumps the counter, and merging a second page of `all` into a freshly
	// loaded `pending` list would produce a list that matches no filter at all.
	const mine = generation;
	const next = await api.queue(page.nextCursor, showAll ? "all" : "pending");
	if (mine !== generation || page === null) return;

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
		console.error("POST withdraw failed", caught);
		error = describeError(caught, "withdrawing that request");
	} finally {
		busy = null;
	}
}

$effect(() => {
	// Reads showAll, so flipping the toggle refetches. The dependency does the work
	// instead of a change handler wired up by hand.
	void showAll;
	void load();
});

const total = $derived(
	page === null ? 0 : page.queues.reduce((sum, q) => sum + q.requests.length, 0),
);

const rail = (tone: Tone): string => `s-${tone}`;
</script>

<div class="head">
	<h2>Queue</h2>
	<label class="small muted toggle">
		<input type="checkbox" bind:checked={showAll} />
		Include finished
	</label>
</div>

<!--
	The standing explanation, stated ONCE for the page.

	It was per-row first, which put the same sentence on ten rows and buried what
	varied. Moving it to the card header only made it repeat three times instead of
	ten -- the same mistake one level up. A fact true of every queue belongs where
	there is exactly one of it.
-->
{#if !loading && error === null && total > 0}
	<p class="small muted standing">
		Flickr caps how many photos you may add to a group each day. One request from each
		line goes every night, in the order you added them.
	</p>
{/if}

{#if loading && page === null}
	<p class="small muted">Loading...</p>
{:else if error !== null}
	<div class="panel panel-quiet railed s-stopped">
		<p class="small" style="margin:0 0 .5rem">{error}</p>
		<button class="small" onclick={load}>Try again</button>
	</div>
{:else if total === 0}
	<div class="panel panel-quiet">
		<p class="small" style="margin:0 0 .3rem">
			{showAll ? "Nothing here yet." : "Nothing waiting."}
		</p>
		<p class="small muted" style="margin:0">
			{showAll
				? "Add a photo to a group and it will show up here."
				: "Everything you have submitted has finished. Tick “Include finished” to see it."}
		</p>
	</div>
{:else}
	{#each page?.queues ?? [] as queue (queue.groupId)}
		{@const waiting = queue.requests.filter((r) => r.state === "pending").length}
		<section class="card">
			<header class="card-head">
				<span class="mono small">{queue.groupId}</span>
				<span class="small muted card-note">
					{waiting > 0
						? `${waiting} waiting`
						: `${queue.requests.length} finished`}
				</span>
			</header>

			<ul class="plain">
				{#each queue.requests as request (request.publicId)}
					{@const said = explain(request)}
					{@const ticks = ticksFor(request.position)}
					<li class="entry railed {rail(said.tone)}">
						{#if ticks !== null}
							<!--
								THE SIGNATURE. Hollow ticks are the requests ahead of yours;
								the filled one is yours. ADR-03 attempts strictly in append
								order per (user, group), and that ordering is the behavior
								most often mistaken for a bug. A row of ticks shows a line,
								and a line explains itself.
							-->
							<span
								class="queue-ticks pos"
								role="img"
								aria-label="Position {request.position} in this group's queue"
							>
								{#each ticks.marks as isYou, i (i)}
									<span class="tick" class:is-you={isYou}></span>
								{/each}
								{#if ticks.overflow > 0}
									<span class="mono ovf">+{ticks.overflow}</span>
								{/if}
							</span>
						{:else}
							<span class="pos"></span>
						{/if}

						<span class="hl {rail(said.tone)}">{said.headline}</span>
						<span class="mono small muted photo">{request.photoId}</span>

						{#if said.detail !== null}
							<!--
								Deliberately NOT truncated. Clipping is right for a photo id
								and wrong for the sentence that carries ADR-01 -- the render
								showed "...your photo is in the..." and cut the promise in half.
								Only a few rows per page carry a detail, so wrapping costs
								nothing the dense layout was protecting.
							-->
							<span class="small muted detail">{said.detail}</span>
						{:else}
							<span class="detail"></span>
						{/if}

						{#if request.attempts > 0}
							<span class="mono small muted tries"
								>{request.attempts}&#215;</span
							>
						{:else}
							<span class="tries"></span>
						{/if}

						<span class="small muted when"
							>{ago(request.resolvedAt ?? request.queuedAt)}</span
						>

						{#if request.state === "pending"}
							<button
								class="linky small"
								disabled={busy === request.publicId}
								onclick={() => withdraw(request.publicId)}
							>
								{busy === request.publicId ? "Withdrawing..." : "Withdraw"}
							</button>
						{:else}
							<span class="withdraw-slot"></span>
						{/if}
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
		margin-bottom: 0.9rem;
	}

	.toggle {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}

	.standing {
		max-width: 56ch;
		margin: -0.4rem 0 1rem;
	}

	.card {
		border: 1px solid var(--rule);
		border-radius: var(--radius);
		margin-bottom: 0.85rem;
		overflow: hidden;
	}

	/* The group id is the card's identity and sits on a quiet band, so the entries
	   below it read as belonging to it rather than as a flat list with a label. */
	.card-head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.5rem 0.9rem;
		background: var(--paper-2);
		border-bottom: 1px solid var(--rule);
	}

	/*
	 * ONE LINE PER REQUEST, on a grid so every column lines up down the card. A console
	 * is read by scanning a column, not by reading rows — and the two-line version of
	 * this made ten requests fill a screen that now holds thirty.
	 */
	.entry {
		display: grid;
		grid-template-columns:
			5.6rem minmax(6rem, auto) 7.5rem minmax(0, 1fr)
			2.6rem 6rem 5.2rem;
		align-items: baseline;
		gap: 0.75rem;
		padding: 0.34rem 0.9rem 0.34rem 0;
		margin-left: 0.9rem;
		border-top: 1px solid var(--rule);
	}

	.entry:first-child {
		border-top: 0;
	}

	.pos {
		justify-self: start;
	}

	.ovf {
		font-size: var(--t-xs);
		color: var(--muted);
		margin-left: 2px;
	}

	.hl {
		font-weight: 600;
		font-size: var(--t-sm);
	}

	.photo,
	.tries,
	.when {
		text-align: right;
	}

	.photo {
		text-align: left;
	}

	.detail {
		min-width: 0;
	}

	/*
	 * A quiet text button. Ten stacked bordered buttons shouted louder than the data
	 * they sat beside; withdrawing is rare and should not be the loudest thing on a row.
	 * It keeps a real focus ring, so quieting it does not cost keyboard access.
	 */
	.linky {
		border: 0;
		background: transparent;
		padding: 0;
		color: var(--muted);
		text-decoration: underline;
		text-decoration-color: var(--rule);
		text-underline-offset: 2px;
		justify-self: end;
	}

	.linky:hover:not(:disabled) {
		background: transparent;
		color: var(--stop);
		text-decoration-color: currentColor;
	}

	@media (max-width: 60rem) {
		.entry {
			grid-template-columns: 5.6rem minmax(6rem, auto) minmax(0, 1fr) 6rem 5.2rem;
		}

		.photo,
		.tries {
			display: none;
		}
	}

	@media (max-width: 34rem) {
		.entry {
			grid-template-columns: 4.2rem minmax(0, 1fr) 5rem;
			row-gap: 0.15rem;
		}

		.detail,
		.when {
			display: none;
		}
	}
</style>
