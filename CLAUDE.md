# FlickrGroupAddr backend-api

**RFC 2119 keywords, and the capitals are load-bearing.** MUST and MUST NOT are absolute. SHOULD is
a strong default a good argument may overrule. MAY is optional.

**Read `docs/architecture/DECISIONS.md` before changing behavior.** This file holds only what a
Claude session needs and the docs do not say.

## ADR-01 outranks everything

**Where an outcome could mean a person declined, treat it as terminal.** FGA submits photos into
queues that unpaid volunteers work through. **Retrying into a human is the one failure this project
will not ship.**

When any two decisions conflict, this one wins.

## Four naming rules, each fixing a real collision

**Never write "DO". Write "Durable Object" in full, every time.** Terry is a long-time DigitalOcean
customer, and the abbreviation collides in his head at exactly the moment he is skimming. **The
diagram build fails if a standalone `DO` reaches the canvas.**

**Decisions are `ADR-nn`, never `D-n`.** Cloudflare's database is called D1.

**Zero-pad anything that will ever sort.** `ADR-02`, not `ADR-7`. The API is `/api/v001/*`. Unpadded
numbers sort `1, 10, 2` and cannot be fixed cheaply once cited.

**Every line a human reads starts with a capital.** Tile labels, edge labels, table cells that are
phrases. **The diagram build fails on a lowercase label.** Legitimately lowercase: identifiers and
paths where case carries meaning, and the continuation of a wrapped sentence. A digit is a correct
first character.

## Dates are versions

No `v1`, `v2`, `draft` or `final`. **Artifacts are dated, and the filename and any in-document date
MUST come from one source.** Bumping a date renames the file — use `git mv`.

## The diagram is generated, and it is gospel

**Edit `scripts/build-diagram.py`, never the `.drawio`.** A hand edit is lost on the next build.

```
python scripts/build-diagram.py
```

It builds and validates in one step, and **refuses to write a diagram that fails any assertion**. It
prints every check as it goes, so **the run is the list.** Most checks exist because a defect got
past everything already there, so a firing check is usually right.

**Distrust the text estimator.** It models what a browser does to wrapped text, and five things it
did not represent at all were found by looking at a render. **When a box looks wrong on screen, the
screen is right.** Changing `CHAR_W` invalidates every hand-set box height, and nothing fails,
because a box that is too large passes.

### RENDER IT AND LOOK, before saying anything about how it turned out

**A green run is not evidence the diagram is good.** On 2026-08-15 it passed every assertion and
Terry's verdict was *"its horrific my bro"*. He was right: 7.9pt body text, four arrows bursting   US-ENGLISH-EXEMPT: quoting Terry
out of one tile, a third of the page empty. **The checks are a RATCHET, not a designer** — each one
exists because a specific defect got past the others, so they prevent the return of known problems
and are blind to new ones.

The loop, and it costs about a minute:

```
python scripts/build-diagram.py && git commit && git push && git rev-parse HEAD
```

Then load `https://viewer.diagrams.net/?lightbox=1&nav=1#U<raw GitHub URL>` and screenshot it.
**Pin the raw URL to the commit SHA, not to `main`** — GitHub's CDN serves a stale copy of `main`
for minutes, and a cached render looks exactly like a change that did not work.

**Claude MUST NOT report a diagram change as done without looking at the render.**

### Two traps that make the type look wrong for reasons the file does not show

- **Inline HTML `font-size:` beats the shape's `fontSize`.** Raising every `fontSize=` in the styles
  left 39 spans at 10pt inside tiles that then declared 12.2pt. One tile read as an eyechart beside
  its neighbors and nothing in the style attributes explained why.
- **`CHAR_W` MUST carry every size the file uses.** It stopped at 20 while the diagram used 26, 28
  and 40, so `text_height` raised `KeyError` for some tiles and measured others against the wrong
  width. **Only three tiles are height-checked at all** — `justification`, `key` and `journey`. The
  rest are hand-sized, so a font change silently overflows them.

### The defect class nothing checks: the picture contradicting the text

**Three defects in one session were the drawing making a claim the document denies.** These are not
geometry, and no assertion compares the two.

| The picture said | The text said |
|---|---|
| An arrow from the Catalog to the browser | Journey step 12: the **plug-in** opens the browser |
| Step 12 drawn dotted | The legend defines dotted as **"Scheduled trigger"** |
| `/*` bold at the start of a line | A route prefix — Terry read it as a C comment |

