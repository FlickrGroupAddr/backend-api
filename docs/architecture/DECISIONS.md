# Decisions

**RFC 2119 keywords. MUST and MUST NOT are absolute. SHOULD is a strong default a good argument may
overrule. MAY is optional.**

**The code is the specification. This file holds only what the code cannot say: why.**

**Numbers run most-important-first.** ADR-01 governs everything below it, and importance descends
from there. Read down, and stop when you have enough.

Labels are `ADR-nn`, never `D-n` — Cloudflare's database is called D1 and the collision confuses
everyone but its author.

**Sections run in ascending order, which is now also importance order.**
`scripts/traceability.py --check` fails the build if that breaks, and `docs/TRACEABILITY.md` maps
every decision to the tests that verify it.

## Renumbered 2026-08-14 — old numbers no longer mean what they did

**Numbers used to record the order decisions were made, which is an accident of history.** They now
record the order a reader should take them in.

Every citation in code, tests, migrations, docs and memory was rewritten in one pass — **178
references across 35 files** — and the suite and the mutation harness both passed afterwards.

**Commit messages were NOT rewritten, and cannot be.** 167 mentions across 65 commits still use the
old numbering, and this project puts a lot of its reasoning there. **Use this table to read anything
written before 2026-08-14.**

| Old | New | Decision |
|---|---|---|
| ADR-08 | **ADR-01** | Fail-polite. Never retry into a human |
| ADR-07 | **ADR-02** | Classify by Flickr's error code |
| ADR-10 | **ADR-03** | FIFO per (user, group). Never jump the queue |
| ADR-11 | **ADR-04** | A pair that reached a moderator is remembered |
| ADR-05 | ADR-05 | Adds are idempotent — **unchanged** |
| ADR-04 | **ADR-06** | The nightly cron work engine |
| ADR-01 | **ADR-07** | The Flickr account is the identity |
| ADR-02 | **ADR-08** | OAuth state lives in a Durable Object |
| ADR-03 | **ADR-09** | Tokens encrypted under a separate key |
| ADR-06 | **ADR-10** | The session is a stateless signed cookie |
| ADR-12 | **ADR-11** | Separate origins, host-only cookie, CORS |
| ADR-09 | **ADR-12** | No cache in front of D1 |
| ADR-13 to ADR-17 | **unchanged** | Engineering policy |

**This table is permanent.** It is the only thing keeping 65 commit messages readable, and deleting
it silently breaks every one of them.

**Renumbering again would be a mistake.** It was done once, deliberately, while the project was two
days old and the cost was measurable. Every repeat doubles the number of mapping tables a reader has
to chain through.

## ADR-01 — Fail-polite. This one outranks the rest.

**Where an outcome could mean a human declined, FGA MUST treat it as terminal.** Even when the same
outcome could also mean something retryable. **When this conflicts with any other decision here,
this one wins.**

A moderated group does not reject an add. It puts the photo in a queue for an unpaid volunteer. If
that person declines, the API says nothing — the photo simply never appears.

**So a second add is not a retry. It is a fresh submission, and the moderator sees it again.**

The asymmetry decides it. Wrongly terminal costs one request, visible to the user who chose to use
FGA. Wrongly retried spends a stranger's attention, invisibly, every night.

**The user MUST be told, in plain language, when a request stopped for this reason.** A silent stop
reads as a bug, and a user who thinks FGA is broken adds the photo by hand — which recreates the
exact harm.

Lives in `src/adds/classify.ts`.

## ADR-02 — Classify by Flickr's error code. Unknown means terminal.

**Only codes 5, 105 and 106 MAY be retried. Everything else is terminal, including codes Flickr has
not invented yet.**

**The default is inverted from the 2022 version, and that is the point.** That version retried every
unrecognized code nightly, forever — a bucket holding codes 1, 2, 4, 7, 8, 10 and 11, every one a
permanent condition. **An unknown failure is the one most likely to be permanent.**

**Widening the retryable set is the most dangerous edit available in this repository.**

The table lives in `src/adds/classify.ts`. Read it there.

## ADR-03 — FIFO per (user, group). The queue is never jumped.

**Every request MUST be attempted in append order within its `(user, group)` queue.**

**The API Worker MAY attempt a new request immediately only when it is the sole unresolved request
in its queue.** A queue of length one is the only case where an immediate attempt cannot take an
allowance slot from something that waited longer.

