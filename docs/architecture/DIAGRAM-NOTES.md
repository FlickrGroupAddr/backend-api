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

### The route labels are a PROPOSAL. The code does not serve these paths

**As of 2026-08-16 the diagram is ahead of the implementation.**

| The diagram says | `src/` actually serves |
|---|---|
| `/auth/device-link/start` | `POST /api/v001/device/start` |
| `/auth/device-link/approve` | `POST /api/v001/device/approve` |
| `/auth/flickr/*` | `/oauth/login`, `/oauth/callback`, `/oauth/logout` |
| `/api/v001/*` | Correct, and the only accurate one |

You proposed the rename because the two credential flows should look related, and `/device` reads as
a *"WTF generator"* — it names a standard (RFC 8628 device authorization) rather than the thing it
does here. **Nothing has been renamed.**

**Either the code moves to match or the diagram moves back. Whichever happens, delete this section
in the same commit.**

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

### The plug-in is missing its most important arrow

**There is no edge from the plug-in to `/api/v001/*`.** `PLUGIN_ALLOWED` in
`src/middleware/session.ts` grants it seven routes there, one being
`POST /api/v001/requests/batch` — **the reason the plug-in exists.** The canvas currently shows the
plug-in getting a credential and never spending it.

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
| `16x9` | 100% | 10.1 pt | 100% | A 1920 x 1080 screen or a slide |
| `8.5x14` | 76% | **7.7 pt** | 100% | Legal landscape, and read the warning below first |

**Each wider sheet spreads its extra width evenly between the four columns**, so all three now fill
their printable area completely. `16x9` gains 240 units across 3 gaps, `8.5x14` gains 124.
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

**`pageScale` is how `8.5x14` says "print me at 76%".** draw.io's page in drawing units is
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

## Open

**None of this blocks anything. It is written down so it is not rediscovered.**

- **The User Journey panel is stale against the picture.** It still runs browser-first and calls step
  10 a browser call. **The picture and the panel disagree**, which is the contradiction class above.
- **No Lightroom Classic logo.** Cloudflare and Flickr both carry their marks. **The trap: Lightroom
  Classic and Lightroom (CC) have different icons**, and this diagram means Classic specifically —
  the whole `getPublishServices(nil)` mechanism is Classic-only.
- **The PDF export is CLEAN, inspected 2026-08-16**, and the reason it "looks some different" is a
  font substitution rather than a layout problem. See below.
- **Dead space bottom-right inside the Cloudflare frame**, right of the Retry Worker and below D1. It
  shrank with the 2026-08-16 relayout but did not close.
- **The Nightly Event tile is cramped** — four wrapped lines in a small box.
- **`text_height` measures three tiles out of thirteen.** Every other tile is hand-sized, which is
  why a type change once burst a box while the build reported clean. **Extending it to every text
  tile is the highest-value check still missing.**
- **The visible-run check does not measure a ROUTED edge**, only a straight one. It reports
  `routed, measured by eye`, so it is an honest hole rather than a false pass.
- **No contradiction check exists.** Comparing an edge's endpoints against the journey step that
  cites it is mechanical, and nobody has written it.

---

## The next change: a two-panel User Journey, plug-in first

**Your direction: split login/auth from publish, and draw the auth panel in full.** Your reasoning
decides the level of detail — *"Terry of 2031 will appreciate us being pedantic af today. Hold his   <!-- DIRTY-WORDS-EXEMPT: quoting Terry -->
hand."*

**Why rewrite it:** today's journey runs browser-first and the plug-in appears at steps 12 and 13 as
an afterthought. Per `docs/LRC-CLIENT-NOTES.md` the plug-in is arguably the more important client —
the goal is queueing adds without leaving Lightroom. **The journey should open with the user
clicking "Authorize with FGA".**

**The auth panel drafts to 18 steps and mostly draws SHIPPED behavior.** ADR-24 built the device flow
— `start`, `poll`, `approve` and `deny` all exist. What remains unbuilt is **a page and a Lua
client**, not a design: the `LrHttp.openUrlInBrowser` call on the Lua side, and the `/link`
confirmation page, which ADR-18 puts in Svelte rather than the Worker.

**That page is the only defense against device-flow phishing.** ADR-24 makes the confirmation a page
requirement precisely because no backend route can substitute: nothing auto-approves, and approval is
always a POST a person had to cause.

**Three constraints bind the design, and each has already caught something:**

- **Every journey step needs a badge, and every badge needs a real edge.** The build fails when the
  row count and the badge count disagree, so the step list and the arrows are one decision.
- **Two panels each numbering from 1 means two badges reading "3".** Letter prefixes — `A1`, `B1` —
  solve it with no new color rule and no legend row. **Not yet decided.**
- **"Publish to Flickr as normal" has no edge**, because FGA does not participate. It is context
  above the publish panel, not a numbered step.

**The plug-in needs its own DNS edge, and it now has one.** It is a network client before it is a
browser launcher: it calls `POST /api/v001/device/start` first and must resolve `flickrgroupaddr.com`
itself. It cannot delegate that to the browser, because `LrHttp.openUrlInBrowser` is fire-and-forget
and the `deviceCode` would land in a tab the plug-in cannot read.

**The publish panel drafts to 9 steps**, from the catalog read through preflight and
`POST /api/v001/requests/batch` to the 00:15 UTC sweep calling `groups.pools.add`.
