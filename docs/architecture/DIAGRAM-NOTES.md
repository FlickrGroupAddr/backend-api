# The architecture diagram: printing it, and changing it

**RFC 2119 keywords. MUST and MUST NOT are absolute. SHOULD is a strong default a good argument may
overrule. MAY is optional.**

**The diagram is generated.** `scripts/build-diagram.py` writes
`FlickrGroupAddr-Architecture-<date>.drawio`, and a hand edit is lost on the next build. This file
records what the generator does not say about itself: how the artifact prints, and how a layout
change is actually made.

**`CLAUDE.md` carries the render loop and the traps a Claude session hits.** This file is about the
artifact. Where they overlap, `CLAUDE.md` wins for procedure and this one for facts about output.

## THIS DIAGRAM IS SCOPED TO THE LIGHTROOM CLASSIC JOURNEY

**Terry, 2026-08-16: *"For this diagram I'm pretending we have no web client and that rescues
this."*** He is right that it rescues it, and the reason is structural rather than convenient.

**Two first-class clients cannot both be drawn as line-of-flow on one canvas.** Their flows
interleave — the plug-in starts a device link, the browser authorizes it, the plug-in resumes — so
neither one sequence nor two independent sequences describes the pair. Every attempt produced
crossings, because the real relationship is a mesh.

**Scoping to the plug-in demotes the browser from a CLIENT to a STEP**, and a step only needs the
routes its own flow touches. That deleted the browser's arrow to `/api/v001/*`, which was the edge
making the mesh a mesh.

**THE WEB UI GENUINELY EXISTS — see ADR-18, a Svelte app shell on the same origin.** A reader who
takes this canvas as the whole system will conclude there is no browser client. **Say so on the
canvas**, in a subtitle or the legend, before this diagram goes anywhere.

### What that scoping bought, in one table

Five route tiles, five straight horizontals, no crossings and no routed edges:

| Line | Route | Caller |
|---|---|---|
| 388 | `/auth/device-link/start` | plug-in |
| 430 | `/auth/device-link/poll` | plug-in |
| 472 | `/api/v001/*` | plug-in |
| — | *the DNS band, 483 to 543* | *separates the two callers* |
| 554 | `/auth/device-link/approve` | browser |
| 596 | `/auth/flickr/*` | browser |

**The plug-in tile spans 370 to 490 for exactly one reason: so its three exits land on `0.15`, `0.5`
and `0.85`.** That evenness was not aimed at. It falls out of a 120-tall tile whose three targets sit
42 apart, and it is a good check that the geometry is right.

**The User Journey panel is now STALE against the picture.** It still describes a browser-first
ordering and calls step 10 `flickrgroupaddr.com/api/v001/*` as a browser call. **The picture and the
panel disagree**, which is the defect class this file warns about, and it is the last one open.

## THE ROUTE LABELS ARE A PROPOSAL. THE CODE DOES NOT HAVE THESE PATHS

**As of 2026-08-16 the diagram is AHEAD of the implementation**, and a reader who takes the Worker's
route tiles as fact will be wrong about every one of them.

| The diagram says | `src/` actually serves |
|---|---|
| `/auth/device-link/start` | `POST /api/v001/device/start` |
| `/auth/device-link/approve` | `POST /api/v001/device/approve` |
| `/auth/flickr/*` | `/oauth/login`, `/oauth/callback`, `/oauth/logout` |
| `/api/v001/*` | correct, and the only accurate one |

**Terry proposed the rename; nothing has been renamed.** He wanted the two credential flows to look
related, and `/device` read as a *"WTF generator"* — his words — because it names a standard
(RFC 8628 device authorization) rather than the thing it does here.

**So this is a picture-contradicts-the-code defect DELIBERATELY INTRODUCED**, which is a different
animal from the accidental kind the checks were built for. It is fine while it is a proposal being
looked at. **It becomes a trap the moment anyone forgets.** Either the code moves to match, or the
diagram moves back — and whichever happens, delete this section in the same commit.

**Also still missing, and NOT caused by the rename: an arrow from the plug-in to `/api/v001/*`.**
`PLUGIN_ALLOWED` in `src/middleware/session.ts` grants the plug-in seven routes there, one of them
`POST /api/v001/requests/batch` — **the reason the plug-in exists.** The canvas currently shows the
plug-in obtaining a credential and never spending it.

## Printing

### The canvas is 100 units per inch, and that is why the page is 1700x1100

drawio's coordinate space is **100 units to the inch**. Letter is `850x1100`, A4 is `827x1169`, and
17x11 landscape is exactly **`1700x1100`**. A font size converts straight to points: `fontSize=14`
is 0.14 in, which is **10.1 pt**.

### Body text took TWO corrections, and the second one is the record worth keeping

| Body text | 2026-08-14 | 2026-08-15 | **2026-08-16** |
|---|---|---|---|
| Tile text | `fontSize=11` — 7.9 pt | `fontSize=17` — 12.2 pt | **`fontSize=14` — 10.1 pt** |
| Tile headings | — | `fontSize=19` — 13.7 pt | **`fontSize=15` — 10.8 pt** |
| Journey panel | `font-size:14px` — 10.1 pt | `font-size:16px` — 11.5 pt | **`font-size:13px` — 9.4 pt** |
| Step badges | `fontSize=22` — 15.8 pt | `fontSize=26` — 18.7 pt | **`fontSize=20` — 14.4 pt** |
| Page title | — | `fontSize=40` — 28.8 pt | **`fontSize=28` — 20.2 pt** |

