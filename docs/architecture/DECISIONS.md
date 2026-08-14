# FlickrGroupAddr backend-api — architecture decisions

**RFC 2119 keywords, and the capitals are load-bearing.** MUST and MUST NOT are absolute;
SHOULD and SHOULD NOT are strong defaults a good argument may overrule; MAY is genuinely
optional.

This file records decisions for the 2026-08 rebuild and, separately, the facts those decisions
rest on. **The repositories under the FlickrGroupAddr GitHub org are stale reference, not
requirements** — they record what was tried between roughly 2016 and 2022, under constraints
that no longer apply. Mine them for domain facts; do not inherit their architecture.

## Revision history

**Recorded because the git history under-describes itself.** Commit `b47c982` carries a message
about the Workers Paid plan but actually contains the whole v1 rewrite, which was authored earlier
and left uncommitted while an unrelated domain emergency was handled.

| Commit | What actually changed |
|---|---|
| `82288e1` | First draft. Per-user Durable Objects with alarms as the work engine; master key in Secrets Store. |
| `77cb9a6` | Added the argument against that alarm engine. Confirmed the Workers Paid plan. |
| `b47c982` | **The v1 rewrite.** Work engine changed to a nightly cron over D1 (ADR-04). Master key moved from Secrets Store to Worker secrets (ADR-03). Session decision added (ADR-06). Flickr's read/write/delete-only scope recorded and its consequence folded into ADR-01. Diagram redrawn to match. Plus the plan allowances this message describes. |
| `361a188` | Decision markers removed from the diagram. It now carries the shape only and points here for the reasoning. |
| `8b09cb1` | **Decisions renumbered `D1`–`D6` to `ADR-1`–`ADR-6`** to end the collision with Cloudflare D1. Any external reference to the old labels is now stale. |
| `ab88b96` | Filled in the SHA this table had left as "this commit". |
| `18c8813` | Zero-padded the labels to `ADR-01`–`ADR-06` so they sort correctly past nine. |
| `22f3d3d` | **Background section added: why OAuth 1.0a shapes so much of this.** Written for a reader who speaks OAuth 2.0 natively. Answers where the callback went — it is a route, not a component — and states the cause behind ADR-01, ADR-02 and ADR-03 in one place: 1.0a issues a token secret that has to survive a redirect through a browser. |
| `eac9117` | **ADR-12 added: the UI and the API are separate origins.** Settles the cookie as host-only with no `Domain` attribute — correcting an earlier claim that it would need widening to the apex — and writes out the CORS contract, including the reflected-`Origin` mistake that would expose every logged-in session. Routes lose their `/api` segment now that the hostname carries it. |
| `ffc5ffa` | **ADR-11 added: pairs that reached a moderator are remembered permanently.** A `(photo, group)` pair resolving with code 6 or 7 is recorded for good, and a later resubmission warns the user without blocking them. Establishes that current pool membership proves approval after the fact, which is the only way the invisible moderator decision becomes partly visible. |
| `28d40c6` | The queue view scoped to the `(user, group)` tuple, not "per group". Recorded that ADR-07 makes the queues fully disjoint — code 5 is the only retryable condition and it is per-user — so the nightly sweep is parallel across queues. |
| `596579a` | **The queue view recorded**, where ADR-08's "the user can find out" half is finally delivered. Noted that ADR-10 caps the write volume ADR-09 warned about, since only queue heads are ever attempted. |
| `cccd677` | **ADR-15 added: which store holds what, and ADR-02 corrected.** The owner could not derive the D1-versus-Durable-Object split from the diagram, and the split turned out to rest on an argument ADR-02 never made: it compared the Durable Object against KV and never against D1, which would also have worked. Consistency does not distinguish them; lifecycle does. Both now say so. |
| `ad0b864` | **ADR-14 added: integrate when feasible, innovate otherwise.** The owner's standing order against reinventing wheels, with the four tests that permit hand-written code and a full survey of the OAuth 1.0a packages showing why the signer is the exception. Records `hono` and `zod` as the only runtime dependencies, both with zero transitive dependencies. |
| `93c455a` | **ADR-13 added: the implementation language is TypeScript.** Rust and Python were each argued for and rejected — Rust on the `workers-rs` maintenance numbers, Python because it is in open beta and ADR-03 already refused a beta dependency for a smaller surface. Carries the version policy, the TypeScript 7 / `typescript-eslint` tradeoff, and a checkable list of the idioms that separate current Workers code from dated Workers code. |
| `dd1e807`, `31c97d8` | Live-call findings folded in: the five `throttle.mode` values, `remaining` being per-user, 330 groups as a real account size, and Flickr needing no pre-registered callback. |
| `5f43291` | **ADR-12 gains the `__Host-` cookie prefix, and records the defect it uncovered.** The attributes were specified in a helper the Worker never called, duplicated in the callback route, and duplicated again in logout — where `HttpOnly` had been lost. Five tests asserted on the dead helper and could not have failed. Replaced with assertions on the real `Set-Cookie` from a full stubbed login, verified by mutation. |
| `1822e3d` | **ADR-10 added: FIFO per (user, group), and the queue is never jumped.** Settles that the API Worker attempts a new request immediately only when its queue is otherwise empty, and that the nightly sweep stops a queue at its first retryable failure. ADR-05 gained the `photos.getAllContexts` check. The Flickr API surface and OAuth 1.0a's signing of the request-token call were recorded as verified facts. |

## Verified facts

**Every row below was established by measurement or by reading a primary source on the date
given, not from recall.** Re-verify before quoting any of them in a later design; several are
beta-era numbers that will move.

