# FlickrGroupAddr backend-api

**RFC 2119 keywords, and the capitals are load-bearing.** MUST and MUST NOT are absolute; SHOULD
and SHOULD NOT are strong defaults a good argument may overrule; MAY is genuinely optional.

## Naming rules, each fixing a real collision

**Never write "DO". Write "Durable Object" in full, every time.** Diagrams, documents, commit
messages, code comments, conversation. Not `DOs`, not `DO-shaped`, not "DO alarms". Terry is a
long-time DigitalOcean customer and the abbreviation collides with that in his head at exactly the
moment he is skimming rather than reading — which is how a years-old diagram gets read. The
diagram build fails if a standalone `DO` reaches the canvas.

**Architecture decisions are `ADR-nn`, never `D-n`.** Cloudflare's SQLite database is called D1 and
this project refers to it constantly, so a decision numbered D1 beside a database named D1 is the
same class of collision.

**Zero-pad any number that will ever be sorted.** `ADR-07` not `ADR-7`; the REST API is
`api.flickrgroupaddr.com/v001/*`. Unpadded numbers sort as `1, 10, 2` and cannot be retrofitted
cheaply once cited. **It paid off the same day it was written** — the decisions reached `ADR-11`
within hours, and unpadded they would have sorted `ADR-1, ADR-10, ADR-11, ADR-2`, burying the
governing `ADR-08` second from last.

**Prefer the unabbreviated form whenever a short form could plausibly mean something else in his
world.** Cloud vendors, storage products, and protocol names are the usual offenders.

## Every line a human reads starts with a capital

**This is a global standing order and it keeps getting broken on this project**, which is why it is
restated here. Tile labels, edge labels, key entries, table cells that are phrases — all of them.
Not "nightly", "drains due requests", "token-encryption key". The build fails on a lowercase label
line.

**The reason is consistency before taste.** A label set that capitalises eleven lines and not the
twelfth reads as *unfinished* rather than as informal, and the eye stops on the odd one out at
exactly the moment someone is trying to skim.

**Two things are legitimately lowercase, and both are listed explicitly in the build check rather
than pattern-matched:** identifiers, paths and domains where case carries meaning
(`flickrgroupaddr.com`, `backend-api`, `flickr.groups.pools.add`), and the continuation line of a
sentence wrapped across two rows. A digit is also a correct first character — numbered steps and
measurements start with one.

## Dates are versions

There is no `v1`/`v2`/`draft`/`final` on this project. **Artifacts are dated, and the filename and
any in-document date MUST come from one source** so they cannot drift. Bumping a date means
renaming the file too — use `git mv` so history follows.

## The architecture diagram is generated

**Edit `scripts/build-diagram.py`, never the `.drawio`.** A hand edit to the XML is lost on the
next build.

```
python scripts/build-diagram.py
```

builds and validates in one step, and **refuses to write a diagram that fails any assertion**. It
prints every check and its verdict as it goes, so **the run itself is the list** — around thirty as
of 2026-08-13, covering collisions, arrow levelness, label fit, edge-PoP containment, badge
placement and pairing, colour distance, boxed-text fit, column alignment, logo aspect and inset,
line styles the legend depends on, the `DO` ban, and capitalisation. Read the output rather than
this paragraph; a count written down here goes stale the first time a check is added.

**Most of those checks exist because a defect got past everything already there**, so when one
fires it is usually right.

**The text estimator is the part to distrust.** It models what a browser does to wrapped text, and
on 2026-08-13 five separate things it did not represent at all were found by looking at a render —
line height, vertical CSS, word boundaries, the hanging indent, and space width. It is much better
now and it is still a model. **When a box looks wrong on screen, the screen is right.** See the
warning above `CHAR_W` in the script: changing those constants invalidates every hand-set box
height on the canvas, and nothing fails, because a box that is too large passes.

## ADR-08 outranks every other decision

**Fail-polite: where an outcome could mean a person declined, treat it as terminal** — even when it
could also mean something retryable. FGA submits photos into queues that unpaid volunteer
moderators work through, and retrying into a human is the one failure this project will not ship.
Read `docs/architecture/DECISIONS.md` before resolving any conflict between the other decisions.

## The old FlickrGroupAddr repos are stale reference

The GitHub org holds roughly a decade of abandoned attempts. **Mine them for domain facts** — the
per-group daily add limits, what the API surface had to cover — and **do not inherit their
architecture**. Precedent is the weakest argument available here.

## The Worker is TypeScript, and `npm run check` is the gate

**ADR-13 and ADR-14 govern the toolchain and the dependency policy, and both are worth reading
before adding either.** The short version: current stable TypeScript, never a `beta`/`rc`/`next`
tag, and take a maintained dependency over hand-written code unless it fails one of ADR-14's four
tests.

```
npm run check
```

runs typecheck, lint, and the whole suite. **It MUST be clean before a commit.**

**Tests run inside real `workerd`** via `@cloudflare/vitest-pool-workers`, against real D1 and real
Durable Objects — hand-mocked bindings would test the mock. Outbound `fetch` is routed to a stub in
`vitest.config.ts`, so **a test that tries to reach the real Flickr fails loudly** rather than
quietly succeeding over the network.

**Recall about installed package APIs is unreliable and has already been wrong five times here.**
Read `node_modules/<pkg>/package.json` for the exports and the `.d.ts` for the names; generate
config files with the tool's own `init` rather than writing them from memory.

## Know the tools on this machine before writing code that replaces one

**Standing order, Terry, 2026-08-14.** Claude **MUST** know what is already installed and reach for
it first. **This is ADR-14 pointed at the toolbox instead of at `package.json`**, and it fails the
same way: the cheapest tool is the one already on the machine, and it is the one most easily skipped,
because using it never feels like a decision.