**7.9 pt is footnote size**, and it made the first 8.5x11 print unreadable. Terry called it an
eyechart, and the fix was type rather than page size.

**Then 12.2 pt overshot.** Terry, 2026-08-16: *"the current text across the diagram is kind of   <!-- DIRTY-WORDS-EXEMPT: quoting Terry -->
comically huge. I appreciate you dialing it up but we overshot some. This will be on an 11x17 in
piece of paper in front of me and I have 20/20."*

**So the target is ABOUT 10 pt for tile body on 11x17, and that number is now measured from two
misses in opposite directions rather than guessed.** A future session moving type SHOULD treat
10.1 pt as the calibrated center and justify a departure from it.

### TWO TRAPS a type change walks straight into

**Inline HTML `font-size:` beats the shape's `fontSize`.** The 2026-08-15 pass changed only one of
them and left 39 spans at the old size inside tiles declaring the new one — one tile read as an
eyechart beside its neighbors and nothing in the style attributes explained why. **Change both, in
one pass.** `scripts/build-diagram.py` is rewritten by a regex over both forms for exactly this
reason.

**Shrinking type leaves every hand-sized box too roomy, and a box that is too large passes every
other geometric assertion in the file.** The slack check is the one that catches it: the 2026-08-16
pass left `justification` at 64px of slack, `key` at 47 and `journey` at 207 against a 45px ceiling,
and all three had to be re-tightened. **`CHAR_W` MUST carry every size the file uses** or
`text_height` raises `KeyError`.

### The coordinates MUST NOT be scaled to chase a pixel count

**A 300 DPI 11x17 PNG is 5100x3300, and the way to get it is to export this page at 300%** — not to
rewrite the canvas as `5100x3300`.

| | Inches | Pixels at 300 DPI |
|---|---|---|
| Full page | 17 x 11 | **5100 x 3300** |
| Live area, quarter-inch margins | 16.5 x 10.5 | **4950 x 3150** |

Scaling the numbers would make drawio report a **51x33 inch page**, and it would silently invalidate
every absolute threshold in the generator — the badge band `NEAR_MIN, NEAR_MAX = 24.0, 32.0`, the
text estimator's `CHAR_W`, every hand-set box height. **None of them would fail. They would stop
meaning anything**, which is worse.

**For PDF none of this applies.** PDF export is vector and therefore resolution-independent.

### Margins are a quarter inch, because that is a hardware fact

Every printer grips the sheet at its edge and cannot put ink there. That strip is the minimum
margin, and it is physical rather than a setting.

| Printer class | Sides and top | Bottom |
|---|---|---|
| Laser | ~0.16 in (4 mm) | same |
| Inkjet, plain paper | ~0.12 in (3 mm) | **often 0.5 in** |

The bottom edge is the outlier: an inkjet releases the trailing edge of the sheet before it finishes
printing, so it reserves extra room. A laser pulls the sheet through a fuser and stays symmetric.

**0.25 in clears every laser device and the sides and top of every inkjet.** Terry prints on an
enterprise color laser at FedEx Office, which is the safe case.

### The page size matters most when it is exactly right

**Measured 2026-08-16 from the ARTIFACT, not the template**, because the question is what would
actually print:

| | |
|---|---|
| Page | `1700 x 1100` — 17 x 11 inches |
| Printable area, quarter-inch margins | **`1650 x 1050`** |
| Content bounds | x 5 to 1655, y 20 to 1050 |
| Content size | **`1650 x 1030`** |
| Scale | **100.0%** — width binds exactly, height has 20 to spare |

**So export WITHOUT "Fit to Page".** That option is now the wrong choice: it would shrink a drawing
that already fits.

**This reverses the instruction that stood from 2026-08-14 to 2026-08-16**, when the content was
`1770 x 1303` — 4% over in width and 18% over in height — and Fit to Page was the only way to get a
single sheet. **A future session finding an old note that says otherwise is reading history.**

**Three changes closed that gap, and none of them was a rescale:** the step badges came off (`n7`
hung to y=1327, 227 units below the page), the Cloudflare frame lost 140 units of height, and the
right column narrowed from 350 to 330 — the last 20 units of width.

**THE MARGIN NOW BINDS, and that is the cost of fitting exactly.** At 1650 of 1650 there is zero
slack in width. A driver asked to fit a mismatched page would scale a percent or two and absorb a
small overflow; there is nothing left to absorb. **Anything that widens the canvas breaks the 1:1
fit immediately**, and the two outer columns — `lrcapp` at x=5 and `journey`/`key` ending at
x=1655 — are what pin it.

**Vertical headroom is 20 units, or 0.2 inch, for the whole sheet.** The lowest ink is not a tile:
it is `e11`'s routed run at **y=1050**, the Browser-to-Flickr-API arrow. Next below it is `cfframe`
at 1005. **So the run has 45 units of clearance it does not need**, and raising it to about y=1020
would free roughly 30 more units at no visual cost. Not done, because nothing needs the room yet.

**`check_page_fit()` in the generator does NOT see that run.** Its regex matches `<mxGeometry>` and
a waypoint is an `<mxPoint>`, so it measures to y=1005 and under-reports the content height by 45.
It also compares against the full page rather than the printable area. **Treat its output as a
lower bound until that is fixed.**

## Changing the layout

