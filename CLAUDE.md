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

**It is ONE drawing on three sheets** — `11x17`, `8.5x14` and `16x9`, named in
`scripts/diagram_sheets.py`. The content is authored for tabloid. The other two hold the same four
columns with **the extra width spread evenly between them — moved, never rescaled**, so every font
size and every threshold in the check suite still means what it meant. **Anything that reads the
diagram MUST call `authored_diagram()`** — four scripts globbed the filename by hand and
`sorted(glob)[-1]` silently became the legal sheet.

**Spreading columns raises COVERAGE and never type size.** Height binds on both wider sheets, so the
print scale is `printable_height / content_height`. Legal reached 100% of the paper and stayed at
7.7 pt, under the 7.9 pt Terry called an eyechart. **Only taking height out raises the type.**

```
python scripts/build-diagram.py
```

It builds and validates in one step, and **refuses to write a diagram that fails any assertion**. It
prints every check as it goes, so **the run is the list.** Most checks exist because a defect got
past everything already there, so a firing check is usually right.

**The checks assert RELATIONSHIPS, not coordinates.** *"This edge is level"*, never *"this edge is at
`y=388`"* — that absolute line moved four times on 2026-08-16 and the requirement never did. A number
appears only where the number itself is the rule.

**THE BUILD'S OWN OUTPUT IS THE RELATIONSHIP MAP.** It prints every shared edge, column, level run,
plumb run and gap on each run, derived from the artifact. **Run it before a layout change rather than
reading a table.** `docs/architecture/DIAGRAM-NOTES.md` holds only what the build cannot say — what
the picture CLAIMS about the system, and breaking one of those makes the diagram false rather than
ugly.

### `CHECKS_ENABLED` is a PERMANENT LEVER, and Claude MUST NOT remove it

**Standing order, Terry, 2026-08-16, verbatim: *"Note that I plan to flip that toggle often, so
leave standing orders to never remove it. That's a lever I pull often."*** RFC 2119 sense — **MUST
NOT is absolute.**

**Claude MUST NOT delete `CHECKS_ENABLED` from `scripts/build-diagram.py` as cleanup**, MUST NOT
fold it into a command-line argument, and MUST NOT simplify it away once the checks are green again.
**Finding it set to `True` is NOT evidence it has stopped being needed** — `True` is its resting
state, and the point is that Terry moves it.

**Why he needs it.** The build otherwise refuses to write a diagram that fails any check. That is
right as a default and wrong during a design pass: an assertion pinned to a layout being redrawn
fires on every intermediate state, and **a check that fires on every run is a check nobody reads.**

**That is the WHOLE reason, and it is signal rather than speed.** This block used to add "it also
spends wall-clock time per edit". **Measured 2026-08-17: the full build is 0.197 s median over seven
runs, of which 0.070 s is starting Python.** The suite is worth about 0.13 s, so the speed argument
was never true and it is deleted rather than softened. **The lever stays exactly as it is** — a
defense resting on a claim the clock refutes is a defense that loses the first time somebody times
it.

**The shape is fixed: ONE flag, never commented-out blocks, and a banner on EVERY build.** The
banner is load-bearing — the first time the suite went off, two documents still said so eight hours
later and nothing on screen disagreed.

**Turning it back on is NOT flipping the flag. A suite switched back on after a redesign asserts the
design that no longer exists.** Re-read the suite against the new layout and rewrite what has
stopped being true.

**While it is off, Claude MUST say so when reporting a diagram change.** An unvalidated render and a
validated one look identical in a screenshot.

**Distrust the text estimator.** It models what a browser does to wrapped text, and five things it
did not represent at all were found by looking at a render. **When a box looks wrong on screen, the
screen is right.** Changing `CHAR_W` invalidates every hand-set box height, and nothing fails,
because a box that is too large passes.

### RENDER IT AND LOOK, before saying anything about how it turned out

**A green run is not evidence the diagram is good.** On 2026-08-15 it passed every assertion and
Terry's verdict was *"its horrific my bro"*. He was right: 7.9pt body text, four arrows bursting   DIRTY-WORDS-EXEMPT: quoting Terry
out of one tile, a third of the page empty. **The checks are a RATCHET, not a designer** — each one
exists because a specific defect got past the others, so they prevent the return of known problems
and are blind to new ones.

#### The live preview, and it costs one command