**The nightly sweep MUST stop a queue at its first retryable failure.** Everything behind the head is
blocked by the same daily cap, so trying the next one is the queue-jump this rule forbids, wearing an
efficiency costume.

**Order MUST come from `requests.id`, never a timestamp.** Timestamps tie.

Queues keyed by different tuples are fully independent, so the sweep MAY run them in any order.

Lives in `src/sweep.ts` and `src/db/requests.ts`.

## ADR-04 — A pair that reached a moderator is remembered forever

**Codes 6 and 7 MUST write a permanent `moderated_pairs` row**, and it MUST outlive the request.

**On resubmission the interface MUST warn, and MUST NOT block.** The warning informs. The person
decides. A block would override a human's judgment about their own photo, which is ADR-01 pointed the
wrong way.

**Check the pool first.** A photo now in the pool was approved, so the warning MUST NOT fire — a
false alarm spends the credibility the real warning needs.

The table is named for what is known. **No rejection signal exists in the Flickr API**, so nothing
here may imply one.

## ADR-05 — Adds are idempotent per (photo, group)

**The handler MUST confirm the pair has not already succeeded before calling Flickr.**

`flickr.photos.getAllContexts` beats the local check because it also sees adds FGA did not make.
**"Already in the pool" MUST be treated as success.**

## ADR-06 — The work engine is a nightly cron over D1

**Pending requests MUST be rows in D1.** A Cron Trigger is the engine. Per-user Durable Object alarms
**MUST NOT** be introduced without measuring one of: the scan threatens Worker limits, Flickr
rate-limits the burst, or per-user scheduling becomes a product requirement.

A `SELECT` beats a fan-out when you need to ask what is stuck and why. **Plan cost was never the
argument and does not reopen it.**

Lives in `src/sweep.ts`.

## ADR-07 — The Flickr account is the identity

**FGA MUST NOT store an email address, a display name, or any contact detail.** The NSID is the key.

**Understand the consequence rather than assuming it away.** Flickr offers no scope narrower than
`write`, so the token FGA holds grants edit access to the user's entire account, while the product
needs only "add this photo to that group". **FGA holds a credential far more powerful than its
feature set.**

## ADR-08 — OAuth state lives in a Durable Object

**The request-token secret MUST be held in a Durable Object keyed by `oauth_token`.** It **MUST NOT**
go in Workers KV, which offers no read-after-write guarantee across points of presence.

**D1 would also have worked** — its reads are strongly consistent. **Lifecycle decides it, not
consistency.** A D1 table here would be a table whose every row is destined for deletion, plus a
sweep the cron must not forget. The Durable Object needs no table and cleans itself.

**It MUST set an alarm on creation that deletes its storage after roughly 15 minutes.** Most logins
are abandoned, so that path is the common case.

**One object per login ATTEMPT, not per user.** At that point no user exists yet.

Lives in `src/oauth/login-attempt.ts`.

## ADR-09 — Tokens are AES-GCM encrypted in D1, under a separate key

**Each user's Flickr token MUST be encrypted before it reaches D1.** The key is a Worker secret.

**The token key and the session key MUST be different values.** Rotating the session key logs
everyone out and costs nothing. Rotating the token key means re-encrypting every stored token.
**Sharing one key makes the cheap rotation as expensive as the dear one, so neither ever happens.**

Per-user tokens **MUST NOT** go in Cloudflare Secrets Store — it caps at 100 secrets per account,
which is a ceiling you discover only once the product works.

Lives in `src/crypto/tokens.ts`.

## ADR-10 — The session is a stateless signed cookie

**After the Flickr callback, the Worker mints a token carrying the NSID and sets it as a cookie.**
The Flickr token **MUST NOT** reach the browser.

It is stateless, so it costs no D1 read per request and there is no session table. **What that gives
up is instant revocation**, which matters little here: the Flickr token never leaves the server, and
a user who wants FGA cut off revokes it at Flickr, which is more thorough anyway.

**This is the softest decision in this document and the cheapest to reverse.** An opaque session row
in D1 replaces it without touching anything else.

`src/session.ts` is the only place that knows the cookie's name or attributes. Set, read and clear
all go through it.

## ADR-11 — The session cookie is host-only, and `Origin` is never reflected

