<script lang="ts">
import { api, beginLogin, NotAuthenticated } from "./lib/api.js";
import {
	currentPath,
	handleLinkClick,
	onNavigate,
	parse,
	type Route,
} from "./lib/router.js";
import AddToGroups from "./routes/AddToGroups.svelte";
import Queue from "./routes/Queue.svelte";

// The shell owns exactly two pieces of state: who you are, and where you are.
let route = $state<Route>(parse(currentPath()));
onNavigate((path) => {
	route = parse(path);
});

type Session =
	| { kind: "checking" }
	| { kind: "in"; nsid: string }
	| { kind: "out" };
let session = $state<Session>({ kind: "checking" });

// The cookie is HttpOnly, so JavaScript cannot read it and asking the server IS the
// check. That is ADR-10 working as designed, not a workaround -- and it held up under
// a broken database, where /api/v001/me answered 200 while every D1 call failed.
async function checkSession(): Promise<void> {
	try {
		const who = await api.me();
		session = { kind: "in", nsid: who.nsid };
	} catch (error) {
		if (!(error instanceof NotAuthenticated)) {
			console.error("session check failed", error);
		}
		session = { kind: "out" };
	}
}

$effect(() => {
	void checkSession();
});

async function signOut(): Promise<void> {
	await api.logout();
	session = { kind: "out" };
}
</script>

<div class="shell">
	<header class="topbar">
		<h1 class="wordmark">FlickrGroupAddr</h1>

		{#if session.kind === "in"}
			<nav class="navlinks" aria-label="Sections">
				<a
					class="navlink"
					href="/"
					aria-current={route.name === "add" ? "page" : undefined}
					onclick={(event) => handleLinkClick(event, "/")}>Add</a
				>
				<a
					class="navlink"
					href="/queue"
					aria-current={route.name === "queue" ? "page" : undefined}
					onclick={(event) => handleLinkClick(event, "/queue")}>Queue</a
				>
			</nav>

			<div class="spacer who">
				<span class="mono small muted">{session.nsid}</span>
				<button class="small" onclick={signOut}>Sign out</button>
			</div>
		{/if}
	</header>

	{#if session.kind === "checking"}
		<p class="muted small">Checking your session…</p>
	{:else if session.kind === "out"}
		<!--
			The only page a person READS rather than uses, so it is the only place that
			gets room to breathe. Everything behind the login is a console and is dense.
		-->
		<section class="welcome">
			<p class="eyebrow">Flickr group submissions</p>
			<h2 class="pitch">
				Flickr limits how many photos you may add to a group each day.
				<span class="pitch-turn">FlickrGroupAddr waits out the limit for you.</span>
			</h2>

			<p class="lede">
				Queue a photo into as many groups as you like. Every night it tries the ones
				that are still waiting, keeps its place in line, and tells you what happened.
			</p>

			<p>
				<button class="commit" onclick={beginLogin}>Sign in with Flickr</button>
			</p>

			<div class="panel panel-quiet caveat">
				<p class="small" style="margin:0 0 .4rem">
					<strong>Two things worth knowing before you sign in.</strong>
				</p>
				<p class="small muted" style="margin:0 0 .4rem">
					Flickr offers no permission narrower than <code>write</code>, so signing in
					grants edit access to your whole account. FlickrGroupAddr only ever adds
					photos to groups. Revoke it at Flickr any time.
				</p>
				<p class="small muted" style="margin:0">
					Many groups are moderated, which means a volunteer reviews every add. If a
					photo has already reached one of those queues, FlickrGroupAddr stops rather
					than send it to the same person twice.
				</p>
			</div>
		</section>
	{:else if route.name === "add"}
		<AddToGroups />
	{:else if route.name === "queue"}
		<Queue />
	{:else}
		<section>
			<h2>No such page</h2>
			<p class="muted">
				Nothing lives at <code>{route.path}</code>.
			</p>
			<p>
				<a href="/" onclick={(event) => handleLinkClick(event, "/")}
					>Back to adding photos</a
				>
			</p>
		</section>
	{/if}
</div>

<style>
	.who {
		display: flex;
		align-items: center;
		gap: 0.7rem;
	}

	.welcome {
		max-width: 40rem;
		padding-top: 1.5rem;
	}

	/*
	 * The one place the display weight is spent at size. A console does not get a hero;
	 * the page you read before you commit your Flickr account does.
	 */
	.pitch {
		font-size: 1.75rem;
		line-height: 1.24;
		letter-spacing: -0.03em;
		margin: 0 0 0.9rem;
		max-width: 22ch;
	}

	/* The sentence turns here -- limit, then relief -- so the second half is the one
	   that carries ink and the first half steps back. */
	.pitch-turn {
		display: block;
		color: var(--ink);
	}

	.pitch {
		color: var(--muted);
	}

	.caveat {
		margin-top: 1.6rem;
	}

	@media (max-width: 34rem) {
		.pitch {
			font-size: 1.35rem;
			max-width: none;
		}
	}
</style>