**Start `scripts/preview-server.py` once, then open `http://127.0.0.1:8791/` and leave it open.**

```
python scripts/preview-server.py     # once, in the background
python scripts/build-diagram.py      # every iteration
```

**The tab redraws itself within 400 ms of the build writing the file.** Nothing to copy, nothing to
commit, no CDN. The page polls `/mtime`, reloads only on a real change, and prints the file name, the
build time and a reload counter in a bar across the top — so **a picture that did not change is
visibly distinguishable from a build that did not run**, which no screenshot alone can tell you.

**Screenshot the tab to look at the result.** `mcp__claude-in-chrome__computer` with `zoom` on the
top 22 px reads the status bar when only the counter matters.

**Claude MUST NOT report a diagram change as done without looking at the render.**

#### Three traps this arrangement had to get past, all measured on 2026-08-16

- **`#U` against loopback fails, and it fails DISHONESTLY.** draw.io fetched
  `http://127.0.0.1:8791/...` successfully — the server logged `200` — and still showed `File not
  found`. So its `#U` loader rejects the *result*, not the request, and the error names the wrong
  cause. **`#R` carries the XML in the fragment and renders**, which is what the preview page uses.
- **Chrome gates loopback behind a Local Network Access permission.** The first attempt showed the
  same `File not found` and the server logged **nothing at all**, because Chrome blocked the fetch
  before it left the browser. Terry granted it from the omnibox prompt. **A fresh browser profile
  MUST grant it again**, and the symptom looks exactly like a server that is not running.
- **A `#R` URL is ~10,000 characters, and it MUST stay out of the conversation.** Navigating to one
  directly echoes the whole thing back through the tool result. **The preview page builds it inside
  the browser**, where it costs nothing.

**The old loop was build, commit, push, read the commit hash, then point the viewer at a
`raw.githubusercontent.com` URL pinned to that hash.** It still works and is still the right form for
a link Terry KEEPS — a `#R` URL is a snapshot that does not track the repository, and pinning to a
commit hash rather than to `main` matters because GitHub's CDN serves a stale copy of a branch for
minutes. **Use it to hand him a durable link. Do not use it to iterate.**

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

**Twelve steps, in this order.** Typecheck (both tsconfigs), Biome, the dirty-words check, `ruff`,
`pyright`, **the LSP gate**, the Lua parse check, `selene`, **the ADR-23 Rule 3 import gate**,
`sqlfluff`, 297 tests, the traceability gate, and the web build. **It MUST be clean before a
commit.**

**This list was STALE for three days and nobody noticed** — it still said "290 tests" and named
neither `ruff`, `pyright`, `selene`, `sqlfluff` nor the LSP gate, all added 2026-08-17. **A
description of a gate is not the gate**, and it rots exactly like any other number in prose. Quote
what the runner prints.

**`scripts/lua-imports.py` refuses any `import` of a namespace, or any `Namespace.member` call, that
the pinned LrC SDK does not document.** It reads two committed indexes —
`scripts/lrc-sdk-modules.json` (56 namespaces) and `scripts/lrc-sdk-api.json` (355 members across
38) — because `vendor/`'s archive is gitignored and a fresh clone has no SDK. It **cross-checks the
namespace list against the archive when one is present**, so a stale index after an SDK bump fails
rather than silently approving a dropped namespace. Regenerate with `--regenerate` and
`--regenerate-api`.

**Three traps it exists to remember:**

- **A dynamic `import(name)` is `UNVERIFIABLE`, never allowed.** That hole was real — the gate's
  first run reported `0 undocumented` against the one file that imports `LrUUID`, because the file
  reads candidates out of a table.
- **An empty member list means OBJECT-ORIENTED, not forbidden.** 18 namespaces including `LrPhoto`
  are reached with a colon. **Reading empty as "nothing is allowed" would reject the modules this
  project uses most.** Instance methods are unchecked and the gate **prints how many it skipped**,
  because silence would read as coverage.
- **The scraper MUST NOT require a call paren.** The first one matched `LrFoo.bar (` only and
  reported `LrDigest` as having one member against seven, because the page names its factories in
  prose. **Over-inclusive is the safe direction** — a spurious entry loosens the gate by a name, a
  missing one rejects working code.