### The generator refuses to write when a check fails, and that sets a trap

**This is correct behavior and it bites every helper script.** While the build is red, the `.drawio`
on disk is the last **green** layout. Anything that parses the artifact to answer a question about
the current layout gets a correct answer to a stale question.

That happened: a helper reported that Cron and the Retry Worker "share NO band" while the working
grid overlapped them by 95 px. **A tool that inspects the layout MUST read
`scripts/build-diagram.py`, not the `.drawio`.** Every geometry and style attribute in the template
is a literal, so a regex over the source is exact.

### RECOMMENDED, not built: make the grid a data table inside the generator

**Today the tile rectangles live as literals inside the XML template**, scattered through ~1,400
lines. A layout change means editing many `<mxGeometry x=... y=... width=... height=.../>` strings
by hand and then re-deriving every edge anchor and badge position that depended on them.

**The 2026-08-15 relayout was done with an external toolchain that simulated the better design:** a
`GRID` dict of `id -> (x, y, w, h)`, checked against the generator's own invariants **on paper**
before the generator was touched, then applied mechanically. That caught a page overflow and four
tile collisions before a single line of the generator changed.

**A future session SHOULD promote `GRID` into `build-diagram.py` itself** and interpolate the
geometry from it. The payoff is that a layout change becomes one edit to one table, and the
invariants can be checked before the XML is built rather than after.

**It was NOT done on 2026-08-15 deliberately.** Checking in the external grid would have created a
second source of truth for the same coordinates, and two copies that must be re-applied by hand
drift. This project's rule is that the diagram is generated and gospel; a half-refactor breaks that
rule in a way the whole toolchain exists to prevent. **Do it properly or leave it alone.**

### `exitPerimeter=0` is REQUIRED for any attachment point off a bounding-box edge

**RFC 2119 sense.** An `exitX`/`exitY` or `entryX`/`entryY` pair that names a point on a rounded
corner, or anywhere inside the bounding box, **MUST** carry `exitPerimeter=0` / `entryPerimeter=0`
on the same edge. Without it draw.io silently relocates the endpoint.

**The default is `1`, and it does not mean what the name suggests.** draw.io takes the fixed point,
draws a ray from the shape's center through it, and returns where that ray crosses the **bounding
rectangle** — `mxRectanglePerimeter`. That function knows nothing about `arcSize`, and nothing about
the artwork inside a `shape=image` tile. **The fraction you wrote is used only as a direction.**

**Measured 2026-08-16**, and it cost three rounds of "that still is not touching":

| | |
|---|---|
| Asked for | `(156.31, 437.31)` — 45° on `lrc`'s bottom-right arc, `r=12.6` |
| draw.io drew | `(160, 440.25)` — the box's right edge, just above the corner |
| Visible result | An arrowhead floating in white space **outside** the rounded outline |

**The failure is quiet in the worst way: the endpoint is CLOSE.** It lands a few units off, which
reads as a rendering imprecision rather than as a style attribute doing something. Two earlier
attempts moved the fraction instead of fixing the cause, and both looked like partial progress.

**An image tile makes it worse, because the artwork's own corners are invisible to the geometry.**
`users` is a 130x104 box holding a `viewBox="0 0 640 512"` glyph whose monitor has a 64-unit corner
radius. Scaled, that is `r=13.0`, so the box's top-right corner sits **13 units of empty space** away
from anything drawn. **Compute the artwork's radius from its own `viewBox`**, never from the tile.

```
# 45 degrees on a corner of radius r, bottom-right:
#   cx, cy = x + w - r, y + h - r
#   px, py = cx + r/sqrt(2), cy + r/sqrt(2)
# then express px, py as fractions of the box, and set exitPerimeter=0
```

**`arcSize` is a PERCENTAGE, not a radius.** draw.io computes `r = min(w, h) * arcSize / 100`, so the
same `arcSize=12` gives a different radius on every tile. On this canvas it ranges from **4.32**
(`dns`, 120x36) to **32.88** (`api`, 300x274).

#### The symptom SIZE varies, and a small one is not a small bug

**`entryPerimeter=1` sometimes returns the corner unchanged, which hides the same defect behind a
1-unit gap instead of a 4-unit one.** The projection lands wherever the center-to-point ray crosses
the bounding rectangle. When a tile's half-extents happen to tie at the corner — `dns` is 120x36,
and its corner sits at exactly `(60, 18)` from center — the ray exits through the corner itself, so
the returned point is the box corner and the ONLY error is the arc inset.

**So a gap of one unit and a gap of four units are the same bug.** Do not read a small gap as
"close enough"; read it as a tile whose proportions happened to be forgiving.

#### TWO rounded corners facing each other need a different formula

45° is correct when one end is a corner and the other is not. **When both ends are corner arcs, the
shortest bridge is the line between the two arc CENTERS**, and each endpoint sits its own radius
along that unit vector. Used by `e14` (`api` to `d1`) and `e15` (`retry` to `d1`).

```
# nearest point pair between two rounded corners:
#   c1, c2 = the two arc centers
#   u      = (c2 - c1) / |c2 - c1|
#   p1     = c1 + r1 * u        # leaves the first arc
#   p2     = c2 - r2 * u        # enters the second
```

**45° is the special case of this where the corners are diagonally opposed** — `e15`'s unit vector
came out `(0.70711, -0.70711)` on its own, which is a useful check that the arithmetic is right.

#### Resizing a tile DRAGS every arrow attached to it

