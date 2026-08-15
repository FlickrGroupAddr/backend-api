# Key management, blast radius, and opaque sessions

**RFC 2119 keywords. MUST and MUST NOT are absolute. SHOULD is a strong default a good argument may
overrule. MAY is optional.**

## Status: DECIDED 2026-08-15, NOT YET IMPLEMENTED

**Terry decided the direction; none of it is built.** This is deliberately not an ADR yet. An ADR in
`DECISIONS.md` must be verified by a test or declare `**Verification: Inspection**`, and declaring
inspection for runtime behavior that does not exist would be the forced link
`scripts/traceability.py` exists to prevent.

**When the code lands, this becomes an ADR with real tests, and this file goes away.**
`DECISIONS.md` carries pointers under ADR-09, ADR-10 and "Still open" until then.

## The question, in Terry's words

> If someone DID get ahold of our token or session keys, it would seem to me that affects all users.

**Correct. Both keys are account-wide today.**

| Leaks | Attacker gets | Needs the D1 contents too? |
|---|---|---|
| `SESSION_KEY` | Mint a session as **any NSID**, full API access as any user | **No** |
| `TOKEN_KEY` | Decrypt every stored Flickr token, granting `write` on every user's entire Flickr account | **Yes** |

**`SESSION_KEY` is the worse of the two**, because it needs no data breach to be catastrophic.

**The deepest exposure is not cryptographic at all.** ADR-07 records that Flickr offers no scope
narrower than `write`, so FGA holds a credential far more powerful than its feature set. No key
scheme changes that.

## Per-user encryption keys were considered and REJECTED

**The test any key scheme must pass: can ADR-06's nightly sweep still run?** It fires at 00:15 UTC
with the user absent, and it MUST decrypt that user's Flickr token. **So the server must obtain
every user's key unaided — and therefore so can anyone who compromises the server.**

| Where a per-user key could live | What it buys |
|---|---|
| Derived by HKDF from a master key plus NSID | **Nothing.** The master still unlocks everything |
| A column in D1 beside the ciphertext | **Nothing.** Key and payload leak in the same dump |
| Cloudflare Secrets Store | Already rejected in ADR-09 — 100 secrets per account |
| Derived from a user secret | **Impossible.** ADR-07 holds no user secret, and the sweep runs unattended |

**The isolation per-user keys would be reaching for already exists.** `src/crypto/tokens.ts` binds
each blob to its row by passing the NSID as AES-GCM additional authenticated data, so moving one
user's ciphertext into another's row fails rather than granting access.

**AES-GCM's own per-key limit does not apply either.** Random 96-bit IVs want fewer than roughly
2^32 encryptions per key; FGA performs two per login.

## Keys are identified by a UTC TIMESTAMP, never an integer version

**Standing preference, Terry, 2026-08-15, and it is not a style note:** *"I've never once regretted
using monotonically increasing timestamps. I HAVE regretted integer version numbers damn near every
time."*

**So `users.token_key_version INTEGER DEFAULT 1` is replaced by an epoch-millisecond stamp.** The
column has existed since migration `0001` and **nothing has ever read or written it** — it is inert,
so replacing it costs nothing but a migration.

| | |
|---|---|
| New column | `token_key_at INTEGER NOT NULL` |
| Meaning | The epoch-ms identifier of the key in `TOKEN_KEYS` that encrypted this row |
| Resolution | Milliseconds, matching `created_at`, `updated_at`, `resolved_at` and every other timestamp in this schema — all of which are `Date.now()` |

**Why the timestamp is more than cosmetic here: it makes "which key is current" self-answering.**
The active key is **the largest stamp in the ring**. No second secret naming the active version, no
pointer to keep in step with the map, and no chance of the pointer and the map disagreeing. **An
integer version needs a separate "which one is current" fact; a timestamp carries it.**

## The keyring

**One Worker secret per key class, holding a JSON object from epoch-ms to base64 key.**

```
TOKEN_KEYS    {"1755264000000":"<base64 32 bytes>","1752585600000":"<base64 32 bytes>"}
SESSION_KEYS  {"1755264000000":"<base64 32 bytes>","1752585600000":"<base64 32 bytes>"}
```

**Three rules, and the first is the one that makes the rest work:**

- **The newest stamp signs and encrypts. Any key in the ring may decrypt or verify.**
- **A key MAY be dropped from the ring once no row references it.** For `TOKEN_KEYS` that is a
  query: `SELECT COUNT(*) FROM users WHERE token_key_at = ?`. For `SESSION_KEYS` it is simply age —
  sessions live 30 days, so a key older than that verifies nothing.
- **`TOKEN_KEYS` and `SESSION_KEYS` MUST hold different values**, exactly as ADR-09 already requires.
  Rotating a session key logs everyone out and costs nothing; rotating a token key means
  re-encrypting every stored token. **Sharing one makes the cheap rotation as expensive as the dear
  one, so neither ever happens.**

