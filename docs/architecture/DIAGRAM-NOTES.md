# The architecture diagram

**RFC 2119 keywords. MUST and MUST NOT are absolute. SHOULD is a strong default a good argument may
overrule. MAY is optional.**

**The diagram is generated.** `scripts/build-diagram.py` writes
`FlickrGroupAddr-Architecture-<date>-<sheet>.drawio`, and a hand edit is lost on the next build.
**Edit the generator.**

**It is ONE drawing on three sheets** — `11x17`, `8.5x14` and `16x9`. The content is authored for
tabloid and the other two carry the same picture moved, never resized, so they share one date.
`scripts/diagram_sheets.py` is the roster. **Everything that reads the diagram wants the `11x17`
sheet**, because it is the only one whose coordinates are the authored ones.

**This file holds the things the generator cannot tell you: what the picture claims about the
system, how to print it, and the draw.io behaviors that will waste your afternoon.** It holds no
coordinates — the build prints those, and any written here would be a lie within the week.

---

## READ THIS FIRST IF YOU ARE ABOUT TO BELIEVE THE DIAGRAM

### The route labels are REAL as of 2026-08-18. The code moved to match

**The rename landed.** `src/` now serves `/auth/device-link/{start,poll,approve,deny}` and
`/auth/flickr/{login,callback,logout}`, which is what the canvas has drawn since 2026-08-16. Terry
proposed it because the two credential flows should look related, and `/device` reads as a *"WTF
generator"* — it names a standard, RFC 8628 device authorization, rather than the thing it does
here.

**It removed a real fragility rather than only reading better.** The device routes used to sit under
`/api/v001/*`, where `apiRoutes` registers a blanket `requireSession`. The ONLY thing keeping
`start` reachable without a credential was mounting `deviceRoutes` first. **An exemption bought by
registration order is invisible in the route it protects**, and this repository had already paid for
that once — the same ordering silently took ADR-12's `no-store` header with it. The blanket rule now
has no exceptions.

### SETTLED 2026-08-18: `enter-user-code` is a Worker route, and it now exists

**Every route label on the canvas is real.** The last one was
`/auth/device-link/enter-user-code`, and until that day it was worse than a proposal — it was a
page that did not exist anywhere. `deviceRoutes` handed the plug-in `new URL("/link", UI_ORIGIN)`,
while `parse()` in `web/src/lib/router.ts` resolves exactly `/`, `/queue` and `/admin`. **So the
last step of device linking told a person to visit a page that said there was no such page**, and
the flow could not complete on either side. Nothing failed and 297 tests passed throughout.

**Terry ruled it belongs to the Worker, and the reason is the redirect.** The session cookie is
`HttpOnly`, so a static SPA page cannot tell whether you are signed in. Only the server can — and
journey step 9 requires exactly that: the page answers a signed-out visitor with a redirect to
`/auth/flickr/login`, carrying `returnTo`.

**It is the one route here that cannot use `requireSession`**, which answers `401` with JSON. That
is right for an API and useless to a person in a browser.

**The page posts JSON rather than submitting a form, and that is a CSRF defense.** A urlencoded
form post is a simple request — no preflight, sent cross-origin with cookies — so any site could
approve a device link for a signed-in user. **A "simplification" back to a native form would hand
that away silently.**

### The canvas is scoped to the Lightroom Classic journey, and the web UI is real

**ADR-18 is a Svelte app shell on the same origin. A reader who takes this canvas as the whole system
will conclude there is no browser client.**

**The scoping is structural, not laziness.** Two first-class clients cannot both be drawn as
line-of-flow on one page: their flows interleave — the plug-in starts a device link, the browser
authorizes it, the plug-in resumes — so neither one sequence nor two independent sequences describes
the pair. Every attempt produced crossings, because the real relationship is a mesh.

