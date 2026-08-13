import { Hono } from "hono";

export { OAuthLoginAttempt } from "./oauth/login-attempt.js";

const app = new Hono<{ Bindings: Env }>();

app.get("/health", (c) => c.json({ status: "ok" }));

export default {
	fetch: app.fetch,

	/**
	 * ADR-04: the nightly sweep is the v1 work engine. Not yet implemented --
	 * it needs the D1 schema, which is the next piece of work.
	 */
	async scheduled(
		_controller: ScheduledController,
		_env: Env,
		_ctx: ExecutionContext,
	): Promise<void> {
		// Intentionally empty for now.
	},
} satisfies ExportedHandler<Env>;
