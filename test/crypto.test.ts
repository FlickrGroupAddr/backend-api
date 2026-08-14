import { describe, expect, it } from "vitest";
import { decryptToken, encryptToken } from "../src/crypto/tokens.js";

/** ADR-09. AES-GCM at rest, bound to the row it belongs to. */

const KEY = "dGVzdC10b2tlbi1rZXktZXhhY3RseS0zMi1ieXRlcyE=";
const OTHER_KEY = "b3RoZXItdG9rZW4ta2V5LWV4YWN0bHktMzItYnl0ZXMh";
const NSID = "12345678@N00";

describe("round trip", () => {
	it.each(["a-flickr-token", "", "héllo · 世界"])(
		"recovers %s",
		async (value) => {
			const packed = await encryptToken(value, NSID, KEY);
			expect(await decryptToken(packed, NSID, KEY)).toBe(value);
		},
	);
});

describe("nonce handling", () => {
	it("never produces the same ciphertext twice", async () => {
		// Reusing a nonce under one key breaks AES-GCM catastrophically.
		const a = await encryptToken("same", NSID, KEY);
		const b = await encryptToken("same", NSID, KEY);
		expect(a).not.toEqual(b);
		expect(a.slice(0, 12)).not.toEqual(b.slice(0, 12));
	});
});

describe("rejection", () => {
	it("refuses a key that is not exactly 32 bytes, or not base64", async () => {
		// Hashing a short value would accept a weak passphrase silently.
		await expect(encryptToken("x", NSID, btoa("too short"))).rejects.toThrow();
		await expect(encryptToken("x", NSID, "not base64 !!")).rejects.toThrow();
	});

	it("fails under the wrong key", async () => {
		const packed = await encryptToken("secret", NSID, KEY);
		await expect(decryptToken(packed, NSID, OTHER_KEY)).rejects.toThrow();
	});

	it("fails under a different NSID, so a blob cannot be moved between rows", async () => {
		const packed = await encryptToken("secret", NSID, KEY);
		await expect(decryptToken(packed, "99999999@N00", KEY)).rejects.toThrow();
	});

	it.each([
		["ciphertext", 20],
		["IV", 0],
	])("fails on a tampered %s", async (_where, index) => {
		const packed = await encryptToken("a-flickr-token", NSID, KEY);
		packed[index] = (packed[index] ?? 0) ^ 0xff;
		await expect(decryptToken(packed, NSID, KEY)).rejects.toThrow();
	});

	it("refuses input too short to hold an IV", async () => {
		await expect(decryptToken(new Uint8Array(8), NSID, KEY)).rejects.toThrow();
	});
});
