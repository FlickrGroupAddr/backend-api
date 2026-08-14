# Bring FlickrGroupAddr up

**RFC 2119 keywords. MUST is absolute. SHOULD is a strong default.**

This ran end to end on 2026-08-13. Production is live.

## Before you start

| | |
|---|---|
| Cloudflare | Workers Paid plan. Run `npx wrangler login`. |
| Flickr | An API key from <https://www.flickr.com/services/apps/create/> |
| Node | 24.x |

**Flickr's app form never asks for a callback URL.** OAuth 1.0a sends `oauth_callback` on every
request-token call, so there is nothing to pre-register and nothing to update when the host changes.

## 1. Create the database

```
npx wrangler d1 create fga
```

Copy the printed `database_id` into `wrangler.jsonc`.

## 2. Apply the schema

```
npx wrangler d1 migrations apply fga --remote
```

**`--remote` is what makes this production.** Without it you migrate the local database and get a
clean success against the wrong target.

## 3. Make two keys

```
node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"
```

Run it twice. **The two values MUST differ.** One encrypts Flickr tokens. One signs session cookies.

**Rotating the session key logs everyone out and costs nothing. Rotating the token key means
re-encrypting every stored Flickr token.** Sharing one key makes the cheap rotation as expensive as
the dear one, so neither ever happens.

Each key MUST decode to exactly 32 bytes. The code refuses anything else.

## 4. Set four secrets

```
npx wrangler secret put FLICKR_CONSUMER_KEY
npx wrangler secret put FLICKR_CONSUMER_SECRET
npx wrangler secret put TOKEN_KEY
npx wrangler secret put SESSION_KEY
```

**These MUST NOT go in `wrangler.jsonc`.** That file is public. For local work, copy
`.dev.vars.example` to `.dev.vars`, which is gitignored.

## 5. Run it and log in

```
npm run dev
```

Open `http://localhost:8787/oauth/login`.

**Reaching Flickr's authorize page proves the signature works.** The test suite cannot establish
that; only a live call can.

**The landing page reports the SESSION, never the redirect.** `?login=ok` means only that the
callback believed it worked. The page verifies the cookie and shows the NSID it recovered.

## 6. Deploy

```
npm run check
npx wrangler deploy
```

The cron trigger starts firing at once, nightly at 00:15 UTC.

## Four traps that cost real time

**Local D1 is two different files.** `wrangler d1 execute --local` and a running `wrangler dev` can
open different SQLite files under `.wrangler/state/v3/d1/miniflare-D1DatabaseObject/`, because the
path is hashed from `database_id`. The CLI then reports `no such table`, which reads as a missing
schema rather than the wrong database. **After changing `database_id`, restart `wrangler dev` and
re-apply local migrations.** To see the real state, read the `.sqlite` file directly. The live one is
the largest.

**`.dev.vars` overrides the `vars` block in `wrangler.jsonc`.** That is what makes a localhost
override work. The test suite MUST NOT depend on it — every value the tests need is pinned in
`vitest.config.ts`.

**`wrangler types` says Node.js compatibility is enabled when it is not.** Ignore it.
`compatibility_flags` is empty and ADR-13 refuses `nodejs_compat`.

**Cloudflare's edge answers error `1010` to a `Python-urllib` user agent** before the Worker runs.
Verify with `curl` and a normal user agent.

## The toolchain check is not in this repository

A fresh clone brings no freshness check. It lives at `~/.claude/hooks/npm-toolchain-check.py` and
fires only for projects listed in `~/.claude/toolchain-projects.json` with `"npm"` in `toolchains`.

**On a new machine, register the checkout or the check stays silent** — and silence looks exactly
like a clean result.

Run it by hand at any time:

```
python ~/.claude/hooks/npm-toolchain-check.py --probe
```