| Fact | How it was established | Date |
|---|---|---|
| `workerd` supports HMAC-SHA1 via WebCrypto | Known-answer test in the local `workerd` runtime (wrangler 4.122.0) against RFC 2202 TC1 and TC2; both matched byte for byte. Corroborated in source: `src/workerd/api/crypto/impl.c++` registers `{"SHA-1", EVP_sha1()}` in `lookupDigestAlgorithm`, and `digest.c++` routes the HMAC `hash` parameter through that same function. | 2026-08-12 |
| `workerd` supports AES-GCM encrypt/decrypt | Round-trip test in the same local runtime. | 2026-08-12 |
| Workers KV is eventually consistent | Cloudflare docs: changes "may take up to 60 seconds or more to be visible in other global network locations." Read-after-write is **not** guaranteed, even at the writing location. Negative lookups are cached too. | 2026-08-12 |
| Durable Object alarms deliver at-least-once | Cloudflare docs: guaranteed at-least-once execution, automatic retry with exponential backoff from 2 seconds, up to 6 retries, and `alarmInfo.retryCount` / `alarmInfo.isRetry` exposed to the handler. | 2026-08-12 |
| Cloudflare Secrets Store caps at 100 secrets | Open beta limits: 100 secrets per account, one store per account, 1024 bytes per secret value. | 2026-08-12 |
| Flickr OAuth offers only three permission levels | Flickr API docs: the `perms` parameter accepts `read`, `write`, or `delete`. **There is no narrower scope** — no way to request permission to add photos to groups without also granting full write access to the account. | 2026-08-12 |
| `flickr.groups.pools.add` returns a numeric error code | Flickr API docs. Relevant codes: **1** photo not found, **2** group not found, **3** photo already in pool, **4** photo in maximum number of pools, **5** photo limit reached, **6** photo added to the Pending Queue for this pool, **7** photo already in the Pending Queue, **8** content not allowed, **10** maximum number of photos in group pool, **11** group pool is disabled. Transient: **105** service unavailable, **106** write operation failed. | 2026-08-13 |
| A moderator's decision on a queued photo is invisible to the API | There is no error code, callback, or endpoint that reports a rejection. After code **6** the photo sits in the pool's pending queue; if a moderator rejects it, it simply never appears in the pool. `flickr.photos.getAllContexts` can show whether a photo landed, but "not in the pool" cannot distinguish *still pending* from *rejected*. | 2026-08-13 |
| D1 bills reads at $0.001/M rows and writes at $1.00/M — writes cost 1,000× more | Cloudflare pricing. Workers Paid includes **25 billion rows read** and **50 million rows written** per month, plus 5 GB storage, then $0.001/M read, $1.00/M written, $0.75/GB-mo. | 2026-08-13 |
| D1 read replication is free and automatic in six regions | Cloudflare docs: *"Read replication does not charge extra for read replicas. You incur the same usage billing based on `rows_read` and `rows_written` by your queries."* No per-replica storage charge, and a write is not billed once per replica. Replicas are placed automatically in **ENAM, WNAM, WEUR, EEUR, APAC, OC** — the count is not configurable. Enabled with `read_replication.mode: auto`; reads must go through the Sessions API (`withSession()`) or they hit the primary regardless. | 2026-08-13 |
| Durable Objects have no TTL, and an idle one is free | Cloudflare docs: there is no automatic expiry, but "inactive objects receiving no requests do not incur any duration charges." Storage is metered separately and "Durable Objects will be billed for stored data until the data is removed"; once deleted through the Storage API the object is cleaned up and stops incurring storage fees. **There is no runtime API to enumerate the objects in a namespace** — a Worker cannot list them. | 2026-08-13 |
| The Flickr API surface FGA needs is six calls | Read from the 2022 code in the old repos, which is working precedent rather than a guess. Login: `oauth/request_token`, then `oauth/authorize` with `perms=write` in the browser, then `oauth/access_token`. Runtime: `flickr.groups.pools.getGroups` for the groups a user may post to, `flickr.photos.getAllContexts` for the pools a photo is already in, and `flickr.groups.pools.add` for the add. Mined for the domain facts only — the architecture around them is not inherited. | 2026-08-13 |
| OAuth 1.0a signs the request-token call itself | RFC 5849 §3.4: the signing key is `consumer_secret&token_secret`, with an empty token secret for the temporary-credentials request, and `oauth_consumer_key` travels in the parameters. **The first call of a login therefore already needs the FGA Flickr API credentials** — there is no unauthenticated leg anywhere in the flow. | 2026-08-13 |
| Workers language support is far more uneven than the docs imply | GitHub `stats/participation` for the thirteen weeks to 2026-08-13: `cloudflare/workerd` **1,360** commits, `cloudflare/workers-sdk` **649**, `cloudflare/workers-rs` **9**. `workers-rs` is at `v0.8.5` (2026-06-12), pre-1.0, with 184 open issues. All four languages are described as first-class on the languages page. **The commit list endpoint caps at 100 per page and must not be used for this** — it reports a flat "100" for both active repos and hides the real ratio. | 2026-08-13 |
| Python Workers are in open beta | Cloudflare docs: the `python_workers` compatibility flag is required "while Python Workers are in open beta." Durable Objects, D1, and cron triggers are all documented as available. | 2026-08-13 |
| TypeScript 7.0 is stable, and `typescript-eslint` cannot consume it | TypeScript 7.0 shipped 2026-07-08 as the first stable release built on the Go-native compiler, 8–12× faster on full builds; `npm dist-tags` gives `latest: 7.0.2`. It ships without a stable programmatic API until 7.1, so compiler-API consumers are blocked — `typescript-eslint@8.67.0` declares `peerDependencies.typescript` of `>=4.8.4 <6.1.0`, excluding 7.x. Biome (`2.5.8`) and oxlint (`1.78.0`) parse TypeScript themselves and are unaffected. | 2026-08-13 |
| Cloudflare recommends `wrangler types` over `@cloudflare/workers-types` | Cloudflare docs: *"We recommend you use `wrangler types` to generate runtime types, rather than using the `@cloudflare/workers-types` package"* — the generated types match the Worker's own compatibility date and flags. The package is **not** deprecated and remains recommended for typing libraries and shared packages. | 2026-08-13 |
| No maintained, Workers-native OAuth 1.0a signer exists on npm | Surveyed via `npm view` and `npm search`: `oauth-1.0a@2.2.6` (2019, synchronous `hash_function` incompatible with async WebCrypto), `oauth-signature@1.5.0` (2017, depends on `crypto-js@3.x`), `oauth@0.10.2` (Node-only, built on `http`/`https`), `node-oauth1@1.3.0` (2020), `axios-oauth-1.0a@0.4.1` (2026, but an axios interceptor). See ADR-14. | 2026-08-13 |
| `hono` and `zod` both ship with zero transitive dependencies | `npm view hono dependencies` and `npm view zod dependencies` both return empty. Versions `4.13.2` and `4.4.3`, both published 2026-08-13. | 2026-08-13 |
| `flickr.groups.getInfo` reports whether a pool is moderated | Flickr API docs: the group element carries an **`ispoolmoderated`** attribute, `0` or `1`. This is the signal that would let an unanswered add be retried safely for unmoderated pools — see the open question on unconfirmed adds. **Not the same field as `restrictions.moderate_ok`**, which is about permitted *content* ratings and is a different thing entirely. | 2026-08-13 |
| `flickr.groups.getInfo` also quantifies the per-group add throttle | Flickr API docs, example response: `<throttle count="10" mode="month" remaining="3" />`. **`count`** is the allowance, **`mode`** its period, and **`remaining`** how much is left. The docs do **not** enumerate the legal values of `mode` — only `month` appears in the example, and day and week are expected but unconfirmed. **Whether `remaining` is per-user or per-group is also unconfirmed** and matters enormously; the call is authenticated, so per-user is the reasonable reading. Both gaps need one live call to close. | 2026-08-13 |
| `throttle.mode` takes five values, not three | Live `groups.getInfo` across 330 of the owner's real groups, 2026-08-13: **`day`**, **`week`**, **`month`**, **`none`** (no limit) and **`disabled`** (always paired with `count: 0`). The documentation shows only `month`. **`disabled` is the operationally important one** — those pools accept no adds at all, so FGA **SHOULD** skip them rather than spend an attempt discovering it. Seen on invite-only and showcase groups. | 2026-08-13 |
| `throttle.remaining` is per-user, not per-group | Same live sample. **`remaining` equaled `count` in every one of 330 groups**, including `Amateurs` (95,352 members, 9.3M photos) and `Bird Photos` (101,665 members). A group-wide counter on pools that busy could not sit at full allowance. The owner had posted nothing that day, which is exactly the shape a per-user counter takes. **Strong but not conclusive** — confirming it needs one add followed by a re-read of the same group. | 2026-08-13 |
| One account can belong to hundreds of groups | The owner is in **330**. Recorded because it invalidated a design assumption rather than as trivia: an endpoint that made one call per group took **53 seconds** and returned **979 KB**. Any per-group work **MUST** be sized against hundreds, not a handful. | 2026-08-13 |
| Flickr accepts any `oauth_callback` with no pre-registration | The app-creation form never asked for a callback URL, and production `GET /oauth/login` against `fga-backend-api.terryott.workers.dev` returned a 302 to Flickr's authorize page carrying a valid request token — with that hostname supplied only in the per-request `oauth_callback` parameter. **FGA can therefore change hostnames without touching anything at Flickr**, which matters because the workers.dev origin is temporary and `flickrgroupaddr.com` replaces it once the domain is recovered. | 2026-08-13 |
| A `__Host-` cookie is accepted by Chrome over plain `http://localhost` | Live check against `wrangler dev` on `http://localhost:8787`, 2026-08-13, after confirming the local Worker was serving the new name (`POST /oauth/logout` returned `Set-Cookie: __Host-fga_session=...`). A full login was followed by `GET /v001/groups` and `GET /v001/queue` returning **200 rather than 401**, and both routes sit behind middleware that reads the prefixed name only. **The prefix requires `Secure` and `wrangler dev` serves no TLS**, so this was a real risk to local development rather than a formality; localhost counts as a trustworthy origin. Production is HTTPS and was confirmed separately. | 2026-08-13 |
| Hono's `prefix: "host"` enforces the `__Host-` attributes rather than only renaming the cookie | Read from `node_modules/hono/dist/helper/cookie/index.js`: `generateCookie` calls `serialize("__Host-" + name, value, { ...opt, path: "/", secure: true, domain: void 0 })`. **The three forced attributes come after the spread**, so a caller cannot override them. `hono/utils/cookie.d.ts` additionally declares `HostCookieConstraint = { secure: true; path: '/'; domain?: undefined }`, though that constraint reaches `serialize` and not `setCookie`, whose `name` parameter is a plain `string`. Reads MUST pass the prefix too — `getCookie(c, name, "host")` — or they look for the unprefixed name and find nothing. | 2026-08-13 |
| `jose` accepts a relative duration string for `setExpirationTime` | Read from `node_modules/jose/dist/webapi/lib/jwt_claims_set.js`: the parser regex accepts `seconds?\|secs?\|s\|minutes?\|...`, so `` `${n}s` `` is a relative offset. This is what lets one seconds constant drive both the token's `exp` and the cookie's `Max-Age`; a bare number would be read as an absolute epoch instead. | 2026-08-13 |
| The account is on the Workers Paid plan | Purchase confirmed on the billing page. Included allowances: Workers and Pages Functions 10M requests/month with 30 s CPU per request and 30M ms/month; **Durable Objects 1M requests/month, 400K GB-s duration, 1 GB storage**; Workers Builds 6 slots and 6,000 minutes/month. Overage: Workers requests $0.30/M, Durable Object requests $0.15/M, KV operations $0.50/M, D1 rows $0.001/M. | 2026-08-12 |

## Why OAuth 1.0a shapes so much of this

**Background, not a decision — so there are deliberately no RFC 2119 keywords below.**
Several of the decisions that follow look like independent choices and are largely
consequences of one fact: Flickr speaks OAuth 1.0a, and 1.0a is not a slightly older
OAuth 2.0. Stating the cause once here saves each effect from re-arguing it.

**It does have a callback.** `oauth_callback` on the way out and `oauth_verifier` on the
way back are essentially what the "a" revision added: plain 1.0 pre-registered the
callback URL and nothing tied a returning user to the request that began the flow, which
was a session-fixation hole. **The callback is a route on the API Worker, not a component
of its own** — `api.flickrgroupaddr.com/v001/auth/callback`. The 2021 code deployed it as
a separate Worker (`flickrgroupaddr-flickr-callback-cfworker`), which is why an
architecture diagram with no callback box looks wrong at first glance to anyone returning
from that era.

| | OAuth 1.0a | OAuth 2.0 |
|---|---|---|
| Proving the caller | Every request is signed, HMAC-SHA1 over the request itself | Bearer token; TLS carries the security |
| Credentials per call | Two secrets — the consumer secret and the token secret | One token |
| Legs in the dance | Three | Two |
| Identity payload | `user_nsid`, `username`, `fullname` as form fields | ID token with claims, verifiable against a JWKS |
| Token lifetime | Does not expire | Short-lived, plus a refresh token |

### The third leg is the thing the architecture is built around

In OAuth 2.0 the browser is redirected to authorize, returns with a code, and the server
exchanges that code for a token. In 1.0a the server must **first** call Flickr for a
request token, which comes back as a token *and a token secret*. Only then is the browser
redirected. When it returns carrying a verifier, the final exchange has to be signed with
that token secret.

**So a provider-issued secret has to survive a round trip through someone's browser.** It
cannot travel in the URL, and it cannot be recomputed. That single constraint is the whole
reason ADR-02 exists: the OAuth Durable Object is not there because Durable Objects are
interesting, it is there because 1.0a hands the server a secret and then walks the user
away for two minutes.

### Three more consequences, each of which reads as arbitrary without the cause

- **There is no unauthenticated leg anywhere.** The very first request-token call is itself
  signed, with the token-secret half of the signing key empty because no token exists yet.
  That empty half is what makes the call *look* anonymous when it is not, and it is why
  reading the FGA credentials is its own step in the user journey rather than an
  implementation detail — nothing can reach Flickr before it has happened.
- **There is no identity payload.** 1.0a returns no ID token and offers nothing to verify
  against a JWKS; the access-token response carries the NSID and username as plain form
  fields. ADR-01's "the Flickr account is the identity" is therefore less a preference than
  an acknowledgment — there is no email address to be had at any price.
- **Access tokens do not expire.** No refresh machinery is needed, which is a real
  simplification. The cost is that a leaked token stays valid until the user revokes FGA at
  Flickr, and that is what ADR-03's encryption at rest is protecting against.

**The load-bearing fact under all of this is that `workerd` implements HMAC-SHA1.** It is a
deprecated primitive that a modern runtime could quite reasonably decline to ship, and
without it every Flickr call would be unsignable and Cloudflare Workers would be off the
table for this project entirely. That is why it is the first row of the verified-facts
table and was established three ways rather than assumed.

## Decisions

**Labelled `ADR-nn` for Architecture Decision Record, deliberately not `D-n`.** Cloudflare's
SQLite database is named **D1**, and this document refers to it constantly — "rows in D1",
"encrypted in D1", "costs no D1 read". A decision numbered D1 sitting beside a database named D1
is a collision that reads fine to whoever wrote it and confuses everyone else. These labels
**MUST NOT** be shortened back to `D-n`.

**ADR-08 is the governing principle and outranks the others.** Where any decision here would have
FGA repeat an action that a person may already have declined, ADR-08 wins. Read it before
resolving a conflict between the rest.

**New decisions MUST continue the sequence and MUST be zero-padded to two digits.** `ADR-07`, not
`ADR-7`. Unpadded numbers sort lexically as `ADR-1, ADR-10, ADR-2`, which scrambles the order in
every file listing, heading index, and grep result the moment a tenth decision exists. Padding
costs one character now and cannot be retrofitted cheaply once the labels are referenced from
commit messages and code comments.

**The REST API version is padded for the same reason, to three digits: `/v001/*`.** The padding
carries over from the 2022 API, which used the same form. A path version is harder to change than
a document label, not easier — it is baked into every client that has ever called it — so the
padding **MUST** be right from the first route.

