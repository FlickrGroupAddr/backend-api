import {
	cloudflareTest,
	readD1Migrations,
} from "@cloudflare/vitest-pool-workers";
import { defineConfig } from "vitest/config";

// ADR-13: tests run inside workerd against real bindings. Hand-mocked D1 and
// Durable Object stubs would test the mock rather than the Worker.
//
// Note the shape: as of @cloudflare/vitest-pool-workers 0.21.3 this is a Vite
// PLUGIN. The older `defineWorkersConfig` from the "/config" subpath no longer
// exists -- the package ships a vitest-v3-to-v4 codemod for exactly this move,
// and every tutorial still shows the old form.

// The real migrations, so schema tests run against the schema that ships rather
// than against a hand-copied approximation of it.
const migrations = await readD1Migrations("./migrations");

/**
 * Every outbound request from the Worker lands here.
 *
 * Two jobs, and the second matters more than the first. It gives the Flickr
 * calls deterministic replies so the route tests can exercise the real code
 * path -- and it makes any request to a host these tests do not expect a LOUD
 * failure rather than a slow, flaky, occasionally-passing call to the actual
 * Flickr API. A test suite that can reach the internet will eventually reach it
 * by accident.
 */
function outboundService(request: Request): Response {
	const url = new URL(request.url);

	if (url.hostname === "api.flickr.com") {
		// The method travels in the form-encoded body, so the stub keys off the
		// path only and answers the shape both calls share.
		return Response.json({ stat: "ok", pool: [] });
	}

	return new Response(
		`Test suite tried to reach ${url.hostname}. Outbound network access is ` +
			`blocked in tests -- add a stub in vitest.config.ts if this is intended.`,
		{ status: 599 },
	);
}

export default defineConfig({
	plugins: [
		cloudflareTest({
			wrangler: { configPath: "./wrangler.jsonc" },
			miniflare: {
				bindings: { TEST_MIGRATIONS: migrations },
				outboundService,
			},
		}),
	],
	test: {
		setupFiles: ["./test/apply-migrations.ts"],
	},
});
