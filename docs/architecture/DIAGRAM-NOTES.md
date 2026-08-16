# The architecture diagram: printing it, and changing it

**RFC 2119 keywords. MUST and MUST NOT are absolute. SHOULD is a strong default a good argument may
overrule. MAY is optional.**

**The diagram is generated.** `scripts/build-diagram.py` writes
`FlickrGroupAddr-Architecture-<date>.drawio`, and a hand edit is lost on the next build. This file
records what the generator does not say about itself: how the artifact prints, and how a layout
change is actually made.

**`CLAUDE.md` carries the render loop and the traps a Claude session hits.** This file is about the
artifact. Where they overlap, `CLAUDE.md` wins for procedure and this one for facts about output.

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

The content measures **1650 x 1055** inside a `1700x1100` page, so it prints **1:1 with no
fit-to-page shrink**. That is the case where the margin actually binds — a driver asked to fit a
mismatched page would scale by a percent or two and absorb a small overflow. Do not rely on that.

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

### Three classes of defect, and only one of them has checks

| Class | Example | Caught by |
|---|---|---|
| Geometry | Two tiles overlap; an arrow crosses a tile | The generator, reliably |
| **Appearance** | 7.9 pt type; four arrows out of one tile; a third of the page empty | **Nothing. Render it and look** |
| **Contradiction** | An arrow says the Catalog opens the browser; the User Journey says the plug-in does | **Nothing. Read the picture as a sentence** |

**The checks are a ratchet, not a designer.** Each one exists because a specific defect got past the
others, so they prevent the return of known problems and are blind to new ones. On 2026-08-15 the
build passed all fifteen assertion blocks over a diagram Terry called horrific.

## Open, as of 2026-08-15

**None of these blocks anything. They are written down so they are not rediscovered.**

- **`text_height` measures three tiles out of thirteen** — `justification`, `key` and `journey`.
  Every other tile is hand-sized, which is why raising the body type from 7.9 pt to 12.2 pt burst
  the Nightly Retry Worker's box while the build reported clean. **Extending it to every text tile
  is the highest-value check still missing.**
- **The Nightly Event Trigger tile is cramped** — four wrapped lines in a small box.
- **Dead space bottom-right inside the Cloudflare frame**, roughly 265 x 335.
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
