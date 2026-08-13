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
| The account is on the Workers Paid plan | Purchase confirmed on the billing page. Included allowances: Workers and Pages Functions 10M requests/month with 30 s CPU per request and 30M ms/month; **Durable Objects 1M requests/month, 400K GB-s duration, 1 GB storage**; Workers Builds 6 slots and 6,000 minutes/month. Overage: Workers requests $0.30/M, Durable Object requests $0.15/M, KV operations $0.50/M, D1 rows $0.001/M. | 2026-08-12 |

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

**The REST API version is padded for the same reason, to three digits: `/api/v001/*`.** This
carries over from the 2022 API, which used the same form. A path version is harder to change than
a document label, not easier — it is baked into every client that has ever called it — so the
padding **MUST** be right from the first route.

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

### ADR-02 — OAuth 1.0a intermediate state lives in a Durable Object, never in KV

The request-token secret **MUST** be held in a Durable Object keyed by `oauth_token` for the
duration of the redirect, and **MUST NOT** be written to Workers KV.

**Why:** the login flow writes the secret, bounces the user to flickr.com for 5 to 30 seconds,
and then must read that secret back when the callback lands. KV offers no read-after-write
guarantee and can take 60 seconds or more to propagate between locations, so the callback can
arrive at a point of presence that cannot yet see the write. The resulting failure is
intermittent, dependent on which PoP the user transited, and effectively unreproducible on a
developer's machine.

**This is the only place in the v1 design where a Durable Object is used, and the narrow scope is
deliberate** — see ADR-04.

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

**The signing key is a Worker secret, and MUST be distinct from the token-encryption key** — see
the secrets table in ADR-03, which is also where the reason for keeping them separate lives.

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

## Considered and rejected

| Option | Why not |
|---|---|
| AWS (the shape of the 2022 `fga-api`) | Workable, but every piece it needed has a simpler Cloudflare equivalent here, and the frontend is already Cloudflare Pages. Splitting across two providers buys nothing. |
| Cognito, or Google logins with a JWKS cache | Both exist to supply an identity FGA has decided not to hold. See ADR-01. |
| Per-user Durable Objects with alarms | **Deferred, not rejected.** The right answer at a scale this project has not reached. See ADR-04 for the promotion criteria. |
| Cloudflare Secrets Store | Correct product, wrong maturity and wrong ceiling. See ADR-03. |
| Cloudflare Queues | Verified as available with dead-letter queues, retries, delays, and batching. Not needed while a nightly sweep does the work. Revisit alongside ADR-04's promotion criteria. |
| Workers KV for session or OAuth state | Consistency model is wrong for the login path. See ADR-02. |
| A nightly cron reaper for abandoned OAuth objects | **Not possible as imagined, and not needed.** A Worker cannot enumerate the Durable Objects in a namespace at runtime, so a reaper would need its own index in D1 — one extra write on every login attempt, purely to clean up what the object's own alarm already deletes. It would add a moving part, a cost, and a new failure mode to replace a mechanism that is strictly better: the alarm fires per object, exactly when that object is due, with no global scan. See ADR-02. |

## Open questions

- **Flickr's per-group daily add limits are not yet quantified.** The retry cadence and the
  per-group counter schema both depend on them, and they appear to vary by group. This
  **SHOULD** be established from the API before the schema is fixed.
- **Whether D1 needs a separate group-metadata cache.** Currently assumed not: group rules can be
  read from Flickr on demand. Revisit if that read turns out to be slow or rate-limited.
- **The wording a user sees when FGA has deliberately stopped.** *That* the queue is shown and
  *how it is scoped* are both settled — see "The queue view". What remains is the copy itself, and
  it is the sentence that either delivers ADR-08's promise or quietly undercuts it. It deserves
  writing carefully rather than defaulting to a status code.
