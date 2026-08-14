# Bringing FlickrGroupAddr up

**RFC 2119 keywords, and the capitals are load-bearing.** MUST and MUST NOT are absolute; SHOULD
and SHOULD NOT are strong defaults a good argument may overrule; MAY is genuinely optional.

**This ran end to end on 2026-08-13 and production is live.** What follows is therefore both the
record of how it was done and the runbook for doing it again — a second environment, a rebuild, or
a recovery. **Steps that produced a value record the value**, so nothing here has to be
re-derived.

## Where it stands

| | |
|---|---|
| Worker | <https://fga-backend-api.terryott.workers.dev> |
| Database | `fga`, D1 id `0a54cbfa-770e-4b6d-a792-a5b65e5fa6be`, bound as `DB` |
| Secrets | Four, set — `FLICKR_CONSUMER_KEY`, `FLICKR_CONSUMER_SECRET`, `TOKEN_KEY`, `SESSION_KEY` |
| Cron | `15 0 * * *`, firing nightly |
| Verified | `/health` and `/` return 200, every `/v001` route returns 401 without a cookie, and a real Flickr login completes and renders the signed-in NSID |

**What is still aspirational is the domain.** `flickrgroupaddr.com` is in `pendingDelete` and a
local watcher is waiting to re-register it, so `UI_ORIGIN` and `API_BASE_URL` both point at the
`workers.dev` host today. **ADR-12's CORS contract is inert while those two are equal** and MUST be
revisited when the domain lands — that is the one place where a same-origin coincidence is hiding
whether the allowlist works.

## Before starting

| | |
|---|---|
| Cloudflare | Workers Paid plan. `npx wrangler login` if the CLI is not already authorized. |
| Flickr | An API key, created at <https://www.flickr.com/services/apps/create/> |
| Node | 24.x |

**Flickr's app form does not ask for a callback URL, confirmed 2026-08-13.** This was recorded as
a risk and is not one: OAuth 1.0a sends `oauth_callback` with each request token call, so there is
nothing to pre-register and nothing to update when the domain changes.

## 1. Create the database

```
npx wrangler d1 create fga
```

**Copy the `database_id` it prints into `wrangler.jsonc`**, replacing the all-zeros placeholder.
That placeholder is deliberate: local development and the test suite use Miniflare's own D1 and
never read it, so an unset value fails at deploy rather than silently pointing somewhere wrong.

## 2. Apply the schema

```
npx wrangler d1 migrations apply fga --remote
```

**`--remote` is what makes this the production database.** Omitting it migrates the local one and
reports success — a clean run against the wrong target.

**And `--local` has a sharper version of the same trap, found 2026-08-13.** `wrangler d1 execute
--local` and a running `wrangler dev` can resolve to **different SQLite files** under
`.wrangler/state/v3/d1/miniflare-D1DatabaseObject/`, because the path is hashed from
`database_id` and a running dev server keeps whichever file it opened at startup — hot reload
reloads code, not bindings. The CLI then reports **`no such table`**, which reads as a missing
schema rather than as the wrong database, and a `migrations apply --local` will "succeed" against
the empty file.

**So: after changing `database_id`, restart `wrangler dev` and re-apply local migrations**, and
expect to log in again because the new file has no user row. **To check what local state really
is, read the `.sqlite` directly** — the largest file in that directory is the live one — rather
than trusting the CLI's answer.

## 3. Generate the two keys

They **MUST** be different values. ADR-03 explains why at length; the short version is that
rotating the session key logs everyone out and costs nothing, while rotating the token key means
re-encrypting every stored Flickr token, and sharing one key makes the cheap rotation as expensive
as the dear one.

```
openssl rand -base64 32     # TOKEN_KEY
openssl rand -base64 32     # SESSION_KEY
```

**Each MUST decode to exactly 32 bytes.** The code refuses anything else rather than hashing a
short value into a key-shaped thing.

**`openssl` is not on PATH on this machine.** Git for Windows ships it at
`C:\Program Files\Git\usr\bin\openssl.exe`, and Node needs no install at all:

```
node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"
```

## 4. Set the four secrets

```
npx wrangler secret put FLICKR_CONSUMER_KEY
npx wrangler secret put FLICKR_CONSUMER_SECRET
npx wrangler secret put TOKEN_KEY
npx wrangler secret put SESSION_KEY
```

**These MUST NOT be written into `wrangler.jsonc`, which is committed to a public repository.**
For local development they go in `.dev.vars`, which is gitignored — copy `.dev.vars.example` and
fill it in.

**`.dev.vars` overrides `wrangler.jsonc`'s `vars` block, verified by reading the values back out of
a running Worker.** That is what makes a localhost override work without editing committed
configuration. The test suite MUST NOT depend on it: every value the tests need is pinned in
`vitest.config.ts`, because `.dev.vars` is per-developer and a suite that reads it passes or fails
according to a file not in the repository.

