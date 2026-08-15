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

**So `users.token_key_version INTEGER DEFAULT 1` is replaced by a timestamp stamp.** The column has
existed since migration `0001` and **nothing has ever read or written it** — it is inert, so
replacing it costs nothing but a migration.

**Why the timestamp is more than cosmetic here: it makes "which key is current" self-answering.**
The active key is **the largest stamp in the ring**. No second secret naming the active version, no
pointer to keep in step with the map, and no chance of the pointer and the map disagreeing. **An
integer version needs a separate "which one is current" fact; a timestamp carries it.**

### Epoch for arithmetic, ISO-8601 for identifiers

**This one is ISO, and the row timestamps stay epoch. The split is principled, not a compromise.**

| Use | Format | Why |
|---|---|---|
| `created_at`, `resolved_at`, `last_attempt_at`, `first_seen_at` … | **Epoch ms, unchanged** | `src/db/metrics.ts` does real arithmetic on them in SQL — `now - windowDays * DAY_MS` |
| `token_key_at`, `session_key_at`, and the ring's own keys | **ISO-8601, fixed** | A hand-pasted secret read at 11pm during an incident. `1755216000000` is hostile there |

**The ring's key is a JSON object key, so it is a string either way** — `{"1755216000000": …}` is no
more numeric than the ISO form. The "integer" was never an integer where a human reads it.

**And a dated identifier is already this project's house style.** Artifacts are versioned by date,
not by `v1`/`v2` — `FlickrGroupAddr-Architecture-2026-08-14.drawio`. **A keyring entry is a dated
artifact, not a row timestamp.**

### The exact spelling. Pin it, because ISO-8601 has variants that silently mismatch.

```
2026-08-15 12:34:56+00:00
```

| Rule | |
|---|---|
| Width | **Always 25 characters.** Fixed width is what makes a lexical sort valid |
| Separator | **A space.** RFC 3339 §5.6 blesses it for readability, and ISO 8601 permits replacing `T` by mutual agreement of the partners — satisfied when one system writes and reads it |
| Offset | **Always `+00:00`.** Never `Z`, never `+0000`, never a local offset |
| Fractional seconds | **None** |

**`+0000` would be non-compliant, and it is the easy mistake to make.** ISO 8601 forbids mixing
**basic** and **extended** format in one representation; the hyphenated date and colonned time are
extended, so the offset must be too. Python's `strftime('%z')` emits the basic form, which is where
the habit comes from — `datetime.isoformat()` emits `+00:00`.

**No fractional seconds because JavaScript cannot honestly produce them.** `Date.now()` is
milliseconds, so `.789012` would always end `000` — a format claiming precision the runtime does not
have. A key rotated quarterly does not need sub-second resolution.

### ISO is only safe if the format is ENFORCED, and this is the one place it can bite badly

**A ring entry spelled `…56Z` against a column spelled `…56+00:00` is a silent lookup miss, and a
missed key means undecryptable Flickr tokens.** That is the worst failure in this document, and
**epoch integers physically cannot have it.**

**So the format MUST be generated by exactly one helper and validated with `zod` on read**, failing
closed and loudly — the pattern `src/admin/allowlist.ts` already uses for `ADMIN_NSIDS`. **A
hand-typed string literal of this format anywhere in the codebase is a defect.**

**Where epoch would win it back:** if the stamp ever needs arithmetic inside SQL rather than a
bound precomputed in the Worker, or if a second system starts writing into the ring.

## The keyring

**One Worker secret per key class, holding a JSON object from stamp to base64 key.**

```
TOKEN_KEYS    {"2026-08-15 12:34:56+00:00":"<base64 32 bytes>",
               "2026-05-15 09:00:00+00:00":"<base64 32 bytes>"}

SESSION_KEYS  {"2026-08-15 12:34:56+00:00":"<base64 32 bytes>",
               "2026-05-15 09:00:00+00:00":"<base64 32 bytes>"}
```

**The stamp format is pinned below and MUST be validated on read.** A ring whose keys do not all
match the pattern **fails closed**, exactly as `ADMIN_NSIDS` does.

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
the stamp of the key that actually encrypted them, and that same stamp MUST be the oldest entry in
the first `TOKEN_KEYS` ring. **Getting this wrong makes every existing token undecryptable.**

## Sessions become opaque, signed handles

**Today's cookie is a JWS: signed, and fully transparent.** `header.payload.signature`, all
base64url. **Anyone holding the cookie can decode the payload with no key** and read `sub` — the
NSID — plus `iss`, `aud`, `iat` and `exp`. The signature prevents tampering and does nothing to
prevent reading.

**Opaque means the token carries no information — a pure lookup handle.**

### THE ADVERSARY IS NOT THE USER. It is whatever steals the cookie jar.

**This framing is load-bearing and an earlier draft of this file got it wrong**, so it is stated
before anything else. Terry's correction, 2026-08-15:

> Making cookies completely opaque is not preventing a USER from seeing data like their own Flickr
> NSID. It's a move to prevent **MALWARE** from pulling sensitive data like the user's NSID out of
> the cookie store. If malware cracks someone's NSID, I don't want it to be because FGA left that
> exposure open.

**The user already knows their own NSID. Hiding it from them would be theater.** The question is
never *should the owner be prevented from seeing this*. It is **who else ends up holding this
artifact** — an infostealer reading the browser's cookie database off disk, a malicious extension, a
disk image, a synced profile, a backup.

**`HttpOnly` does not help here, and assuming it does is the trap.** It stops JavaScript from
reading the cookie. It does nothing about a native process opening the cookie store directly, which
is exactly what commodity infostealers do first.

