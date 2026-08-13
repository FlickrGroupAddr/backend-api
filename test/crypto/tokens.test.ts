import { describe, expect, it } from "vitest";
import { decryptToken, encryptToken } from "../../src/crypto/tokens.js";

/** 32 bytes, base64. Test material only -- never a real key. */
const KEY = btoa(String.fromCharCode(...new Uint8Array(32).fill(7)));
const OTHER_KEY = btoa(String.fromCharCode(...new Uint8Array(32).fill(9)));

const NSID = "12345678@N00";
const TOKEN = "72157720000000000-abcdef0123456789";

describe("round trip", () => {
	it("recovers the plaintext", async () => {
		const packed = await encryptToken(TOKEN, NSID, KEY);
		expect(await decryptToken(packed, NSID, KEY)).toBe(TOKEN);
	});

	it("handles empty and non-ASCII values", async () => {
		for (const value of ["", "café ☕", "a".repeat(4096)]) {
			const packed = await encryptToken(value, NSID, KEY);
			expect(await decryptToken(packed, NSID, KEY)).toBe(value);
		}
	});
});

describe("nonce handling", () => {
	it("never produces the same ciphertext twice", async () => {
		// A repeated nonce under one key breaks AES-GCM catastrophically. If this
		// ever fails, the IV has stopped being random and the scheme is worthless.
		const seen = new Set<string>();
		for (let i = 0; i < 50; i++) {
			const packed = await encryptToken(TOKEN, NSID, KEY);
			seen.add(btoa(String.fromCharCode(...packed)));
		}
		expect(seen.size).toBe(50);
	});

	it("prepends a 12-byte IV", async () => {
		const packed = await encryptToken("", NSID, KEY);
		// 12 IV + 0 plaintext + 16 GCM tag.
		expect(packed.length).toBe(28);
	});
});

describe("rejection", () => {
	it("refuses a key that is not 32 bytes", async () => {
		const short = btoa(String.fromCharCode(...new Uint8Array(16).fill(1)));
		await expect(encryptToken(TOKEN, NSID, short)).rejects.toThrow(
			/must decode to 32 bytes/,
		);
	});

	it("refuses a key that is not base64", async () => {
		await expect(encryptToken(TOKEN, NSID, "!!!not base64!!!")).rejects.toThrow(
			/not valid base64/,
		);
	});

	it("fails to decrypt with the wrong key", async () => {
		const packed = await encryptToken(TOKEN, NSID, KEY);
		await expect(decryptToken(packed, NSID, OTHER_KEY)).rejects.toThrow();
	});

	it("fails to decrypt under a different NSID", async () => {
		// The binding that stops one user's token blob being moved into another
		// user's row by anyone with D1 write access but no key.
		const packed = await encryptToken(TOKEN, NSID, KEY);
		await expect(decryptToken(packed, "99999999@N00", KEY)).rejects.toThrow();
	});

	it("fails on a tampered ciphertext", async () => {
		const packed = await encryptToken(TOKEN, NSID, KEY);
		const tampered = new Uint8Array(packed);
		// Flip a bit in the payload, past the IV.
		tampered[20] = (tampered[20] ?? 0) ^ 0x01;
		await expect(decryptToken(tampered, NSID, KEY)).rejects.toThrow();
	});

	it("fails on a tampered IV", async () => {
		const packed = await encryptToken(TOKEN, NSID, KEY);
		const tampered = new Uint8Array(packed);
		tampered[0] = (tampered[0] ?? 0) ^ 0x01;
		await expect(decryptToken(tampered, NSID, KEY)).rejects.toThrow();
	});

	it("refuses input too short to hold an IV", async () => {
		await expect(decryptToken(new Uint8Array(8), NSID, KEY)).rejects.toThrow(
			/too short/,
		);
	});
});
