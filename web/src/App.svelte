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

// The shell owns two pieces of state and nothing else: who you are, and where you
// are. Everything below reads them.
let route = $state<Route>(parse(currentPath()));
onNavigate((path) => {
	route = parse(path);
});

type Session =
	| { kind: "checking" }
	| { kind: "in"; nsid: string }
	| { kind: "out" };
let session = $state<Session>({ kind: "checking" });

// The cookie is HttpOnly, so JavaScript cannot read it. Asking the server IS the
// check -- and that is the correct design, not a workaround. The 2021 UI kept a
// readable cookie so the page could inspect it, which is exactly the property
// ADR-10 gives up on purpose.
async function checkSession(): Promise<void> {
	try {
		const who = await api.me();
		session = { kind: "in", nsid: who.nsid };
	} catch (error) {
		session =
			error instanceof NotAuthenticated ? { kind: "out" } : { kind: "out" };
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

<main>
	<nav>
		<h1>FlickrGroupAddr</h1>

		{#if session.kind === "in"}
			<a
				href="/"
				aria-current={route.name === "add" ? "page" : undefined}
				onclick={(event) => handleLinkClick(event, "/")}>Add to groups</a
			>
			<a
				href="/queue"
				aria-current={route.name === "queue" ? "page" : undefined}
				onclick={(event) => handleLinkClick(event, "/queue")}>Queue</a
			>

			<span class="spacer small muted">{session.nsid}</span>
			<button onclick={signOut}>Sign out</button>
		{/if}
	</nav>

	{#if session.kind === "checking"}
		<p class="muted">Checking your session...</p>
	{:else if session.kind === "out"}
		<h2>Sign in with Flickr</h2>
		<p>
			FlickrGroupAddr queues your photos into groups and keeps trying until they land,
			so you do not have to come back every day to work around the daily limits.
		</p>
		<p class="small muted">
			Flickr offers no permission narrower than <code>write</code>, so signing in grants
			FlickrGroupAddr edit access to your whole account. It only ever adds photos to
			groups. You can revoke it at Flickr at any time.
		</p>
		<p><button class="primary" onclick={beginLogin}>Sign in with Flickr</button></p>
	{:else if route.name === "add"}
		<AddToGroups />
	{:else if route.name === "queue"}
		<Queue />
	{:else}
		<h2>No such page</h2>
		<p class="muted">Nothing lives at <code>{route.path}</code>.</p>
		<p><a href="/" onclick={(event) => handleLinkClick(event, "/")}>Back to the start</a></p>
	{/if}
</main>