**`exitY` and `entryY` are fractions of the box, so changing a tile's height moves every endpoint on
it.** This is not a corner problem and it has bitten repeatedly:

| Change | Broke | Fix |
|---|---|---|
| `api` grew 244 to 274 | `e3`, `e9`, `e14` | Recompute each `exitY` to pin its absolute `y` |
| `flickrapi` grew 380 to 398 | `e9`, `e10` | Same, for `entryY` |
| `users` shrank 112 to 104 | `e22`, `e13` | Same |
| `d1` narrowed 190 to 169 | `e14`, `e15` | Recompute the nearest-point pairs |

**A horizontal run is the case that matters**, because a 2-unit drift reads as a mistake rather than
as a change. `e18` and `e3` share `y=388` and carry the device-link handshake straight across the
canvas as one line; `e9` and `e10` land on `flickrapi` at `y=536` and `y=860`.

### Step badges: ON the line now, and the ring is what makes them work

**Terry moved them onto the line on 2026-08-16.** They used to sit BESIDE their arrow, and that
changes which constraint binds. Beside the line, the limit was the shortest visible run — `e4`,
Worker Secrets to the API Worker, at 30 units. **On the line, run length stops mattering entirely**
and the limit becomes the spacing between two parallel arrows.

**The tightest pair is the browser's two channels**: `e22` to `/oauth` at `y=512` and `e13` to `/api`
at `y=554`, **42 units apart**. Two badges centered on those lines touch at diameter 42.

| | |
|---|---|
| Diameter | **34** |
| `fontSize` | **17** — 12.2 pt |
| Fill | `#003087` |
| Text | `#FFFFFF`, bold |
| Stroke | `#FFFFFF`, **3 units**, matching the arrows' own `strokeWidth=3` |
| Badge-to-badge gap on the tightest pair | 8 |

**Sized against a TWO-DIGIT number, because that is the hard case.** `10` measures about 19 units
inside a 34 circle, leaving ~7 clear on each side. The journey is heading for 18 steps, still two
digits.

#### THE WHITE RING IS LOAD-BEARING, and the fill is not

**Measured, WCAG relative luminance:**

| Pair | Ratio |
|---|---|
| White text on `#003087` | 11.85 : 1 |
| `#003087` vs the white page | 11.85 : 1 |
| White ring vs the `#1A1A1A` arrow | **17.4 : 1** |
| `#003087` vs the `#1A1A1A` arrow | **1.47 : 1** |

**That last row is the finding.** Navy against a black line is 1.47, below even the 3:1 floor for
large text. **Remove the ring and the badge merges into the arrow it sits on.** The fill's only job
is to hold the digit; the ring is what separates the badge from the line.

**Two alternatives were computed and rejected.** White fill with navy text and ring fails twice: the
fill against the white page is 1:1, so the badge dissolves into the background, and a navy ring
against a black arrow is that same weak 1.47. Cloudflare orange `#F6821F` reaches only **2.58:1**
against the page, and it already belongs to three tiles.

**`#003087` now collides with the Lightroom mark.** The rule is 90 RGB units minimum between the
badge fill and any tile fill; `#003087` against the mark's ground `#001E36` is **83**. They never sit
near each other, but `MIN_COLOR_DISTANCE` will fire the moment the checks come back. **Shift the
badge navy, darken the mark, or exempt the pair — but decide it rather than discovering it.**

### A BOX-TO-BOX GAP IS NOT VISIBLE WHITESPACE, and `LOGO_GAP_MIN/MAX` is now stale

**`LOGO_GAP_MIN, LOGO_GAP_MAX = 6.0, 8.0` in the generator describes a gap that is now 2.95**, and
Terry approved the 2.95. **The constant is wrong, not the layout.** Retune it when the checks come
back; do not "fix" the layout to satisfy it.

**Three terms sit between the Flickr dots and the cap of the word "Flickr", and the check measures
only one of them:**

| Term | Size today | Where it comes from |
|---|---|---|
| Padding inside the mark's own box | ~4.9 | `viewBox="68 167 376 178"` is the dots' bounding box **plus 10 units** |
| Box-to-box gap | 2.95 | `flickrtitle.y` minus `flickrlogo` bottom — **the only term asserted** |
| Leading above the cap | ~8 | A 32-tall cell, `fontSize=20`, `verticalAlign=middle` |

**So the assertion is measuring the middle row of three.** That is survivable while nothing resizes,
and it broke the moment something did.

**The mark shrank from `h=107` to `h=88.05` on 2026-08-16**, and its `viewBox` padding shrank with it
— same nominal gap, less actual white. **The band would have PASSED the version Terry rejected and
FAILED the one he liked.** A check that inverts under a resize is worse than no check, because it
argues confidently for the wrong answer.

**The correction was 4 units. That is 0.04 inch, about a millimeter on the printed sheet.**
Proximity grouping is a threshold rather than a gradient: the eye asks whether the word belongs to
the mark above or the tile below, and the answer flips from *maybe* to *obviously* inside a 2-unit
window. **No arithmetic in this file models that**, which is the same lesson as the appearance row
in the defect table below — and the reason Terry looks at every render.

**If this check is rebuilt, measure the artwork's ink**, not its box: derive the mark's real bottom
from the `viewBox` and the artwork's own extents, then add the label's leading. Otherwise leave it
reported rather than asserted.

### AN XML COMMENT MUST NOT CONTAIN TWO CONSECUTIVE HYPHENS