**Amended by ADR-18 on 2026-08-14.** This decision was written when the UI and the API were
planned as separate origins. **They now share one.** Everything below still holds; the CORS half
is inert rather than wrong, and it MUST NOT be deleted on that basis.

**The cookie is `__Host-fga_session`: `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`, no `Domain`.**

**The `__Host-` prefix is browser-enforced.** Without it, anything able to set cookies on the parent
domain can plant a same-named cookie that shadows ours, and the API cannot tell them apart because
`Domain` is not sent back.

**`SameSite=Lax` is the CSRF control.** It worked when the two shared a registrable domain, and
under ADR-18 they share the whole origin, which is strictly stronger. Same-site is not the same
as same-origin.

**Every API response MUST carry `Access-Control-Allow-Origin` set to our own configured origin.**

**The Worker MUST NOT reflect the request's `Origin` header.** With credentials enabled that lets any
site on the internet make authenticated calls as a logged-in user. **It is a two-line mistake and it
looks exactly like the fix.**

## ADR-12 — No cache in front of D1

**FGA MUST NOT build an application cache.** Every `/api/v001/*` response carries
`Cache-Control: private, no-store`.

**Cost is not the reason to cache.** D1 bills reads at $0.001 per million rows. **Writes cost 1,000×
reads**, so anyone adding a per-attempt write MUST check the volume first.

The trap this prevents: a per-user response in a shared cache without a per-user key, which serves
one member's queue to another.

**Anyone auditing indexes MUST use `PRAGMA index_list`.** A `UNIQUE` constraint creates an index that
`grep "CREATE INDEX"` will never find, and the usual result is a duplicate B-tree that costs writes
and serves nothing. **Read a query plan only against populated tables** — on an empty one SQLite has
no statistics and guesses.

## ADR-13 — TypeScript, on the current stable toolchain

**Verification: Inspection.** Read package.json and wrangler.jsonc, plus the daily
python ~/.claude/hooks/npm-toolchain-check.py --probe. **No runtime behavior to test.**

**The project MUST track current stable and MUST NOT adopt a `beta`, `rc`, `next` or `dev` tag.**

Rust was rejected on maintenance — `workers-rs` had 9 commits in 13 weeks against the runtime's
1,360. Python was rejected because it is in open beta.

**TypeScript 7 costs the project `typescript-eslint`, which cannot consume the Go-native compiler
until 7.1.** Biome parses TypeScript itself and is unaffected.

**It costs `svelte-check` too**, found 2026-08-14 while adding ADR-18's UI. It peers on
`typescript: ^5 || ^6`, so nothing typechecks inside a `.svelte` file — not `tsc`, not Biome.
**The mitigation is placement rather than tooling:** logic lives in `web/src/lib/*.ts` under
`web/tsconfig.json`, and components stay thin enough that a mistake is visible.

### The Go compiler is real, and npm is now the slow part

**Measured 2026-08-14, warm, on this machine.** The binary is
`node_modules/@typescript/typescript-win32-x64/lib/tsc.exe`, 18 MB of native Go.

| | |
|---|---|
| `tsc.exe --noEmit` (Worker config) | **~330 ms** |
| `tsc.exe --noEmit -p web` | **~160 ms** |
| `tsc.exe --version`, pure startup | 52 ms |
| The same two through `npm run typecheck` | 960–2,160 ms |

**So TypeScript spends about 280 ms checking the Worker and 110 ms on the web app, and process
spin-up costs three to six times that.** Optimizing the typecheck would be optimizing the wrong
thing.

**The inputs are small and one of them dominates.** 3,070 lines across `src/` and `test/`, 651 in
`web/src/` — against the generated `worker-configuration.d.ts` at **15,188 lines**, five times all
the hand-written code combined.

**ESLint was never in this project.** Biome went in at the scaffold commit. This was a choice, not a
migration.

**Revisit when TypeScript 7.1 ships stable — and returning is NOT automatic.** Reopening needs a named
lint rule this project needs, requiring full type information, that Biome does not implement.

## ADR-14 — Integrate when feasible, innovate otherwise

**Verification: Inspection**, for the policy. **Test**, for the signer it permitted --
see 	est/signature.test.ts against RFC 5849's own vectors.

**Where a maintained dependency runs in this runtime and does the job, take it.** Hand-written code
**MUST** be justified against four tests: does it run here, **is the platform already doing it**, is
it maintained, is the spec short with published vectors.