**Read the diagram as a sentence and check it against `DECISIONS.md` and the User Journey.**

## `npm run check` is the gate

```
npm run check
```

Typecheck (both tsconfigs), lint, the US English check, the Lua block-balance check, 245 tests, the
traceability gate, and the web build. **It MUST be clean before a commit.**

**`scripts/lua-balance.py` runs the REAL Lua 5.1 compiler.** It extracts `Lua Compiler/win/luac.exe` on demand from the SDK archive this repo vendors, and parse-checks every plug-in file. **An earlier version of this line said no `luac` existed here** -- a search for names matching `*Lightroom*SDK*` and `luac*.exe`, against an archive named `LrC_...` holding the binary INSIDE the zip. Neither pattern could have matched. **A search that finds nothing is not evidence that nothing is there.** Its block-balance pass survives as a FALLBACK for a machine without the archive, and the script announces which instrument ran -- a balance pass and a real parse are very different assurances. It is a
block-balance check and **NOT a parser** — it catches a block left open or closed twice, which is
the error that has actually bitten (a `for` loop closed with `}`, JavaScript muscle memory). It
takes a DIRECTORY and refuses to report success on an empty match, so a new plug-in file cannot go
silently unchecked.

**Its first version cried wolf on three files Lightroom loads fine**, because it kept comment text
after stripping the dashes and it read a bare `}` as a mistaken `end` — which is how every Lua table
closes. **A checker validated in only one direction is half-validated**: prove it stays silent on
known-good input as well as firing on known-bad.

### `scripts/us-english.py` enforces the US English standing order

**Terry is American and the rule covers prose, comments, docs, commit messages and identifiers.**
It kept slipping anyway — `scripts/build-diagram.py` printed `badge colour distinct from tile fills`   US-ENGLISH-EXEMPT: quoting the defect
on every run for days. **A rule nobody enforces is a rule written down, not a rule kept.**

**The word list is EXPLICIT and MUST NOT become a pattern.** A regex for `-ise` matches `precise`,
`advertise`, `surprise`, `expertise` and `otherwise`. `analysis` is correct US English while
`analyse` is not, which is why the file lists words rather than stems. **A checker that cries wolf   US-ENGLISH-EXEMPT: naming a banned form
gets ignored.**

**Exempt a legitimate use with `US-ENGLISH-EXEMPT: <reason>` on the line** — quoting somebody else's
text, naming a third-party package, or a fixture that must be misspelled.

**It self-tests on every run**, including against the false positives an `-ise` pattern would
produce. Same guard `scripts/build-diagram.py` puts on its collision detector.

**It reads FILES ONLY.** It cannot see conversation, and it cannot see a commit message already
written. **Those are the surfaces this rule actually slips on most**, so its silence MUST NOT be
read as full coverage.

**This count has now been wrong THREE times, which is why the rule below is absolute rather than a
reminder.** It was documented as 178, the suite rebuild took it to 156, and neither this file nor
the README was updated. It then read 160 while the runner printed 201 — found 2026-08-14 while
catching a cleared session up. **It then read 205 while the runner printed 239** — found 2026-08-15,
during a documentation pass, by running the gate rather than by reading anything.

**Quote the number the runner prints, never one read from a document, and that includes this line.**
**The third miss is the informative one:** two sessions wrote the rule and then updated the count
from a stale document anyway. A number in prose has no mechanism keeping it true, so **the honest
options are to run `npm run check` before quoting it or to not quote it at all.**

**Tests run inside real `workerd`** against real D1 and real Durable Objects. Outbound `fetch` is
stubbed in `vitest.config.ts`, so **a test reaching the real Flickr fails loudly.**

**The lint step is type-aware.** Biome 2.x has a `types` domain, so `npm run check` does analysis
that usually needs `typescript-eslint`. Five such rules are on; `biome.json` is the record.

**Adding a lint rule MUST include proving it can fire.** Write a throwaway file with one deliberate
violation, confirm the rule reports it, delete the file. **A clean run from an inert rule is
indistinguishable from a clean run from a satisfied one**, and a silent rule is worse than no rule
because it counts as coverage.

**Recall about installed package APIs is unreliable and has been wrong five times here.** Read
`node_modules/<pkg>/package.json` and the `.d.ts`. Generate config with the tool's own `init`.

### Every decision is verified, and every test defends one

`npm run check` ends with `scripts/traceability.py --check`, which **fails the build** on any of:

