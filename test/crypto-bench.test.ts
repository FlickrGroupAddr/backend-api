import { describe, expect, it } from "vitest";

/**
 * The crypto costs `docs/architecture/KEY-ROTATION-NOTES.md` quotes, made
 * reproducible.
 *
 * **Why this exists.** Six figures sat in that document as hand-recorded numbers
 * with nothing able to re-derive them. They were measured once, on 2026-08-15, and
 * would have gone stale silently -- the exact shape of claim this project already
 * distrusts everywhere else.
 *
 * **IT ASSERTS ON THE CLOCK, NEVER ON A DURATION.** A benchmark that fails when the
 * laptop is busy is a checker that cries wolf, and a rule nobody trusts is a rule
 * nobody reads. The only assertion is that `performance.now()` ADVANCED -- which is
 * not a formality here: naive benchmarks under Spectre timer mitigations report a
 * flat zero, and a table of zeroes reads exactly like a very fast machine.
 *
 * **So the numbers are printed, not checked.** Read them when the design is being
 * re-argued; trust the relative costs and re-measure the absolutes on production
 * hardware before quoting them anywhere that matters.
 *
 * **To SEE the table, console interception has to be off:**
 *
 * ```
 * npx vitest run test/crypto-bench.test.ts --disableConsoleIntercept
 * ```
 *
 * **The gate runs this file without that flag on purpose.** The assertions still
 * fire every run, so the claims cannot rot silently; the table is a thing you ask
 * for when you are re-arguing the design, not noise in every green build.
 */

/**
 * **The iteration count IS the resolution, and 4,000 was not enough.**
 *
 * `performance.now()` reports whole milliseconds in this pool, so the smallest
 * measurable step is `1 ms / ITERATIONS`. At 4,000 every figure landed on a
 * multiple of **0.25 µs** — 0.25, 0.50, 1.75, 2.25 — which reads as real precision
 * and is quantization. 20,000 gives 0.05 µs steps and matches the methodology
 * behind the numbers in `KEY-ROTATION-NOTES.md`.
 *
 * Costs roughly half a second in the gate. **Do not lower it to save that** without
 * also widening the figures quoted downstream.
 */
const ITERATIONS = 20000;

/* TRACE-EXEMPT: a benchmark measures cost, it does not verify a decision. */

// The marker above MUST sit in its own block comment, and that is not cosmetic.
// `scripts/traceability.py` requires the reason to be followed by a block-comment
// close, or to be the last thing in the file: `.` does not cross newlines and `$`
// is end-of-string without `re.MULTILINE`.
//
// PUTTING IT IN A `describe` NAME LOOKS RIGHT AND SILENTLY DOES NOTHING. That was
// the first attempt here, and the gate caught it.
//
// These four lines are `//` and not a block comment on purpose: an earlier version
// spelled the terminator literally inside a block comment, which closed the comment
// early and produced fifteen TypeScript parse errors.
const KEY_BYTES = new Uint8Array(32).fill(7);

async function timeOp(run: () => unknown | Promise<unknown>): Promise<number> {
	const start = performance.now();
	for (let i = 0; i < ITERATIONS; i++) await run();
	return ((performance.now() - start) * 1000) / ITERATIONS;
}

describe("crypto costs, for KEY-ROTATION-NOTES.md", () => {
	it("prints the per-operation cost, and proves the clock moved", async () => {
		const sixteen = new Uint8Array(16).fill(1);
		const thirtyTwo = new Uint8Array(32).fill(1);

		const hmacKey = await crypto.subtle.importKey(
			"raw",
			KEY_BYTES,
			{ name: "HMAC", hash: "SHA-256" },
			false,
			["sign"],
		);

		const results: [string, number][] = [
			[
				"getRandomValues(16)",
				await timeOp(() => crypto.getRandomValues(new Uint8Array(16))),
			],
			[
				"getRandomValues(32)",
				await timeOp(() => crypto.getRandomValues(new Uint8Array(32))),
			],
			["randomUUID()", await timeOp(() => crypto.randomUUID())],
			[
				"SHA-256 of 16 bytes",
				await timeOp(() => crypto.subtle.digest("SHA-256", sixteen)),
			],
			[
				"SHA-256 of 32 bytes",
				await timeOp(() => crypto.subtle.digest("SHA-256", thirtyTwo)),
			],
			[
				"SHA-512 of 32 bytes",
				await timeOp(() => crypto.subtle.digest("SHA-512", thirtyTwo)),
			],
			[
				"HMAC-SHA256 sign, 32 bytes",
				await timeOp(() => crypto.subtle.sign("HMAC", hmacKey, thirtyTwo)),
			],
		];

		const lines = results.map(
			([name, us]) => `  ${name.padEnd(28)}${us.toFixed(2)} µs`,
		);
		console.log(
			`\ncrypto costs, ${ITERATIONS.toLocaleString()} iterations each\n${lines.join("\n")}\n`,
		);

		/**
		 * **The only assertion, and it is about the INSTRUMENT.** If every figure is
		 * zero the timer is frozen and the table above is meaningless -- which looks
		 * identical to a machine that is simply very fast. Nothing else here is safe
		 * to assert: absolute timings depend on what else the laptop is doing.
		 */
		const total = results.reduce((sum, [, us]) => sum + us, 0);
		expect(total).toBeGreaterThan(0);
	});

	it("confirms 16 and 32 bytes cost the same to hash, which is why 256 bits is free", async () => {
		/**
		 * The load-bearing claim behind the 256-bit session id: both widths fit in one
		 * 64-byte SHA2-256 compression block, so the wider id buys the same number of
		 * compression calls. **Asserted as a RATIO, not a duration** -- a ratio is
		 * stable under load in a way a microsecond figure is not.
		 */
		const small = await timeOp(() =>
			crypto.subtle.digest("SHA-256", new Uint8Array(16).fill(1)),
		);
		const large = await timeOp(() =>
			crypto.subtle.digest("SHA-256", new Uint8Array(32).fill(1)),
		);

		console.log(
			`\n  SHA2-256 32B / 16B ratio: ${(large / small).toFixed(2)}\n`,
		);

		// Generous bound. One extra compression block would roughly double it; this
		// catches that without failing on ordinary scheduling noise.
		expect(large / small).toBeLessThan(1.6);
	});
});