**The second test pays off most often.** `crypto.subtle.timingSafeEqual` and `crypto.randomUUID()`
were both about to be replaced by dependencies.

**The OAuth 1.0a signer is the documented exception.** Every package on npm is unmaintained,
Node-only, or wraps an HTTP client this project does not use. It is tested against RFC 5849's own
vectors, because a signature Flickr rejects tells you nothing about which layer was wrong.

Lives in `src/oauth/signature.ts`.

## ADR-15 — Which store holds what

**Verification: Inspection.** A placement rule, so it is verified by reading where state
lives rather than by running anything.

**New state goes in D1 if either answer is yes.** Does anything need to find this without already
knowing its key? Does it outlive a single interaction?

**A Worker cannot enumerate the Durable Objects in a namespace.** Anything that must be swept,
listed or reported on therefore **MUST NOT** live in one.

The OAuth attempt is the only state answering no to both. **Workers KV holds nothing.**

## ADR-16 — A request has two identifiers

**`requests.id` orders and never leaves the server. `requests.public_id` is a UUIDv4 handle that
always does.**

**The ordering key MUST NOT become a UUID.** Every UUID form ties somewhere, and v7 ties within a
millisecond — which is exactly what bulk-queueing fifty photos looks like.

**v4 rather than v7 for the public handle**, because v7 republishes its own creation time.

## ADR-17 — Every list endpoint is paginated, with a cursor

**A list endpoint MUST NOT return an unbounded result set.** Pagination **MUST** be keyset, never
offset.

**Offset paging silently skips rows here.** The nightly sweep resolves requests continuously, so the
set shifts under the reader between pages.

**The cursor MUST be opaque, and the end of a list is a fact the server states.** A short page is not
the end — that is wrong exactly when the last page is full.

**A `limit` MUST be capped, not merely defaulted.** FGA's is 1–200, default 50.

## ADR-18 — One origin, an `/api` prefix, and a Svelte app shell

**The UI is a prebuilt single-page app served as static assets by the SAME Worker that
answers the API.** One hostname, `flickrgroupaddr.com`, at the apex. `wrangler.jsonc` routes
`/api/*`, `/oauth/*` and `/health` to the Worker with `run_worker_first`, and everything else
falls through to `index.html` via `not_found_handling: "single-page-application"`.

**The Worker MUST NOT claim `/`.** The app shell owns it. A Worker route there shadows
`index.html` for every visitor, and it does so only in production, where the assets binding
exists and local tests have nothing to notice.

### One origin, because the safest CORS code is the code that is not reachable

**ADR-11 assumed two origins and its CORS contract was the price.** That contract is now
inert: a same-origin browser sends no `Origin` worth checking. **ADR-11 is amended, not
repealed** — the `__Host-` prefix still matters, `SameSite=Lax` still works, and the
prohibition on reflecting the request's `Origin` is still absolute.

**The middleware and its tests MUST stay.** A control deleted because it is currently
unreachable is a control nobody restores when a second origin appears. ADR-11 itself calls
reflection "a two-line mistake and it looks exactly like the fix," which is the argument for
keeping a test that can still catch it.

**The registrar was never the constraint, and that is worth writing down because it nearly
drove the design.** A Cloudflare zone is not a registration. `flickrgroupaddr.com` is
registered at Amazon Registrar and its nameservers point at Cloudflare, which is all a Workers
custom domain at the apex requires.

### Svelte, and specifically not React

**The framework MUST compile away.** Svelte generates DOM operations at build time rather than
shipping a runtime and a virtual DOM, which is what makes a framework defensible on a
three-screen console at all.

**React was proposed first and withdrawn.** It entered on conventionality, which is the weakest
argument available here, and it costs four dependencies against a backend that runs on three
zero-dependency ones. **Conventionality is a real criterion and it lost to a stronger one.**

**No framework was the other candidate, and it is refused for one specific screen.** Submitting
one photo to forty groups fans out forty requests that resolve independently — some `202`, some
resolved, some `409 needs_acknowledgement`. Hand-written DOM code tracking forty small state
machines is where the 2021 UI became unmaintainable, and it is also where ADR-01 is finally kept
or broken. **That screen MUST be declarative.**

**`{expr}` escapes by default**, which retires the hand-rolled `innerHTML` string building that
the previous UI used. Same class of fix as ADR-14 choosing `hono/html`.

### Two things this decision does NOT settle