**Migration `0001`'s existing rows carry `token_key_version = 1`.** The migration MUST map them to
the epoch-ms of the key that actually encrypted them, and that same stamp MUST be the oldest entry
in the first `TOKEN_KEYS` ring. **Getting this wrong makes every existing token undecryptable.**

## Sessions become opaque, signed handles

**Today's cookie is a JWS: signed, and fully transparent.** `header.payload.signature`, all
base64url. **Anyone holding the cookie can decode the payload with no key** and read `sub` — the
NSID — plus `iss`, `aud`, `iat` and `exp`. The signature prevents tampering and does nothing to
prevent reading.

**Opaque means the token carries no information — a pure lookup handle.**

### The shape

**Cookie value: `<id>.<hmac>`**

| Piece | What | Why |
|---|---|---|
| `id` | 256 random bits from `crypto.getRandomValues`, base64url | Unguessable, and carries nothing |
| `hmac` | HMAC-SHA256 of `id` under the newest `SESSION_KEYS` entry | Rejects forgeries with **no D1 read** |
| Stored | **SHA-256 of `id`**, plus `nsid`, `created_at`, `expires_at`, `session_key_at` | A D1 leak yields hashes, not usable tokens |

**Verify in that order: HMAC first, then look up.** An attacker spraying random cookies is rejected
on CPU alone and never costs a database read.

**Storing the hash rather than the id is not optional.** Store raw ids and a D1 leak hands over
directly usable bearer tokens for every live session. Same reasoning as never storing a password.

### Why signing SURVIVES the move to opaque, which is the whole blast-radius win

**A signature on an opaque handle looks redundant and is not.** With both, leaking `SESSION_KEY`
alone no longer mints anything — a forger passes the cheap filter and then **fails the database
lookup**. They would need the key *and* a live session id.

**That is the direct answer to the question this file opens with.** `SESSION_KEY` stops being a
single secret that grants account takeover.

### UUIDv7 is ruled out, by this project's own reasoning

**ADR-16 already rejected v7 for `requests.public_id`** because it "republishes its own creation
time" and spends 48 bits on a plaintext timestamp, leaving 74 random against v4's 122. **A session
id is a bearer credential, so that argument binds harder here than it did there.**

**256 raw random bits is preferred over UUIDv4.** v4's 122 bits are adequate; the extra bits cost
nothing, and a session id never appears in an API contract, so there is no consistency benefit to
being a UUID. **This one is a preference rather than a rule.**

### What is gained and what is lost

**Gained:** instant revocation, which ADR-10 explicitly names as the thing it gave up. Real
server-side logout. The ability to enumerate and kill sessions. And the blast-radius reduction above.

**Lost: one D1 read per authenticated request.** ADR-12 prices reads at $0.001 per million rows, so
the cost is noise.

**Lost, and subtler — a diagnostic worth mourning.** `docs/SETUP.md` records that
`/api/v001/me` keeps working through a completely broken database, "which is ADR-10 behaving as
designed rather than a fluke." **That property goes away.** It is a genuinely useful signal when
debugging, and losing it is a real cost rather than a rounding error.

**Unchanged: everything in ADR-11.** `__Host-fga_session`, `HttpOnly`, `Secure`, `SameSite=Lax`,
`Path=/`, no `Domain`. Only the payload changes, and `src/session.ts` remains the only place that
knows the cookie's name or attributes.

## Rotation, and what it actually buys

**Rotation bounds the window of a key that leaked and was never noticed. Against an attacker with
ongoing access to the Worker environment it buys NOTHING** — they receive the new key too. Say that
plainly rather than selling rotation as a general defense.

| Key class | Cost to rotate | Mechanism |
|---|---|---|
| `SESSION_KEYS` | Near zero | Add a new stamp. Old sessions keep verifying against the older key until they expire |
| `TOKEN_KEYS` | Re-encrypt every stored token | Add a new stamp, then re-encrypt a slice of users per night |

**Session rotation needs no grace-period special case under the keyring.** The ring *is* the grace
period — any key in it verifies, and one older than the 30-day session lifetime can be dropped.

**Token rotation is incremental by design**, which is what `token_key_at` exists for: a nightly job
re-encrypts users whose stamp is not the newest, and the column says exactly who is left.

### The cron is DEFERRED, and deliberately

**ADR-06's promotion bar applies.** A "re-encrypt a slice per night" job is machinery for a table
that currently holds a very small number of rows, and this project's rule is to start with the
simple flat thing and promote it when a real second case appears.

**Build the keyring and the column now; they are cheap and they are what a later cron needs. Build
the cron when the user count makes a manual rotation annoying.** The column costs one integer.

## Open questions

- **Exact `session_key_at` retention.** Dropping a `SESSION_KEYS` entry older than 30 days is
  correct only if the session lifetime never grows. Tie the two together in code rather than by
  comment.
- **Whether `/api/v001/me` keeps a stateless fast path** purely to preserve the broken-database
  diagnostic. Probably not worth the second code path, but it should be a decision rather than an
  omission.
- **Whether admin findings should surface an unrotated key**, per ADR-19's "act / watch / info".
  A key older than some threshold is exactly the shape of a `watch` finding.
