import {
	env,
	listDurableObjectIds,
	runDurableObjectAlarm,
	runInDurableObject,
} from "cloudflare:test";
import { describe, expect, it } from "vitest";

/**
 * ADR-02's Durable Object, tested as a real Durable Object in workerd.
 *
 * The alarm test is the reason this project uses @cloudflare/vitest-pool-workers
 * rather than mocks: `runDurableObjectAlarm` fires the scheduled alarm
 * immediately, so the fifteen-minute cleanup guarantee is checkable in a
 * millisecond. Without it the options were to not test it, or to inject a fake
 * clock -- an abstraction existing only to make the test possible.
 */

const TOKEN = "72157720000000000-abcdef0123456789";
const SECRET = "fedcba9876543210";

function stubFor(token: string) {
	return env.OAUTH_LOGIN.get(env.OAUTH_LOGIN.idFromName(token));
}

describe("the login attempt lifecycle", () => {
	it("returns the secret exactly once", async () => {
		const stub = stubFor(TOKEN);
		await stub.start(TOKEN, SECRET);

		expect(await stub.consume(TOKEN)).toEqual({ requestTokenSecret: SECRET });

		// Single-use by construction. A replayed callback MUST find nothing.
		expect(await stub.consume(TOKEN)).toBeNull();
	});

	it("returns null for an attempt that was never started", async () => {
		expect(await stubFor("never-existed").consume("never-existed")).toBeNull();
	});

	it("refuses a mismatched token WITHOUT destroying the attempt", async () => {
		// A callback bearing the wrong token must not be able to knock out a
		// legitimate login that is still in flight.
		const stub = stubFor(TOKEN);
		await stub.start(TOKEN, SECRET);

		expect(await stub.consume("some-other-token")).toBeNull();
		expect(await stub.consume(TOKEN)).toEqual({ requestTokenSecret: SECRET });
	});
});

describe("the abandoned-login alarm, ADR-02", () => {
	it("arms an alarm as part of starting, not afterwards", async () => {
		const stub = stubFor(TOKEN);
		await stub.start(TOKEN, SECRET);

		await runInDurableObject(stub, async (_instance, state) => {
			// No window exists in which the secret is stored with nothing scheduled
			// to remove it.
			expect(await state.storage.getAlarm()).not.toBeNull();
		});
	});

	it("destroys the secret when the alarm fires", async () => {
		const stub = stubFor(TOKEN);
		await stub.start(TOKEN, SECRET);

		// Fires the scheduled alarm now instead of waiting a quarter of an hour.
		expect(await runDurableObjectAlarm(stub)).toBe(true);

		await runInDurableObject(stub, async (_instance, state) => {
			expect([...(await state.storage.list()).keys()]).toEqual([]);
		});

		// And the login can no longer be completed, which is the point.
		expect(await stub.consume(TOKEN)).toBeNull();
	});

	it("reports no alarm to run once the attempt has been consumed", async () => {
		const stub = stubFor(TOKEN);
		await stub.start(TOKEN, SECRET);
		await stub.consume(TOKEN);

		// deleteAll() clears the alarm too, so nothing is left scheduled for an
		// object that has already done its job.
		expect(await runDurableObjectAlarm(stub)).toBe(false);
	});

	it("leaves no storage behind for an abandoned login", async () => {
		// The common case, not the exception: most people close the tab at
		// Flickr's authorize page.
		const stub = stubFor("abandoned-token");
		await stub.start("abandoned-token", SECRET);
		await runDurableObjectAlarm(stub);

		await runInDurableObject(stub, async (_instance, state) => {
			expect((await state.storage.list()).size).toBe(0);
		});
	});
});

describe("one object per login attempt, ADR-02", () => {
	it("gives concurrent logins separate objects", async () => {
		// NOT one object per user. At this point in the flow there is no user --
		// nobody has authorized anything -- and two attempts must not share state
		// or be able to invalidate each other.
		await stubFor("token-one").start("token-one", "secret-one");
		await stubFor("token-two").start("token-two", "secret-two");

		expect(await stubFor("token-one").consume("token-one")).toEqual({
			requestTokenSecret: "secret-one",
		});
		expect(await stubFor("token-two").consume("token-two")).toEqual({
			requestTokenSecret: "secret-two",
		});
	});

	it("creates a distinct object id per request token", async () => {
		await stubFor("token-a").start("token-a", SECRET);
		await stubFor("token-b").start("token-b", SECRET);

		const ids = await listDurableObjectIds(env.OAUTH_LOGIN);
		expect(ids.length).toBeGreaterThanOrEqual(2);
	});
});
