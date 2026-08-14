/**
 * Svelte does NOT ship an ambient `*.svelte` module declaration -- verified against
 * `node_modules/svelte` 5.56.9 rather than assumed. Without this, `tsc` cannot resolve
 * `import App from "./App.svelte"` and the whole web typecheck fails at the first line
 * of `main.ts`.
 *
 * **This is a deliberately loose shim, and the looseness is the cost ADR-18 accepted.**
 * The tool that would give real prop types across a `.svelte` boundary is
 * `svelte-check`, which peers on TypeScript ^5 || ^6 while ADR-13 pins 7.0.2.
 *
 * The mitigation is architectural rather than clever: components take few or no props,
 * and everything worth checking lives in `web/src/lib/*.ts`, which `tsc` reads properly.
 * **A component that grows a complicated prop contract is a signal to move the logic
 * into `lib/`, not a reason to loosen this further.**
 */

declare module "*.svelte" {
	import type { Component } from "svelte";

	const component: Component<Record<string, unknown>>;
	export default component;
}

declare module "*.css" {
	const url: string;
	export default url;
}