**The path has no `/api` segment, because ADR-12 put the API on its own hostname.** Routes are
`https://api.flickrgroupaddr.com/v001/*`; writing `/api/v001/*` there would say "api" twice. The
earlier form in this document dated from before the origins were split.

### ADR-01 — The Flickr account is the identity

FGA **MUST NOT** run its own identity service and **MUST NOT** store an email address, a display
name, or any other contact detail. The Flickr NSID is the user key.

**Why:** the NSID is a pseudonymous identifier that is already public. An email address is not,
and holding one creates a breach obligation that buys nothing the product needs. The 2022 design
ran Cognito specifically so it would hold email addresses for alerting; that requirement was
never confirmed and is dropped.

**The consequence MUST be understood rather than assumed away.** Minimizing PII here relocates
risk rather than removing it, and Flickr's coarse permission model makes the relocation worse
than it first appears: because there is no scope narrower than `write`, the token FGA holds
grants edit access to the user's entire Flickr account, when the only capability the product
needs is "add this photo to that group." **FGA therefore holds a credential far more powerful
than its own feature set.** Token handling is the security crux of this design, and ADR-03 governs
it.

### ADR-02 — OAuth 1.0a intermediate state lives in a Durable Object

The request-token secret **MUST** be held in a Durable Object keyed by `oauth_token` for the
duration of the redirect, and **MUST NOT** be written to Workers KV.

**Why not KV:** the login flow writes the secret, bounces the user to flickr.com for 5 to 30
seconds, and then must read that secret back when the callback lands. KV offers no read-after-write
guarantee and can take 60 seconds or more to propagate between locations, so the callback can
arrive at a point of presence that cannot yet see the write. The resulting failure is
intermittent, dependent on which PoP the user transited, and effectively unreproducible on a
developer's machine.

**This is the only place in the v1 design where a Durable Object is used, and the narrow scope is
deliberate** — see ADR-04 for why the work engine is not one, and ADR-15 for the rule that decides
which store holds what.

#### Why not D1, which is the question this decision originally failed to ask

**Corrected 2026-08-13, after the owner read the diagram and could not derive the rule.** The
paragraphs above argue against **KV** and stop there. D1 was never evaluated for this job despite
already being in the design, and the omission mattered: a reader would reasonably conclude D1 had
been rejected on consistency grounds, **which is false.**

**D1 does not have KV's problem.** Reads go to the primary unless the Sessions API is used to opt
into a replica — see the verified-facts row on read replication — so **an ordinary D1 read is
strongly consistent** and would have satisfied the read-after-write requirement above perfectly
well. The consistency argument simply does not distinguish these two options.

**What actually decides it is lifecycle, not consistency:**

| | Durable Object | D1 |
|---|---|---|
| Cleanup of abandoned logins | An alarm per object, firing whether or not anything else in the system is healthy | A fourth table, plus a sweep the nightly cron must not forget |
| What the table would contain | No table exists | Rows whose every member is destined for deletion |
| Read-after-write across PoPs | Yes | Yes, on a primary read |
| Single-use semantics | Single-threaded actor; read-and-delete cannot race | `DELETE ... RETURNING` is also atomic — a wash |
| Latency | Object is placed near the first request, so the callback usually stays local | One hop to wherever the primary lives |

**The deciding argument is the second row.** A D1 `oauth_attempts` table would be a table whose
entire purpose is to be emptied, and its cleanup would become a second responsibility of the cron
that already carries the product's real work. The Durable Object needs no table and cleans itself,
which is fewer moving parts *in the failure case* rather than in the happy path.

**This is a close call and MUST be recorded as one.** If a future change makes the cron sweep
cheaper or makes a fourth table useful for something else, collapsing to a single store is a
reasonable reversal — the interface is two methods, `start` and `consume`, so the migration is
small. **What MUST NOT happen is a future reader inheriting this as settled on consistency
grounds.**

**The object MUST set an alarm on creation that calls `deleteAll()` on its storage after roughly
15 minutes.** This is not tidiness; it is the entire cleanup strategy. Durable Objects have no
TTL, so nothing expires on its own, and stored data is billed until it is removed. An object whose
storage has been deleted costs nothing, because an inactive object receiving no requests accrues
no duration charges either. Most login attempts are abandoned — the user closes the tab at
Flickr's authorize page — so this path is the common case, not the exception.

**The alarm handler MUST catch its own exceptions and reschedule.** Alarm delivery is
at-least-once with a bounded six retries; past that, a handler that never succeeds leaks its
storage forever with nothing to notice.

**It is one object per login attempt, NOT one per user, and the distinction MUST be preserved in
any diagram or document that names it.** At this point in the flow there is no user yet — the
person has not authorized, so FGA holds no identity for them; the key is the ephemeral
`oauth_token`. Calling it a per-user object would also read as adopting the per-user Durable
Object design that ADR-04 explicitly rejected, which is the opposite of what this is.

### ADR-03 — Per-user Flickr tokens are AES-GCM encrypted in D1

Each user's Flickr access token and token secret **MUST** be encrypted with AES-GCM and stored in
D1 beside that user's row. The token key **MUST** be held as a Worker secret. Per-user tokens
**MUST NOT** be stored in Cloudflare Secrets Store.

**Why not Secrets Store for tokens:** it holds 100 secrets per account, so one secret per user
puts a hard ceiling at 100 users — discovered only once the product has traction. This is the
same mistake the 2022 design made with one SSM parameter per user, and it is named here so it is
not reintroduced as an improvement.

**Four app-level secrets exist, and they do different jobs.** Naming them together in one place,
because "the secrets" as a single blob is what makes their roles hard to reason about:

| Secret | What it is for | Touched during |
|---|---|---|
| Flickr consumer key | Identifies FGA to Flickr as an application | Every Flickr call |
| Flickr consumer secret | Signs every OAuth 1.0a request, HMAC-SHA1 | Every Flickr call |
| **Token key (encryption)** | AES-GCM. Encrypts each user's Flickr access token before it is written to D1, and decrypts it when a Worker needs to act as that user | Storing the token after login; every group-add attempt |
| **Session key (signing)** | HMAC-SHA256. Signs the session cookie, and verifies it on the way back in | Minting the cookie after login; every authenticated request |

**The consumer key and secret together are the FGA Flickr API credentials** — the pair that marks a
call as coming from *this application*, and the name the diagram uses for them. They are
per-application and identical for every user. **The per-user half of a signed call is separate**:
the user's own access token, held AES-GCM encrypted in D1. Every authenticated Flickr request is
signed with both — app credentials and user token — which is why a leak of these two alone lets
someone impersonate the application but act as nobody.

**The session cookie is the only thing making a browser request trustworthy, and this key is the
only thing making the cookie unforgeable.** Nothing about a session is stored server-side — that
is the whole point of ADR-06 — so there is no session record to look up and no session table to
consult. The cookie carries the NSID in the clear alongside a signature; the Worker recomputes
that signature with this key and trusts the NSID only if they match. Lose the key and every
session breaks. Leak it and anyone can mint a cookie claiming to be any Flickr user.

**The token-encryption key and the session-signing key MUST be separate values.** Using one key
for both AES-GCM encryption and HMAC signing violates key separation, and the practical
consequence is sharper than the theoretical one: **rotating the session key logs everyone out and
costs nothing, while rotating the token-encryption key requires re-encrypting every stored Flickr
token.** Those two operations must stay independent — sharing a key makes the cheap one as
expensive as the dear one, which in practice means neither ever gets rotated.

**Why plain Worker secrets rather than Secrets Store:** four values is not a management problem,
and Secrets Store is in open beta while Worker secrets are GA. A beta dependency is not worth the
better management story when the values being protected are the key to every user's Flickr
credential and the key to every session. **Revisit once Secrets Store leaves beta.**

### ADR-04 — The v1 work engine is a nightly Cron Trigger over a D1 table

Pending requests **MUST** be rows in D1. A Cron Trigger **MUST** be the primary work engine for
v1. Per-user Durable Object alarms **MUST NOT** be introduced without meeting the promotion
criteria below.

**Why the boring design wins here.** An alarm-driven engine — one Durable Object per user,
self-scheduling to its own quota window — was designed first and rejected. Its advantages are
real but are **scale** advantages: no global scan to find due requests, and no burst of Flickr
traffic at 00:01 UTC. This project has no evidence it operates at a scale where either matters.
Against them, at the scale it actually has:

- **A `SELECT` beats a fan-out.** With one table, "what is stuck and why" is a query. With state
  sharded per user, the same question needs a fan-out or a separate aggregate kept correct by
  hand.
- **Failure history stays in one place.** These failures are intermittent and unfold over weeks.
  One cron run writes one log; ten thousand alarms write ten thousand fragments.
- **Durable Objects are the deepest lock-in Cloudflare offers.** Workers are close to portable
  Web-standard code. An application whose stateful core is shaped around Durable Objects is not.

**Plan cost is not, and never was, an argument in this decision.** The account now carries the
Workers Paid plan with a Durable Object allowance far larger than this project will use, and that
**MUST NOT** be read as reopening ADR-04. The case for the cron was debuggability, failure-history
locality, and lock-in — none of which a billing change touches.

**Promotion criteria.** Move to the alarm design when **any** of the following is *measured*, not
anticipated: the nightly scan takes long enough to threaten the Worker's limits; Flickr rate-limits
or rejects the concentrated midnight burst; or per-user scheduling becomes a product requirement
rather than an implementation preference.

### ADR-05 — The retry handler MUST be idempotent per (photo, group)

Before calling `flickr.groups.pools.add`, the handler **MUST** confirm from D1 that the pair has
not already succeeded.

**Why:** sweeps can overlap or be re-run, and a handler that throws part-way through leaves work
half-done. Without a guard, the next run submits a duplicate add. This is a correctness
requirement, not a defensive nicety. It survives unchanged if ADR-04 is ever promoted to alarms,
where at-least-once delivery makes it mandatory for a second reason.

**Flickr can be asked directly, and that answer beats the local one.** `flickr.photos.getAllContexts`
returns the pools a photo already belongs to, which is how the 2022 CLI did this check. The D1
guard is the cheap first pass and catches the common case without a network call; the remote check
is authoritative, because it also sees adds FGA did not make — the user adding the photo by hand,
or a second FGA session. A handler **SHOULD** consult it before an add it believes is the first
attempt, and **MUST** treat "already in the pool" as success rather than as an error.

### ADR-06 — Sessions are a backend-signed cookie

After the Flickr callback completes, the API Worker **SHOULD** mint a signed token carrying the
NSID and set it as an `HttpOnly; Secure; SameSite=Lax` cookie. It **MUST NOT** send the Flickr
token to the browser under any circumstances.

**The signing key is a Worker secret, and MUST be distinct from the token key** — see the secrets
table in ADR-03, which is also where the reason for keeping them separate lives.

