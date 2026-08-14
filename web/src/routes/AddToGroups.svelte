<script lang="ts">
import { SvelteSet } from "svelte/reactivity";
import { api } from "../lib/api.js";
import type { Group } from "../lib/contract.js";
import { describeError } from "../lib/outcomes.js";
import {
	awaitingAcknowledgement,
	type Batch,
	photoIdFromUrl,
	runBatch,
} from "../lib/submission.js";

/*
 * One photo, many groups.
 *
 * TWO PANELS SIDE BY SIDE, and the right one is not a preview. Submissions are
 * sequential and land one at a time over ten-odd seconds, so the results column is a
 * live log of something actually happening. That is what earns the width -- a static
 * preview pane beside a form would just be a wider form.
 *
 * The picker is a combobox, not a checkbox list. An account here holds 372 groups, so a
 * list is a scroll rather than a choice. You type a name; chosen groups become chips you
 * can see without scrolling back.
 */

let photoUrl = $state("");
let groups = $state<Group[]>([]);
let loading = $state(true);
let loadError = $state<string | null>(null);

let query = $state("");
let open = $state(false);
let cursor = $state(0);
const picked = new SvelteSet<string>();

let batch = $state<Batch | null>(null);
let running = $state(false);

const photoId = $derived(photoIdFromUrl(photoUrl));

const matches = $derived.by(() => {
	const needle = query.trim().toLowerCase();
	const pool = groups.filter((group) => !picked.has(group.id));
	if (needle === "") return pool.slice(0, 8);
	return pool
		.filter((group) => (group.name ?? group.id).toLowerCase().includes(needle))
		.slice(0, 8);
});

const chosen = $derived(groups.filter((group) => picked.has(group.id)));
const moderatedCount = $derived(
	chosen.filter((group) => group.poolModerated).length,
);
const pendingAck = $derived(
	batch === null ? [] : awaitingAcknowledgement(batch),
);
const canSubmit = $derived(!running && photoId !== null && picked.size > 0);

const hint = $derived.by(() => {
	const seconds = Math.max(1, Math.ceil(picked.size * 0.4));
	const pace = `one at a time, about ${seconds}s`;
	return moderatedCount > 0 ? `${moderatedCount} moderated · ${pace}` : pace;
});

/** "that 1" reads wrong; "those 3" reads right. Grammar is part of the interface. */
const ackLabel = $derived(
	pendingAck.length === 1
		? "Send it anyway"
		: `Send those ${pendingAck.length} anyway`,
);

$effect(() => {
	void (async () => {
		try {
			const list = await api.groups();
			groups = [...list.groups].sort((a, b) =>
				(a.name ?? a.id).localeCompare(b.name ?? b.id),
			);
		} catch (error) {
			console.error("GET /api/v001/groups failed", error);
			loadError = describeError(error, "loading your groups");
		} finally {
			loading = false;
		}
	})();
});

function choose(group: Group): void {
	picked.add(group.id);
	query = "";
	cursor = 0;
}

function onKeydown(event: KeyboardEvent): void {
	if (event.key === "ArrowDown") {
		event.preventDefault();
		cursor = Math.min(cursor + 1, matches.length - 1);
	} else if (event.key === "ArrowUp") {
		event.preventDefault();
		cursor = Math.max(cursor - 1, 0);
	} else if (event.key === "Enter") {
		event.preventDefault();
		const group = matches[cursor];
		if (group !== undefined) choose(group);
	} else if (event.key === "Escape") {
		open = false;
	} else if (event.key === "Backspace" && query === "") {
		// Backspace on an empty token input removes the last chip. Every token field
		// does this, and its absence is felt immediately.
		const last = chosen.at(-1);
		if (last !== undefined) picked.delete(last.id);
	}
}

async function send(only?: ReadonlySet<string>): Promise<void> {
	const id = photoId;
	if (id === null) return;

	const targets = only === undefined ? [...picked] : [...only];
	if (targets.length === 0) return;

	running = true;
	batch = await runBatch(
		api.submit,
		id,
		targets,
		only ?? new Set<string>(),
		(progress) => {
			batch = progress;
		},
	);
	running = false;
}

const nameOf = (groupId: string): string =>
	groups.find((group) => group.id === groupId)?.name ?? groupId;