**This repository's prose uses `--` as an em dash everywhere, and an SVG is XML.** The first version
of `logos/lightroom-classic-mark.svg` carried four of them inside its trailing comment.

**The failure was silent in every direction.** The file was malformed, `embed()` base64'd the bytes
without looking at them, drawio drew nothing at all, and the build reported success. **Nothing
anywhere checks that an embedded logo is well-formed.**

**Decode the payload and parse it** when a logo does not appear:

```
ET.fromstring(base64.b64decode(payload))   # names the line and column immediately
```

Three logos parsed and one did not, which took the diagnosis from minutes to seconds.

### WHAT IS PINNED TO WHAT, which is the map that makes a layout change tractable

**Stated as RELATIONSHIPS rather than coordinates, deliberately.** Every number on this canvas moved
at least twice on 2026-08-16. The relationships did not. **A coordinate written down here would be a
lie within the hour; a relationship tells the next session which lever it is actually pulling.**

**Semantic. These are claims about the system, and breaking one makes the picture false:**

| Pinned | Because |
|---|---|
| The OAuth Durable Object stack sits OUTSIDE `netb` | A Worker runs at the nearest PoP; a Durable Object lives in exactly one location |
| `d1` sits outside `netb` | D1 has one primary, and every query crosses to it |
| `dns`, `api`, `secrets`, `cron`, `retry` sit INSIDE `netb` | All anycast or edge-resident |
| The plug-in has no arrow to Flickr | It never calls Flickr. It reads Adobe's records out of the catalog |

**Load-bearing horizontals. A two-unit drift reads as a mistake rather than a change:**

| Run | Carries |
|---|---|
| `e18` and `e3` share one `y` | The device-link handshake, plug-in to `/device` to the Durable Object, as ONE line across the canvas |
| `e9` and `e10` land on `flickrapi`'s left edge | Every Worker-to-Flickr call |
| `e22` and `e13` land on the Worker's route tiles | The browser's two channels |
| `e10` and `e6` share one `y` | **The Cron trigger's horizontal leg and the Retry-to-Flickr call are ONE line through the Worker.** Both sit on `retry`'s vertical midpoint, so `exitY` and `entryY` are both `0.5` — but that is a coincidence of the current geometry, not the rule. **The ABSOLUTE line is the constraint.** When `retry` moved down 18.3 earlier the same day, `0.5` took the line with it and had to become `0.343590` before the two were re-aligned |

**Shared edges and columns. Break one and the eye sees raggedness before it sees why:**

| These share | |
|---|---|
| `cfframe` and `lrcapp` | Top edge |
| `cflogo` and `netb` | Left edge |
| `flickr` and `justification` | Left edge and width |
| `flickrlogo`, `flickrtitle`, `flickrapi` | Left edge and width, and the mark's top inset equals its side inset |
| `dns` and `cron` | Left edge, width and height |
| `oauthdo` and `d1` | Left edge and width |
| `lrcat`, `lrc` and `users` | Width, and the `x=95` centerline that keeps `e19` and `e20` vertical |
| `cfframe` and the `flickr` card | **BOTTOM edge.** The two outer boxes share a baseline |
| `netb` and `flickrapi` | **BOTTOM edge.** The two inner boxes share a baseline |

**Those last two are a structural rhyme rather than a coincidence**, and it is what finally made the
right column read: two nested boxes on the left, two nested boxes on the right, both pairs sharing
both baselines. Terry's words when it landed — *"bottom aligning the cloudflare and Flickr boxes is
what I needed"*.

**The page. Content spans exactly the printable width, so there is ZERO slack:** `lrcapp`'s left
edge and the `journey`/`key` right edge are what hold the 1:1 fit. **Anything that widens either
breaks it.**

### Coordinated moves: use a CHECKED SCRIPT, not a run of hand edits

**Three moves on 2026-08-16 touched 8, 12 and 26 geometries at once.** Each was applied by a
throwaway script that holds a list of `(label, exact anchor, replacement)` and **raises unless every
anchor matches exactly once.**

```python
n = text.count(old)
if n != 1:
    raise SystemExit(f"ANCHOR {label}: found {n} times, want 1")
```

**A half-applied coordinated move is the expensive failure here**, because the diagram still renders
and the damage is a few tiles out of alignment somewhere off-screen. **An all-or-nothing script
converts that into a loud stop.**

**Slack is FUNGIBLE across the canvas, which is the move worth remembering.** Terry's insight:
narrowing the Flickr column by 34 freed 34 units that walked left through a chain of pinned
relationships — the Cloudflare frame grew, the PoP box grew, the Durable Object stack moved to stay
outside it, and the PoP's contents re-centered. **The DNS arrows ended up with 38.75 of clearance
from a starting point of 13.5**, and nothing was shrunk to get it.

### Evenly spacing N gaps inside a fixed box: set the adjustable ones EQUAL

**`flickrapi` carries three gaps that must match** — above "OAuth Endpoints", between
`oauth/access_token` and "API Functions", and below `groups.pools.add`. Terry: *"those are three
sets of padding and not using the same size for all three is off"*. They were 93 / 30 / 99.

**They share one budget, which is the whole trick.** The tile is a fixed height, the text and
headings consume a fixed amount of it, and whatever remains divides among the gaps. **So the third
gap is not free — it is the remainder.**

