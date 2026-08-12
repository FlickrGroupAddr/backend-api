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
| Durable Object alarms deliver at-least-once | Cloudflare docs: guaranteed at-least-once execution, automatic retry with exponential backoff from 2 seconds, up to 6 retries, and `alarmInfo.retryCount` / `alarmInfo.isRetry` exposed to the handler. Only uncaught exceptions trigger a retry. | 2026-08-12 |
| Cloudflare Secrets Store caps at 100 secrets | Open beta limits: 100 secrets per account, one store per account, 1024 bytes per secret value. | 2026-08-12 |

## Decisions

### D1 — The Flickr account is the identity

FGA **MUST NOT** run its own identity service and **MUST NOT** store an email address, a display
name, or any other contact detail. The Flickr NSID is the user key.

**Why:** the NSID is a pseudonymous identifier that is already public. An email address is not,
and holding one creates a breach obligation that buys nothing the product needs. The 2022 design
ran Cognito specifically so it would hold email addresses for alerting; that requirement was
never confirmed and is dropped.

**The consequence MUST be understood rather than assumed away:** minimizing PII here relocates
risk rather than removing it. FGA still holds a long-lived OAuth token that can act on each
user's Flickr account, which is a more attractive target than an email address. Token handling is
therefore the security crux of this design, and D3 governs it.

### D2 — OAuth 1.0a intermediate state lives in a Durable Object, never in KV

The request-token secret **MUST** be held in a Durable Object keyed by `oauth_token` for the
duration of the redirect, and **MUST NOT** be written to Workers KV.

**Why:** the login flow writes the secret, bounces the user to flickr.com for 5 to 30 seconds,
and then must read that secret back when the callback lands. KV offers no read-after-write
guarantee and can take 60 seconds or more to propagate between locations, so the callback can
arrive at a point of presence that cannot yet see the write. The resulting failure is
intermittent, dependent on which PoP the user transited, and effectively unreproducible on a
developer's machine. A Durable Object is strongly consistent and cannot exhibit this.

The object **SHOULD** set an alarm to delete itself after roughly 15 minutes, so abandoned login
attempts expire without a cleanup job.

### D3 — Per-user Flickr tokens are encrypted into the user's Durable Object

Each user's Flickr access token and token secret **MUST** be encrypted with AES-GCM and stored in
that user's Durable Object. The master key **MUST** live in Secrets Store. Per-user tokens
**MUST NOT** be stored in Secrets Store.

**Why:** Secrets Store holds 100 secrets per account, so storing one secret per user puts a hard
ceiling at 100 users — discovered only once the product has traction. This is the same mistake
the 2022 design made with one SSM parameter per user, and it is worth naming so it is not
reintroduced as an improvement. Secrets Store is correct for the three app-level secrets: the
Flickr consumer key, the consumer secret, and the master encryption key.

### D4 — The retry loop is driven by Durable Object alarms, not a global nightly cron

Each user's Durable Object **MUST** schedule its own next attempt with `setAlarm()`. A Cron
Trigger **MAY** run as a safety-net sweeper for objects whose alarm was lost, but it **MUST NOT**
be the primary work engine.

**Why:** Flickr caps how many photos a member may add to a group per day, so a request can retry
for weeks. A global nightly scan reads every pending request to find the few that are due, and
concentrates the entire day's Flickr traffic into one minute at 00:01 UTC. Alarms invert this:
each object wakes only when its own quota window opens, work spreads naturally across the day,
and no scan is needed.

### D5 — The alarm handler MUST be idempotent per (photo, group)

Before calling `flickr.groups.pools.add`, the handler **MUST** confirm from its own state that
the pair has not already succeeded.

**Why:** alarm delivery is at-least-once, so a handler that throws part-way through, or whose
delivery is retried, will run again. Without a guard, the retry submits a duplicate add. This is
a correctness requirement, not a defensive nicety.

## Considered and rejected

| Option | Why not |
|---|---|
| AWS (the shape of the 2022 `fga-api`) | Workable, but every piece it needed has a simpler Cloudflare equivalent here, and the frontend is already Cloudflare Pages. Splitting across two providers buys nothing. |
| Cognito, or Google logins with a JWKS cache | Both exist to supply an identity FGA has decided not to hold. See D1. |
| Cloudflare Queues | Verified as available with dead-letter queues, retries, delays, and batching. Not needed: DO alarms already provide the scheduling, and the per-user object is the natural unit of both work and rate limiting. Revisit if fan-out across users ever needs throttling in one place. |
| Workers KV for session or OAuth state | Consistency model is wrong for the login path. See D2. |

## Open questions

- **Session mechanism.** A backend-signed JWT in an `HttpOnly` cookie is the current default, but
  a Durable-Object-backed opaque session would allow instant revocation. Not yet decided.
- **D1 (the database) may not be needed for v1.** It is drawn as a group-metadata cache. If group
  rules are read from Flickr on demand, it can be dropped.
- **Whether Durable Objects require a paid Workers plan** for the storage backend intended here.
  This has not been verified and **MUST** be checked before committing to the design.
