/**
 * The two places this app leaves itself, rather than fetching.
 *
 * **This module exists so `api.ts` can be imported outside a browser.** It held
 * `beginLogin` until 2026-08-19, and that one line made the whole API client unloadable
 * from a Worker-side test: `window` does not exist there, so `tsc --noEmit` failed with
 * `Cannot find name 'window'` the moment a test imported `ApiError`. **713 lines of the
 * UI's logic were untested, and one function in the wrong file is what kept them that
 * way.**
 *
 * **The boundary is honest rather than convenient.** `api.ts` says of itself that it is
 * the only place that talks to the Worker. A full-page navigation is not talking to the
 * Worker at all -- it hands the tab to the OAuth leg and never sees a reply. So this was
 * always a different concern wearing the same import.
 */

/** A full navigation, not a fetch -- the OAuth leg ends in a redirect chain. */
export function beginLogin(): void {
	window.location.href = "/auth/flickr/login";
}