**ADR-12 settles the cookie's remaining attributes**, once the UI and API became separate origins.
The short version: it is minted by `api.flickrgroupaddr.com`, stays **host-only** with no `Domain`
attribute, and `SameSite=Lax` above is still correct because same-site is not the same thing as
same-origin. The CORS contract that makes it work — including the reflected-`Origin` mistake that
would undo all of this — is recorded there.

**Why:** it is stateless, costs no D1 read per request, and uses HMAC-SHA256, which is already
proven in this runtime. Instant revocation is the thing given up, and it matters little here: the
Flickr token never leaves the server, and a user who wants to cut FGA off can revoke the
application at Flickr directly, which is both more thorough and outside FGA's control anyway.

**This is the softest decision in this document and the cheapest to reverse.** If revocation
becomes a real requirement, an opaque session row in D1 replaces it without touching anything
else.

### ADR-07 — Add failures are classified by Flickr's error code, and an unrecognized code is terminal

Every attempt **MUST** record the numeric error code Flickr returned. Only codes on the
**retryable allowlist** below **MAY** be attempted again. Every other outcome — including any code
not in this table, and any code added by Flickr in future — **MUST** be terminal.

| Code | Meaning | Class |
|---|---|---|
| *(success)* | Added to the pool | Terminal success |
| 3 | Photo already in pool | Terminal success — it is already there |
| **6** | **Added to the Pending Queue** | **Terminal. MUST NOT be retried. See below.** |
| **7** | **Already in the Pending Queue** | **Terminal. MUST NOT be retried.** |
| 5 | Photo limit reached | **Retryable** — this is the per-group, per-user throttle the project exists to wait out |
| 105 | Service currently unavailable | **Retryable** — transient |
| 106 | Write operation failed | **Retryable** — transient |
| 1 | Photo not found | Terminal failure — deleted, or no longer visible to us |
| 2 | Group not found | Terminal failure |
| 4 | Photo in maximum number of pools | Terminal failure — needs the user to remove it from another group |
| 8 | Content not allowed | Terminal failure — a policy rejection, not a queue |
| 10 | Maximum number of photos in group pool | Terminal failure — the pool is full |
| 11 | Group pool is disabled | Terminal failure |
| 98, 99 | Auth failure | Terminal for the request; **MUST** flag the user to re-link their Flickr account |

**Why the default is inverted from the 2022 implementation.** That version classified codes 5 and
6 explicitly and wrote everything else to a status string beginning `fail_`. Its retry query
selected every request with no recorded status matching `permstatus_%`, so **every unrecognized
code was retried nightly, forever**. That bucket held codes 1, 2, 4, 7, 8, 10, and 11 — every one
of them a permanent condition that could never succeed. **An unknown failure is the one most
likely to be permanent, and it was the one guaranteed to repeat.**

**Codes 6 and 7 are the moderator-protection rule, and they are absolute.** When a pool is
moderated, an add does not fail — it lands in a queue for a human volunteer to review. If that
person rejects the photo, the API says nothing; the photo is simply removed from the queue and
never appears in the pool. **A subsequent add for the same pair therefore does not look like a
retry to Flickr. It looks like a brand-new submission, and the moderator sees it again.** Nightly
retries against a rejected photo would make FGA an instrument for pestering the exact volunteers
whose goodwill the product depends on. Once a pair reaches a queue, FGA is done with it.

**FGA MUST NOT attempt to detect rejection by resubmitting.** `flickr.photos.getAllContexts` can
confirm whether a photo landed in a pool, and **MAY** be used to update what the user is shown.
But absence from the pool is ambiguous — still pending, or rejected — and no amount of resubmitting
resolves it. The correct behavior on ambiguity is to report the state honestly to the user and
stop.

### ADR-08 — Fail-polite: ambiguity about a person's decision resolves to "stop"

**Where an outcome could mean that a human declined, FGA MUST treat it as terminal** — even where
the same outcome could also mean something retryable. **This rule outranks every retry rule in
this document, including ADR-07's allowlist.** When they disagree, this one wins.

**Why this matters more than a retry policy usually would.** In the project owner's words,
2026-08-13:

> *"One thing I love about Flickr is the community aspect. Group mods are taking on a real burden
> in that job, and I do not want FGA getting a bad reputation in a community I love."*

**FGA is a convenience layer sitting on top of a community that runs on unpaid attention.** Group
moderators review submissions because they care about their pool, not because anyone pays them.
A tool that automates submissions into that queue is **spending someone else's volunteer time by
default**, and it earns its place only by spending less of it than the human would have. A tool
that becomes known for wasting moderator time gets banned from pools — and that ban would be the
community working correctly, not failing. **The reputational risk is not a side effect to manage;
it is the accurate signal that the tool has started taking more than it gives.**

**The engineering justification, which is the asymmetry rather than the courtesy:**

| Getting it wrong this way | Costs |
|---|---|
| Wrongly terminal | One request does not complete. The user sees why, and can resubmit deliberately. Bounded, visible, and paid by the person who chose to use FGA. |
| Wrongly retried | A volunteer moderator reviews and declines the same photo again, and again. Unbounded, invisible to the user, compounding nightly, and paid by someone who owes FGA nothing. |

**These costs are not comparable, so the decision is not a judgment call.** The failure mode that
lands on a stranger is the one to design against, and it is the one nobody will report — a
moderator has no way to tell FGA to stop, and no reason to believe the pestering is a bug rather
than a person.

**The user MUST be told, in plain language, when a request stopped for this reason** — that FGA
will not resubmit, and why. This is not politeness to the user; it is what stops the harm from
being recreated by hand. **A silent stop reads as a bug**, and a user who believes FGA is broken
will go and add the photo themselves, repeatedly, which is precisely the outcome this rule exists
to prevent. Explaining the refusal is load-bearing.

**Scope: this is not only about group moderation.** Any future capability that can put work in
front of a person who did not ask for it — a report, a message, a notification, an invitation —
falls under the same rule. If FGA cannot tell whether a person already said no, it MUST assume
they did.

### ADR-09 — Read latency is answered with D1 read replication, not an application cache

Reads **SHOULD** go through the D1 Sessions API with `read_replication.mode: auto`. Per-user API
responses **MUST NOT** be written to the shared edge cache (`caches.default`) unless the cache key
includes the user; `Cache-Control: private` is the default for anything behind a session.

**Cost is not the reason to cache here.** D1 bills reads at $0.001 per million rows. At any scale
this project plausibly reaches, the query volume is free, and a cache built to save money would be
saving nothing.

**Latency is the real cost, and it comes from a fact already recorded in ADR-02's neighbourhood:
the D1 primary lives in one location, outside the edge PoP.** A user in Sydney reaches a Worker in
Sydney in a few milliseconds, and that Worker then crosses the planet to the primary. The
anycast win is spent on the first query.

**Read replication fixes that at the source.** Replicas exist in every region at no extra cost,
and the Sessions API provides sequential consistency **including read-your-own-writes**. That last
property is the one that matters: an application cache would have to be invalidated the instant a
user submits a request, because a user who adds a photo and does not see it appear concludes the
product is broken. Cloudflare has solved the hard half of the problem already; reimplementing it
in cache-invalidation logic would be strictly worse.

**The premise that state changes only once a day is true of the nightly sweep and false of the
user.** The cron mutates each `(photo, group)` row at most daily, but a person can submit at any
moment, and their own change is the one they watch for. Any caching scheme MUST treat the user's
own mutation as the common case rather than the edge case.

### The stale-read failure, and where it will actually come from

**If a write appears not to have persisted, the first suspect is bookmark propagation, not
Cloudflare's replication.** Replication rarely breaks. Bookmarks get dropped constantly, because
doing it right requires deliberate plumbing that is easy to omit and produces no error when
omitted.

`withSession()` guarantees read-your-own-writes **within a session**. A session is identified by a
**bookmark** — an opaque token D1 returns after a query, marking how far along the database state
that session has seen. Pass it into the next `withSession()` call and D1 guarantees the replica
serving you is at least that current, waiting or falling back to the primary if it is not. Fail to
pass it and the next request starts unconstrained, free to be served by any replica, including one
that has not yet received the write made moments earlier.

**FGA runs over HTTP, so consecutive requests are different Worker invocations with no shared
memory.** A user submitting a request and then loading their dashboard is two invocations. Unless
the bookmark from the write travels to the read — in a cookie, a response header the client echoes
back, or similar — **the dashboard read is unconstrained and may legitimately miss the row that was
just written.** Nothing is broken. The guarantee simply was not asked for.

| Symptom | Likely cause |
|---|---|
| User adds a request, dashboard does not show it | Bookmark not carried from the write response into the next read |
| Intermittent, and worse for distant users | Same — a nearby replica lags the primary by more than the round trip |
| Reproducible on every read, all users | Not replication. Look at the write path. |

**So: the write response MUST return its bookmark, and the client MUST send it back on subsequent
reads.** This is cheap to build in and unpleasant to retrofit, because by then the symptom has been
misdiagnosed at least once as a caching bug or a phantom write.

#### This MUST be made unreachable rather than remembered

A rule of the form "remember to carry the bookmark" fails the moment anyone writes a query without
thinking about it, and it fails **silently** — no error, no warning, just an occasional missing
row that reproduces for nobody. A convention is the wrong instrument for a failure mode with no
symptom at the point of the mistake.

**The D1 binding MUST NOT be reachable from request-handling code.** All database access **MUST**
go through a single accessor that takes the incoming `Request`, extracts the bookmark, opens the
session, and hands back a session-scoped handle. Writing a query that skips the bookmark then
stops being a thing a person could forget, because there is no un-sessioned handle to reach for.

**The response layer MUST attach the resulting bookmark on the way out**, in the same one place, so
returning it is not a per-endpoint decision either.

Both halves belong in one module, and **a build check SHOULD assert that the raw binding name
appears nowhere outside it.** That converts the whole class of bug from a runtime surprise into a
failed build — the outcome this project prefers wherever it is available.

**Recorded before any code exists, deliberately.** Wrapping the binding costs nothing today and is
a refactor across every handler once the direct calls are written.

**Where a cache still earns its place:** group metadata — name, icon, rules — is identical for
every user and changes rarely, so it **MAY** be held in the shared edge cache with a normal TTL.
That is genuinely shared data, which is exactly what a shared cache is for.

**The trap this decision exists to prevent** is caching a per-user response in `caches.default`
without a per-user key, which serves one member's pending list to another. It is an easy mistake,
it is silent, and on a product whose whole security model is a signed cookie identifying a Flickr
account, it would be the worst bug in the system.

**Worked against real rates, there is nothing for a read cache to save.** At 1,000 users holding
100 pending requests each — 100,000 rows — the nightly sweep and the dashboard together read on
the order of 6 million rows a month, against 25 **billion** included. That is 0.02% of the
allowance. A read cache would be optimizing four orders of magnitude below the point where cost
becomes visible.