**The traceability gate cannot see UI tests.** `scripts/traceability.py` globs `test/*.test.ts`
only. ADR-01's user-facing wording will live in `web/`, so **a future session MUST decide
whether to widen that glob rather than let the most important copy in the product go
unverified.**

**A batch preflight endpoint is still missing.** Without it the picker discovers ADR-04
warnings as N separate `409`s. See "Still open."

## ADR-19 — The admin surface reports findings, not figures

**`/api/v001/admin/*` is gated by an NSID allowlist in the `ADMIN_NSIDS` Worker secret, a JSON
array.** It is a secret rather than a `vars` entry because `wrangler.jsonc` is committed publicly,
and publishing who reads operational data is free reconnaissance.

**The allowlist MUST fail closed.** Missing, malformed, or empty admits nobody. **The tempting
failure is the other way** — a config mistake where "no allowlist" reads as "no restriction", which
opens the dashboard to every signed-in user and reports nothing.

**A signed-in non-admin gets 404, never 403.** A 403 confirms the surface exists and that this
account merely is not on the list. That is worth nothing to the caller and something to a prober.

**The allowlist is deliberately NOT compared in constant time.** The caller's NSID comes from their
own verified session, so they already know it, and list membership is not a value anyone can grind
for. A constant-time compare here would imply a threat model that does not exist.

### Volume tracks actionability, which is why this is findings and not a dashboard

**The endpoint returns things an admin can DO something about, and says nothing when there is
nothing.** This is the toolchain-check doctrine applied to operations: a page that always shows
twelve numbers teaches its reader to skim, and then the one night a number matters they scroll past.

Three severities, and **the middle one MUST NOT be collapsed into either neighbor**:

| | |
|---|---|
| `act` | Confirmed, and something fixes it now. MUST carry an action |
| `watch` | Real, nothing to do this minute |
| `info` | We cannot currently tell. Naming the blindness beats implying health |

**The load-bearing check is a queue HEAD not attempted in 48 hours**, not silence in resolutions. A
sweep can run correctly and resolve nothing — every queue throttled is the product working, and
`stoppedOnThrottle` is expected. **An attempt is recorded before the Flickr call regardless of
outcome**, so a stale head proves the sweep never reached it. Accounts flagged `needs_relink` are
excluded, matching `queueHeads()`, because the sweep skips them by design.

**Queue length and attempt count MUST NOT raise a finding.** Waiting is this product working, and
`docs/FLICKR.md` measured throttle modes of `day`, `week` and `month` — a month-throttled group with
forty ahead legitimately takes years. Nothing stores a group's throttle mode, so a jammed queue and
a patient one are identical from here. **Alerting on either would be a warning that fires when
nobody can act**, which is the fastest way to make every warning worthless.

### Predicting a throttle was considered and rejected. Detecting a surprising one was not.

**The sweep MUST continue to attempt every eligible queue every night.** Skipping a queue because
`flickr.groups.getInfo` suggests the user is throttled is refused on three grounds.

**The cost inverts.** `getInfo` is itself a Flickr call, so you spend one call to save one call —
net zero when the prediction is right, and net worse for every queue that was not throttled.

**The premise is unconfirmed.** `docs/FLICKR.md` records `remaining` as reading per-user and marks
it **"strong, not conclusive"**; confirming it needs one add followed by a re-read of the same
group, which nobody has done. Skip logic built on it would be a well-argued design resting on a
measurement that does not say what the design needs it to say.

**A wrong skip fails silently and invisibly.** The photo waits an extra day and the queue looks
exactly as it always looks. Flickr's code 5 already answers this authoritatively for the same one
call, and ADR-02 already handles it.

**The inversion IS worth building.** Persist `throttle.mode` when `/api/v001/groups/:groupId`
happens to fetch it — no extra calls — and use it to explain rather than to decide. It turns the
`throttle-mode-unknown` blind spot into a real alert, and it makes a genuine signal available: **a
nightly attempt refused for throttle when our own model says the user has allowance left.** That
disagreement means either our reading of `remaining` is wrong or something else is spending the
allowance, and both are worth knowing. **Observation cannot cause a silent skip, because nothing
skips.**

---

## Considered and rejected