- An ADR that no test block verifies, unless it declares `**Verification: Inspection**`.
- A test block that cites no ADR and carries no `TRACE-EXEMPT: <reason>`.
- A test citing an ADR `DECISIONS.md` does not define.
- `DECISIONS.md` sections out of ascending ADR order.
- The old-to-new renumbering table going missing.

**Numbers encode importance.** ADR-01 governs, and it descends from there. They were renumbered once,
on 2026-08-14. **MUST NOT be renumbered again** — 167 mentions across 65 commit messages already
depend on one mapping table, and a second would make readers chain through two.

`docs/TRACEABILITY.md` is **generated** by the same script. Do not edit it.

**Tag at the `describe` level, not per test.** A block is one coherent risk, which is the
unit an ADR maps onto. Put the tag in the block name so it shows in failure output.

**An honest exemption beats a forced link.** `/health` answers 200 because a health
endpoint should, not because a decision asked for it.

### Before changing the suite, prove it still bites

```
python scripts/mutation-check.py
```

**It breaks the source in 34 specific ways and checks the suite screams at each.**
**This count drifts exactly like the test count above.** It read 25 while the harness ran 34,
found 2026-08-15. Quote what the runner prints. Every mutation is
a decision this project made against — retry a photo a moderator saw, drop `HttpOnly`, reflect the
CORS origin, reuse a crypto nonce.

**A mutation's name SHOULD open with the ADR it attacks**, because `scripts/traceability.py` reads
the tag out of the name and nothing else links the two. An untagged mutation makes the matrix report
`—` for a decision that is genuinely mutation-covered, which understates the safety net rather than
overstating it. Two are untagged on purpose, and `mutation-check.py` says which and why.

**A green suite proves it AGREES with the code, never that it would NOTICE the code being wrong.**
Those are different claims, and only the second one matters when tests are being deleted or
rewritten. **Run it before and after any change to `test/`, and a survivor is a hole.**

**Adding a decision to `docs/architecture/DECISIONS.md` SHOULD add a mutation here.** A rule nothing
can break is a rule nothing is enforcing.

**A decision about build or deploy CONFIGURATION is the honest exception, and it MUST NOT be
"fixed".** `mutation-check.py` runs the Vitest suite, and the suite never reads `vite.config.ts`,
`wrangler.jsonc` or `package.json`. A mutation there reports a survivor and describes a hole that
does not exist, which understates the safety net by inventing a gap. ADR-13, ADR-15 and ADR-21 all
carry `—` in that column deliberately, and each says so in its own text.

## Know the tools before writing code that replaces one

**This is ADR-14 pointed at the toolbox**, and it fails the same way: the cheapest tool is the one
already installed, and it is the easiest to skip, because using it never feels like a decision.

### Cloudflare's agent skills are on disk and MUST be read before Workers code

`wrangler login` installed them under `~/.claude/skills/`. **Read from disk. MUST NOT answer from
recall where a skill applies** — that is the skills' own first instruction, and it already corrected
two runtime gotchas: `crypto.subtle.timingSafeEqual` exists here, and `ctx` **MUST NOT** be
destructured.

| Skill | Use it for |
|---|---|
| `cloudflare` | Workers, D1, KV, R2, bindings, the platform |
| `workers-best-practices` | Whether Worker code is idiomatic |
| `durable-objects` | Durable Object classes, RPC, alarms — ADR-08 |
| `wrangler` | Any `wrangler` command or `wrangler.jsonc` field |
| `agents-sdk` | Read before promoting ADR-06 |

**Ignore the rest for this project** — `cloudflare-one*`, `sandbox-*`, `cloudflare-email-service`
(ADR-07 holds no email address), `turnstile-spin`, `web-perf`.

**Where a skill and this repository disagree, the repository wins.** Cloudflare's skill advises
enabling `nodejs_compat` broadly; ADR-13 refuses it unless a dependency forces it.

### `jq` owns JSON, and `wrangler.jsonc` is the trap

**`jq` MUST NOT be pointed at `wrangler.jsonc`.** It is JSONC. `jq -e '.name' wrangler.jsonc` reports
`parse error: Invalid numeric literal at line 6, column 4` — and line 6 is the first `//` comment.
**The message names a number when the problem is a comment.** Use `Read`.

### The rest of the belt