### The cost lever is write volume, and it is a schema decision

**Writes cost 1,000× what reads cost — $1.00 per million against $0.001 — and the included
allowance is 500× smaller.** That inverts the usual instinct. Reads are the thing you would
naturally try to reduce, and they are free; writes are the thing nobody thinks about, and they are
the entire bill.

The driver is **how much gets written per attempt**. Recording one attempt row for every pending
request every night, at 100,000 pending rows, is 3 million writes a month — 6% of the included
50 million. The same design at 1 million pending rows is 30 million writes a month, 60% of the
allowance, and the next step past that is a real invoice.

**ADR-10 has since capped this, and the cap is structural rather than a mitigation.** Because only
the head of each queue is ever attempted, attempt records scale with the number of active
`(user, group)` queues rather than with the number of pending requests. The 3-million-writes figure
above assumed every pending row is touched nightly, which ADR-10 makes impossible. See "The queue
view" for where that interacts with what the interface promises.

**Anyone extending the schema MUST check this before adding a per-attempt write.** The obvious
mitigations — write only when the outcome *changes* rather than on every attempt, or roll several
nights of no-change attempts into one row — are cheap to design in and awkward to retrofit once a
history table has a shape people depend on. **This is recorded now because it is obvious today and
invisible later**, when someone reasonably adds "just one more column, written every run" to a
table that is already the most expensive thing in the system.

#### Implementation status, 2026-08-13: the cache half is done and the replication half is not

**Asked directly, and worth recording because the honest answer is "no".** Neither
`read_replication.mode: auto` nor a single `withSession()` call exists in the codebase. **ADR-09
predicted this exact omission** — it says bookmarks "get dropped constantly, because doing it right
requires deliberate plumbing that is easy to omit and produces no error when omitted" — and then
the implementation omitted the plumbing and the mode alongside it.

**The current state is correct, merely not fast.** With replication off, every read goes to the
primary and is strongly consistent, which is what ADR-15 relies on. **Nothing is broken and nothing
is stale.**

**Enabling the mode alone is inert, and this is the part that misleads.** A plain `db.prepare()`
read hits the primary whether or not replication is on — replicas are reached only through the
Sessions API. So `read_replication.mode: auto` is not a switch that makes reads faster; **the
bookmark plumbing is the entire feature**, and turning the mode on without it buys nothing while
looking like progress.

**Three reads MUST NOT be served from an unconstrained replica when this is built:**

| Read | What a stale answer does |
|---|---|
| `pendingCount` before ADR-10's immediate attempt | Returns 1 when two are pending, so a new request jumps a queue that had someone waiting |
| `pairReachedAModerator` before ADR-11's warning | Misses a recent moderation record and submits to a volunteer with no warning shown |
| A user's own queue view after submitting or withdrawing | They do not see their own change and conclude the product is broken — ADR-09's own stated case |

**The first two are correctness, not latency**, and they are why this is not a configuration change.
The third is what bookmarks exist for.

**Recommendation: leave it off until there is a user outside ENAM.** The database is in ENAM and so
is the only user, so replicas would currently shorten a journey nobody makes, in exchange for
plumbing that touches the two invariants above. **Revisit when a non-ENAM user appears** — that is
the trigger, and it is a real one rather than a way of saying later.

**The cache half of this ADR was implemented the same day it was checked.** Every `/v001/*`
response now carries `Cache-Control: private, no-store`, set by a middleware registered **before**
`requireSession` — a rejecting middleware never calls `next()`, so registering it after would have
left precisely the 401s uncovered. `no-store` goes beyond ADR-09's `private` deliberately: the queue
view changes the moment a user withdraws something, and a browser reusing its own cached copy would
show the request still sitting there. **Nothing was leaking before** — Cloudflare does not cache a
Worker's JSON by default — **and it becomes real the day somebody adds a Cache Rule**, which is
exactly the change made without auditing what is already behind a session.

### ADR-10 — Requests are FIFO per (user, group), and the queue is never jumped

**This governs ordering the way ADR-08 governs ambiguity, and it yields to ADR-08 where the two
ever meet.** Where a design choice would let a later request be attempted before an earlier one in
the same queue, that choice is wrong, however much faster or more convenient it looks.

They do not currently conflict, and it is worth saying why rather than leaving it to be
rediscovered: a request that fails terminally under ADR-08 **resolves** and leaves the queue, so
being polite to a moderator never holds the queue up. If a future change makes a fail-polite
outcome something a request can sit in rather than exit through, that change **MUST** resolve in
ADR-08's favor, and this paragraph is wrong and needs rewriting.

Every add request **MUST** be appended to a queue keyed by `(user, group)` and **MUST** be
attempted in the order it was appended. **No request MAY be attempted while an earlier unresolved
request sits ahead of it in the same queue.** A request leaves the queue only by resolving —
succeeding, or failing terminally under ADR-07 and ADR-08.

**The API Worker MUST attempt a new request immediately if, and only if, it is the sole unresolved
request in its queue.** Otherwise it **MUST** be appended and left for the nightly sweep.

**Why the condition is exactly "the queue is empty", and not "try it and see":** a greedy attempt
can succeed for the wrong reason. Groups change their add throttling dynamically, and an attempt
made now may roll into a fresh day's allowance and consume a slot that belonged to a request that
had been waiting since last week. The greedy request wins precisely because it arrived last. **A
queue of length one is the only case where an immediate attempt cannot take anything from
anybody** — which is what makes the instant path safe rather than merely usually-safe.

The owner's framing, recorded because it is the reason and not decoration: *"Groups can change add
throttling dynamically and I don't ever want someone jumping the queue — I spent enough time in the
UK to respect the queue!"*

**The nightly sweep MUST walk each queue from the head, and MUST stop at the first retryable
failure.**

| Outcome at the head of a queue | What the sweep does next |
|---|---|
| Succeeded | Head resolves. The next request becomes head, and the sweep **MAY** continue in this queue. |
| Failed terminally (ADR-07, ADR-08) | Head resolves. The next request becomes head, and the sweep **MAY** continue in this queue. |
| Failed retryably — the daily cap | **This queue is done for the night.** The sweep **MUST NOT** attempt anything behind it. |

**That last row is the whole decision in miniature, and it is the one a future optimization will
attack.** When the head is blocked by a group's daily cap, everything behind it in that queue is
blocked by the same cap — so trying the next one is not merely wasted, it is the queue-jump this
decision exists to forbid. It reads like an efficiency win because it saves nothing and costs an
API call; it is actually a correctness rule wearing an efficiency costume.

**The FIFO guarantee is a within-queue property and nothing more.** Queues keyed by different
`(user, group)` tuples are fully independent — ADR-07 classifies the only retryable condition,
code **5**, as a per-group *per-user* throttle — so the sweep **MAY** process queues in any order
or concurrently without weakening this decision. The argument is in "The queue view", where it also
settles how the interface is scoped.

#### Three mechanisms this rule needs, each of which fails silently if missed

**The append and the "am I alone?" test MUST be atomic.** Two submissions to the same
`(user, group)` arriving together can each read an empty queue, each append, each conclude it is
alone, and both attempt. That is the forbidden queue-jump arriving by race rather than by design,
and it will be rare enough to survive testing.

**The queue-position read MUST NOT be served by a read replica.** Determining position straight
after appending is a read-your-own-writes operation, and ADR-09 records that replicas are
eventually consistent. A stale replica returns a count of zero, the Worker concludes the queue is
empty, and it authorizes an immediate attempt in front of a queue that is not empty. **This is the
exact trap ADR-09's binding wrapper exists to make unreachable** — it must be unreachable here too.

**Wall-clock time MUST NOT be the ordering key.** Timestamps collide at the resolution they are
stored, and clocks move backwards. Order **MUST** come from a monotonic insert sequence, and rows
**SHOULD** be resolved in place rather than deleted, so the sequence stays stable and the history
survives.

**What this costs, stated honestly:** a user's second and later submissions to the same group get
no instant feedback, even when the group has plenty of headroom that minute. That is the price of
never starving the request that was there first, and it is worth paying. The interface **SHOULD**
say where in the queue a request sits, so the wait is visible rather than mysterious.

### ADR-11 — Every `(photo, group)` pair that reached a moderator is remembered permanently

When an add resolves with code **6** or **7**, FGA **MUST** record the `(photo, group)` pair in a
permanent table, and that record **MUST** outlive the request row, the queue, and any later cleanup.
When a user submits a request for a pair already in that table, the interface **MUST** warn them
prominently before the request is queued.

**FGA MUST NOT block the resubmission.** The warning informs; the person decides. Owner's framing,
2026-08-13: *"We won't hard block them but are giving them the data to be a good community member
and say 'oh shit thank you yeah cancel let's not try again'."*

**Why not block, given ADR-08 usually resolves ambiguity by stopping:** because the ambiguity here
belongs to the user, not to FGA. They may have re-tagged the photo, the group's rules may have
changed, or they may have spoken to a moderator. **A block would be FGA overriding a human's
judgment about their own photo, which is the same disrespect ADR-08 exists to prevent, pointed the
other way.** FGA's obligation is to make sure the decision is *informed*, not to make it.

#### Name it for what is known, not what is suspected

The table records that a request **reached a human's queue**, which code 6 states outright. It does
not record a rejection, because **no such signal exists** — see the verified-facts row on moderator
decisions being invisible to the API. Naming it for the arrival rather than the suspicion keeps the
schema honest, keeps the user-facing copy honest, and stays correct in the common case where the
moderator in fact approved.

**What goes in, and nothing else:**

| Outcome | Recorded? |
|---|---|
| **6** — Added to the Pending Queue | **Yes.** The request is demonstrably in front of a person. |
| **7** — Already in the Pending Queue | **Yes.** Same, and it also confirms an earlier one is still undecided. |
| **8** — Content not allowed | No. A policy rejection, not a queue — nobody is reviewing it. |
| Any other terminal failure, including unrecognized codes | No. ADR-07 stops retrying them, but nothing suggests a human saw them, and a warning that fires on ordinary errors is a warning nobody reads. |

**Record the code alongside the pair**, so the interface can distinguish these cases later without
a schema change. The cost is one integer.

#### Current pool membership resolves most of the ambiguity, after the fact

**Before warning, the interface SHOULD check whether the photo is in the pool now.** ADR-05 already
requires `flickr.photos.getAllContexts` for idempotency, and the same call answers this: **a pair in
this table whose photo is now in the pool was approved, not rejected.** The record stays — it is a
permanent log of what reached a moderator — but the warning **MUST NOT** fire, because re-adding an
approved photo pesters nobody and a false alarm here spends exactly the credibility the real warning
needs.

**This is the one way the invisible decision becomes visible, and it only works in one direction.**
Presence in the pool proves approval. Absence still cannot separate *rejected* from *never decided*,
so the honest warning is about what is known — this reached a moderator and did not land — rather
than about a rejection FGA cannot see.

