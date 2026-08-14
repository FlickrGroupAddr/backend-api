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

## 4. Set five secrets

```
npx wrangler secret put FLICKR_CONSUMER_KEY
npx wrangler secret put FLICKR_CONSUMER_SECRET
npx wrangler secret put TOKEN_KEY
npx wrangler secret put SESSION_KEY
npx wrangler secret put ADMIN_NSIDS
```

**`ADMIN_NSIDS` is a JSON array of the NSIDs allowed to reach `/api/v001/admin/*`**, for example
`["12345678@N00"]`. ADR-19.

**Skipping it does not break anything, and that is the point.** The allowlist fails closed, so a
missing secret admits nobody and the Health page simply 404s. The Worker logs one
`admin_config_error` line saying why, which is the only way to tell "not configured" from "not
you".

**These MUST NOT go in `wrangler.jsonc`.** That file is public. For local work, copy
`.dev.vars.example` to `.dev.vars`, which is gitignored.

## 5. Run it and log in

**Two processes, and you need both.** ADR-18 puts the app and the API on one origin, so
development mirrors that with a proxy rather than a second hostname.

```
npm run dev        # the Worker, on :8787
npm run dev:web    # Vite, on :5173 -- proxies /api, /oauth and /health to :8787
```

Open `http://localhost:5173`. **Use that port, not 8787.** The browser must see one origin or the
`__Host-` session cookie will not come back, and that failure reads as a broken login rather than a
misconfigured proxy.

**Reaching Flickr's authorize page proves the signature works.** The test suite cannot establish
that; only a live call can.

**The diagnostic page moved to `/api/debug`**, because `/` now serves the app shell. It reports the
SESSION, never the redirect: `?login=ok` means only that the callback believed it worked, while the
page verifies the cookie and shows the NSID it recovered.

## 6. Deploy

```
npm run check
npm run deploy
```

`npm run deploy` builds `web/dist` first and then runs `wrangler deploy`. **Running
`npx wrangler deploy` by hand ships whatever is already in `web/dist`**, which on a fresh clone is
nothing and on a stale one is worse than nothing.

The cron trigger starts firing at once, nightly at 00:15 UTC.

**`vars.UI_ORIGIN` and `vars.API_BASE_URL` in `wrangler.jsonc` MUST match the custom domain actually
attached to the Worker.** A mismatch sends Flickr an `oauth_callback` it cannot reach, and that
fails inside Flickr's redirect where there is nothing useful to read.

## The zone, and why every record is there

**Six records. Configured 2026-08-14, verified from public DNS rather than from the API that wrote
them.**

| Record | Purpose |
|---|---|
| `AAAA flickrgroupaddr.com → 100::` proxied | The Workers Custom Domain. **Cloudflare manages this — do not edit it by hand** |
| `AAAA www → 100::` proxied | Exists only so a redirect rule has something to attach to |
| `MX @ → "."` priority 0 | RFC 7505 null MX: this domain accepts no mail |
| `TXT @ → v=spf1 -all` | No host may send as this domain |
| `TXT _dmarc → v=DMARC1; p=reject; sp=reject` | Receivers bin anything claiming to be us |
| `TXT *._domainkey → v=DKIM1; p=` | Empty `p=` revokes **every** selector, including invented ones |

**`100::` is the IPv6 discard prefix.** Traffic never reaches it; Cloudflare intercepts at the edge.
It is the conventional target for a hostname that exists only to be proxied.

**The mail records are hard-fail on purpose.** ADR-07 holds no email address and FGA sends none, so
the honest configuration says so rather than leaving the domain silently spoofable. **There is no
`rua=` on the DMARC record**, because collecting aggregate reports would mean holding an address
ADR-07 declines to hold. **If FGA ever needs to send mail, all four of these MUST change together**
— relaxing SPF alone would still be rejected by DMARC.

### `www` redirects at the edge, NOT in the Worker

**A Cloudflare Dynamic Redirect rule**, `http.host eq "www.flickrgroupaddr.com"` → 301 to
`concat("https://flickrgroupaddr.com", http.request.uri)`, with `preserve_query_string` **off**
because `http.request.uri` already carries the query and enabling both duplicates it.

**Doing this in the Worker was tried in production and reverted.**
`not_found_handling: "single-page-application"` serves `index.html` before the Worker is invoked for
any path outside `run_worker_first`, so the redirect middleware never ran and `www` served the whole
application on a second hostname — precisely what ADR-18 removes. A redirect rule runs ahead of both
Workers and assets. The guard in `src/index.ts` stays, and says so.

## Seeing the app with data in it

**A fresh local database means every screen is an empty state**, which is the one shape you cannot
judge a queue view by. Two things are worth knowing.

**Apply the migrations locally, or every `/api/v001/*` call answers 500.** The failure reads
`D1_ERROR: no such table: users`, which looks like a code bug and is not:

```
npx wrangler d1 migrations apply fga --local
```

**Then seed rows straight into the tables** with `npx wrangler d1 execute fga --local --file=...`.
The queue view needs no Flickr call at all — it is pure D1 — so a user row plus some `requests`
rows renders the whole screen. `/api/v001/groups` is the exception and does need a real login.

**`/api/v001/me` keeps working through a completely broken database**, which is ADR-10 behaving as
designed rather than a fluke: a stateless signed cookie needs no read.

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