**The docs are provably incomplete: `LrSystemInfo` hides 12 of its 23 members, `LrDigest.SHA384` and
`LrUUID.generateUUID` appear nowhere in the archive.** Exempt a deliberate use with
`SDK-UNDOCUMENTED-EXEMPT: <reason>` on the line.

**`scripts/lua-balance.py` runs the REAL Lua 5.1 compiler.** It extracts `Lua Compiler/win/luac.exe` on demand from the SDK archive this repo vendors, and parse-checks every plug-in file. **An earlier version of this line said no `luac` existed here** -- a search for names matching `*Lightroom*SDK*` and `luac*.exe`, against an archive named `LrC_...` holding the binary INSIDE the zip. Neither pattern could have matched. **A search that finds nothing is not evidence that nothing is there.** Its block-balance pass survives as a FALLBACK for a machine without the archive, and the script announces which instrument ran -- a balance pass and a real parse are very different assurances. It is a
block-balance check and **NOT a parser** — it catches a block left open or closed twice, which is
the error that has actually bitten (a `for` loop closed with `}`, JavaScript muscle memory). It
takes a DIRECTORY and refuses to report success on an empty match, so a new plug-in file cannot go
silently unchecked.

**Its first version cried wolf on three files Lightroom loads fine**, because it kept comment text
after stripping the dashes and it read a bare `}` as a mistaken `end` — which is how every Lua table
closes. **A checker validated in only one direction is half-validated**: prove it stays silent on
known-good input as well as firing on known-bad.

### `scripts/claude-dirty-words.py` enforces THREE word lists, not just US English

**Renamed from `us-english.py` on 2026-08-16.** Terry: *"UK english is only ONE of the things   <!-- DIRTY-WORDS-EXEMPT: quoting Terry -->
caught by that script now."* The exemption marker moved with it — `DIRTY-WORDS-EXEMPT`, not the
old one — because a marker naming a scope the file no longer has is the same drift one level down.

| List | Rule |
|---|---|
| **British spellings** | The standing order below |
| **House phrases** | Say CLIENT TYPE, never "kind", when you mean a browser session against a plug-in token |
| **House terms** | **Name the hash family.** `SHA2-256`, never the bare three letters and never `SHA-256`   <!-- DIRTY-WORDS-EXEMPT: naming the banned form --> |

**The hash rule is Terry's, 2026-08-16**, and `SHA-256` does not satisfy it: SHA3-256 exists, so   <!-- DIRTY-WORDS-EXEMPT: naming the banned form -->
the family is implied by convention rather than stated. **The check refuses a match preceded by a
quote, a dot or a hyphen**, which leaves `crypto.subtle.digest("SHA-256", …)`, `LrDigest.SHA256`
and RFC 5849's `HMAC-SHA1` alone — rewriting any of those would break a call or a wire value.

**Terry is American and the rule covers prose, comments, docs, commit messages and identifiers.**
It kept slipping anyway — `scripts/build-diagram.py` printed `badge colour distinct from tile fills`   DIRTY-WORDS-EXEMPT: quoting the defect
on every run for days. **A rule nobody enforces is a rule written down, not a rule kept.**

**The word list is EXPLICIT and MUST NOT become a pattern.** A regex for `-ise` matches `precise`,
`advertise`, `surprise`, `expertise` and `otherwise`. `analysis` is correct US English while
`analyse` is not, which is why the file lists words rather than stems. **A checker that cries wolf   DIRTY-WORDS-EXEMPT: naming a banned form
gets ignored.**

**Exempt a legitimate use with `DIRTY-WORDS-EXEMPT: <reason>` on the line** — quoting somebody else's
text, naming a third-party package, or a fixture that must be misspelled.

### It also checks HOUSE PHRASES, and the list is phrases for a reason

**Say CLIENT TYPE, never "kind", when you mean a browser session against an LrC plug-in token.**
Terry, 2026-08-16: *"I want to be consistent on purging 'kind' where we mean 'lrc plugin or JS
clients'."* The column is `client_type`, the type is `SessionClientType`, and the prose kept saying
`kind` anyway.

**A checker for the bare word would be useless and would be switched off within a day.** `kind` is
the discriminant on `classify`'s dispositions, on `flickr/api`'s results and on `LinkState`, and it
is ordinary English besides — *"the kind thing to do"*, *"kind of comically huge"*. **So the list
holds phrases that can only mean the client type**, and the self-test pins both polarities: four
that MUST fire, eight that MUST NOT.

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
- **`docs/TRACEABILITY.md` being STALE** — not byte-for-byte what the script would generate now.