**Two of the three are `margin-top` on a heading `div` and have identical structure**, a text line
above and a heading below. **Setting those two equal makes their rendered gaps equal by
construction**, which reduces the problem to one variable. Then tune that single value until the
remainder matches. `72px` on both landed all three within about one unit.

**MEASURE THIS ONE OFF THE RENDER, not off `text_height`.** The estimator was about 24 units wrong
on this tile, which is roughly a fifth of a gap. Two rounds of look-and-adjust beat any amount of
arithmetic here — the first guess of 104 gave 164/130, and half the difference corrected it.

### When two clients reach one node, SPLIT THE NODE rather than routing around it

**2026-08-16, and it is the sharpest design lesson of the session.** The browser and the Lightroom
plug-in both talk to the device-link surface. Drawn as one tile, the browser's arrow had to cross
the DNS tile and both of its arrows, so every option on the table was bad: an orthogonal detour, a
re-layout that spent a horizontal run, or leaving the loop visibly open.

**Terry's fix was to stop drawing one node.** The routes were never shared — `start` and `poll` are
the plug-in's and are unauthenticated, `approve` and `deny` are browser-only and carry
`requireBrowserSession`. **So the surface splits cleanly by ROUTE, and each half sits where its
caller already points.** `start` keeps the plug-in's straight sweep at `y=388`; `approve` joins the
browser's stack. Two straight arrows, zero crossings, zero routed edges.

**The generalizable form: a node that two callers reach by DISJOINT sub-surfaces is two nodes.**
Ask whether the callers actually share endpoints before spending layout to make one box reachable
from two directions. Here the code had already answered — the allow-lists are disjoint — and the
answer was quoted back in conversation an hour before anyone acted on it.

**A tile may stand for an exact path or for a namespace, and the label must say which.** The four
route tiles now do: a bare path means one route, a trailing `*` means a prefix. Plurality follows —
`API endpoint` against `API endpoints`.

### Park an edge on a floating `sourcePoint` while its anchor is out of reach

**A tile sometimes has to move before the shape its arrow comes from can reach the new line.** On
2026-08-16 `/api/v001/*` moved up to `y=454`, putting its arrow at `y=472` — above the Browser
glyph's top edge at `490`. No fraction of that shape reaches 472; `exitY` would have to go negative.

**Do not bend it, and do not delete it.** Drop `source` and the whole `exit*` set, and give the
geometry an explicit point:

```xml
<mxGeometry x="0.55" relative="1" as="geometry">
  <mxPoint x="186.25" y="472" as="sourcePoint" />
</mxGeometry>
```

**The arrow stays dead horizontal and visibly unfinished**, which is the honest state while a
multi-step move is in flight. Reattaching later is one edit: restore `source` and `exitX`/`exitY`.

**Pick the floating `x` to match where the eventual anchor's edge will be**, so the reattachment
moves the endpoint as little as possible.

**Two things go quiet while an edge floats.** `scripts/badge-positions.py` skips it, because it
needs both ends attached to tiles. And any badge riding it is orphaned until the rescue lands.

### `scripts/badge-positions.py` answers where a badge goes

```
python scripts/badge-positions.py            # every straight edge
python scripts/badge-positions.py e20 e4     # just these
```

**It reads the ARTIFACT and prints paste-ready `mxGeometry`** — on the line, and beside it on either
side — plus each run's length and what fraction of it a badge would cover. It reimplements
`mxRectanglePerimeter`, so its endpoints are what draw.io actually draws rather than what the
fractions suggest.

**It exists because recall placed a badge wrongly twice**, 30 units out and then 3.2, both times with
correct arithmetic on a stale coordinate. **A check would have caught neither**, because a check
would read the coordinate from the same place the mistake did.

**Its first survey settled a question that was going to be an arbitrary style call.** A badge sits ON
its line where it covers under about half the run, and BESIDE it above that. Four runs fail the test
— which is a fact about the geometry, not a preference.

### Three classes of defect, and only one of them has checks

| Class | Example | Caught by |
|---|---|---|
| Geometry | Two tiles overlap; an arrow crosses a tile | The generator, reliably |
| **Appearance** | 7.9 pt type; four arrows out of one tile; a third of the page empty | **Nothing. Render it and look** |
| **Contradiction** | An arrow says the Catalog opens the browser; the User Journey says the plug-in does | **Nothing. Read the picture as a sentence** |

**The checks are a ratchet, not a designer.** Each one exists because a specific defect got past the
others, so they prevent the return of known problems and are blind to new ones. On 2026-08-15 the
build passed all fifteen assertion blocks over a diagram Terry called horrific.

## THE ASSERTIONS ARE CURRENTLY OFF

**`CHECKS_ENABLED = False` near the top of the check block in `scripts/build-diagram.py` short
circuits every geometry and quality assertion**, and the build prints a banner saying so on every
run. **Terry turned them off on 2026-08-16** for a canvas overhaul he reviews by eye through the
live preview: nearly every assertion is pinned to a coordinate the overhaul moves, so they fired on
every intermediate state, and a check that fires on every run is a check nobody reads.

**Restoring is one word.** Set the flag to `True`, run, and fix what it reports. **Expect several
failures** — the badge checks have empty tables, `check_page_fit()` has never seen the current
layout, and the boxed-text slack band was tuned against tiles that have all since moved.

**A future session MUST NOT turn them back on unasked.** That is Terry's call, the same way the
layout is.

## Open, as of 2026-08-16

