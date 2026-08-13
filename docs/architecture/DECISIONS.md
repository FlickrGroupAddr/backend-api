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
| Durable Objects have no TTL, and an idle one is free | Cloudflare docs: there is no automatic expiry, but "inactive objects receiving no requests do not incur any duration charges." Storage is metered separately and "Durable Objects will be billed for stored data until the data is removed"; once deleted through the Storage API the object is cleaned up and stops incurring storage fees. **There is no runtime API to enumerate the objects in a namespace** — a Worker cannot list them. | 2026-08-13 |
| The account is on the Workers Paid plan | Purchase confirmed on the billing page. Included allowances: Workers and Pages Functions 10M requests/month with 30 s CPU per request and 30M ms/month; **Durable Objects 1M requests/month, 400K GB-s duration, 1 GB storage**; Workers Builds 6 slots and 6,000 minutes/month. Overage: Workers requests $0.30/M, DO requests $0.15/M, KV operations $0.50/M, D1 rows $0.001/M. | 2026-08-12 |

## Decisions

**Labelled `ADR-nn` for Architecture Decision Record, deliberately not `D-n`.** Cloudflare's
SQLite database is named **D1**, and this document refers to it constantly — "rows in D1",
"encrypted in D1", "costs no D1 read". A decision numbered D1 sitting beside a database named D1
is a collision that reads fine to whoever wrote it and confuses everyone else. These labels
**MUST NOT** be shortened back to `D-n`.

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
D1 beside that user's row. The master key **MUST** be held as a Worker secret. Per-user tokens
**MUST NOT** be stored in Cloudflare Secrets Store.

**Why not Secrets Store for tokens:** it holds 100 secrets per account, so one secret per user
puts a hard ceiling at 100 users — discovered only once the product has traction. This is the
same mistake the 2022 design made with one SSM parameter per user, and it is named here so it is
not reintroduced as an improvement.

**Why plain Worker secrets rather than Secrets Store for the master key:** only three app-level
values need storing, and Secrets Store is in open beta while Worker secrets are GA. A beta
dependency is not worth the better management story when the value being protected is the key to
every user's Flickr credential. **Revisit once Secrets Store leaves beta.**

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
  Web-standard code. An application whose stateful core is DO-shaped is not.

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

### ADR-06 — Sessions are a backend-signed cookie

After the Flickr callback completes, the API Worker **SHOULD** mint a signed token carrying the
NSID and set it as an `HttpOnly; Secure; SameSite=Lax` cookie. It **MUST NOT** send the Flickr
token to the browser under any circumstances.

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
