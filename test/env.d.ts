import type { D1Migration } from "@cloudflare/vitest-pool-workers";

// `cloudflare:test` types its `env` as `Cloudflare.Env` -- note that this is a
// DIFFERENT interface from the global `Env` the Worker sees, though both extend
// the same generated base. Augmenting here therefore gives the test binding to
// tests only; src/ still cannot reference TEST_MIGRATIONS, which is correct.
//
// The older `ProvidedEnv` interface no longer exists in
// @cloudflare/vitest-pool-workers 0.21.3.
declare global {
	namespace Cloudflare {
		interface Env {
			// Supplied by vitest.config.ts, which reads the real migrations directory.
			TEST_MIGRATIONS: D1Migration[];
		}
	}
}