**Numbers encode importance.** ADR-01 governs, and it descends from there. They were renumbered once,
on 2026-08-14. **MUST NOT be renumbered again** — 167 mentions across 65 commit messages already
depend on one mapping table, and a second would make readers chain through two.

`docs/TRACEABILITY.md` is **generated** by the same script. Do not edit it.

**The staleness check was added 2026-08-16 and it closed a real hole.** `--check` used to validate
only the ADR-to-test relationship, so **ADR-23 sat missing from the matrix for hours while the gate
reported "Traceability holds in both directions"** — the relationship genuinely was intact, and
nothing looked at the generated document. Terry asked whether the matrix had been updated; it had
not, and `npm run check` had passed the whole time.

**The generator is the checker.** `build()` produces the exact text, so `--check` compares it to
disk and needs no second implementation to drift. **Newlines are normalized on both sides** — the
writer emits LF and `core.autocrlf` hands back CRLF, so a raw byte compare would fail on every
Windows checkout and teach everybody to ignore the check.

**A missing ADR is named by number**, because "the file is stale" is not actionable.

**Tag at the `describe` level, not per test.** A block is one coherent risk, which is the
unit an ADR maps onto. Put the tag in the block name so it shows in failure output.

**An honest exemption beats a forced link.** `/health` answers 200 because a health
endpoint should, not because a decision asked for it.

### Before changing the suite, prove it still bites

```
python scripts/mutation-check.py
```

**It breaks the source in 45 specific ways and checks the suite screams at each.**
**This count drifts exactly like the test count above.** It read 25 while the harness ran 34,
found 2026-08-15. Quote what the runner prints. Every mutation is
a decision this project made against — retry a photo a moderator saw, drop `HttpOnly`, reflect the
CORS origin, reuse a crypto nonce.

**A mutation's name SHOULD open with the ADR it attacks**, because `scripts/traceability.py` reads
the tag out of the name and nothing else links the two. An untagged mutation makes the matrix report
`—` for a decision that is genuinely mutation-covered, which understates the safety net rather than
overstating it. Two are untagged on purpose, and `mutation-check.py` says which and why.

### Anchor a mutation to its CONDITION, never to the code around it

**This cost two re-cuts on 2026-08-16 alone.** An anchor that spans a check and its neighbor breaks
the moment anything is inserted between them, and the two edits that broke it were both routine:
`consume` grew a return field, and `poll` grew a throttle.

**The harness said so both times — `SKIPPED, anchor appears 0 times` — and that is the design
working.** A mutation whose anchor has drifted defends nothing, and a silent skip would have read
as coverage. **A SKIPPED mutation is a SURVIVOR**; treat it as a hole, not as a warning.

So anchor on the thing the mutation is actually about. `got.byteLength !== want.byteLength || …`
survives an edit two lines away; `return …;\n}\n\nif (attempt.denied) {` does not.

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
| `scripts/diagram_sheets.py` | **The sheet roster, and the one place that resolves a diagram path.** Underscored because it is imported, not run |
| `web/src/lib/*.ts` | **Where the UI's real logic MUST live.** `tsc` checks these |
| `web/src/**/*.svelte` | Markup and wiring only. Nothing here is typechecked — see below |
| `web/src/lib/outcomes.ts` | **ADR-01's promise, as the sentences a user reads.** Still-open copy |

## Language tooling compliance, against the global standing order

**Terry, 2026-08-17: every language in a project MUST have a language server AND a
best-of-breed linter at best-practice pedantry, XOR a written override in this file put
there by Terry and only Terry.** The full order and the method are in `~/.claude/CLAUDE.md`.
**Claude MUST NOT write an override**, and MUST report a gap rather than proceeding past it.

Tracked file counts as of 2026-08-17.

| Language | Files | Linter | LSP | State |
|---|---|---|---|---|
| TypeScript | 50 | `biome`, 8 rules past `recommended` | **pending** | Version-gated to TS 7.1; `npm run lsp` turns red on its own |
| Python | 13 | `ruff`, 20 families | `pyright-lsp` | **Equipped** |
| Lua | 9 | `selene` + `lua-balance.py` + `lua-imports.py` | `lua-lsp` | **Equipped** |
| SQL | 6 | `sqlfluff`, parser only | — | **Equipped**, and read why below |
| **Svelte** | **4** | none — Biome cannot read the template | none | **NOT COMPLIANT** — blocked by the same TS 7 pin, ADR-13 |
| CSS / HTML | 1 each | `biome` covers CSS | — | One file each |