**A resubmission that returns code 7 is itself information:** the original is still sitting in the
queue undecided, which means nobody has been pestered and nobody has said no. The interface
**SHOULD** say so rather than repeating the original warning.

#### Two smaller obligations

**Reads MUST be scoped to the requesting user's own photos.** Flickr photo IDs are global and carry
their owner, so `(photo, group)` needs no user column — but that also means an unscoped lookup would
answer questions about other people's moderation history. Same class of leak as the queue-view
scoping above, and it needs closing the same way.

**The cost is negligible and worth stating so nobody optimizes it away.** One row written per pair
that ever reaches a moderator, and one indexed read on submission. Against ADR-09's write budget it
does not register.

### ADR-12 — The UI and the API are separate origins, and the session cookie stays host-only

The JAMstack UI is served from `https://flickrgroupaddr.com` and the API Worker answers on
`https://api.flickrgroupaddr.com`. Decided by the owner, 2026-08-13. They are **same-site** — one
registrable domain — but **different origins**, and every requirement below follows from that one
distinction.

**The session cookie MUST NOT carry a `Domain` attribute.** The API Worker is the OAuth callback
endpoint and therefore the thing that mints the session, so the cookie is set by
`api.flickrgroupaddr.com` and is sent back to `api.flickrgroupaddr.com` as a host-only cookie. It
never needs to reach the apex, and giving it a `Domain` would widen it to every subdomain that will
ever exist for no benefit. **Host-only is both the correct and the narrower choice, and it is easy
to get wrong in the safe-looking direction.**

**`SameSite=Lax` from ADR-06 remains correct, because same-site is not same-origin.** A `fetch` from
the UI to the API shares the registrable domain, so it is a same-site request and a `Lax` cookie
rides along. No change is needed there, and `SameSite=None` **MUST NOT** be adopted — it would be
strictly worse and would hand back the CSRF protection described below. ADR-02 keeps OAuth state in
a Durable Object rather than a cookie, so nothing needs to be read during Flickr's cross-site
redirect back, which is the one place `Lax` could otherwise have bitten.

| Cookie attribute | Value | Why |
|---|---|---|
| Name | `__Host-fga_session` | The prefix makes the four rows below browser-enforced rather than merely intended. |
| `HttpOnly` | set | Script **MUST NOT** be able to read the session. ADR-06. |
| `Secure` | set | HTTPS only. Required by the `__Host-` prefix. |
| `SameSite` | `Lax` | Same-site covers UI-to-API; also the CSRF control. |
| `Domain` | **absent** | Host-only to `api.flickrgroupaddr.com`. Required by the `__Host-` prefix. |
| `Path` | `/` | Required by the `__Host-` prefix. |

#### The `__Host-` prefix, added 2026-08-13, and why host-only was not already enough

**The cookie name MUST carry the `__Host-` prefix.** It is a contract the browser enforces: a cookie
so named is rejected unless it is `Secure`, has `Path=/`, and carries no `Domain`. ADR-12 already
required all three, so **this costs nothing and asks the browser to enforce what the code already
intended.**

**The gap it closes is one host-only does not.** Host-only controls where *our* cookie goes. It does
not stop somebody else's cookie of the same name arriving: anything able to set cookies for the
parent domain — a sibling subdomain, an XSS anywhere under it, a stray CNAME on a hostname nobody
is watching — can set `Domain=flickrgroupaddr.com; fga_session=<attacker value>`, and the browser
will send it to the API. **`Domain` is not transmitted with a cookie, so the API cannot tell the two
apart**, which is what makes this session fixation rather than a nuisance. The prefix is the only
mechanism that refuses the shadowing cookie at the browser.

**It MUST be applied through the cookie library's `prefix: "host"` option rather than by writing
`__Host-` into the name.** Hono prepends the prefix and then forces `Path=/`, `Secure` and
`domain: undefined` *after* spreading the caller's options, so the three attributes the prefix
depends on cannot be broken from the call site. Hand-written, the name and the attributes are two
facts that must agree, and when they stop agreeing **the browser silently drops the cookie** — the
failure is a login that appears to succeed and produces no session.

**One-time effect on deploy: every existing session ends**, because the Worker now looks for a
cookie name no browser has yet. Users log in again. There is no migration worth writing for a
thirty-day cookie.

#### The defect this ADR was hiding, and it is a testing lesson more than a security one

**The attributes above were correct in this document and specified in a function the Worker never
called.** `sessionCookieAttributes()` returned a hardcoded string; the live cookie was set from a
second, separate literal in the callback route, and the logout route held a third copy that had
**lost `HttpOnly` entirely**. Five tests asserted against the string helper.

**Those tests could not have failed.** The helper took no arguments and returned a constant, so
their result was a function of one string literal and was mathematically independent of the cookie
the Worker actually issued. They would have passed against a cookie with no attributes at all.

**The rule this establishes: a test of an HTTP-level property MUST assert on the response.** Not on
a helper that describes the response, and not on a constant the production path does not read. The
replacement drives a full login against a stubbed Flickr and reads the real `Set-Cookie` header
— which required stubbing Flickr's two OAuth endpoints, previously unreachable in tests, and **that
unreachability is why the gap existed for as long as it did.** The new tests were verified by
mutation: changing `SameSite` and `Max-Age` at the source made exactly the expected assertions fail.

**The attributes now live in one place, `SESSION_COOKIE_OPTIONS` in `src/session.ts`**, used by the
set, read and clear paths alike. A single lifetime constant drives both the token's `exp` and the
cookie's `Max-Age`; they were separate literals, and **a token outliving its cookie is the dangerous
direction** — the credential stays valid after the browser stops presenting it.

#### The CORS contract, stated exactly, because the shortcut here is catastrophic

Every API response **MUST** carry `Access-Control-Allow-Origin: https://flickrgroupaddr.com` and
`Access-Control-Allow-Credentials: true`, plus `Vary: Origin` so no cache can serve one origin's
CORS decision to another. Preflight responses **MUST** additionally answer with the permitted
methods and headers, and **SHOULD** set `Access-Control-Max-Age` so the browser stops asking.

**`Access-Control-Allow-Origin: *` is not an option** — the browser refuses a wildcard whenever
credentials are included, so the allowed origin has to be written out.

**The Worker MUST NOT reflect the request's `Origin` header back in `Access-Control-Allow-Origin`.**
This is the shortcut that makes the error go away during development, and combined with
`Allow-Credentials: true` it means **any website on the internet can make authenticated calls as a
logged-in FGA user** and read the responses. The permitted origin **MUST** be compared against a
fixed allowlist and the header emitted only on a match. It is recorded here in this much detail
because it is the single highest-severity mistake available in this design, it is a two-line
mistake, and it looks exactly like the fix.

**Every browser call to the API MUST set `credentials: 'include'`.** The `fetch` default is
`same-origin`, which silently omits the cookie across origins — the failure is a well-formed
request that authenticates as nobody, which reads as a session bug rather than a client bug.

**`SameSite=Lax` is doing the CSRF work here**, and no token scheme is required while it holds. If a
future change ever loosens it, CSRF tokens become mandatory in the same commit, not afterwards.

**What this costs, honestly:** a same-origin design — the API on `flickrgroupaddr.com/api/*` —
would need none of this. The split buys clean routing and independent deploys, and the price is the
contract above. That is a fair trade only while the contract is actually written down, which is why
it is here rather than left to the implementation.

### The queue view — where ADR-08 becomes visible

Not yet an ADR, because the scoping is undecided. Recorded now because the requirement is settled
and it constrains the schema.

**The web app MUST show a user the state of their outstanding requests.** ADR-08's standing order
is that where a person may have declined, FGA stops *and the user can find out*. Every decision in
this document implements the stopping; **this view is the only place the second half is delivered**,
and without it fail-polite is a promise the product never keeps.

Per request, the view **SHOULD** carry: when it was queued, how long it has been queued, when it
was last attempted, and what came back. Owner's list, 2026-08-13.

**Add the request's position in its queue.** ADR-10 makes ordering the thing that determines when a
request will be tried, so position is the only field that describes the *future*. "Queued 6 days
ago" invites the question; "third in line for this group" answers it.

**A terminally-resolved request MUST NOT be presented as pending.** A code **6** request is in the
group's own moderation queue, FGA is deliberately finished with it, and per the verified-facts table
a moderator's decision is invisible to the API forever. Listing it beside requests genuinely waiting
for tonight's sweep misrepresents FGA's behavior at precisely the point ADR-08 exists to make
honest. Terminal outcomes **MUST** read as closed, and **SHOULD** say why in plain language;
the numeric code **MAY** be shown alongside, never instead.

#### Two consequences for the schema, both cheap if taken now

**"Last attempted" is usually "not yet", and that is correct.** Under ADR-10 only the head of a
queue is attempted, so a request sitting fifth in line has never been tried and may not be for a
week. The view **MUST NOT** imply otherwise — an absent attempt is information, not a gap.

**This bounds the write volume ADR-09 warns about.** That section's worst case is a per-attempt
write for every pending request: 3 million writes a month at 100,000 pending rows. Because ADR-10
attempts only queue heads, **attempt records scale with the number of active `(user, group)` queues,
not with the number of pending requests** — one per queue per night, whether that queue holds one
photo or four hundred. The expensive version of this feature is the one ADR-10 already prevents.

**Durations MUST be computed at render from stored timestamps.** Storing "8 hours ago" in any form
means updating every pending row on a schedule, which reinvents exactly the per-row nightly write
the paragraph above avoids.

#### Scoping — decided: the `(user, group)` tuple

**The real view is scoped to the `(user, group)` tuple, which is ADR-10's queue key exactly.**
Decided by the owner, 2026-08-13. Within that scope position means something and a capped head
explains every row beneath it at a glance.

**Saying "per group" is wrong and the difference is not pedantic.** Three hundred users with
requests queued for Group G hold three hundred separate queues, not one shared queue with three
hundred participants. From a signed-in user's own screen the distinction is invisible — their user
dimension is fixed to themselves, so their view looks per-group — but a future reader who takes
"per group" literally builds a global queue for Group G, and that view is both meaningless and a
disclosure of other people's activity that ADR-01 exists to avoid holding in the first place.

**The queues are genuinely disjoint, and ADR-07 is what guarantees it.** The sole retryable
condition in that table is code **5**, the per-group *per-user* throttle. The group-wide conditions
— **10**, pool full, and **11**, pool disabled — are classified terminal, so they resolve requests
out of a queue rather than stalling it. **Nothing one user's queue does can block another's**, even
for the same group.

Two things follow, both worth having written down before someone needs them:

- **The nightly sweep is embarrassingly parallel across queues.** No queue's progress depends on
  any other's, so queues **MAY** be processed in any order, or concurrently, without weakening
  ADR-10. The FIFO guarantee is a within-queue property and nothing more.
- **A pool filling up or being disabled will fail many users' requests on the same night**, and
  those failures are independent and terminal rather than a shared blockage. Support-wise it will
  *look* like a systemic outage. It is not one, and the queue view should make that legible.