**None of these blocks anything. They are written down so they are not rediscovered.**

- **`text_height` measures three tiles out of thirteen** — `justification`, `key` and `journey`.
  Every other tile is hand-sized, which is why raising the body type from 7.9 pt to 12.2 pt burst
  the Nightly Retry Worker's box while the build reported clean. **Extending it to every text tile
  is the highest-value check still missing.**
- **`check_page_fit()` cannot see a routed waypoint.** Its regex matches `<mxGeometry>`, and `e11`'s
  run along the page bottom is a pair of `<mxPoint>` elements — so it measures the content 45 units
  shorter than it is. It also scales against the full page rather than the printable area. **The
  fix is deferred until the layout settles**, because the checking machinery is not being touched
  mid-overhaul.
- **The Nightly Event Trigger tile is cramped** — four wrapped lines in a small box.
- **Dead space bottom-right inside the Cloudflare frame**, now roughly **265 x 265** — right of the
  Nightly Retry Logic Worker (ends x=730) and below D1 (ends y=740), out to the frame at x=995,
  y=1005. It shrank with the 2026-08-16 relayout but did not close.
- **No logo for Lightroom Classic.** Cloudflare and Flickr both carry their marks; the Lightroom
  card carries only text. Adobe ships an "Lr" mark and Wikimedia Commons hosts Adobe product icons,
  which is where the other two came from. **The trap is that Lightroom Classic and Lightroom (CC)
  have DIFFERENT icons**, and this diagram means Classic specifically — the whole
  `getPublishServices(nil)` cross-plugin mechanism is Classic-only.
- **The PDF export has never been inspected.** Terry: *"the PDF looks some different from the drawio   DIRTY-WORDS-EXEMPT: quoting Terry
  render"*. The `Read` tool opens PDFs natively via its `pages` parameter, so the only missing step
  is producing the file.
- **A contradiction check does not exist.** Three defects in one session were the drawing asserting
  something `DECISIONS.md` or the User Journey denies. Comparing an edge's endpoints against the
  step text that cites it is mechanical and nobody has written it.

- **The dotted "Scheduled trigger" legend row has NOTHING VISIBLE to point at.** Found 2026-08-16 by
  looking at a render, and it is the sharpest example on this page of an assertion passing over a
  defect.

  `e6` carries `dashed=1;dashPattern=1 4` and the `LINE_STYLE` check reports `dotted ok`. **The
  render shows a bare arrowhead.** `cron` ends at x=420 and `retry` begins at x=430 — a **10-unit
  gap**, one tenth of an inch, which the arrowhead consumes entirely. No reader can tell it from
  solid, so the legend defines a line style the drawing never visibly uses.

  **The geometry is boxed in, and that is why this is not a one-line fix.** The left and right
  columns are separated by a single 10-unit corridor at x≈425. `netb` spans 245..760, `cron` cannot
  move left past 250, and the right column's left edge is pinned by the *flush* and *one column*
  checks. **A straight horizontal `e6` can never be longer than 10 units.**

  So `MUST_BE_HORIZONTAL` and a visible dotted line are in direct conflict, and one must give.
  **The legend row is the more important of the two** — horizontality is meaningless on a line you
  cannot see. The fix is an orthogonal route (a U below both tiles, roughly 300 units of visible
  run), which means removing `e6` from `MUST_BE_HORIZONTAL` and **replacing it with a check that
  catches the real defect**: any edge whose declared style is broken MUST have a minimum visible run.
  That replacement is the part that matters; deleting the old check without it is how a ratchet
  loses a tooth.

## Closed on 2026-08-16

- **THE DIAGRAM FITS AN 11x17 SHEET AT 100%, for the first time.** See the printing section. It had
  been 4% over in width and 18% over in height.
- **Every arrow lands on drawn pixels rather than on a bounding box.** `exitPerimeter=0` /
  `entryPerimeter=0`, plus the corner arithmetic above. Six edges: `e1`, `e21`, `e11`, `e14`, `e15`,
  and the `dns` ends of the first two.
- **The left column was rebuilt.** The Lightroom card widened leftward to 180 so its arrows are not
  cramped against its own border while the 30-unit gap to the Cloudflare frame held; the Browser
  glyph matches the plug-in tile's width and shares its centerline, which made `e19` vertical for
  free; the Catalog tile lost a line and rose; and DNS sits where its two diagonals make equal
  angles, which is also the midpoint between the plug-in's bottom and the glyph's top.
- **The Catalog tile says what it holds.** "Local SQLite / Published photo IDs" became "Flickr photo
  IDs". The plug-in reads Adobe's Flickr publish service records out of the catalog and never calls
  Flickr, so the ids are the fact worth naming. See `docs/LRC-CLIENT-NOTES.md`.
- **The Cloudflare mark is no longer 0.12% squashed.** Its box now uses the artwork's own
  `viewBox="0 0 101.4 33.5"` ratio of 3.0268657 rather than the 3.023256 it happened to sit in.
  **The 1% distortion assertion passed that happily**, which is the reminder that a band is not a
  measurement.
- **`e19` is ONE HEAD. Terry chose it**, from the three options this section used to list. The
  picture now matches journey steps 12 and 13 and matches the device flow: `LrHttp.openUrlInBrowser`
  is fire-and-forget, and the token arrives on `e18`, which is already double-headed.