**Svelte is the one gap left, and it is the only one with no tool to install.**
`svelte-check` peers on TypeScript `^5 || ^6` against ADR-13's 7.0.2. **It needs Terry's
written override or the same 7.1 release everything else is waiting on.**

### `sqlfluff` earns its place as a PARSER, and the numbers are funny

**A bare run on 6 migrations reported 375 findings, and not one was a defect.** 373 were
`layout` — including 82 objecting to the hand-aligned column formatting that makes these
files readable — and the other 2 were false positives: `AL03` on an
`INSERT INTO t (cols…) SELECT …`, where the target columns come from the INSERT list so a
SELECT alias names nothing.

**Terry's reaction is the right one: *"we have like 20 lines of SQL. That's hilarious."***
Measured, it is 176 lines of actual SQL across 40 statements, under 194 lines of comment.
**2.1 findings per line of SQL, all of them noise.**

**So `exclude_rules = layout, aliasing.expression`, and what remains is the parser.**
Nothing else in `npm run check` parses SQL — D1 discovers a malformed migration at apply
time, which is the worst possible moment. **Proven to fire**: a deliberate `CREATE TABEL`
draws an unparsable violation. **The yield is zero today and the point is migration #7.**

### Lua is the clearest gap, and both halves exist

**Surveyed 2026-08-17, and the survey is recorded because "there wasn't one" needs
evidence:**

| Candidate | Verdict |
|---|---|
| `LuaLS.lua-language-server` | **On winget at 3.18.2.** One command. Pairs with the marketplace's `lua-lsp` plugin |
| `selene`, crates.io 0.31.0 | **The linter.** Rust-based, so `cargo` — already on this box — installs it. 135,940 downloads, updated 2026-05-21 |
| `luacheck` | The real one is a LuaRocks package and needs a Lua runtime plus luarocks |
| **npm `luacheck`** | **AN IMPOSTOR. MUST NOT be installed.** Version 0.1.2, "luacheck bindings for Node.JS", from `za-creature/node-luacheck`. **Third name-collision trap found today** — see the ruff one in `~/.claude/CLAUDE.md` |

**What this project already has is not nothing, and that matters to the decision.**
`scripts/lua-balance.py` runs the REAL Lua 5.1 compiler out of the vendored SDK, and
`scripts/lua-imports.py` refuses any SDK namespace or member the pinned archive does not
document. **That is stronger than a generic linter for the one failure that has actually
bitten here.** What is missing is the language server and a general-purpose linter.

**`selene` needs a standard-library definition for the Lightroom globals** — `import`,
`LrTasks` and the rest — or it reports every SDK call as undefined. That is a real setup
cost and it is the honest reason this is a decision rather than a one-liner.

### The UI has a typechecking hole, and it is architectural

**`svelte-check` peers on TypeScript `^5 || ^6`, and ADR-13 pins 7.0.2.** So nothing typechecks the
inside of a `.svelte` file — not `tsc`, not Biome. This is the same bill TypeScript 7 already
charged for `typescript-eslint` — **and for the TypeScript LANGUAGE SERVER, which is the third item
on that tab.** The `typescript-lsp` plugin drives `tsserver`, and **TypeScript 7.0.2 ships no
`tsserver` at all**: `node_modules/typescript/lib` holds `tsc.js` and nothing else. Using it would
mean a second, older TypeScript analyzing this code with a different compiler than the gate.
**Pending until the native TS 7 language server lands, same 7.1 milestone. See ADR-13.**

**Python is not in that boat.** `pyright-lsp` is enabled globally, and it catches the one thing
ruff structurally cannot: **ruff checks that an annotation EXISTS, pyright checks that it is TRUE.**

**The mitigation is placement, not tooling.** Logic goes in `web/src/lib/*.ts` where `tsc --noEmit
-p web` reads it properly, and components stay thin enough that a mistake is visible. **A component
growing real branching logic is a signal to move it into `lib/`.**

`web/src/shims.d.ts` declares `*.svelte` loosely because Svelte ships no ambient declaration —
verified against `node_modules/svelte` 5.56.9, not assumed.
