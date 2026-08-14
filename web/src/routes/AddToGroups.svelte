<script lang="ts">
import { SvelteSet } from "svelte/reactivity";
import { api } from "../lib/api.js";
import type { Group } from "../lib/contract.js";
import {
	awaitingAcknowledgement,
	type Batch,
	photoIdFromUrl,
	runBatch,
} from "../lib/submission.js";

/*
 * One photo, many groups.
 *
 * The picker is a combobox rather than a list of checkboxes. An account here holds
 * 372 groups, so a checkbox list is a scroll, not a choice -- you find a group by
 * typing its name, the way every tool people actually like works. Selected groups
 * become removable chips, so the answer to "what did I pick" is visible without
 * scrolling back.
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

$effect(() => {
	void (async () => {
		try {
			const list = await api.groups();
			groups = [...list.groups].sort((a, b) =>
				(a.name ?? a.id).localeCompare(b.name ?? b.id),
			);
		} catch (error) {
			loadError =
				error instanceof Error ? error.message : "Could not load your groups.";
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
		// Removing the last chip on an empty backspace is the behavior every token
		// input has, and its absence is felt immediately.
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
</script>

<h2>Add a photo to groups</h2>

<label class="field">
	<span class="small muted">Flickr photo URL</span>
	<input
		type="text"
		bind:value={photoUrl}
		disabled={running}
		placeholder="https://www.flickr.com/photos/you/54321098765"
	/>
</label>

{#if photoUrl.trim() !== "" && photoId === null}
	<p class="small stop">
		That is not a Flickr photo URL. Paste the address of the photo page, or its numeric
		id.
	</p>
{:else if photoId !== null}
	<p class="small ok">Photo <code>{photoId}</code> — looks right.</p>
{/if}

{#if loading}
	<p class="muted">Loading your groups...</p>
{:else if loadError !== null}
	<p class="stop">{loadError}</p>
{:else}
	<h2>Groups</h2>

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
						onclick={() => picked.delete(group.id)}>×</button
					>
				</li>
			{/each}
		</ul>
	{/if}

	<div class="combo">
		<input
			type="search"
			role="combobox"
			aria-expanded={open && matches.length > 0}
			aria-controls="group-options"
			autocomplete="off"
			bind:value={query}
			disabled={running}
			placeholder={picked.size === 0
				? `Search ${groups.length} groups`
				: "Add another group"}
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
								<span class="badge">Moderated</span>
							{/if}
							<span class="small muted">{group.photos.toLocaleString()} photos</span>
						</button>
					</li>
				{/each}
			</ul>
		{/if}
	</div>

	<div class="actions">
		<button class="primary" disabled={!canSubmit} onclick={() => send()}>
			{running
				? "Submitting..."
				: `Add to ${picked.size} group${picked.size === 1 ? "" : "s"}`}
		</button>

		{#if moderatedCount > 0 && !running}
			<span class="small muted">
				{moderatedCount} of these {moderatedCount === 1 ? "is" : "are"} moderated — a volunteer
				reviews the add.
			</span>
		{/if}
	</div>

	{#if picked.size > 4 && !running}
		<p class="small muted">
			Sent one at a time rather than all at once, so we do not hammer Flickr on your
			account. About {Math.ceil(picked.size * 0.4)} seconds.
		</p>
	{/if}
{/if}

{#if batch !== null}
	<h2>Results</h2>

	{#if pendingAck.length > 0 && !running}
		<div class="warn">
			<p>
				<strong>
					{pendingAck.length}
					{pendingAck.length === 1 ? "group has" : "groups have"} seen this photo before.
				</strong>
			</p>
			<p class="small">
				It already reached a moderator's queue there. Flickr never reports what they
				decided, so we stopped rather than put it in front of the same volunteer again.
				Sending it a second time is your call, not ours.
			</p>
			<p>
				<button disabled={running} onclick={() => send(new Set(pendingAck))}>
					Send those {pendingAck.length} anyway
				</button>
			</p>
		</div>
	{/if}

	<ul class="plain">
		{#each [...batch] as [groupId, state] (groupId)}
			<li class="row">
				<span class="grow truncate">{nameOf(groupId)}</span>
				<span class="small">
					{#if state.kind === "waiting"}
						<span class="muted">Waiting</span>
					{:else if state.kind === "sending"}
						<span class="muted">Sending...</span>
					{:else if state.kind === "queued"}
						<span class="muted">Queued — we keep trying nightly</span>
					{:else if state.kind === "resolved"}
						<span class="ok">Added</span>
					{:else if state.kind === "needsAcknowledgement"}
						<span class="stop">
							{state.stillPending
								? "Still with a moderator from last time"
								: "A moderator has seen this before"}
						</span>
					{:else}
						<span class="stop">Stopped — {state.message}</span>
					{/if}
				</span>
			</li>
		{/each}
	</ul>
{/if}

<style>
	.field {
		display: block;
		margin: 0.75rem 0;
	}

	.combo {
		position: relative;
	}

	.options {
		position: absolute;
		z-index: 10;
		left: 0;
		right: 0;
		margin-top: 2px;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		background: var(--bg);
		box-shadow: 0 6px 20px rgb(0 0 0 / 12%);
		max-height: 17rem;
		overflow-y: auto;
	}

	.option {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		width: 100%;
		border: 0;
		border-radius: 0;
		text-align: left;
		padding: 0.45rem 0.7rem;
		background: transparent;
	}

	.option.active {
		background: color-mix(in srgb, var(--accent) 14%, transparent);
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		margin: 0 0 0.6rem;
	}

	.chip {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		max-width: 18rem;
		padding: 0.15rem 0.2rem 0.15rem 0.55rem;
		border: 1px solid var(--line);
		border-radius: 999px;
		font-size: 0.875rem;
	}

	/* Moderated groups are marked in the chip too, not just in the dropdown. The
	   decision to submit is made while looking at the chips. */
	.chip.moderated {
		border-color: var(--warn-line);
	}

	.chip-x {
		border: 0;
		background: transparent;
		padding: 0 0.35rem;
		line-height: 1;
		font-size: 1.05rem;
		color: var(--muted);
	}

	.badge {
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		border: 1px solid var(--warn-line);
		color: var(--warn-line);
		border-radius: 999px;
		padding: 0 0.4rem;
	}

	.actions {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
		margin: 1rem 0 0.25rem;
	}
</style>