/** Maps a per-group outcome onto the four state rails. */
function railOf(kind: string): string {
	if (kind === "resolved") return "s-good";
	if (kind === "needsAcknowledgement") return "s-human";
	if (kind === "failed") return "s-stopped";
	return "s-waiting";
}
</script>

<section class="photo">
	<p class="eyebrow">Photo</p>
	<div class="measure">
		<input
			type="text"
			aria-label="Flickr photo URL"
			bind:value={photoUrl}
			disabled={running}
			placeholder="Paste a Flickr photo URL"
		/>
	</div>

	<p class="small verdict">
		{#if photoUrl.trim() === ""}
			<span class="muted">The photo page address, or just its numeric id.</span>
		{:else if photoId === null}
			<span class="s-stopped">That is not a Flickr photo URL.</span>
		{:else}
			<span class="s-good">Photo <span class="mono">{photoId}</span></span>
		{/if}
	</p>
</section>

<!--
	One column until a batch exists, two once it does.

	The render showed a permanently empty Results panel taking half the width, which is
	the "form on the left, dead preview on the right" layout that made me suspicious of
	the split in the first place. The second column now appears when it has something to
	say, and its arrival is itself the signal that submitting started.
-->
<div class:split={batch !== null} class:solo={batch === null}>
	<section>
		<p class="eyebrow">Groups</p>

		{#if loading}
			<div class="panel panel-quiet"><p class="small muted" style="margin:0">Loading your groups…</p></div>
		{:else if loadError !== null}
			<div class="panel panel-quiet railed s-stopped">
				<p class="small" style="margin:0">{loadError}</p>
			</div>
		{:else}
			{#if chosen.length > 0}
				<ul class="chips plain">
					{#each chosen as group (group.id)}
						<li class="chip" class:moderated={group.poolModerated}>
							<span class="truncate">{group.name ?? group.id}</span>
							<button
								type="button"
								class="chip-x"
								aria-label="Remove {group.name ?? group.id}"
								disabled={running}
								onclick={() => picked.delete(group.id)}>&times;</button
							>
						</li>
					{/each}
				</ul>
			{/if}

			<div class="combo">
				<input
					type="search"
					role="combobox"
					aria-label="Search groups"
					aria-expanded={open && matches.length > 0}
					aria-controls="group-options"
					autocomplete="off"
					bind:value={query}
					disabled={running}
					placeholder={picked.size === 0
						? `Search ${groups.length} groups`
						: "Add another"}
					onfocus={() => (open = true)}
					onblur={() => setTimeout(() => (open = false), 120)}
					oninput={() => {
						open = true;
						cursor = 0;
					}}
					onkeydown={onKeydown}
				/>

				{#if open && matches.length > 0}
					<ul id="group-options" class="options plain" role="listbox">
						{#each matches as group, index (group.id)}
							<li role="option" aria-selected={index === cursor}>
								<button
									type="button"
									class="option"
									class:active={index === cursor}
									onmouseenter={() => (cursor = index)}
									onclick={() => choose(group)}
								>
									<span class="truncate grow">{group.name ?? group.id}</span>
									{#if group.poolModerated}
										<span class="tag">Moderated</span>
									{/if}
									<span class="mono small muted"
										>{group.photos.toLocaleString()}</span
									>
								</button>
							</li>
						{/each}
					</ul>
				{/if}
			</div>

			<div class="actions">
				<button class="commit" disabled={!canSubmit} onclick={() => send()}>
					{running
						? "Adding…"
						: picked.size === 0
							? "Add to groups"
							: `Add to ${picked.size} group${picked.size === 1 ? "" : "s"}`}
				</button>

				{#if picked.size > 0 && !running}
					<!--
						Built as one string rather than spliced fragments. The `{#if}` form
						swallowed the space around its middle dot and rendered "·one at a
						time" — the exact "conditional structure as spliced strings" failure
						the house rules warn about.
					-->
					<span class="small muted">{hint}</span>
				{/if}
			</div>
		{/if}
	</section>

	{#if batch !== null}
		<section>
			<p class="eyebrow">Results</p>

			{#if pendingAck.length > 0 && !running}
				<div class="ask">
					<p class="small" style="margin:0 0 .35rem">
						<strong
							>{pendingAck.length}
							{pendingAck.length === 1 ? "group has" : "groups have"} seen this photo
							before.</strong
						>
					</p>
					<p class="small muted" style="margin:0 0 .6rem">
						It already reached a moderator's queue there. Flickr never reports what
						they decided, so we stopped rather than put it in front of the same
						volunteer again. Sending it a second time is your call.
					</p>
					<button disabled={running} onclick={() => send(new Set(pendingAck))}>
						{ackLabel}
					</button>
				</div>
			{/if}

			<ul class="plain results">
				{#each [...batch] as [groupId, state] (groupId)}
					<li class="result railed {railOf(state.kind)}">
						<div class="truncate grow">{nameOf(groupId)}</div>
						<div class="small">
							{#if state.kind === "waiting"}
								<span class="muted">Waiting</span>
							{:else if state.kind === "sending"}
								<span class="muted">Sending…</span>
							{:else if state.kind === "queued"}
								<span class="s-waiting">In line — we keep trying nightly</span>
							{:else if state.kind === "resolved"}
								<span class="s-good">Added</span>
							{:else if state.kind === "needsAcknowledgement"}
								<span class="s-human">
									{state.stillPending
										? "Still with a moderator"
										: "A moderator has seen this"}
								</span>
							{:else}
								<span class="s-stopped"
									>{describeError(state.error, "adding this group")}</span
								>
							{/if}
						</div>
					</li>
				{/each}
			</ul>
		</section>
	{/if}
</div>

<style>
	.photo {
		margin-bottom: 1.75rem;
	}

	/* Before a batch exists there is one column, and a picker does not want 68rem. */
	.solo {
		max-width: 34rem;
	}

	.verdict {
		margin: 0.4rem 0 0;
		min-height: 1.4em; /* Reserve the line so validity never shifts the layout. */
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
		margin: 0 0 0.55rem;
	}

	.chip {
		display: inline-flex;
		align-items: center;
		gap: 0.2rem;
		max-width: 100%;
		padding: 0.1rem 0.15rem 0.1rem 0.5rem;
		border: 1px solid var(--rule);
		border-radius: 999px;
		font-size: var(--t-sm);
		background: var(--paper);
	}

	/* Moderated groups are marked on the CHIP, not only in the dropdown. The decision
	   to submit is made while looking at the chips. */
	.chip.moderated {
		border-color: var(--human);
		color: var(--human);
	}

	.chip-x {
		border: 0;
		background: transparent;
		padding: 0 0.3rem;
		line-height: 1;
		color: var(--muted);
		font-size: 1rem;
	}

	.chip-x:hover:not(:disabled) {
		background: transparent;
		color: var(--ink);
	}

	.combo {
		position: relative;
	}

	.options {
		position: absolute;
		z-index: 20;
		left: 0;
		right: 0;
		margin-top: 3px;
		border: 1px solid var(--rule);
		border-radius: var(--radius);
		background: var(--paper);
		box-shadow: 0 8px 24px rgb(0 0 0 / 14%);
		max-height: 16rem;
		overflow-y: auto;
	}

	.option {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		width: 100%;
		border: 0;
		border-radius: 0;
		text-align: left;
		padding: 0.4rem 0.65rem;
		background: transparent;
		font-size: var(--t-sm);
	}

	.option.active {
		background: var(--paper-2);
	}

	/*
	 * An outline on a focused option gets clipped by the list's own `overflow-y: auto`,
	 * which showed up in the render as a stray magenta sliver at the left edge. An inset
	 * shadow draws inside the element, so it survives the clip and still announces focus.
	 */
	.option:focus-visible {
		outline: none;
		box-shadow: inset 0 0 0 2px var(--commit);
	}

	.tag {
		font-size: var(--t-xs);
		letter-spacing: 0.05em;
		text-transform: uppercase;
		border: 1px solid var(--human);
		color: var(--human);
		border-radius: 999px;
		padding: 0 0.35rem;
		flex: none;
	}

	.actions {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
		margin-top: 0.9rem;
	}

	.results {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.result {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.75rem;
		padding-top: 0.1rem;
		padding-bottom: 0.1rem;
	}
</style>
