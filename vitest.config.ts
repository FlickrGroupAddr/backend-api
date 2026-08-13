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

export default defineConfig({
	plugins: [
		cloudflareTest({
			wrangler: { configPath: "./wrangler.jsonc" },
			miniflare: {
				bindings: { TEST_MIGRATIONS: migrations },
			},
		}),
	],
	test: {
		setupFiles: ["./test/apply-migrations.ts"],
	},
});
