# Bringing FlickrGroupAddr up for the first time

**RFC 2119 keywords, and the capitals are load-bearing.** MUST and MUST NOT are absolute; SHOULD
and SHOULD NOT are strong defaults a good argument may overrule; MAY is genuinely optional.

**Everything here needs Terry's credentials and therefore Terry.** The steps are in dependency
order — each one's output is the next one's input — and step 6 is the interesting one, because it
answers three questions this design has been carrying unresolved.

## Before starting

| | |
|---|---|
| Cloudflare | Already on the Workers Paid plan. `wrangler login` if the CLI is not already authorized. |
| Flickr | An API key, created at <https://www.flickr.com/services/apps/create/> |
| Node | 24.x, already installed |

**A note on the callback URL, because it may bite at app-creation time.** OAuth 1.0a sends
`oauth_callback` with each request, so Flickr **SHOULD NOT** need one registered in advance. If the
app form demands one anyway, `flickrgroupaddr.com` is **not owned yet** — it is in `pendingDelete`
and a local watcher is waiting to re-register it. Use `http://localhost:8787/oauth/callback` for
now and revisit once the domain lands.

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

**`--local` MUST NOT be omitted by accident in the other direction either** — the local database
is already migrated, and this step is specifically about the remote one.

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

## 5. Run it locally and log in

```
npm run dev
```

Then open `http://localhost:8787/oauth/login`. That runs the whole three-leg dance: it fetches a
request token, parks the secret in a Durable Object, bounces to Flickr for authorization, and
returns to mint a session cookie.

**Reaching Flickr's authorize page at all proves the signature is accepted**, which is the one
thing 146 passing tests cannot establish. The signer is checked against RFC 5849's published
vectors, so it implements the specification correctly — but Flickr is idiosyncratic and only a live
call settles whether that is enough.

## 6. The diagnostic call, which answers three open questions at once

With the session cookie set, request:

```
http://localhost:8787/v001/groups
```

**Read the reply carefully rather than only checking that it worked.** It carries the answers to
three things recorded as unresolved in `docs/architecture/DECISIONS.md`:

| Look at | Question it settles |
|---|---|
| That the call returned anything at all | Whether Flickr accepts our OAuth 1.0a signature on an authenticated REST call, not just on the login legs |
| `throttle.mode` across several groups | Which periods Flickr actually uses. Only `month` appears in its own documentation; `day` and `week` are expected and unconfirmed |
| `throttle.remaining` | **Whether the allowance is per-user or per-group.** If it is per-user, the nightly sweep can skip a queue whose allowance is already spent instead of burning an attempt to discover it |
| `ispoolmoderated` | Whether the pool is moderated. This is the field that would let an unanswered add be retried safely for unmoderated pools — see the open question on unconfirmed adds |

**The `raw` field in that response holds the unparsed group list on purpose**, because the JSON
shapes above are read from Flickr's documentation and have never been checked against a live reply.
It **SHOULD** be removed once they are confirmed.

**Record what is found in the verified-facts table**, with the date and how it was established —
that table's whole value is that every row says how it was learned.

## 7. Deploy

```
npm run check       # Typecheck, lint, and 146 tests. MUST be clean first.
npx wrangler deploy
```

**The cron trigger starts firing as soon as this succeeds**, nightly at 00:15 UTC. With no users
and no queued requests it walks nothing and logs a report saying so.

## What is deliberately not here

**Routes are not yet mounted on a custom domain**, because the domain is not owned. Once
`flickrgroupaddr.com` is re-registered, the API needs a route on `api.flickrgroupaddr.com` and the
UI origin in `wrangler.jsonc` stops being aspirational. ADR-12 records the CORS contract that
depends on both.
