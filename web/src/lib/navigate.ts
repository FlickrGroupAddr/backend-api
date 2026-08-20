/**
 * Everything in this app that touches `window`.
 *
 * **This module exists so the rest of `lib/` can be imported outside a browser**, and it
 * was created on 2026-08-19 after that turned out to be the only thing keeping 713 lines
 * of UI logic untested. Two separate blockers, both one line long:
 *
 *   1. `api.ts` held `beginLogin`, whose `window.location` made `tsc --noEmit` fail with
 *      `Cannot find name 'window'` the moment a Worker-side test imported `ApiError`.
 *   2. `router.ts` called `window.addEventListener("popstate", ...)` AT MODULE LOAD, so
 *      importing it outside a browser threw before any test ran. **That one is worse,
 *      because no typechecker objects to a side effect at import time.**
 *
 * **The boundary is honest rather than convenient.** `api.ts` says of itself that it is
 * the only place that talks to the Worker, and a full-page navigation into the OAuth leg
 * never talks to the Worker at all. `router.ts` decides which screen a path means, and
 * that decision needs no browser. What is left here is binding, not logic.
 *
 * **Keep it that way.** Anything with a rule in it belongs in a module a test can load.
 */

/** A full navigation, not a fetch -- the OAuth leg ends in a redirect chain. */
export function beginLogin(): void {
	window.location.href = "/auth/flickr/login";
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
