import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

/**
 * ADR-18. Builds the Svelte app shell into `web/dist`, which `wrangler.jsonc` serves
 * as static assets from the same Worker that answers `/api/v001/*`.
 *
 * **`vitest.config.ts` is a separate file on purpose and Vitest prefers it**, so the
 * test run does not inherit this config. Merging the two would drag the Svelte plugin
 * into a workerd pool that has no DOM.
 *
 * The dev proxy is what keeps development same-origin. Without it the browser would
 * see `localhost:5173` for the app and `localhost:8787` for the API, which is exactly
 * the two-origin arrangement ADR-18 removed -- and `__Host-` cookies would stop
 * arriving, failing in a way that looks like a login bug rather than a config one.
 *
 * **A tighter option exists and is deliberately deferred:** `@cloudflare/vite-plugin`
 * runs the Worker inside `workerd` under one Vite server with the real D1 and Durable
 * Object bindings, removing this proxy entirely. It is not wired up yet because it
 * changes how the Worker is built and bundled, and that MUST NOT ride along with a
 * scaffold commit.
 */
const WORKER = "http://localhost:8787";

export default defineConfig({
	root: "web",
	plugins: [svelte()],

	build: {
		outDir: "dist",
		emptyOutDir: true,

		/*
		 * ADR-21, and it is SETTLED. Litigated with measurements on 2026-08-15 and closed
		 * by Terry; the reasoning, the numbers and the reopening bar all live in
		 * docs/architecture/DECISIONS.md rather than being restated here.
		 *
		 * **Do not flip this because the build would be faster.** It costs 6.2 s of a
		 * 64.87 s gate, that figure was known when the decision was made, and ADR-21
		 * names cost-alone as explicitly insufficient to reopen it. Read the ADR before
		 * touching this line.
		 *
		 * Two operational facts that belong beside the code rather than in the ADR: the
		 * emitted `.map` is 934 kB and reaches no visitor unless devtools is open, and it
		 * carries `sourcesContent` for all 76 inputs -- so **the minifier stripping
		 * comments out of the bundle does NOT keep them off the wire.**
		 */
		sourcemap: true,
	},

	server: {
		// Mirrors `run_worker_first` in wrangler.jsonc. **These two lists MUST agree** --
		// a path proxied here but not routed there works in development and 404s in
		// production, which is the worst order to discover it in.
		proxy: {
			"/api": WORKER,
			"/oauth": WORKER,
			"/health": WORKER,
		},

		/**
		 * **Polling is REQUIRED here, because this repository lives on a NAS share.**
		 *
		 * Node's native Windows watcher uses `ReadDirectoryChangesW`, which SMB does not
		 * deliver reliably. `vite` died on startup with `Error: UNKNOWN: unknown error,
		 * watch`, `errno: -4094`, `syscall: 'watch'` -- measured 2026-08-14 on `X:`.
		 *
		 * **The error names no filename and no permission**, which is why it reads like a
		 * privilege problem and is not one. Running elevated changes nothing.
		 *
		 * Polling costs CPU proportional to the file count, so the interval is loose
		 * rather than instant. `node_modules` is excluded because it is by far the
		 * largest tree here and never changes during a dev session.
		 */
		watch: {
			usePolling: true,
			interval: 400,
			ignored: ["**/node_modules/**", "**/.git/**", "**/.wrangler/**"],
		},
	},
});
