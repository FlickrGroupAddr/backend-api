import { DurableObject } from "cloudflare:workers";

/**
 * ADR-08. One object per LOGIN ATTEMPT, never per user -- at this point the person has
 * authorized nothing, so no identity exists yet.
 *
 * It exists because OAuth 1.0a hands the server a token SECRET and then walks the user
 * away to flickr.com for two minutes. KV cannot hold it: the callback often lands at a
 * different point of presence, well inside KV's propagation window.
 */

const ABANDONED_AFTER_MS = 15 * 60 * 1000;

interface StoredAttempt {
	readonly requestToken: string;
	readonly requestTokenSecret: string;
	readonly createdAt: number;
}

export class OAuthLoginAttempt extends DurableObject<Env> {
	/** The alarm is armed in the same call that writes the secret, so no window exists
	 *  where state lives with nothing scheduled to remove it. Durable Objects have no
	 *  TTL, and most logins are abandoned, so this path is the common case. */
	async start(requestToken: string, requestTokenSecret: string): Promise<void> {
		await this.ctx.storage.put<StoredAttempt>("attempt", {
			requestToken,
			requestTokenSecret,
			createdAt: Date.now(),
		});
		await this.ctx.storage.setAlarm(Date.now() + ABANDONED_AFTER_MS);
	}

	/** Single-use by construction: the callback needs the secret exactly once, and a
	 *  replay MUST find nothing. Null covers unknown, consumed and expired alike --
	 *  telling them apart would only help someone probing the endpoint. */
	async consume(
		requestToken: string,
	): Promise<{ requestTokenSecret: string } | null> {
		const attempt = await this.ctx.storage.get<StoredAttempt>("attempt");

		// Compare BEFORE erasing, so a callback carrying the wrong token cannot destroy
		// a legitimate attempt still in flight.
		if (attempt === undefined || attempt.requestToken !== requestToken) {
			return null;
		}

		await this.ctx.storage.deleteAll();
		return { requestTokenSecret: attempt.requestTokenSecret };
	}

	/** The entire cleanup strategy for abandoned logins. */
	override async alarm(): Promise<void> {
		await this.ctx.storage.deleteAll();
	}
}
