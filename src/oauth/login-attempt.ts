import { DurableObject } from "cloudflare:workers";

/**
 * Holds the intermediate state of a single OAuth 1.0a login, per ADR-02.
 *
 * One object per LOGIN ATTEMPT, not per user. A user who abandons a login and
 * starts another gets a second object; nothing is shared between them and
 * neither can invalidate the other.
 *
 * It exists because OAuth 1.0a issues a request token SECRET that has to
 * survive a redirect out to Flickr and back. Workers KV cannot hold it -- it is
 * eventually consistent, and the callback frequently lands at a different edge
 * location than the one that started the login, well inside KV's propagation
 * window. A Durable Object is single-homed, so the read after the redirect sees
 * the write that preceded it.
 */

/**
 * ADR-02 requires the state to be destroyed roughly fifteen minutes after it is
 * created. A login that has not completed by then has been abandoned, and the
 * secret has no reason to outlive it.
 */
const ABANDONED_AFTER_MS = 15 * 60 * 1000;

interface StoredAttempt {
	readonly requestToken: string;
	readonly requestTokenSecret: string;
	readonly createdAt: number;
}

export class OAuthLoginAttempt extends DurableObject<Env> {
	/**
	 * Records the temporary credentials and arms the cleanup alarm.
	 *
	 * The alarm is set in the same call that writes the secret, so there is no
	 * window in which state exists without something scheduled to remove it.
	 */
	async start(requestToken: string, requestTokenSecret: string): Promise<void> {
		await this.ctx.storage.put<StoredAttempt>("attempt", {
			requestToken,
			requestTokenSecret,
			createdAt: Date.now(),
		});
		await this.ctx.storage.setAlarm(Date.now() + ABANDONED_AFTER_MS);
	}

	/**
	 * Returns the stored credentials exactly once and erases them.
	 *
	 * Single-use by construction: the callback needs the secret precisely once,
	 * and a replayed callback MUST NOT find anything to work with. Returns null
	 * when the attempt is unknown, already consumed, or expired -- all three are
	 * the same answer to the caller, which is "start over".
	 */
	async consume(
		requestToken: string,
	): Promise<{ requestTokenSecret: string } | null> {
		const attempt = await this.ctx.storage.get<StoredAttempt>("attempt");

		// Compare before erasing, so a callback carrying the wrong token cannot
		// destroy a legitimate attempt that is still in flight.
		if (attempt === undefined || attempt.requestToken !== requestToken) {
			return null;
		}

		await this.ctx.storage.deleteAll();
		return { requestTokenSecret: attempt.requestTokenSecret };
	}

	/** ADR-02: the abandoned-login sweep. Deletes everything this object holds. */
	override async alarm(): Promise<void> {
		await this.ctx.storage.deleteAll();
	}
}
