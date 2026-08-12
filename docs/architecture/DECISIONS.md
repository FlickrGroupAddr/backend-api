# FlickrGroupAddr backend-api — architecture decisions

**RFC 2119 keywords, and the capitals are load-bearing.** MUST and MUST NOT are absolute;
SHOULD and SHOULD NOT are strong defaults a good argument may overrule; MAY is genuinely
optional.

This file records decisions for the 2026-08 rebuild and, separately, the facts those decisions
rest on. **The repositories under the FlickrGroupAddr GitHub org are stale reference, not
requirements** — they record what was tried between roughly 2016 and 2022, under constraints
that no longer apply. Mine them for domain facts; do not inherit their architecture.

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
| The account is on the Workers Paid plan | Purchase confirmed on the billing page. Included allowances: Workers and Pages Functions 10M requests/month with 30 s CPU per request and 30M ms/month; **Durable Objects 1M requests/month, 400K GB-s duration, 1 GB storage**; Workers Builds 6 slots and 6,000 minutes/month. Overage: Workers requests $0.30/M, DO requests $0.15/M, KV operations $0.50/M, D1 rows $0.001/M. | 2026-08-12 |

## Decisions

### D1 — The Flickr account is the identity

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
than its own feature set.** Token handling is the security crux of this design, and D3 governs
it.

### D2 — OAuth 1.0a intermediate state lives in a Durable Object, never in KV

The request-token secret **MUST** be held in a Durable Object keyed by `oauth_token` for the
duration of the redirect, and **MUST NOT** be written to Workers KV.

**Why:** the login flow writes the secret, bounces the user to flickr.com for 5 to 30 seconds,
and then must read that secret back when the callback lands. KV offers no read-after-write
guarantee and can take 60 seconds or more to propagate between locations, so the callback can
arrive at a point of presence that cannot yet see the write. The resulting failure is
intermittent, dependent on which PoP the user transited, and effectively unreproducible on a
developer's machine.

**This is the only place in the v1 design where a Durable Object is used, and the narrow scope is
deliberate** — see D4. The object **SHOULD** set an alarm to delete itself after roughly 15
minutes, so abandoned login attempts expire without a cleanup job.

### D3 — Per-user Flickr tokens are AES-GCM encrypted in D1

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

### D4 — The v1 work engine is a nightly Cron Trigger over a D1 table

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
**MUST NOT** be read as reopening D4. The case for the cron was debuggability, failure-history
locality, and lock-in — none of which a billing change touches.

**Promotion criteria.** Move to the alarm design when **any** of the following is *measured*, not
anticipated: the nightly scan takes long enough to threaten the Worker's limits; Flickr rate-limits
or rejects the concentrated midnight burst; or per-user scheduling becomes a product requirement
rather than an implementation preference.

### D5 — The retry handler MUST be idempotent per (photo, group)

Before calling `flickr.groups.pools.add`, the handler **MUST** confirm from D1 that the pair has
not already succeeded.

**Why:** sweeps can overlap or be re-run, and a handler that throws part-way through leaves work
half-done. Without a guard, the next run submits a duplicate add. This is a correctness
requirement, not a defensive nicety. It survives unchanged if D4 is ever promoted to alarms,
where at-least-once delivery makes it mandatory for a second reason.

### D6 — Sessions are a backend-signed cookie

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

## Considered and rejected

| Option | Why not |
|---|---|
| AWS (the shape of the 2022 `fga-api`) | Workable, but every piece it needed has a simpler Cloudflare equivalent here, and the frontend is already Cloudflare Pages. Splitting across two providers buys nothing. |
| Cognito, or Google logins with a JWKS cache | Both exist to supply an identity FGA has decided not to hold. See D1. |
| Per-user Durable Objects with alarms | **Deferred, not rejected.** The right answer at a scale this project has not reached. See D4 for the promotion criteria. |
| Cloudflare Secrets Store | Correct product, wrong maturity and wrong ceiling. See D3. |
| Cloudflare Queues | Verified as available with dead-letter queues, retries, delays, and batching. Not needed while a nightly sweep does the work. Revisit alongside D4's promotion criteria. |
| Workers KV for session or OAuth state | Consistency model is wrong for the login path. See D2. |

## Open questions

- **Flickr's per-group daily add limits are not yet quantified.** The retry cadence and the
  per-group counter schema both depend on them, and they appear to vary by group. This
  **SHOULD** be established from the API before the schema is fixed.
- **Whether D1 needs a separate group-metadata cache.** Currently assumed not: group rules can be
  read from Flickr on demand. Revisit if that read turns out to be slow or rate-limited.