**The asymmetry that settles it: a session is revocable and an NSID is not.** Under the opaque
design a thief gets a bearer token that dies at logout or in 30 days, and that the server can kill
on demand. Under the current design they get that **plus a permanent identifier tying the loot to a
real Flickr account.** Nobody can rotate their NSID.

**So opaque sessions and revocation are one control, not two** — and this threat model is what makes
revocation worth the D1 read rather than a nice-to-have.

**It is also ADR-07's instinct applied to a different surface.** That decision minimizes what FGA
*stores*; this minimizes what FGA *hands to a browser to keep on disk*.

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

### What the runtime actually provides, probed 2026-08-15

**Measured against real `workerd`, not recalled.** Recall about installed APIs has been wrong five
times on this project.

| | |
|---|---|
| Digests present | `SHA-1`, `SHA-256`, `SHA-384`, `SHA-512`, and `MD5` as a Cloudflare extension |
| Digests **absent** | `SHA3-256`, `SHA3-512`, `BLAKE2b-256`, `BLAKE3` — *"Unrecognized or unimplemented digest algorithm requested"* |
| HMAC hashes | `SHA-1`, `SHA-256`, `SHA-384`, `SHA-512`. **No SHA-3** |
| `crypto.subtle.timingSafeEqual` | **Present and working** |

**So SHA-3 is not a choice here.** It is not in the Web Crypto specification and Cloudflare has not
extended it. Any design naming SHA-3 is unimplementable on this runtime.

**`crypto.subtle.timingSafeEqual` MUST NOT be destructured.** Pulling it off the object loses the
`this` binding and throws `Illegal invocation` — **at runtime only**, so it passes both typecheck and
lint. Call it as `crypto.subtle.timingSafeEqual(a, b)`. This is the same trap Cloudflare's own skill
records for `ctx`, and it applies to `crypto.subtle` methods too. **Hit while writing this
section.**

**Use it for the HMAC comparison.** A `===` on a MAC is a timing oracle, and the platform hands you
the fix — which is ADR-14's second test, "is the platform already doing it".

### UUIDv7 is ruled out, by this project's own reasoning

**ADR-16 already rejected v7 for `requests.public_id`** because it "republishes its own creation
time" and spends 48 bits on a plaintext timestamp, leaving 74 random against v4's 122. **A session
id is a bearer credential, so that argument binds harder here than it did there.**

### 256 bits, DECIDED 2026-08-15, and the overkill is measurably free

**Terry's call, in his words: *"I want a crypto expert to review the code and cackle at the ludicrous
overkill. It's best practices maxed out."*** That is a legitimate reason on a hobby project, and the
cost turns out to be a rounding error.

**122 bits would have been overwhelmingly sufficient**, and the arithmetic is recorded so nobody
re-derives it: a trillion guesses against ten live sessions gives roughly **2 × 10⁻²⁴** odds of a
hit. OWASP asks for 128-bit identifiers with at least 64 bits of entropy; UUIDv4's 122 nearly
doubles the entropy requirement. **256 prevents no attack that 122 allows.**

**And the signed cookie means guessing is not even the attack.** Without `SESSION_KEYS` a forger
fails the HMAC gate before the database is touched, so the id's entropy is the second line rather
than the first.

**It costs 100 NANOSECONDS.** Both 16 and 32 bytes fit inside a single SHA-256 compression block —
the block is 64 bytes — so the wider id buys the same number of compression calls.

| Operation | Measured |
|---|---|
| `getRandomValues(32)` | **0.45 µs** |
| `randomUUID()` | 0.20 µs |
| `SHA-256` of **16** bytes | 1.65 µs |
| `SHA-256` of **32** bytes | **1.75 µs** |
| `SHA-512` of 32 bytes | 1.90 µs |
| `HMAC-SHA256` sign, 32 bytes | **2.25 µs** |

**Per authenticated request the crypto totals about 4 µs** — one HMAC verify plus one SHA-256 — against
a D1 read measured in milliseconds. **The crypto is well under a tenth of one percent of the
request.** Terry estimated "small double-digit ms at most"; the real figure is three orders of
magnitude smaller.

**These figures are REPRODUCIBLE, and the command is the record.** `test/crypto-bench.test.ts`
re-derives every row:

```
npx vitest run test/crypto-bench.test.ts --disableConsoleIntercept
```

**The gate runs that file on every `npm run check` without the flag.** Its assertions therefore
cannot rot silently, while the table stays out of every green build. **Quote the command's output,
never this table**, if the two ever disagree.

**Caveat on the measurement.** 20,000 iterations each, inside `@cloudflare/vitest-pool-workers` on
the development laptop, **not** on production Cloudflare. Relative costs should hold; absolute
figures may not. The clock **did** advance normally here — 5 ms across a five-million-iteration busy
loop — so the Spectre timer freeze that makes naive benchmarks report zero did not apply in the test
pool. **Do not assume that holds in production.**

**THE ITERATION COUNT IS THE RESOLUTION.** `performance.now()` reports whole milliseconds in this
pool, so the smallest measurable step is `1 ms / iterations`. **A first attempt at 4,000 produced
figures that all landed on multiples of 0.25 µs** — 0.25, 0.50, 1.75, 2.25 — which reads as
precision and is quantization. 20,000 gives 0.05 µs steps. **Lowering it to speed the gate silently
widens every number downstream.**

**Re-measured 2026-08-15 by the committed benchmark**, and the agreement is close enough to trust
the table: `randomUUID` 0.20 identical, `SHA-256` of 16 bytes 1.70 against 1.65, `HMAC-SHA256` 2.30
against 2.25. **Every row within 0.1 µs.**

**If more overkill is ever wanted, SHA-512 costs 0.15 µs more and adds no security** — the input is
one block either way and there is no length-extension exposure to close. Recorded so the option is
priced rather than re-argued.

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
