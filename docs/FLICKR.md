# What Flickr actually does

**Every row here was measured against the live API or read from Flickr's own docs.** Several
contradict the documentation. **Re-verify before quoting any number.**

## The six calls FGA needs

| Stage | Call |
|---|---|
| Login | `oauth/request_token`, then `oauth/authorize`, then `oauth/access_token` |
| List groups | `flickr.groups.pools.getGroups` |
| Check a photo's pools | `flickr.photos.getAllContexts` |
| Add | `flickr.groups.pools.add` |

## OAuth 1.0a, and why it shapes the design

**There is no unauthenticated leg.** The very first request-token call is signed, with an empty
token-secret half. So nothing can reach Flickr before the FGA credentials are read.

**The server gets a token SECRET, then walks the user away for two minutes.** That secret must
survive a round trip through someone's browser. It cannot travel in the URL and cannot be
recomputed. **That single fact is why ADR-08 exists.**

**Access tokens never expire.** No refresh machinery is needed. A leaked token stays valid until the
user revokes FGA at Flickr.

**Flickr accepts any `oauth_callback` with no pre-registration** — confirmed 2026-08-13 by a
production login. **FGA can change hostnames without touching anything at Flickr.**

**`workerd` implements HMAC-SHA1.** Verified against RFC 2202 test vectors. It is a deprecated
primitive a modern runtime could reasonably refuse, and **without it this project could not run on
Cloudflare Workers at all.**

## Flickr has no group-creation API

**The `flickr.groups.*` family is read and pool operations only.** There is no method to create a
group, so a test group cannot be provisioned by script — it takes a browser, logged in as the
account, and it is close to permanent afterward. Flickr provides no comfortable way to delete a
group you own.

**So there is no such thing as a throwaway Flickr group.** Any end-to-end test either uses a group
the account is already in, or leaves a permanent artifact behind. Plan accordingly rather than
discovering it after the fact.

## Permissions are coarse, and that is a security fact

**Flickr offers exactly three levels: `read`, `write`, `delete`.**

**There is no scope for "add photos to groups".** `write` is the narrowest that works, and it grants
edit access to the user's entire account. See ADR-07.

## A moderator's decision is invisible

**No error code, no callback, no endpoint reports a rejection.**

After code **6** the photo sits in the pool's pending queue. If a moderator declines it, the photo is
simply removed and never appears. `flickr.photos.getAllContexts` shows whether a photo landed, but
**"not in the pool" cannot distinguish *still pending* from *rejected*.**

**Presence in the pool proves approval. Absence proves nothing.** This is the whole reason ADR-01
exists.

## `groups.pools.add` error codes

Terminal unless marked. The executable version is `src/adds/classify.ts`.

| Code | Meaning |
|---|---|
| *(none)* | Added |
| 3 | Already in pool — **treat as success** |
| **5** | **Photo limit reached — RETRYABLE. This is the throttle FGA exists to wait out** |
| 6 | Added to the pending queue — **a person now has it** |
| 7 | Already in the pending queue |
| 1, 2, 4, 8, 10, 11 | Not found, no group, max pools, content refused, pool full, pool disabled |
| 98, 99 | Auth failure — flag the user to re-link |
| **105, 106** | **Service unavailable, write failed — RETRYABLE, transient** |

## The throttle, measured across all 372 of one account's groups

**`flickr.groups.getInfo` returns `<throttle count mode remaining />`.**

**`mode` takes five values, not the one Flickr documents.** Measured 2026-08-13:

| `mode` | Groups |
|---|---|
| `none` | 170 |
| `day` | 167 |
| `week` | 17 |
| `month` | 13 — **the only value Flickr's docs show** |
| `disabled` | 5 |

**A `disabled` pool answers `groups.pools.add` with code 11.** Measured against a real add. FGA
**SHOULD** skip those rather than spend an attempt discovering it.

**Those five are not simply the moderated or invite-only ones** — three are moderated, two are not,
and only one is invite-only. **A skip rule keyed on invite-only would miss four of them.**

**`remaining` reads as per-user, not per-group.** It equaled `count` in every one of 330 groups,
including pools with 95,000+ members. **Strong, not conclusive** — confirming it needs one add
followed by a re-read of the same group.

## Group size, and the trap in it

**One account can belong to hundreds of groups, and the number moves.** The owner was in **330**
early on 2026-08-13 and **372** later the same day.

**Any per-group work MUST be sized against hundreds, and MUST NOT cache the count.**

**372 is not the ceiling, and an independent source says so.** Jeffrey Friedl's Flickr plug-in for
Lightroom shipped a fix in 2009 *"for a bug that prevented more than 400 groups from showing"*, with
the aside *"(Yes, some people are members of more than 400 groups!)"*. **A second implementation hit
this and capped at 400 by accident**, which is the shape ADR-17's walk-every-page rule exists to
prevent. Terry raised the plug-in as a survey lead; its code is compiled and unreadable, so its
changelog is the only evidence available.

**A full `getInfo` sweep of 372 groups takes about 50 seconds**, at roughly 130 ms per call. An
endpoint that made one call per group returned 979 KB and took **53 seconds**. The fix was not
concurrency. **The fix was not making the calls.**

### `flickr.groups.pools.getGroups` IS PAGED, and FGA ignored that until 2026-08-15

**FGA sent no `page` and no `per_page`, and read only `groups.group` — never `pages` or `total`.**
So it took Flickr's default page size and returned page one as the complete list. **No code path
could produce a symptom**, and the owner sat at 372 with the default unmeasured.

**The default page size for this method is STILL UNMEASURED, and that is the point.** Nothing here
should depend on it. `getUserGroups` now sends `per_page=500`, reads `pages`, and walks to the end.

**Flickr clamps an over-large `per_page` silently rather than erroring.** So a single call with a big
page size and no loop inherits the clamp as fresh silent truncation. **The walk is what makes the
page size safe to guess.**

**Read `total` and `pages` as data, not decoration.** Both arrive inconsistently typed — sometimes a
JSON number, sometimes a string — which is why `asNumber` absorbs them and the test stub deliberately
returns strings.

See ADR-17, which was widened the same day to cover any list whose size a third party sets.

## Two fields that look alike and are not

**`ispoolmoderated`** on `groups.getInfo` is `0` or `1` and says whether adds go to a human queue.

**`restrictions.moderate_ok`** is about permitted content ratings. **Different thing entirely.**