**Scoping to the plug-in demotes the browser from a CLIENT to a STEP**, and a step only needs the
routes its own flow touches. That deleted the browser's arrow to `/api/v001/*`, which was the edge
making the mesh a mesh.

**Say the scope on the canvas** — a subtitle or a legend row — before this diagram goes anywhere.

### The plug-in's arrow to `/api/v001/*` EXISTS as of 2026-08-17

**This section used to say the canvas showed the plug-in getting a credential and never spending
it.** `e13` now runs plug-in to `/api/v001/*` and carries step 32, *"Plugin performs FGA app
operations against /api/v001/*"*. `PLUGIN_ALLOWED` in `src/middleware/session.ts` grants it seven
routes there, one being `POST /api/v001/requests/batch` -- the reason the plug-in exists.

---

## Printing it

**This is the part you will come back for. Print the `11x17` sheet.**

```
Page          1700 x 1100 drawing units = 17 x 11 inches
Margins       30 units a side = 0.30 in, all four
Content       1640 x 1040 of INK, which is exactly the printable area
Export at     100%.  NEVER "Fit to Page"
```

**Fit to Page is the likeliest way this print goes wrong**, and it has nothing to do with margins.
The content fits the printable area exactly, so any fit pass shrinks it and puts white space back on
all four sides. Adobe Reader defaults to it. **Say "actual size, 100%" at the counter.**

### The other two sheets, and what each one costs

**The build prints these for every sheet on every run.** Read them there rather than here — they
move the moment the content does.

| Sheet | Prints at | Body type | Covers | Use it for |
|---|---|---|---|---|
| `11x17` | 100% | 10.1 pt | 100% | **The print.** The content fits this sheet exactly |
| `16x9` | 100% | 20.2 px | 100% | **A 4K monitor.** 3840 x 2160 at 100% zoom — see below |
| `8.5x14` | 100% | **7.7 pt** | 100% | Legal landscape, and read the warning below first |

**Each wider sheet spreads its extra width evenly between the four columns**, so all three now fill
their printable area completely. `16x9` gains 239.99 units across 3 gaps, `8.5x14` gains 124.04.
`build-diagram.py` derives the columns from the artifact and re-derives them from each written sheet
to prove no column changed width.

### COVERAGE AND TYPE SIZE ARE DIFFERENT THINGS, and this is the trap

**Spreading the columns raised coverage to 100% and moved the type size by ZERO.** Height binds on
both new sheets, so the print scale is `printable_height / content_height` and no amount of width
touches it. **Legal went from 92.97% of the paper to 100% and stayed at 7.7 pt.**

**So `8.5x14` still reproduces the eyechart.** Legal landscape carries 7.9 in of printable height
against tabloid's 10.4. **7.7 pt is below the 7.9 pt that made the first print unreadable.** The
sheet holds 62% of tabloid's printable *area*, so even a redesign that traded height for width tops
out at `sqrt(0.62)` = 78.8%, or 7.96 pt. **Making legal readable means cutting content.**

**The one useful shortcut:** when a dimension binds exactly, the fraction of printable area used is
the ratio of the two aspect ratios. Content 1.5769 against legal's 1.6962 gave 92.97% before the
reflow.

### The `16x9` sheet is measured in PIXELS, and 100 units per inch does not apply to it

**Terry, 2026-08-18: *"make sure 16:9 diagram is native 4K/2160p at 100%."*** The page is 3840 x
2160, and reading that as 38.4 x 21.6 inches of paper is a category error. **draw.io maps one
drawing unit to one pixel at 100% zoom**, so pixels are the only unit this sheet has.

**Native means nobody types a zoom percentage.** A 1920-unit page can reach 4K only if the person
exporting it remembers to ask for 200%, and a forgotten export dialog is exactly the kind of step
that goes wrong once and is never noticed. A 3840-unit page is 4K at 100%.

**So this is the one sheet allowed to scale the content UP** — `Sheet.scale_up` in
`scripts/diagram_sheets.py`, off everywhere else. The content is 1640 x 1040 of ink against a
3760 x 2080 printable area, so the scale comes out **exactly 2.0000** and the 10.1 pt body type
lands on 20.2 px. **That default is load-bearing:** tabloid's printable height is 1040 against
1040 of content, and a sheet allowed to fill would still grow the AUTHORED drawing by any rounding
the fit produced. The reference sheet MUST stay 1:1.

### One open question on the `16x9` spread, raised and not settled

**The gaps there are 98.5, 100 and 100 authored units — 197, 200 and 200 px on the glass — while
the Edge PoP's internal gaps stay at 28.2.** The
drawing reads as four islands rather than one diagram, and the Worker-to-Flickr arrows run a long
way through empty space.

**Terry has not ruled on it.** The obvious alternative is weighting the spread toward the two text
columns on the right — `justification` / `journey` / `key` are independent panels that tolerate a
wide gutter, where the arrows between the Worker and Flickr do not. **That is a design call and he
holds the pen**; this note exists so the observation is not lost with the session that made it.

**`pageScale` is 1 on every sheet now, and the geometry carries the scale instead.** draw.io's page in drawing units is
`pageWidth * pageScale`, so a scale above 1 keeps the drawing on ONE page instead of spilling it
across a 2x2 grid. **That figure is asserted by the build and has NOT been checked against a real
print** — if an export dialog asks for a percentage, the build printed the number.

### Why 0.30 in and not 0.25 in

Every printer grips the sheet at its edge and cannot put ink there. That strip is physical, not a
setting. **Sheet-fed laser engines carry 4–5 mm (0.157–0.197 in), and some specify 6 mm (0.236 in) on
the trailing edge. A sheet-fed engine is also allowed about 1 mm of image-placement drift.**

`0.25 in` is `6.35 mm`. It clears the stated border and **does not clear the border plus the drift.**
`0.30 in` absorbs both and costs `0.1 in` out of a 17 in sheet.

### Margins are measured in INK, not in boxes, and the difference is large

**A geometry is not what the reader sees.** Three corrections separate them, and the generator now
applies all three:

| | |
|---|---|
| A stroke straddles its path | Half of `strokeWidth` paints **outside** the box |
| A text box is taller than its letters | **13.65 units** for the page title alone |
| A routed edge lives in `<mxPoint>` | It is in no tile's `<mxGeometry>` |

**The page title's cap top sits ON the top margin**, which is what you asked for and what the build
asserts. Its *box* therefore starts above the margin, and that is correct rather than a violation.

**All four margins are equal and exact.** The build names the cell that owns each edge, so a failure
says which shape to move.

### The exports, checked against the real files on 2026-08-16

**Both were inspected rather than assumed**, and the PDF settles a question that had been open since
the first print.

| | |
|---|---|
| PDF page box | **1224 × 792 pt = 17.0000 × 11.0000 in exactly**, one page. No Fit-to-Page scaling happened |
| PDF internal space | `5100 × 3300` scaled by `0.24` to points — the same grid as the 300 DPI raster |
| PDF logos | **Vector.** Zero embedded images, so the marks stay sharp at any zoom |
| PNG | **5100 × 3300**, which is 300 DPI on 17 × 11 |

**Why the PDF looks a little different from the browser: the fonts are LIBERATION SANS, not Arial.**
`LiberationSans`, `-Bold` and `-Italic`, subset-embedded. draw.io's export substitutes the
metric-compatible free clone. **Metric-compatible means the advance widths match, so every line break
and every box fit is identical** — only the glyph shapes differ slightly. **It is a cosmetic
substitution, not a layout change.**

**The ink model was verified end to end against the export.** `label_ink_y()` predicts the title's
baseline at **50.052**; the PDF places it at **50.000**. **Off by 0.052 drawing units, which is
0.0005 inch.** So the top margin in the file that actually prints is 29.95 rather than 30.00.

**One caveat worth keeping: the cap-height ratio in the model is Arial's.** Liberation Sans matches
Arial on widths by design; its vertical metrics are close but were not measured here. **If the top
margin ever needs to be exact to better than a tenth of a unit, measure the embedded font rather
than trusting the ratio.**

### Other page facts

- **100 drawing units = 1 inch.** A font size converts straight to points: `fontSize=14` is 0.14 in,
  which is **10.1 pt**.
- **Body type is 10.1 pt, and that number is calibrated rather than chosen.** 7.9 pt made the first
  print an eyechart; 12.2 pt was *"comically huge"*. Ten is the center between two misses in opposite
  directions. **Justify any departure from it.**
- **For a raster export, scale the EXPORT — never the coordinates.** 300 DPI on 11x17 is 5100x3300,
  which you get by exporting this page at 300%. Rewriting the canvas to those numbers would make
  draw.io report a 51x33 inch page and would silently invalidate every absolute threshold in the
  generator. PDF is vector, so none of this applies to it.

---

## What the picture CLAIMS, which is what breaking it would cost

**These are assertions about the system. Break one and the diagram becomes false, not just ugly.**

| Pinned | Because |
|---|---|
| The OAuth Durable Object stack sits **outside** the Edge PoP box | A Worker runs at the nearest PoP; a Durable Object lives in exactly one location |
| `d1` sits **outside** it too | D1 has one primary, and every query crosses to it |
| DNS, the Worker, Secrets, Cron and Retry sit **inside** | All anycast or edge-resident |
| The plug-in has **no arrow to Flickr** | It never calls Flickr. It reads Adobe's publish records out of the catalog |

**Two nested boxes on the left, two nested boxes on the right, and both pairs share both baselines.**
That structural rhyme is what finally made the right column read — your words when it landed were
*"bottom aligning the cloudflare and Flickr boxes is what I needed"*.

### Line style and badge placement mean something. Decided 2026-08-17

**Solid means SYNCHRONOUS TRANSFER. Dotted means ASYNCHRONOUS TRIGGER.** Your definition, and the
Legend now prints it -- it said *"Request / response"* and *"Scheduled trigger"* until 2026-08-18,
which are two examples rather than the rule. A solid arrow on this canvas also covers a Worker
reading its own storage and a Worker reading Secrets, and neither is a request/response pair.

**The word "data" came out because the row WRAPPED, and the estimator could not see it.** The
Legend's rule samples are `display:inline-block` spans, 39px wide plus 10px of margin, and
`text_block` stripped every span before measuring width -- so both rows were measured against a
column 49px wider than the browser lays out. *"Synchronous data transfer"* broke onto a second line
that lost its hanging indent, while the build reported the identical line count and `key`'s slack
never moved off 26. **The render caught it and the estimator now charges an inline-block's width**,
which drops that slack to 11 and fails the band. *"Synchronous transfer"* fits on one line and sits
within a unit of *"Asynchronous trigger"*, so the two rows read as a pair.

**Badge placement is a language, and a reader learns it once:**

| Where the badge sits | What it means | Examples |
|---|---|---|
| A tile's **top-left** corner | The first action on that thing | 1, 4, 14 |
| A tile's **top-right** corner | The last action on that thing | 31, 28, 20 |
| Alone on a run | A one-way action | 2, 11, 27, 29, 32 |
| Paired on one run | A round trip, request then response | 3/5, 8/9, 12/13, 29/30 |

**Three badge sizes, for three situations, and this is NOT drift.** 24 du is the default. 21 du is for
the three tight channels where a 24 would touch a border -- badges 2, 7, 11, 14 and 20 all sit
between two vertical lines under 30 du apart. 30 du is badge 16 and 17 alone, because an isolated
badge on a bare line with no surrounding detail reads smaller than the same badge on a color fill.

### The sweep tiles get no visual cue either. CONSIDERED AND REJECTED

**`Nightly Event`, `Nightly Retry Logic` and the lower arrows on `App Secrets Store` and `SQL
Database` belong to the nightly sweep, not to the auth flow.** They carry no badges and never will --
Auth Data Flow ends at step 32. A reader following the numbers reaches them and has to work out for
themselves that this is a different story.

**Rejected, your call, and the reason is better than the cue would have been:** *"it's the reason the
project exists -- the 'cool, try to work all queues until a group says stop it, that user is at the
max for today'. 2031 Terry will remember THAT much."*

**So the absence of badges IS the signal.** Everything numbered is the auth dance; everything
unnumbered is the thing the auth dance exists to enable. A cue would only restate what the reader
already knows about their own product.

### A repeating arrow gets no special line style. CONSIDERED AND REJECTED

**`/auth/device-link/poll` fires every few seconds for as long as a person takes, while every other
arrow on the canvas fires once.** A dashed or doubled treatment on that one run would say so without
prose.

**Rejected, your call: step 29 says "Plugin POLLS", and that verb already carries it.** A new line
style costs a Legend entry, and the Legend is the one place a reader has to learn something before
the picture works. **Spending an entry to restate a verb is a bad trade.**

### When two clients reach one node, SPLIT THE NODE

**Your call, and the sharpest design lesson on this canvas.** The browser and the plug-in both talked
to the device-link surface. Drawn as one tile, the browser's arrow had to cross the DNS tile and both
of its arrows, and every fix on the table was bad — an orthogonal detour, a re-layout that spent a
horizontal run, or leaving the loop visibly open.

**The routes were never shared.** `start` and `poll` are the plug-in's and are unauthenticated;
`approve` and `deny` are browser-only and carry `requireBrowserSession`. **So the surface splits
cleanly by route and each half sits where its caller already points.** Two straight arrows, zero
crossings, zero routed edges.

**The general form: a node that two callers reach by DISJOINT sub-surfaces is two nodes.** Ask
whether the callers actually share endpoints before spending layout to make one box reachable from
two directions.

### The step badges need their white ring, and the fill is decoration

**Measured, WCAG relative luminance:**

| Pair | Ratio |
|---|---|
| White ring against the `#1A1A1A` arrow | **17.4 : 1** |
| `#003087` against that same arrow | **1.47 : 1** |

**Remove the ring and the badge merges into the line it sits on.** 1.47 is below even the 3:1 floor
for large text. The fill's only job is to hold the digit.

Two alternatives were computed and rejected: white fill dissolves into the page at 1:1, and
Cloudflare orange reaches only 2.58:1 against the page while already belonging to three tiles.

---

## draw.io behaviors that will bite you again

### `exitPerimeter=0` is REQUIRED for any attachment point off a bounding-box edge

**RFC 2119 sense.** Without it, draw.io takes your `exitX`/`exitY` as a **direction**, casts a ray
from the shape's center through it, and returns where that ray crosses the **bounding rectangle**.
It knows nothing about `arcSize` and nothing about artwork inside an image tile.

**The failure is quiet because the endpoint lands CLOSE** — a few units off reads as rendering
imprecision rather than as a style attribute misbehaving.

**A one-unit gap and a four-unit gap are the same bug.** When a tile's half-extents happen to tie at
the corner, the ray exits through the corner itself and the only error left is the arc inset. Do not
read a small gap as close enough; read it as a tile whose proportions were forgiving.

**`arcSize` is a PERCENTAGE, not a radius.** `r = min(w, h) * arcSize / 100`, so the same `arcSize`
gives a different radius on every tile.

**For an image tile, compute the artwork's radius from its own `viewBox`, never from the tile.**

### `exitY` and `entryY` are FRACTIONS, so resizing a tile drags every arrow on it

**This is the single most repeated defect on this canvas.** Change a tile's height and every endpoint
attached to it slides, including runs that are supposed to be dead level. A two-unit drift on a
horizontal reads as sloppiness, and nothing in the diff explains it.

**Recompute each fraction against the new dimension to pin the absolute position.** The build's level
and plumb checks catch this immediately — which is worth remembering, because a design pass with the
checks off will hand you a fresh crop of them.

### An XML comment MUST NOT contain two consecutive hyphens

**This repository's prose uses `--` as an em dash, and an SVG is XML.** A logo file once carried four
of them in a trailing comment. **The failure was silent in every direction**: the file was malformed,
the build base64'd the bytes without looking, draw.io drew nothing, and the run reported success.

**When a logo does not appear, decode the payload and parse it.**

```
ET.fromstring(base64.b64decode(payload))   # names the line and column immediately
```

---

## The checks, and their limits

`python scripts/build-diagram.py` builds and validates in one step and **refuses to write a diagram
that fails**. Every check prints as it goes, so the run is the list.

**They assert RELATIONSHIPS, not coordinates** — *"this edge is level"*, never *"this edge is at
y=388"*. Absolute lines on this canvas have moved on every axis; the requirements never did. That
choice is why the suite survived a redesign that moved every number on the page.

**`CHECKS_ENABLED` in the generator turns them all off for a design pass, and it is a permanent
lever.** See `CLAUDE.md` — it MUST NOT be removed, and turning the checks back on means re-reading
them against the new layout, not flipping the flag.

### Three classes of defect, and only one has checks

| Class | Example | Caught by |
|---|---|---|
| Geometry | Two tiles overlap; an arrow crosses a tile | The build, reliably |
| **Appearance** | 7.9 pt type; four arrows out of one tile; a third of the page empty | **Nothing. Render it and look** |
| **Contradiction** | An arrow says the Catalog opens the browser; the User Journey says the plug-in does | **Nothing. Read the picture as a sentence** |

**The checks are a ratchet, not a designer.** Each exists because a specific defect got past the
others. On 2026-08-15 the build passed every assertion over a diagram you called horrific.

---

## The suite is back on, and what it cost to get there

**Done 2026-08-17.** Terry's bet was right -- twenty-three assertions failed against the
restructured canvas, and most of them were the CHECK being wrong rather than the drawing.
**The build's own output is the current relationship map; this section holds only what the
build cannot say.**

**The two failures worth remembering, because both had been PASSING while describing
something false:**

- **`e3`'s level-run assertion named the OAuth Durable Object** after the arrow had been
  retargeted to `devicedo`. It went green for as long as the two objects sat on one line.
- **Five badges, `n21` to `n25`, were on the canvas and in no placement table.** Every other
  badge check printed `ok` throughout. A hand-written membership list stops covering new
  members silently, so the roster is derived from the artifact now and compared to the tables.

**The estimator was the expensive part, and it was out by 110 units on the Auth Data Flow
panel.** Four terms were wrong at once: an average character width instead of real Arial
advances, bold ignored entirely, the tile's padding hardcoded rather than read, and a line
height rounded to an integer. It agrees with Chrome to about 3 units now.

**Coverage was the estimator's real limitation, not accuracy.** It measured 3 of 25 text-bearing
cells; it now measures every wrapped one, 19 of them, plus a header-clearance check on the two
containers. The roster is derived from the artifact, so a new tile is covered the day it is drawn.
**Only overflow fails** -- a roomy tile is usually sized by the arrows that must reach it, so the
build names the tightest and the loosest and leaves that verdict to the eye.

**THE LAST TENTH STILL BELONGS TO THE EYE.** Arial's `line-height: normal` measures 1.15 and
mxGraph's own constant is 1.2; the rendered canvas sits between them, so no arithmetic here
picks the final row size. Terry bracketed it across three renders -- 12.1 left white space,
12.3 pushed step 32 outside the border, **12.2 is right.** Do not re-tune it from the
estimator alone.

## SETTLED 2026-08-18: every sheet exports at its REAL paper size

**Terry, 2026-08-18: the legal PDF came out 18.43 x 11.19 in, not 14 x 8.5.** The aspect was right
and the size was not, so printing needed *Fit on page* -- *"it's minor but feels stupid"*.

**The cause was arithmetic, and the shrink itself is unavoidable.** The content is 1764 x 1040 units
after the column spread and a legal page is 1400 x 850, so something has to scale. It used to be
`pageScale`: draw.io sizes an exported page as `pageWidth * pageScale`, so a scale of 1.3165 bought
a page big enough to hold the drawing and handed the shrink to the print dialog.

**Now the GEOMETRY carries the scale and `pageScale` is always 1.** The rendered picture is
identical -- same content, same proportions -- and the only thing that changed is the number the
exported file declares.

| Sheet | Page declares | Content scale |
|---|---|---|
| `11x17` | **17.00 x 11.00 in** | 1.0000 |
| `8.5x14` | **14.00 x 8.50 in** | 0.7596 |
| `16x9` | **3840 x 2160 px** | 2.0000 |

**Print every paper sheet at 100%, with Fit to Page OFF.** That instruction is now the same for
both, which is the point. **`16x9` is glass rather than paper** — export it as PNG at 100% and it
comes out 3840 x 2160.

**The two paper sheets MUST NOT be allowed to scale up**, and `Sheet.scale_up` is what keeps them
1:1 or smaller. Lifting the cap for the screen sheet is the whole change; lifting it everywhere
would have grown the authored tabloid drawing, and every threshold in the check suite is expressed
in authored units.

### The refusal to rescale still stands, and it was never about this

`diagram_sheets.py` says the content is authored once at tabloid and never resized. **That is about
the AUTHORED canvas**, where every font size, every hand-set box height and every threshold in the
check suite is expressed. All of them still mean what they meant: **the whole check suite runs in
authored units, and the scale is the last thing that happens on the way out.**

### Two checks make the scale safe, and one of them was blind at first

**A census enumerated every scale-sensitive term from the artifact** -- nine style keys and nine
inline CSS properties -- rather than from memory. `arcSize` is a percentage and the exit/entry pairs
are fractions, so those are named as excluded.

**A census can only list what somebody thought of**, so the build additionally proves the round
trip: the written style and label must be the authored one with every length multiplied by the
scale and **everything else identical**. That check found a real miss immediately -- `spacingTop=-6`
on the browser glyph was never scaled, because the regex was `([\d.]+)` and did not match a
negative.

**It was blind in its first version, and the fix is the useful part.** It began with *"if the tokens
are equal, move on"*, so a term that was never scaled AT ALL looked identical and passed -- it only
caught terms scaled wrongly. **An unchanged scaled key is now a failure.**

**One honest limit: a term deleted from `SCALED_STYLE_KEYS` is invisible to it**, because the check
consults the same list. That is the checker's-configuration-is-part-of-the-instrument problem, and
the defense against it is the census plus looking at the render.

## Open

**None of this blocks anything. It is written down so it is not rediscovered.**
- **No Lightroom Classic logo.** Cloudflare and Flickr both carry their marks. **The trap: Lightroom
  Classic and Lightroom (CC) have different icons**, and this diagram means Classic specifically —
  the whole `getPublishServices(nil)` mechanism is Classic-only.
- **The PDF export is CLEAN, inspected 2026-08-16**, and the reason it "looks some different" is a
  font substitution rather than a layout problem. See below.
- **Dead space bottom-right inside the Cloudflare frame**, right of the Retry Worker and below D1.
  It shrank with the 2026-08-16 relayout but did not close, and it is **241 x 202 units** — the
  largest empty region on the page.
- **Dead space down the LEFT column**, below the Browser glyph. `users` ends at y 687 and the
  bottom rail sits at 1053, so roughly **366 units** of the narrowest column carry nothing.
  Not previously listed here; seen in the render on 2026-08-18.
- **The visible-run check still does not measure a ROUTED edge**, only a straight one. It reports
  `routed, measured by eye`, so it is an honest hole rather than a false pass. **The BADGE checks
  no longer share it** -- they walk the full polyline through an edge's waypoints, and refuse a
  badge on an auto-routed edge whose drawn shape the file does not carry.
- **A contradiction check exists now, in the only form that does not cry wolf.** The obvious
  version -- *the step's named path must be owned by an endpoint of its badge's edge* -- fails
  honestly on step 18, where Flickr redirects the browser to FGA's callback and the path named
  belongs to neither end of that arrow. So the build asserts the two directions that hold without
  exception: **every route the journey names exists on the canvas, and every route tile is named by
  some step.** Which arrow a step belongs to is still unasserted, and that is the honest remainder.

---

## What was actually built, 2026-08-17: ONE panel, 32 steps

**The plan in this section was a two-panel journey with `A1`/`B1` prefixes and roughly 27 steps.
What shipped is one panel called Auth Data Flow, plug-in first, numbered 1 to 32 with no prefixes.**
Terry's framing when it started: *"Terry of 2031 will appreciate us being pedantic af today. Hold his   <!-- DIRTY-WORDS-EXEMPT: quoting Terry -->
hand."*

**The publish panel was never drawn**, so the letter-prefix question never had to be answered. If a
second panel is ever added, that decision reopens.

**The auth flow grew rather than shrank, and every added step came from a question Terry asked:**

| Step | Exists because |
|---|---|
| 4 and 5 | He split the old step 3, which fused a request, an object write and a response into one line |
| 9 | He demanded the walkthrough assume a fresh Windows install, zero cookies, zero DNS cache |
| 20 | He asked whether the Durable Object is deleted or merely times out |
| 30 | He noticed the panel jumped from polling to saving with nothing saying the token arrived |

**Two defects in the DRAWING were found the same way**, neither by any check: the canvas showed one
Durable Object while `wrangler.jsonc` declares two, and `e3` pointed at the OAuth object while the
suite asserted it carried the DEVICE-LINK handshake. That assertion had been passing while describing
something false.

**Naming settled along the way.** `/link` became `/auth/device-link/enter-user-code`, because its
siblings are verbs and "form" names a widget that ages badly. `OAuth Request Token` became
`Flickr OAuth State`, because the object holds the token secret and the return path too. And OAuth's
two token/secret pairs stopped sharing one name -- `Request Token`/`Request Secret` versus
`Access Token`/`Access Secret` -- which a reader would otherwise have taken for one value returned
twice.

### Still true from the old plan, and still binding

- **Every step badge needs a real edge**, and the build compares the row count against the badge
  count. The step list and the arrows are one decision.
- **"Publish to Flickr as normal" has no edge**, because FGA does not participate. If a publish panel
  is ever drawn, that is context above it rather than a numbered step.
- **The plug-in needs its own DNS edge and has one.** It is a network client before it is a browser
  launcher: it calls `POST /auth/device-link/start` first and must resolve `flickrgroupaddr.com`
  itself. It cannot delegate that to the browser, because `LrHttp.openUrlInBrowser` is
  fire-and-forget and the `deviceCode` would land in a tab the plug-in cannot read.
- **The confirmation page is the only defense against device-flow phishing.** ADR-24 makes it a page
  requirement because no backend route can substitute: nothing auto-approves, and approval is always
  a POST a person had to cause.

### State at the end of that pass

**The suite went back on the same day and all three sheets are written again.** What that cost,
and the one number no arithmetic here can settle, is in *The suite is back on* above.

**The route labels are STILL a proposal**, per the section at the top of this file. Terry, the same
day: *"let's not catch the code up just yet. Diagram is future state."*