**Per user remains a useful roll-up** for "what is the state of my stuff", and it **MUST** group by
group rather than presenting one flat list sorted by submission time. A flat list looks like a
single queue when there are many, which makes correct FIFO behavior read as a bug the first time a
later request lands ahead of an earlier one in a different group.

### ADR-13 — The Workers are written in TypeScript, on the current stable toolchain

Every Worker in this project — the API Worker, the retry Worker, and any Durable Object class —
**MUST** be written in TypeScript with `strict` enabled. Decided by the owner, 2026-08-13, after
Rust and Python were each argued for and rejected.

**The deciding evidence was maintenance velocity, not taste.** Cloudflare's documentation describes
JavaScript, TypeScript, Python, and Rust as having first-class support. Commit activity over the
thirteen weeks to 2026-08-13 says otherwise:

| Repository | What it is | Commits, 13 weeks |
|---|---|---|
| `cloudflare/workerd` | The runtime itself | 1,360 |
| `cloudflare/workers-sdk` | Wrangler and the JavaScript toolchain | 649 |
| `cloudflare/workers-rs` | The Rust bindings | 9 |

**TypeScript compiles to what the runtime already executes.** `workerd` is a V8 isolate, so there is
no translation layer between the source and the thing that runs — no WebAssembly boundary, no
interpreter to instantiate, and nothing that can bit-rot independently of the runtime. Cold start
stays sub-millisecond, and the Durable Object and D1 surfaces are exercised by essentially every
Worker in existence rather than by a minority dialect.

**Rust was rejected on maintenance, not on merit.** `workers-rs` is at `v0.8.5`, released 2026-06-12,
still pre-1.0, with 184 open issues and the nine commits above. Its own README warns of "rough
edges, unimplemented APIs, and potential bugs." Everything in it must compile to
`wasm32-unknown-unknown`, which excludes `tokio` and any crate that does not target WebAssembly, and
release builds need `lto`, `strip`, and `codegen-units = 1` to stay inside the bundle limit.
**Against that, Rust's actual advantages do not apply to this workload.** FGA signs an HTTP request,
calls an API, and writes a database row; there is no CPU-bound work anywhere in it, so zero-cost
abstraction and manual memory control buy nothing. The stateful core of this design is Durable
Objects, which is precisely the least-exercised part of that crate.

**Python was rejected on maturity, and the argument is one this document already made.** Python
Workers are in **open beta** and require the `python_workers` compatibility flag. ADR-03 rejected
Cloudflare Secrets Store for holding four values on the grounds that "a beta dependency is not worth
the better management story." **A beta runtime for the entire codebase cannot pass a bar that a beta
secret store failed.** The 2022 code in the old repos was Python, which is precedent and therefore
the weakest argument available here. Python's runtime lives inside `workerd`, so it is being
actively built; **revisit this decision if Python Workers reach general availability.**

#### The version policy, because "LTS" does not exist here

**TypeScript has no LTS channel.** It ships roughly quarterly with no long-term-support line, so
"latest LTS TypeScript" has no referent. The owner's intent — current, expert, not experimental — is
recorded instead as this rule:

**The project MUST track the current stable release of each tool, and MUST NOT adopt a `beta`,
`rc`, `next`, or `dev` tag.** Where a stable release breaks a tool the project depends on, the
project **MUST** either drop that tool or hold back, and **MUST** record which it chose and why.

| Tool | Pinned at | Note |
|---|---|---|
| TypeScript | `7.0.2` | The Go-native compiler. Stable since 2026-07-08. |
| Node.js | `24.x` (Krypton) | Active LTS. Build-time only; it is not the runtime. |
| Wrangler | `4.123.0` | |
| Vitest | `4.1.10` | With `@cloudflare/vitest-pool-workers` `0.21.3`. |
| Biome | `2.5.8` | Lint and format. See the tradeoff below. |

**TypeScript 7 costs the project `typescript-eslint`, and that is an accepted trade.** The Go-native
compiler ships without a stable programmatic API until 7.1, so tools built on the compiler API
cannot yet consume it — `typescript-eslint@8.67.0` declares a peer range of `>=4.8.4 <6.1.0`, which
excludes 7.x outright. **The project therefore uses Biome, which parses TypeScript itself and has no
compiler-API dependency**, making the incompatibility irrelevant rather than merely tolerated. The
alternative was holding TypeScript at `6.0.3` to keep ESLint; that was rejected because type
checking via `tsc --noEmit` is the safety net that matters here and it is unaffected either way.
**If Biome proves insufficient, the correct response is to hold TypeScript at 6.0.3 in the same
commit — not to run unlinted.**

#### What "modern" means concretely, so it is checkable rather than a vibe

**These are the idioms a 2026 Workers expert would expect, and each has a dated-looking alternative
that still works.** Recorded because "write it in a modern style" is unenforceable and this is not.

- **Types MUST be generated with `wrangler types`**, producing `worker-configuration.d.ts` from the
  project's own compatibility date and flags. Hand-importing `@cloudflare/workers-types` is the
  dated form; Cloudflare now recommends it only for libraries and shared packages.
- **Durable Object classes MUST extend `DurableObject` from `cloudflare:workers`** and expose their
  operations as **RPC methods**. The older pattern — a `fetch` handler on the object parsing a
  synthetic URL to dispatch internally — is what this replaces, and Cloudflare directs all new
  projects past it.
- **The entrypoint MUST be an ES module** using `satisfies ExportedHandler<Env>`. Service-worker
  syntax and `addEventListener("fetch", ...)` **MUST NOT** appear anywhere.
- **Configuration MUST be `wrangler.jsonc`**, not `wrangler.toml`.
- **`strict` MUST be on, together with `noUncheckedIndexedAccess`.** `any` **MUST NOT** be used to
  silence an error; `unknown` plus a narrowing check is the expected form.
- **Tests MUST run inside `workerd`** via `@cloudflare/vitest-pool-workers`, against real bindings.
  Hand-mocked D1 and Durable Object stubs test the mock rather than the Worker.
- **Platform primitives MUST be used directly** — WebCrypto, `AbortSignal`, `structuredClone`, and
  top-level await. Polyfills and `nodejs_compat` **SHOULD** be avoided unless a specific dependency
  forces it, and the forcing dependency named when it does.
- **`enum` SHOULD be avoided** in favor of union types or `as const` objects. **CommonJS `require`
  and `namespace` MUST NOT appear.**

**What this decision does not settle:** the OAuth 1.0a signing helper is a pure function — percent-
encode, sort, concatenate, sign — with no platform dependency, and it would be equally correct in
any of the three languages. The language choice is about the other ninety percent, which touches
bindings continuously.

### ADR-14 — Integrate when feasible, innovate otherwise

**Standing order from the owner, 2026-08-13, in his words: *"integrate when feasible, innovate
otherwise. If we can take stable, modern, well tested deps rather than write our own code, that's
preferable 99% of the time. I just hate reinventing wheels."*** This decision governs every
subsequent choice between adding a dependency and writing the code.

**Where a maintained dependency exists that runs in this runtime and does the job, the project
SHOULD take it.** Writing an equivalent by hand **MUST** be justified against the tests below, and
the justification **MUST** be recorded where the code lives.

**The reason is not effort, it is defect count.** A dependency with real adoption has been run
against inputs this project will never think to try, by people who hit the edge cases first. Hand-
written code starts at zero of that. The owner's framing is about wheels; the operative version is
that **our version starts less correct and stays less correct**, because nobody else is finding bugs
in it.

#### The four tests that permit writing our own

**A candidate must fail one of these for hand-written code to be the right answer.** Distaste for a
dependency is not on the list.

| Test | Meaning |
|---|---|
| **Does it run here?** | Workers are not Node. A package needing the filesystem, `http`/`https`, or Node built-ins does not run without `nodejs_compat`, which ADR-13 says to avoid unless a dependency forces it. |
| **Is the platform already doing it?** | WebCrypto is native and does HMAC-SHA1, HMAC-SHA256, and AES-GCM. Taking a crypto library on top of it adds bundle, adds supply-chain surface, and removes an audited implementation. |
| **Is it maintained?** | A package last published years ago is not "stable", it is unmaintained. The distinction matters most for anything security-adjacent. |
| **Is the spec short, exact, and covered by published vectors?** | Where correctness can be *proven* against a standards body's own test data, the usual argument for a dependency — other people found the bugs — is replaced by something stronger. |

**Supply-chain surface is a reason to choose dependencies carefully, and MUST NOT be read as a
reason to avoid them.** This project decrypts users' Flickr tokens, so a compromised package in the
production bundle is the worst outcome available. **The mitigation is preferring packages with no
transitive dependencies of their own**, pinning exact versions, and keeping the production bundle
small — not hand-writing more code, which trades a small audited risk for a large unaudited one.

#### The worked example: OAuth 1.0a signing is the 1%

**Surveyed 2026-08-13, before writing the signer, specifically to avoid reinventing a wheel.**
Recorded in full because "we checked and there wasn't one" is worthless without the evidence:

| Candidate | Last published | Why it fails |
|---|---|---|
| `oauth-1.0a@2.2.6` | 2019 | Its `hash_function` is **synchronous**; WebCrypto's `crypto.subtle.sign()` returns a Promise. Using it means `nodejs_compat` and `node:crypto` purely to satisfy the library's shape. |
| `oauth-signature@1.5.0` | 2017 | Depends on `crypto-js@~3.1.9-1`, superseded and no longer the right way to do crypto in a browser-class runtime. |
| `oauth@0.10.2` | 2025 | Node-only. Built on the `http`/`https` modules; does not run in a Worker. |
| `node-oauth1@1.3.0` | 2020 | Unmaintained. |
| `axios-oauth-1.0a@0.4.1` | 2026 | Actively maintained, but it is an **axios interceptor**. `fetch` is native here; adding an HTTP client to get a signer inverts the dependency. |

**So FGA writes its own OAuth 1.0a signer, and it fails three of the four tests at once** — nothing
maintained runs here, the crypto underneath it is already native, and RFC 5849 §3.4 ships worked
example vectors that make the result provable rather than merely tested. **The signer MUST be a pure
function** — percent-encode, sort, concatenate, sign — **and MUST be tested against the RFC's own
published vectors**, not only against Flickr accepting it. A signature Flickr rejects tells you
nothing about which of the four layers was wrong.

#### What the project takes

| Dependency | Version | Transitive deps | Why |
|---|---|---|---|
| `hono` | `4.13.2` | **0** | Routing, middleware, cookie helpers, and a CORS implementation that matches ADR-12's contract including the allowlist behavior. Workers-first rather than ported. |
| `zod` | `4.4.3` | **0** | Runtime validation at the API boundary. TypeScript types vanish at runtime; request bodies arrive untrusted and need checking by something that still exists. |
| `jose` | `6.2.8` | **0** | Signs and verifies the ADR-06 session cookie. Lists `workerd` among its supported runtimes and is built on WebCrypto. |
| `vitest`, `@cloudflare/vitest-pool-workers`, `biome`, `wrangler`, `typescript` | see ADR-13 | dev only | None reach the deployed bundle. |

