import {
	createExecutionContext,
	createScheduledController,
	env,
	waitOnExecutionContext,
} from "cloudflare:test";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { enqueue } from "../src/db/requests.js";
import worker from "../src/index.js";

/**
 * ADR-06's ENTRY POINT, which had no test at all until 2026-08-19.
 *
 * **The engine was well covered and the thing that runs it was not.** `sweep` has its own
 * file of tests; nothing had ever invoked `scheduled`. A wrong binding, a missing `await`,
 * or a renamed log event would have run unattended every night and passed every gate.
 *
 * **The log line IS the deliverable here.** Nobody watches this run. ADR-06 chose
 * structured JSON so a bad night is queryable rather than
 * readable-if-somebody-happens-to-look, and a query that cannot find its event name finds
 * nothing at all.
 */

const USER = "12345678@N00";

let logged: string[] = [];

beforeEach(async () => {
	await env.DB.exec("DELETE FROM requests");
	await env.DB.exec("DELETE FROM users");
	await env.DB.prepare(
		`INSERT INTO users
       (nsid, access_token_encrypted, access_token_secret_encrypted, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?)`,
	)
		.bind(USER, new Uint8Array([1]), new Uint8Array([2]), 0, 0)
		.run();

	logged = [];
	vi.spyOn(console, "log").mockImplementation((line: unknown) => {
		logged.push(String(line));
	});
});

afterEach(() => {
	vi.restoreAllMocks();
});

async function runNight(over?: Env): Promise<void> {
	const ctx = createExecutionContext();
	await worker.scheduled(createScheduledController(), over ?? env, ctx);
	await waitOnExecutionContext(ctx);
}

describe("ADR-06, the nightly entry point", () => {
	it("logs one structured line, under the name a query looks for", async () => {
		await runNight();

		expect(logged).toHaveLength(1);
		const line = JSON.parse(logged[0] ?? "{}");
		expect(line.event).toBe("nightly_sweep");
	});

	/**
	 * The report's own fields, because a line that carries only its name is a heartbeat
	 * rather than a record. `stoppedOnThrottle` is on it deliberately: it is expected, and
	 * a night that stopped on the cap has to be distinguishable from a night with nothing
	 * to do.
	 */
	it("carries the whole report, not just that it ran", async () => {
		await enqueue(env.DB, USER, "53912345678", "g1");
		await runNight();

		const line = JSON.parse(logged[0] ?? "{}");
		expect(line).toMatchObject({
			event: "nightly_sweep",
			queuesWalked: expect.any(Number),
			attempted: expect.any(Number),
			resolved: expect.any(Number),
			stoppedOnThrottle: expect.any(Number),
		});
		expect(Array.isArray(line.errors)).toBe(true);
	});

	/**
	 * **The worst night is the one that logged nothing.** `sweep` catches per queue, so
	 * what reaches the handler is a failure before any queue was walked -- D1 refusing
	 * `queueHeads`, a missing binding. The `console.log` sits after `sweep` returns, so
	 * without a catch that night left no trace and ADR-06's promise was exactly inverted.
	 */
	it("still logs when the sweep itself fails, and rethrows", async () => {
		const broken = {
			...env,
			DB: {
				prepare() {
					throw new Error("D1_ERROR: no such table");
				},
			} as unknown as D1Database,
		} as Env;

		await expect(runNight(broken)).rejects.toThrow("D1_ERROR");

		expect(logged).toHaveLength(1);
		const line = JSON.parse(logged[0] ?? "{}");
		expect(line.event).toBe("nightly_sweep");
		expect(line.failed).toBe(true);
		expect(line.error).toContain("D1_ERROR");
	});
});
