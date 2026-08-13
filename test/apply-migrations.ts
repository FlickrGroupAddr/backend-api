import { applyD1Migrations, env } from "cloudflare:test";

// Runs once per test file, before its tests. Storage is isolated per file, so
// every file gets the schema fresh rather than inheriting another file's rows.
await applyD1Migrations(env.DB, env.TEST_MIGRATIONS);
