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

## The toolchain freshness check is live, daily, and MUST NOT be answered from memory

**Standing order, Terry, 2026-08-14:** on the first build of each day, confirm that this project has
the latest stable `tsc`, the latest of every **direct** npm dependency, the latest `npm`, and the
**LTS** `node`. **Quiet when current. Very loud when not.**

**Transitive dependencies are deliberately NOT checked**, and that **MUST NOT** be reinstated as an
improvement. See below.

**Every answer MUST come from the network, on every run.** Not from training data, not from a memory
file, not from ADR-13's version table, and not from this file. **A freshness check sourced from
recall is worse than no check at all**, because it looks like a record and is not.

| What | Authoritative source, queried every time |
|---|---|
| `node` | `https://nodejs.org/dist/index.json`, newest entry with `lts != false` |
| `npm` | `https://registry.npmjs.org/npm/latest` |
| `typescript` | `https://registry.npmjs.org/typescript/latest`, compared against `node_modules/typescript/package.json` |
| Every **direct** dependency | `npm outdated --json`, which queries the registry itself |

**It runs as `~/.claude/hooks/npm-toolchain-check.py`**, a `PreToolUse` hook gated on this project
appearing in `~/.claude/toolchain-projects.json` with `"npm"` in its `toolchains`. It **never
blocks** — a stale toolchain is worth knowing about and is not worth refusing to build over. Run it
by hand with `python ~/.claude/hooks/npm-toolchain-check.py --probe`, which ignores the daily
suppression and always asks live.

### Volume tracks what Terry can fix, and that is the whole design

**Measured here 2026-08-14: 23 packages were behind and every single one was transitive.** Zero
direct dependencies had drifted. `nanoid` sat at `3.3.18` against a latest of `6.0.1` because
`postcss` pins it there, and **no command the owner can type changes that.**

#### Transitive drift is NOT REPORTED, and reinstating it would be a regression

**Terry's instruction, 2026-08-14, in his words: *"let's drop the warning on outdated
indirect/transitive deps — I want to focus on what I can control. If direct deps pin outdated
indirect deps, telling me that is only wasting my time; I'm not able to fix that."***

**The position moved three times in one afternoon, and the history is the argument.** The first
version put transitive drift in the banner. The measurement above killed that — all 23 were
unfixable, so the banner would have been permanently red. It moved to a quiet counted line. **Terry
then removed it entirely, and that is correct**: a line he cannot act on still costs attention, and
in the npm ecosystem it is non-empty essentially always.

**A future session WILL be tempted to add it back**, because "we check every dependency" sounds more
thorough than "we check the ones you can fix. **It is not.** A checker that reports only actionable
findings is a checker that keeps being read, which is the entire point of the volume doctrine.

**The scope is now exactly what one `npm install` can move.** `npm outdated` runs **without**
`--all`, so transitive packages are never even fetched.

**The speedup is a consequence rather than the motive, and it is large.** Dropping `--all` took the
dependency query from **26.3 s to 1.2 s**, and the whole check from roughly 30 s to **1.5 s** —
measured both ways on this project.

**The banner fires only when ALL THREE of these hold. Terry's wording, 2026-08-14:** *"we should
only go LOUD when we have internet and we KNOW we are behind **and** Terry can take immediate action
on it."*

| # | Clause | What fails it |
|---|---|---|
| 1 | The network answered | Offline, a dead registry, a proxy eating the request |
| 2 | The answer is a **confirmed** behind | An unparsed reply, a missing field, a version that will not compare |
| 3 | **Terry can act this minute** | A fix needing an installer download, or a package pinned by somebody else |

| Finding | Volume | Why |
|---|---|---|
| `npm`, `tsc`, or a **direct** dependency behind | **Unmissable banner** | Each is exactly one `npm install` |
| `node` behind, **with** a version manager or a working `winget` upgrade | **Unmissable banner** | One command |
| `node` behind with **no** such path | Quiet note | An installer download is real, and it is not *immediate* |
| **Transitive** dependencies behind | **Not reported at all** | Not the owner's to fix, so saying it only spends attention |
| Anything unreachable | A short quiet note | **Offline is not stale.** See the global `CLAUDE.md` |

**A banner MUST name what it could not check.** A confirmed-behind on one probe and silence on
another is not a complete picture, and a banner that implies otherwise is the same overclaim in a
different costume.

#### The defect this rule caught, and it had already shipped

**`npm outdated` reports network failure as JSON on STDOUT with exit code 1**, not on stderr:

```json
{"error":{"code":"ECONNREFUSED","summary":"FetchError: request to ... failed", ...}}
```

**Parsed naively that is a dict whose one entry has no `current` field, so every filter skips it and
the function returns "nothing is outdated."** The first version of this check did exactly that.
**On a plane it produced a confirmed-current verdict for a query that never left the machine** —
"could not confirm" wearing the costume of "current", which is the one substitution the whole
doctrine exists to forbid.

**Two guards now stand there**, and both were proven by pointing npm at an unreachable registry: an
explicit `error`-key check, and a rule that **empty stdout only means "nothing outdated" when npm
exited zero.**

#### `winget` is not a Node upgrade path on this machine, and the check verifies rather than assumes

**Established 2026-08-14 when Terry asked why the output said "22".** It does not: `node --version`
is **24.19.0**, which is exactly the newest LTS. **The 22 is winget's package id, and winget's record
here is wrong in a way that matters.**

| | |
|---|---|
| Installed Node | **24.19.0** — the current LTS |
| winget's package id for it | `OpenJS.NodeJS.22` |
| That package's catalog version | **22.23.2** |
| `winget upgrade --id OpenJS.NodeJS.22` | **`No available upgrade found`** |
| An `OpenJS.NodeJS.24` package | **Does not exist** |

winget compares the installed 24.19.0 against its catalog's 22.23.2, concludes the machine is ahead,
and declines to act. **So `winget upgrade` will never move Node here**, and a check that offered it
would hand over a command that runs, succeeds, and changes nothing.

**The hook therefore asks winget whether it can actually perform the upgrade before offering it**, and
treats `No available upgrade found` as "no path". **A fix that looks available and is not is worse
than admitting there is no fix**, because it turns the banner from a call to action into a lie.

**A banner listing two dozen unfixable packages would be red permanently, and a banner that is
always red is scenery.** That is the erosion the global build-chain doctrine spends four paragraphs
refusing, and it is why those packages are not reported at all rather than merely reported softly.

**The direct dependencies ARE the incremental lever**, which is what makes the narrower scope
sufficient rather than merely quieter: bumping one usually carries its transitive tree forward as a
side effect, without anybody having to read a list of things they cannot fix.

**Fixes MUST be offered one at a time**, smallest first, with `npm run check` re-run after each.
**MUST NOT** propose a big-bang update of everything at once.

### Three shapes in `npm outdated --json` that recall gets wrong

**All three were read off real output rather than remembered**, and each one silently corrupts a
naive reader:

- **A value MAY be an array**, not an object, when a package resolves under several dependents.
  Six of 152 entries here took that form. `jq` reports `Cannot index array with string`.
- **`current` MAY be absent.** Platform-specific optional dependencies — the darwin and linux halves
  of `@biomejs/cli-*` — are listed but not installed here. **They are not drift.**
- **`latest` MAY be LOWER than `current`.** `unenv` showed `2.0.0-rc.24` against a `latest` of
  `1.10.0`, because the installed version is a prerelease ahead of the `latest` dist-tag. **A string
  `!=` comparison reports BEHIND forever.** The comparison **MUST** be semver-aware and
  one-directional.

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
