/**
 * Compile every tracked `.svelte` file with THIS project's own Svelte and fail on any
 * warning.
 *
 * **This exists because the inside of a `.svelte` file is the one surface here that no
 * tool inspects.** `tsc` does not read templates. Biome cannot parse them. `svelte-check`
 * peers on TypeScript `^5 || ^6` and ADR-13 pins 7.0.2, so installing it would mean a
 * SECOND, older compiler analyzing this code -- the mismatch this project has already
 * refused twice.
 *
 * **The Svelte compiler is not a second compiler. It is the one that already runs.**
 * `vite build` compiles these same files on every gate run and PRINTS its warnings, and
 * a printed warning in a 200-line build log is a warning nobody reads. This step fails
 * on them.
 *
 * **It does NOT typecheck.** Nothing here checks that a `.svelte` expression has the
 * right type; that hole stays open until the native TypeScript 7 language service ships.
 * Claiming otherwise would be worse than the gap, so the summary line says what ran.
 *
 * **It refuses to report success on an empty match.** A renamed directory that made the
 * glob find nothing would otherwise print a clean result forever -- the failure
 * `scripts/lua-balance.py` was given the same guard against.
 */

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { compile } from "svelte/compiler";

const REPO_ROOT = path.resolve(
	path.dirname(fileURLToPath(import.meta.url)),
	"..",
);

/** Every git-tracked Svelte file, repository-relative, with forward slashes. */
function trackedSvelte() {
	const out = execFileSync("git", ["ls-files", "*.svelte"], {
		cwd: REPO_ROOT,
		encoding: "utf8",
	});
	return out
		.split("\n")
		.map((line) => line.trim())
		.filter((line) => line.length > 0);
}

/**
 * Prove the instrument can still fire, before trusting it to say "clean".
 *
 * **`result.warnings ?? []` is a silent-inertness hazard, and this closes it.** If a
 * future Svelte renames or moves that field, every component would report zero warnings
 * forever and the step would pass while checking nothing. Nothing else here would
 * notice: no test covers this script, and its normal output is exactly the same words.
 *
 * The fixture is a `<div>` with a click handler and no keyboard handler, which is the
 * same violation this gate was proven to catch when it was added.
 */
function selfTest() {
	const bad = `<script lang="ts">\nlet n = 0;\n</script>\n\n<div onclick={() => { n += 1; }}>{n}</div>\n`;
	const warnings =
		compile(bad, { filename: "self-test.svelte" }).warnings ?? [];
	if (warnings.length === 0) {
		console.error("Self-test FAILED: the compiler reported no warning for a");
		console.error("<div> with a click handler and no keyboard handler.");
		console.error(
			"Either Svelte moved `result.warnings`, or that rule is gone.",
		);
		console.error("Until this is understood, a clean run here means nothing.");
		return false;
	}
	console.log(
		`Self-test passed: a deliberate a11y defect drew ${warnings.length} warning(s).`,
	);
	return true;
}

if (!selfTest()) {
	process.exit(1);
}

const files = trackedSvelte();

if (files.length === 0) {
	console.error("No tracked .svelte files found. Refusing to report success.");
	console.error("Either the glob is wrong or the components moved.");
	process.exit(1);
}

let problems = 0;

for (const relative of files) {
	const source = readFileSync(path.join(REPO_ROOT, relative), "utf8");
	let result;
	try {
		result = compile(source, { filename: relative, generate: "client" });
	} catch (error) {
		problems += 1;
		console.log(`${relative}: COMPILE ERROR`);
		console.log(`    ${error.message}`);
		continue;
	}
	const warnings = result.warnings ?? [];
	if (warnings.length === 0) {
		console.log(`${relative}: clean`);
		continue;
	}
	for (const warning of warnings) {
		problems += 1;
		const line = warning.start?.line ?? "?";
		console.log(`${relative}:${line}: ${warning.code}`);
		console.log(`    ${warning.message}`);
	}
}

console.log("");
if (problems > 0) {
	console.log(
		`Found ${problems} Svelte compiler problem(s) in ${files.length} file(s).`,
	);
	console.log(
		"Fix the markup, or state why the warning is wrong in the component.",
	);
	process.exit(1);
}
console.log(
	`Svelte compiles ${files.length} component(s) with no warnings. ` +
		"This is the COMPILER, not a typechecker -- template expressions are still unchecked.",
);