| Option | Why not |
|---|---|
| AWS | Every piece has a simpler Cloudflare equivalent here |
| An off-the-shelf OAuth 1.0a library | All unmaintained, Node-only, or wrapping an HTTP client we do not use |
| Per-user Durable Object alarms | **Deferred, not rejected.** See ADR-06's promotion criteria |
| D1 read replication | Removed 2026-08-13. One user, in ENAM, with the database in ENAM. Replicas are eventually consistent and the bookmark plumbing fails silently |
| Cloudflare Secrets Store | Right product, wrong maturity, and a 100-secret ceiling |
| Workers KV | Consistency model is wrong for the login path |
| Cognito or Google login | Both supply an identity ADR-07 declines to hold |
| React for the UI | Proposed, then withdrawn. It entered on conventionality and costs four dependencies to a compiler's one. See ADR-18 |
| Astro | Its islands and zero-JS pages buy nothing when every view is authenticated and client-rendered. There is nothing to prerender |
| Cloudflare Pages | Cloudflare's own static-assets guidance routes "API routes + SPA" to Workers static assets, which is one deploy rather than two |
| Hand-written DOM code, no framework | Refused for the batch-submit screen specifically. Forty independent request outcomes is where the 2021 UI became unmaintainable |
| Separate UI and API hostnames | **Reversed by ADR-18.** It was the plan until the domain landed; one origin makes the CORS contract inert instead of load-bearing |
| Skipping a queue the sweep predicts is throttled | `getInfo` costs the call it would save, `remaining` is unconfirmed as per-user, and a wrong skip is invisible. See ADR-19 |
| A counters-and-charts admin dashboard | A page that always shows twelve numbers trains its reader to skim. ADR-19 emits findings and stays silent when there is nothing to do |

## Still open

- **An unanswered add is terminal, and that MAY be too strict.** A dropped connection has no error
  code, and the pool may be moderated. `flickr.groups.getInfo` reports whether a pool is moderated,
  and **for an unmoderated pool the ambiguity disappears** — `getAllContexts` then answers
  definitively. Only moderated pools would stay terminal.
- **Nothing persists a group's `throttle.mode`, and three things want it.** ADR-19's
  `throttle-mode-unknown` finding cannot become a real alert without it; a `disabled` pool costs one
  wasted call per request; and the signal ADR-19 names — **a nightly attempt refused for throttle
  when our own model says the user still has allowance** — needs it to exist at all. That last one
  is **informational only and MUST NOT gate an attempt.** `/api/v001/groups/:groupId` already
  fetches it, so recording it costs no extra Flickr calls.
- **`www.flickrgroupaddr.com` needs a Cloudflare Redirect Rule, and currently answers 522.** The
  DNS record exists but nothing is behind it. **Routing `www` to the Worker and 301-ing there was
  tried in production on 2026-08-14 and reverted**: `not_found_handling: "single-page-application"`
  serves `index.html` before the Worker runs for any path outside `run_worker_first`, so the
  redirect never fired and `www` served the whole app on a second hostname — the exact thing ADR-18
  removes. Making it work in the Worker would mean `run_worker_first` covering navigations and the
  Worker serving assets itself through an `ASSETS` binding, which is a lot of machinery to bounce a
  hostname. A Redirect Rule runs at the edge, ahead of both Workers and assets. **301, and it MUST
  preserve the path and query.**
- **The domain sends no mail and does not say so.** ADR-07 holds no email address and FGA sends
  none, so a null MX plus a hard-fail SPF record is the honest configuration. Without them the
  domain is spoofable as a sender.
- **`remaining` has never been confirmed as per-user.** `docs/FLICKR.md` calls it "strong, not
  conclusive." One add followed by a re-read of the same group settles it, and several decisions
  are waiting on the answer.
- **The wording a user sees when FGA has deliberately stopped.** That the queue is shown is settled.
  The sentence itself is not, and it either delivers ADR-01's promise or quietly undercuts it.
- **No endpoint answers "which of my groups already hold this photo."** `getPhotoPools` exists in
  `src/flickr/api.ts` but is reachable only inside `POST /api/v001/requests`. Without a batch
  preflight the picker discovers ADR-04 warnings as N separate `409`s, one round trip each, which
  is unusable at forty groups. **The shape is not settled** — one call per photo returning its
  pools, or one call taking a group list and returning warnings for each.
- **Whether `scripts/traceability.py` should scan `web/`.** It globs `test/*.test.ts`, so no UI test
  can verify a decision today. ADR-01's user-facing copy will live there.