## 5. Run it locally and log in

```
npm run dev
```

Then open `http://localhost:8787/oauth/login`. That runs the whole three-leg dance: it fetches a
request token, parks the secret in a Durable Object, bounces to Flickr for authorization, and
returns to mint a session cookie.

**Reaching Flickr's authorize page at all proves the signature is accepted**, which is the one
thing the test suite cannot establish. The signer is checked against RFC 5849's published vectors,
so it implements the specification correctly — but Flickr is idiosyncratic and only a live call
settles whether that is enough. It does.

**The landing page reports the session, never the redirect.** `?login=ok` means only that the
callback believed it worked; the page verifies the cookie's signature and shows the NSID it
recovered. Those two agree right up until something is wrong, which is the only moment anybody
reads that page carefully.

**The `__Host-` prefix works on plain `http://localhost`, verified 2026-08-13.** The prefix requires
the `Secure` attribute and `wrangler dev` serves no TLS, so this was an open risk; browsers treat
localhost as a trustworthy origin and Chrome accepted, stored and returned the cookie. **The
evidence is that `/v001/groups` and `/v001/queue` answered 200 rather than 401** — both sit behind
the session middleware, which reads the prefixed name and nothing else.

**If a local login ever does report success while showing no session, suspect this first**, because
the failure mode is precisely the discrepancy the landing page exists to surface: the callback
succeeds, the browser silently drops the cookie, and the page says so rather than claiming a
session it does not have.

## 6. The diagnostic call

```
http://localhost:8787/v001/groups
```

**This settled four questions the design had been carrying unresolved**, and the answers are in the
verified-facts table in `docs/architecture/DECISIONS.md` with the date and method against each.
Summarized:

| Question | Answer |
|---|---|
| Does Flickr accept our signature on an authenticated REST call? | Yes |
| Which `throttle.mode` periods are real? | Five, not the one Flickr documents |
| Is the allowance per-user or per-group? | Per-user, so a spent allowance cannot be inferred across queues. Strong but not conclusive — confirming it needs one add and a re-read of the same group |
| Is `ispoolmoderated` present? | Yes, and it is what a safe retry rule for unmoderated pools would key off |

**It also produced a performance defect worth remembering rather than a clean pass.** The endpoint
originally fetched every group's detail in one request — 331 sequential Flickr calls and 979 KB for
an account in 330 groups, taking **53 seconds**. `/v001/groups` now returns the list alone in one
call (**308 ms**), and `/v001/groups/:groupId` returns the throttle and moderation detail for one
group. **The fix was not concurrency; it was not making the calls.**

## 7. Deploy

```
npm run check       # Typecheck, lint, and the whole suite. MUST be clean first.
npx wrangler deploy
```

**`npm run check` reports its own totals, so read the run rather than this page.** It was **178
tests on 2026-08-14**, from a cold run with `node_modules/.vite` and `node_modules/.cache` removed.
**A count written here goes stale the first time somebody adds a test, and this one already had** —
it said 154. Same reasoning as the diagram build in `CLAUDE.md`: the run itself is the list.

**The cron trigger starts firing as soon as this succeeds**, nightly at 00:15 UTC. With no queued
requests it walks nothing and logs a report saying so.

**Verify against production rather than assuming**, and note that two instruments lie here:
Cloudflare's edge returns error `1010` to a `Python-urllib` user-agent before the Worker ever runs,
and `wrangler types` reports Node.js compatibility as enabled when it is not. Use `curl` with a
normal user-agent, and check `wrangler.jsonc` for the flags.

## The toolchain freshness check lives OUTSIDE this repository

**A clone of this repo does not bring the daily freshness check with it**, and that is worth knowing
before somebody concludes the toolchain is being watched when it is not.

| | |
|---|---|
| The check | `~/.claude/hooks/npm-toolchain-check.py` |
| What turns it on | An entry in `~/.claude/toolchain-projects.json` with `"npm"` in its `toolchains` |
| When it fires | The first `npm run build\|test\|check\|dev\|deploy` of each day, inside a registered root |
| Run it by hand | `python ~/.claude/hooks/npm-toolchain-check.py --probe` |

**On a fresh machine, register the checkout or the check stays silent.** Silence from an
unregistered project is indistinguishable from a clean result, which is the failure this project
keeps writing down in other forms.

**The probe ignores the daily suppression and always asks live**, so it is the right thing to run
before quoting any version number. `CLAUDE.md` carries the loudness rules and what each source is.

## What is deliberately not here

**No frontend exists.** The API can drive one and it would be a separate Cloudflare Pages project.
**Routes are not yet mounted on a custom domain**, because the domain is not owned — once
`flickrgroupaddr.com` is re-registered, the API needs a route on `api.flickrgroupaddr.com` and both
origins in `wrangler.jsonc` stop pointing at the same host.