- **Body type overshot and came back to 10.1 pt.** See the printing section above.
- **The date sat a blank line below the title.** Both cells are `verticalAlign=middle`, so the gap
  was arithmetic rather than a stray line: centers 46px apart against 29px of type. The date box
  moved from y=72 to y=56, which also bought clearance above the Cloudflare frame — that had been
  **2px**.

## The next change: a TWO-PANEL User Journey, plug-in first

**Terry's direction, 2026-08-16: two panels split between login/auth and publish, with the auth
panel drawn in full.** His reasoning, and it decides the level of detail: *"Terry of 2031 will   <!-- DIRTY-WORDS-EXEMPT: quoting Terry -->
appreciate us being pedantic af today. Hold his hand."*

**Why the journey is being rewritten at all:** today's runs browser-first and the plug-in appears at
steps 12 and 13 as an afterthought. Per `docs/LRC-CLIENT-NOTES.md`, **the plug-in is arguably the
more important of the two clients** — the stated goal is queueing adds without leaving Lightroom.
The journey should open with the user clicking **Authorize with FGA**.

**The drafted auth panel is 18 steps and 17 distinct badges** (step A11 rides A10's arrow). The full
list, with the edge each step needs and whether the code exists, was drafted in the 2026-08-16
session and **is NOT yet in the generator.** Its shape:

| Steps | What they cover | Built? |
|---|---|---|
| A1–A2 | `POST /api/v001/device/start`, the `DeviceLinkAttempt` Durable Object | **Yes**, 2026-08-16 |
| A3 | `LrHttp.openUrlInBrowser` — **the Lua side, which does not exist** | **No** |
| A4 | DNS | **Yes** |

**THE PLUG-IN NEEDS ITS OWN DNS EDGE. DRAWN 2026-08-16 as `e21`**, plug-in bottom-right corner to
the DNS tile's top-left. `e1` was re-cornered the same way, browser top-right to DNS bottom-left, so
the two converge on the tile instead of crossing the channel. **`e21` carries no badge**, because
the plug-in's DNS query is not a step in the current thirteen-step journey and the build requires
the row count and the badge count to agree. It gets one when the two-panel rewrite lands.

Found 2026-08-16 while
Terry walked the journey aloud. **The plug-in is a network client before it is a browser launcher**:
it calls `POST /api/v001/device/start` first and must therefore resolve `flickrgroupaddr.com`
itself. It cannot delegate that to the browser, because `LrHttp.openUrlInBrowser` is fire-and-forget
and the `deviceCode` would land in a tab the plug-in cannot read.

**`docs/LRC-CLIENT-NOTES.md` recorded the opposite** — *"only the browser connects to the app shell
and to DNS"* — which was true before ADR-24 and is corrected there now. **A note that argues against
drawing a real edge is worse than a missing edge**, because it makes the omission look deliberate.
| A5 | `GET /link` — **a Svelte route, not a Worker one** | **No** |
| A6 | Redirect to `GET /oauth/login`, carrying `returnTo` | **Yes**, 2026-08-16 |
| A7–A16 | The whole Flickr OAuth leg | **Yes** |
| A17 | `userCode` confirmation, then `POST /api/v001/device/approve` | **API yes, page no** |
| A18 | `POST /api/v001/device/poll`, and the token it mints | **Yes**, 2026-08-16 |

**So the auth panel is now mostly a picture of things that EXIST**, which changes the honesty
calculation the panel was drawn under. **What remains unbuilt is a page and a Lua client**, not a
design.

**The remaining gaps are on the two ends, not in the middle.** A3 is the plug-in, and A5/A17 are the
`/link` page — ADR-18 gives `/` to the app shell and `run_worker_first` does not list `/link`, so it
is Svelte's. **Its confirmation step is the only defense against device-flow phishing**, and ADR-24
makes that a page requirement precisely because no backend route can substitute for it: nothing
auto-approves, and approval is always a POST a person had to cause.

**Three constraints that bind the design, and each has already caught something:**

- **Every journey step needs a badge, and every badge needs a real edge.** `build-diagram.py` fails
  the build when the row count and the badge count disagree, so the step list and the arrows are one
  decision rather than two.
- **Two panels each numbering from 1 means two badges reading "3".** Letter prefixes — `A1`, `B1` —
  solve it with no new color rule and no legend row. Two badge colors also work, at the cost of a
  rule a reader has to learn. **Not yet decided.**
- **"Publish to Flickr as normal" has no edge on the canvas**, because FGA does not participate. It
  belongs as context above the publish panel rather than as a numbered step.

**The publish panel drafts to 9 steps**, from the catalog read through preflight and
`POST /api/v001/requests/batch` to the 00:15 UTC sweep calling `groups.pools.add`.

**A17 WAS BLOCKED BY A REAL BUG. FIXED 2026-08-16, so the diagram no longer has to flag it.**
`src/routes/oauth.ts` used to end the callback unconditionally at `UI_ORIGIN?login=ok`, stranding
any flow that began somewhere else. It now carries a validated `returnTo` through the Flickr round
trip in the ADR-08 login attempt. **See ADR-11**, which gained the open-redirect rule in the same
change, and which has three mutations defending it.

**And the device flow itself was BUILT later the same day, as ADR-24.** `start`, `poll`, `approve`
and `deny` all exist, with 25 tests and six mutations. **The panel therefore draws mostly shipped
behavior rather than a decided design**, and the honesty question it was raising has mostly gone
away. **If the device flow is ever abandoned, the panel comes out**, same rule that removed the
read replica.
