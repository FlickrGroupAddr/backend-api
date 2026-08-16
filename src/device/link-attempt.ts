import { DurableObject } from "cloudflare:workers";

/**
 * One object per DEVICE LINK ATTEMPT, never per user — at `start` nobody has
 * authorized anything, so no identity exists yet. Same reasoning as ADR-08's
 * `OAuthLoginAttempt`, and deliberately the same shape.
 *
 * **Why a Durable Object rather than D1.** The plug-in polls every few seconds
 * while a browser somewhere else approves. That is a short-lived single-writer
 * conversation between two clients that may land at different points of
 * presence — exactly what ADR-08 already chose this for. A D1 row would also
 * need sweeping; an alarm deletes itself.
 *
 * ## The object is addressed by `userCode`, and that is the security design
 *
 * **`userCode` is what a human reads and types. `code` is the polling secret
 * and never appears in a URL.** Addressing the object by `userCode` is what
 * lets the browser reach it with nothing but the string on the Lightroom
 * screen — no link required, so the fully-typed flow works and the convenience
 * link is only ever a shortcut.
 *
 * **Only the HASH of `code` is stored**, so a leak of this object's storage
 * yields no usable polling credential. Same reasoning as `src/session.ts`
 * never storing a session id.
 *
 * ## What this does NOT solve
 *
 * **Device-flow phishing.** An attacker can start a flow and talk a signed-in
 * victim into approving it. Nothing in this class can prevent that, and PKCE
 * would not either — the attacker started the flow, so the attacker holds the
 * secret. **The mitigation lives in the approval page**, which MUST show the
 * `userCode` and make the person confirm it matches their own screen.
 *
 * That matters more here than in most device flows. Under ADR-01 a request
 * that reached a moderator is terminal, so a phished token can push a
 * stranger's photos into volunteer queues and revoking it afterwards takes
 * none of that back.
 */

/** Ten minutes. Long enough to find the browser, short enough that an
 *  abandoned code is not sitting there to be stumbled into. */
const ABANDONED_AFTER_MS = 10 * 60 * 1000;

export type LinkState =
	| { readonly kind: "pending" }
	| { readonly kind: "approved"; readonly nsid: string }
	| { readonly kind: "denied" }
	/** Unknown, expired and consumed are ONE answer on purpose. Telling them
	 *  apart would only help somebody probing the endpoint. */
	| { readonly kind: "expired" };

interface StoredAttempt {
	readonly codeHash: string;
	readonly createdAt: number;
	readonly approvedBy: string | null;
	readonly denied: boolean;
}

export class DeviceLinkAttempt extends DurableObject<Env> {
	/** The alarm is armed in the same call that writes the state, so no window
	 *  exists where an attempt lives with nothing scheduled to remove it.
	 *
	 *  **Returns the expiry rather than letting the route compute it.** The alarm
	 *  and the number the plug-in counts down against MUST be the same instant, and
	 *  two places deriving it from `ABANDONED_AFTER_MS` is two places to drift. */
	async start(codeHash: string): Promise<{ expiresAt: number }> {
		const expiresAt = Date.now() + ABANDONED_AFTER_MS;
		await this.ctx.storage.put<StoredAttempt>("attempt", {
			codeHash,
			createdAt: Date.now(),
			approvedBy: null,
			denied: false,
		});
		await this.ctx.storage.setAlarm(expiresAt);
		return { expiresAt };
	}

	/**
	 * The browser's half. **Requires a signed-in caller**, which the route
	 * enforces — this class never sees a cookie.
	 *
	 * **Returns false for an unknown or expired code rather than throwing**, so
	 * the page can say "that code has expired" instead of failing.
	 */
	async approve(nsid: string): Promise<boolean> {
		const attempt = await this.ctx.storage.get<StoredAttempt>("attempt");
		if (attempt === undefined || attempt.denied) return false;

		await this.ctx.storage.put<StoredAttempt>("attempt", {
			...attempt,
			approvedBy: nsid,
		});
		return true;
	}

	/** The person said no. Recorded rather than deleted, so the waiting plug-in
	 *  can say "you declined" instead of timing out — which is ADR-01's habit of
	 *  never letting a refusal look like a failure. */
	async deny(): Promise<boolean> {
		const attempt = await this.ctx.storage.get<StoredAttempt>("attempt");
		if (attempt === undefined) return false;
		await this.ctx.storage.put<StoredAttempt>("attempt", {
			...attempt,
			denied: true,
			approvedBy: null,
		});
		return true;
	}

	/**
	 * The plug-in's half, and the only caller that must prove it holds `code`.
	 *
	 * **Single-use on success.** The attempt is erased the moment an approval is
	 * collected, so a replay finds `expired` — the same construction
	 * `OAuthLoginAttempt.consume` uses, and for the same reason.
	 */
	async poll(codeHash: string): Promise<LinkState> {
		const attempt = await this.ctx.storage.get<StoredAttempt>("attempt");
		if (attempt === undefined) return { kind: "expired" };

		/**
		 * **Compared with `timingSafeEqual`, not `===`.** These are equal-length
		 * base64url digests, so a byte-by-byte string compare would leak how much
		 * of a guess was right through timing. It also MUST come before any state
		 * is read out, and before the attempt is erased — a poll carrying the
		 * wrong code MUST NOT be able to destroy a legitimate attempt in flight.
		 */
		const encoder = new TextEncoder();
		const got = encoder.encode(codeHash);
		const want = encoder.encode(attempt.codeHash);
		if (
			got.byteLength !== want.byteLength ||
			!crypto.subtle.timingSafeEqual(got, want)
		) {
			return { kind: "expired" };
		}

		if (attempt.denied) {
			await this.ctx.storage.deleteAll();
			return { kind: "denied" };
		}

		if (attempt.approvedBy === null) return { kind: "pending" };

		const nsid = attempt.approvedBy;
		await this.ctx.storage.deleteAll();
		return { kind: "approved", nsid };
	}

	/** The entire cleanup strategy for abandoned link attempts. */
	override async alarm(): Promise<void> {
		await this.ctx.storage.deleteAll();
	}
}