| The question | The tool | Not |
|---|---|---|
| A range of lines | `Read` with `offset` and `limit` | `sed`, `awk`, `head`, `tail`, `cat` — permission-gated globally |
| Where does this string appear | `Grep` | A language server, which has no symbol graph for prose |
| What does this package expose | `node_modules/<pkg>` | Recall. **Wrong five times here** |
| Anything in the old GitHub org | `gh` | The web |
| Is the code correct | `npm run check` | Reasoning about it |
| What is a long run doing | `Monitor`, filtered to progress **and** failure | Re-reading a log on a hunch |
| Is a domain still `pendingDelete` | RDAP, plus DoH with a control | The Cloudflare dashboard, stale here before |

The global `CLAUDE.md` carries the full table and the reasoning.

## The daily toolchain check

**Standing order: on the first build of each day, confirm `node`, `npm`, `tsc`, every direct
dependency, `compatibility_date` and the `biome.json` schema pin are current.**

**Every answer MUST come from the network, on every run.** Never from training data, never from a
memory file, never from ADR-13's version table, never from this file. **A freshness check sourced
from recall is worse than none, because it looks like a record and is not.**

It runs as `~/.claude/hooks/npm-toolchain-check.py`. **That file's docstring is the specification** —
sources, loudness rules, and the traps. Do not restate it here. Run it by hand with `--probe`.

**Three rules a future session will be tempted to break:**

- **Transitive dependencies are deliberately NOT checked. MUST NOT be reinstated.** Measured here:
  every one of 23 outdated packages was transitive and unfixable. A permanently red banner is
  scenery.
- **"Incremental" means DAILY, not one package at a time.** Apply every available update in one
  sitting, then run `npm run check` once. **The increment is the day.** Taking everything at once is
  safe *because* it is done daily. **The failure to design against is a skipped day, never a large
  batch.**
- **Loud requires all three: the network answered, the answer is a confirmed behind, and Terry can
  act this minute.** Offline is not stale.

## The old FlickrGroupAddr repos are stale reference

The GitHub org holds a decade of abandoned attempts. **Mine them for domain facts. Do not inherit
their architecture.** Precedent is the weakest argument available here.

## Where things live

| | |
|---|---|
| `docs/ORIENTATION.md` | **A cold or compacted session starts here.** A router, not a summary — and it says what NOT to read |
| `docs/architecture/DECISIONS.md` | The rules that bite. Read before changing behavior |
| `docs/architecture/KEY-ROTATION-NOTES.md` | Crypto blast radius, the timestamped keyring, opaque sessions. **Decided 2026-08-15, not built.** Becomes ADR-22 when the code lands |
| `docs/FLICKR.md` | What the API actually does. Several rows contradict Flickr's docs |
| `docs/SETUP.md` | Bring-up, and four traps that cost real time |
| `docs/architecture/*.drawio` | Generated, and gospel. Do not edit |
| `src/adds/classify.ts` | **ADR-02 and ADR-01 as executable code.** Widening its retryable set is the most dangerous edit available |
| `src/sweep.ts` | ADR-06's engine and ADR-03's queue discipline. Its attempt function is injected so the rules test without a network |
| `src/session.ts` | **The only place that knows the cookie's name or attributes.** They were once duplicated, and one copy had silently lost `HttpOnly` |
| `src/oauth/signature.ts` | ADR-14's documented exception. Checked against RFC 5849's own vectors |
| `migrations/` | The schema. Constraints carry the rules, not application code |
| `scripts/build-diagram.py` | The diagram generator and its assertions |
| `web/src/lib/*.ts` | **Where the UI's real logic MUST live.** `tsc` checks these |
| `web/src/**/*.svelte` | Markup and wiring only. Nothing here is typechecked — see below |
| `web/src/lib/outcomes.ts` | **ADR-01's promise, as the sentences a user reads.** Still-open copy |

### The UI has a typechecking hole, and it is architectural

**`svelte-check` peers on TypeScript `^5 || ^6`, and ADR-13 pins 7.0.2.** So nothing typechecks the
inside of a `.svelte` file — not `tsc`, not Biome. This is the same bill TypeScript 7 already
charged for `typescript-eslint`.

**The mitigation is placement, not tooling.** Logic goes in `web/src/lib/*.ts` where `tsc --noEmit
-p web` reads it properly, and components stay thin enough that a mistake is visible. **A component
growing real branching logic is a signal to move it into `lib/`.**

`web/src/shims.d.ts` declares `*.svelte` loosely because Svelte ships no ambient declaration —
verified against `node_modules/svelte` 5.56.9, not assumed.