### Cloudflare publishes agent rules, they are on disk, and they MUST be read before Workers code

**`wrangler login` installed Cloudflare's own guidance for agents under `~/.claude/skills/`.** Read
them from disk rather than fetching them. **Claude MUST consult the covering skill before writing
Workers code and MUST NOT answer from recall where one applies** — that instruction is the skills'
own first line, and ADR-14 records the two runtime gotchas it has already corrected here:
`crypto.subtle.timingSafeEqual` exists in this runtime, and `ctx` **MUST NOT** be destructured.

| Skill | Owns | Load-bearing for FGA |
|---|---|---|
| `cloudflare` | Workers, D1, KV, R2, Pages, bindings, the platform generally | **Yes** |
| `workers-best-practices` | Whether Worker code is idiomatic, and the anti-patterns | **Yes** |
| `durable-objects` | Durable Object classes, RPC methods, alarms, SQLite storage, testing | **Yes** — ADR-02 |
| `wrangler` | Any `wrangler` command, and `wrangler.jsonc` fields | **Yes** |
| `agents-sdk` | Stateful agents, Workflows, queues, scheduled tasks | Adjacent. Read before promoting ADR-04 |
| `web-perf` | Core Web Vitals, load performance | Only once a frontend exists |
| `turnstile-spin` | Bot protection on a form or endpoint | Only if FGA ever takes public writes |
| `cloudflare-email-service` | Sending and routing mail | **No.** ADR-01 holds no email address |
| `cloudflare-one`, `cloudflare-one-migrations` | Zero Trust, SASE, Access, Gateway | **No** |
| `sandbox-stable`, `sandbox-next`, `sandbox-migrate-to-next` | The Sandbox SDK | **No** |

**The right-hand column exists so the list stays usable.** A future session that reaches for
`cloudflare-one-migrations` on this project has been misled by a long list, and a session that never
opens `durable-objects` has been failed by one.

**Where a skill and this repository disagree, the repository wins and the divergence gets recorded.**
ADR-14 already carries the live example: Cloudflare's skill advises enabling `nodejs_compat` broadly,
and ADR-13 refuses it unless a dependency forces the flag.

### `jq` owns JSON, and `wrangler.jsonc` is the trap

**`jq` is installed. Use it for `package.json`, `package-lock.json`, `wrangler d1 ... --json` output,
saved Flickr replies, and the nightly sweep's structured log line.** The sweep logs one JSON object
per run by design — `console.log(JSON.stringify({ event: "nightly_sweep", ... }))` — specifically so a
bad night is queryable rather than readable-if-somebody-happens-to-look.

**`jq` MUST NOT be pointed at `wrangler.jsonc`.** That file is JSONC and carries comments, so `jq`
fails on it. **Verified 2026-08-14:** `jq -e '.name' wrangler.jsonc` reports
`parse error: Invalid numeric literal at line 6, column 4`, and line 6 is the first `//` comment.

**Record the error text, because it misdirects.** "Invalid numeric literal" points at a number, and
there is no number involved — the reader goes hunting through the D1 id and the cron expression for a
malformed value that does not exist. **Read `wrangler.jsonc` with `Read`.** Same shape as the local-D1
`no such table` trap in `docs/SETUP.md`: a confident error message naming the wrong cause.

### The rest of the belt, in one place

| The question | The tool | Not |
|---|---|---|
| A range of lines in a file | `Read` with `offset` and `limit` | `sed`, `awk`, `head`, `tail`, `cat` — **permission-gated in the global `CLAUDE.md`, and the bar is high** |
| Where does this string appear | `Grep` with `output_mode: "content"` | A language server, which has no symbol graph for prose |
| What shape does this installed package expose | `node_modules/<pkg>/package.json` and its `.d.ts` | Recall. **It has been wrong five times here** |
| Anything in the old FlickrGroupAddr org on GitHub | `gh` | The web, or guessing |
| Is the code correct | `npm run check` | Reasoning about it |
| What is a long run doing right now | `Monitor`, filtered to progress **and** failure | Re-reading a log on a hunch |
| Is a domain still `pendingDelete` | RDAP, plus DoH with a control | The Cloudflare dashboard, which has been stale here |

**The global `CLAUDE.md` carries the full table and the reasoning behind each row.** This section
names only what is specific to this project, and it exists because the general rule kept losing to
whatever tool was already in hand.

## Where things live

| | |
|---|---|
| `docs/architecture/DECISIONS.md` | The ADRs, and a verified-facts table where every row records how it was established |
| `docs/SETUP.md` | First-time bring-up, in dependency order. Needs Terry's credentials throughout. |
| `docs/architecture/*.drawio` | Generated. Do not edit. |
| `src/oauth/signature.ts` | OAuth 1.0a signing. Hand-written by ADR-14's documented exception, and checked against RFC 5849's own vectors. |
| `src/adds/classify.ts` | **ADR-07 and ADR-08 as executable code.** The most consequential function here; widening its retryable set is the most dangerous edit available. |
| `src/session.ts` | ADR-06 and ADR-12's cookie contract, and **the only place that knows the cookie's name or attributes.** Set, read and clear all go through it. They were once specified in a helper nothing called and duplicated at two call sites, one of which had silently lost `HttpOnly`. |
| `src/sweep.ts` | ADR-04's nightly engine and ADR-10's queue discipline. Its attempt function is injected so the walking rules test without a network. |
| `migrations/` | The D1 schema. Constraints carry the rules rather than application code. |
| `scripts/build-diagram.py` | The generator and its assertions |
| `scripts/check-diagram-date.py` | SessionStart hook; reports whether the diagram's date is stale |
