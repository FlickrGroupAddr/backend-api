/**
 * A router in about fifty lines, because three screens do not justify a dependency.
 *
 * **This is the one place ADR-14 was weighed and answered "innovate".** The survey:
 * `svelte-routing`, `svelte-spa-router` and `@sveltejs/kit` all exist and all work. Kit
 * brings its own build, its own adapter and its own server rendering, which is a second
 * framework wrapped around the one we chose. The other two are ~1500 lines each to
 * resolve three paths against no nested layouts, one route param and no guards.
 * **ADR-14's own carve-out applies: the spec is short and fully exercised.**
 *
 * The 2021 UI got the behavior right and paid for it three times over -- its dispatch
 * logic lived in `main()`, in the `popstate` listener and in a click handler, and every
 * copy reset the same divs by hand. **Here it is one `parse` and one listener.**
 *
 * **No runes in this file, deliberately.** `$state` is a compiler rune that only exists
 * in `.svelte` and `.svelte.ts` files, and `svelte-check` -- the only tool that
 * typechecks either -- peers on TypeScript ^5 || ^6 while ADR-13 pins 7.0.2. So the
 * reactive value lives in `App.svelte` and everything here is plain TypeScript that
 * `tsc --noEmit` actually verifies. See ADR-18.
 *
 * Deep links work because `wrangler.jsonc` sets
 * `not_found_handling: "single-page-application"`, so a cold load of `/queue` receives
 * `index.html` and `parse` reads the path back out. That replaces five `_redirects` rules.
 */

export type Route =
	| { name: "add" }
	| { name: "queue" }
	| { name: "admin" }
	| { name: "notFound"; path: string };

/**
 * **`/admin` resolves for everybody, and that is correct.** The route is not a
 * permission; the server is. A non-admin who types the path gets the page, the page asks
 * the API, the API answers 404, and the page says there is no such page. Hiding the
 * route here would only look like security while the API did the actual work.
 */
export function parse(pathname: string): Route {
	const segments = pathname.split("/").filter((segment) => segment.length > 0);

	if (segments.length === 0) return { name: "add" };
	if (segments.length === 1 && segments[0] === "queue")
		return { name: "queue" };
	if (segments.length === 1 && segments[0] === "admin")
		return { name: "admin" };

	return { name: "notFound", path: pathname };
}

export function currentPath(): string {
	return window.location.pathname;
}

type Listener = (path: string) => void;
const listeners = new Set<Listener>();

/** Returns its own unsubscribe, so a caller cannot leak one by forgetting the handle. */
export function onNavigate(listener: Listener): () => void {
	listeners.add(listener);
	return () => listeners.delete(listener);
}

function announce(path: string): void {
	for (const listener of listeners) listener(path);
}

/** Push a new history entry. Use for an in-app click. */
export function navigate(path: string): void {
	if (path === window.location.pathname) return;
	window.history.pushState(null, "", path);
	announce(path);
}

/**
 * Back and forward. **Registered once, at module load.** This single listener is what
 * the old UI spent three copies on.
 */
window.addEventListener("popstate", () => {
	announce(window.location.pathname);
});

/**
 * Ctrl/cmd/shift-click and middle-click MUST still reach the browser.
 *
 * The 2021 UI handled this and dropping it would be a regression: a router that eats
 * modified clicks is a router people stop trusting with links.
 */
export function handleLinkClick(event: MouseEvent, path: string): void {
	if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) {
		return;
	}
	event.preventDefault();
	navigate(path);
}