**All three runtime dependencies have zero dependencies of their own**, which is why they clear the
supply-chain bar above rather than merely being popular.

**The session cookie is the case this rule caught, and it is worth recording as the counterweight to
the OAuth exception above.** ADR-06 specifies an HMAC-SHA256-signed cookie, and the obvious reading
was to write it by hand — serialize, sign, base64url, and on the way back parse, recompute, compare,
check expiry. **That is roughly forty lines in which every plausible bug is a security bug**: a
non-constant-time comparison leaks the signature through timing, a missing expiry check makes
sessions immortal, and a missing algorithm check invites algorithm-confusion attacks. `jose`
implements exactly this as JWS with `HS256`, which **is** HMAC-SHA256 — so **ADR-06 is unchanged and
merely stops being hand-written.** This is the rule working in the direction it was written for, and
it landed on the more security-critical of the two cases.

#### The rule was broken the same day it was written, and how it got caught matters

**Hours after this ADR landed, the landing page shipped a hand-written `escapeHtml`** — a
`replaceAll` chain for the five HTML metacharacters, carrying a confident comment explaining why the
escaping belonged next to the only code that builds markup. **The premise was that no library was
available. It was never checked.** `hono` was already a dependency and exports `html` from
`hono/html`, a tagged template that escapes every interpolation and leaves nested results alone.

**Terry caught it by asking a question about the platform, not about the code**: *doesn't JS have a
built-in for this?* It does not — there is no `String.prototype.escapeHTML`, and the DOM trick
browsers use has no equivalent in Workers — **so the answer to his literal question was "no, we had
to write it," and that answer was wrong at the level above.** The dependency question is the one this
ADR exists to force, and a true statement about the platform stood in for it.

**Two things this establishes, beyond the fix:**

- **The survey MUST include dependencies already in the project**, not only the registry. The
  cheapest possible integration — an import from something already installed and already audited —
  is the one most easily skipped, because nothing about it looks like adding a dependency.
- **Tests written against behavior make the swap free.** All 154 passed unchanged when the
  hand-written function was deleted, including a `<script>` username and an ampersand case checking
  for double-encoding, because none of them named the function. **Had they asserted on `escapeHtml`
  they would have had to be rewritten**, and a rewritten test proves nothing about the change that
  motivated it.

**The escaping is load-bearing rather than cosmetic**: a Flickr display name is a third-party string
the user controls, rendered into a page served from the origin that holds the session cookie.

#### Cloudflare's own agent guidance is a source, and it corrected two things

**`github.com/cloudflare/skills` publishes Cloudflare's rules for agents building on Workers**, and
it **SHOULD** be consulted before writing Workers code rather than relying on training data — which
is, verbatim, its own first instruction. **`wrangler login` offered to install these locally on
2026-08-13 and they now live under `~/.claude/skills/`**, so they are read from disk rather than
fetched. Two corrections it supplied:

- **`crypto.subtle.timingSafeEqual` exists in this runtime.** Comparing secret values with `===` is a
  timing side-channel, and the platform already solves it. This is the ADR-14 test "is the platform
  already doing it?" answering yes for something that looked like hand-written territory.
- **`ctx` MUST NOT be destructured.** `const { waitUntil } = ctx` loses the `this` binding and throws
  "Illegal invocation" at runtime — a mistake that looks like ordinary modern JavaScript and fails
  only in production.

**Where its advice conflicts with a decision here, this document wins and the divergence gets
recorded.** Cloudflare's skill advises enabling `nodejs_compat` broadly because many libraries need
Node built-ins; ADR-13 avoids it unless a dependency forces it, and all three dependencies above are
Web-standard and zero-dependency. **If one ever forces the flag, ADR-13 already requires naming the
dependency that did.**

### ADR-15 — Which store holds what

**Written 2026-08-13 because the owner looked at the architecture diagram and could not work out
why some state is in D1 and some in a Durable Object.** That question having no findable answer was
itself the defect; the split was principled, but the principle existed only in my head and in the
shape of two separate decisions.

**New state MUST be placed by answering two questions. D1 wins if either is "yes".**

| | Question |
|---|---|
| **1** | Does anything ever need to find this **without already knowing its key**? |
| **2** | Does it **outlive a single interaction**? |

| State | Searched? | Outlives? | Store |
|---|---|---|---|
| Users, and their encrypted Flickr tokens | Yes — joined against requests | Yes | **D1** |
| The add-request queues | Yes — *"what is due tonight"* is a query across every user | Yes | **D1** |
| Pairs that reached a moderator | Yes — the queue view lists them per user | Permanently, by ADR-11 | **D1** |
| The OAuth request-token secret | **No** — the callback arrives holding the exact key | **No** — roughly 15 minutes, read once | **Durable Object** |

**Question 1 is not a preference, it is a hard platform constraint.** A Worker **cannot enumerate
the Durable Objects in a namespace** — see the verified-facts row. Anything that must be swept,
reported on, listed, or searched therefore **MUST NOT** live in a Durable Object, because there is
no runtime operation that would find it again. That single fact decides most of the table above
before lifecycle is even considered.

**Question 2 catches what question 1 misses.** A user row is fetched by NSID, which is a key the
caller already holds, so question 1 alone would permit it in a Durable Object. It belongs in D1
anyway because it is durable, joined, and reportable — and because a store that outlives a single
interaction eventually gets asked a question nobody predicted.

**The OAuth attempt is the only state in the system that answers "no" to both**, which is why there
is exactly one Durable Object. **A rule with a single instance reads as an exception, and that is
precisely why it needed writing down** rather than left to be inferred from the diagram.

**Workers KV holds nothing.** Its consistency model is wrong for the login path (ADR-02) and there
is no other candidate, so it is absent from the design rather than merely unused.

**Where this rule and ADR-14 disagree, ADR-14 does not apply** — this is about placing state, not
about taking dependencies.

## Considered and rejected

| Option | Why not |
|---|---|
| AWS (the shape of the 2022 `fga-api`) | Workable, but every piece it needed has a simpler Cloudflare equivalent here, and the frontend is already Cloudflare Pages. Splitting across two providers buys nothing. |
| D1 for the OAuth request-token secret | **A close call, not a clear loss.** D1 primary reads are strongly consistent, so it would work. It loses on lifecycle: it needs a fourth table whose every row is destined for deletion, plus a cleanup the cron must not forget. See ADR-02. |
| An off-the-shelf OAuth 1.0a library | Every candidate is unmaintained, Node-only, or wraps an HTTP client we do not use. Full survey in ADR-14. |
| Hand-rolling the router, CORS, and cookie parsing | Hono does all three, has zero dependencies, and its CORS middleware already implements the allowlist behavior ADR-12 spends a section warning about. See ADR-14. |
| Rust via `workers-rs` | Nine commits in thirteen weeks against the runtime's 1,360, still pre-1.0, and its advantages do not apply to an I/O-bound workload. See ADR-13. |
| Python Workers | Open beta, and ADR-03 already rejected a beta dependency for a far smaller surface. Revisit at general availability. See ADR-13. |
| Holding TypeScript at `6.0.3` to keep `typescript-eslint` | Considered seriously. Biome removes the need by not depending on the compiler API at all. See ADR-13. |
| Cognito, or Google logins with a JWKS cache | Both exist to supply an identity FGA has decided not to hold. See ADR-01. |
| Per-user Durable Objects with alarms | **Deferred, not rejected.** The right answer at a scale this project has not reached. See ADR-04 for the promotion criteria. |
| Cloudflare Secrets Store | Correct product, wrong maturity and wrong ceiling. See ADR-03. |
| Cloudflare Queues | Verified as available with dead-letter queues, retries, delays, and batching. Not needed while a nightly sweep does the work. Revisit alongside ADR-04's promotion criteria. |
| Workers KV for session or OAuth state | Consistency model is wrong for the login path. See ADR-02. |
| A nightly cron reaper for abandoned OAuth objects | **Not possible as imagined, and not needed.** A Worker cannot enumerate the Durable Objects in a namespace at runtime, so a reaper would need its own index in D1 — one extra write on every login attempt, purely to clean up what the object's own alarm already deletes. It would add a moving part, a cost, and a new failure mode to replace a mechanism that is strictly better: the alarm fires per object, exactly when that object is due, with no global scan. See ADR-02. |

## Open questions

- **An unanswered add is currently terminal, and it MAY be too strict.** Found while writing the
  Flickr client, 2026-08-13. ADR-07 classifies by Flickr's error code, but a request that times
  out or dies in transport has no code at all — and it may still have been processed. If the pool
  was moderated, the photo could be in front of a volunteer right now, so ADR-08 makes the safe
  reading terminal, and that is what the code does today (`kind: "unconfirmed"`, distinct from a
  Flickr-reported failure so the user can be told "we could not confirm this" rather than "Flickr
  said no"). **The cost is that one dropped connection permanently fails a request that probably
  never happened.** The refinement worth investigating: `flickr.groups.getInfo` reports whether a
  pool is moderated, and **for an unmoderated pool the ambiguity disappears entirely** — ADR-05's
  `photos.getAllContexts` check then says definitively whether the add landed, so a retry is safe.
  Only moderated pools would stay terminal. That would need one extra call and a verified fact
  about what `getInfo` actually returns. **Note the asymmetry that already exists and is
  deliberate:** Flickr's own 105 and 106 stay retryable because there Flickr is *telling* us the
  write did not happen, which a dead socket does not.
- **Flickr's per-group add limits are now quantified, and two changes follow that are not yet
  made.** `flickr.groups.getInfo` returns `<throttle count mode remaining />`, the five `mode`
  values are known, and `remaining` reads as per-user — see the three verified-facts rows added
  2026-08-13. **FGA does not need to model the limits or count attempts itself; it can ask**,
  which removes the per-group counter table this question was written to design. What remains:
  **the sweep SHOULD skip a queue whose `remaining` is 0 and MUST skip a group whose `mode` is
  `disabled`**, since a disabled pool accepts nothing and every attempt is wasted. ADR-07's code 5
  stays the authority either way — a cached `remaining` can be stale in a way a live rejection
  cannot — so this is an optimization on top of the classifier, never a replacement for it.
- **Whether D1 needs a separate group-metadata cache.** Currently assumed not: group rules can be
  read from Flickr on demand. Revisit if that read turns out to be slow or rate-limited.
- **The wording a user sees when FGA has deliberately stopped.** *That* the queue is shown and
  *how it is scoped* are both settled — see "The queue view". What remains is the copy itself, and
  it is the sentence that either delivers ADR-08's promise or quietly undercuts it. It deserves
  writing carefully rather than defaulting to a status code.
