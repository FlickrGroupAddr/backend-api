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
17x11 landscape is exactly **`1700x1100`**. A font size converts straight to points: `fontSize=17`
is 0.17 in, which is **12.2 pt**.

| Body text | Was | Is |
|---|---|---|
| Tile text | `fontSize=11` — **7.9 pt** | `fontSize=17` — **12.2 pt** |
| Journey panel | `font-size:14px` — 10.1 pt | `font-size:16px` — 11.5 pt |
| Step badges | `fontSize=22` — 15.8 pt | `fontSize=26` — 18.7 pt |

**7.9 pt is footnote size**, and it is what made the first 8.5x11 print unreadable. Terry called it
an eyechart, and the fix was type, not page size.

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
- **The PDF export has never been inspected.** Terry: *"the PDF looks some different from the drawio   US-ENGLISH-EXEMPT: quoting Terry
  render"*. The `Read` tool opens PDFs natively via its `pages` parameter, so the only missing step
  is producing the file.
- **A contradiction check does not exist.** Three defects in one session were the drawing asserting
  something `DECISIONS.md` or the User Journey denies. Comparing an edge's endpoints against the
  step text that cites it is mechanical and nobody has written it.

- **`e19` may now be a FOURTH contradiction, and it is one I introduced.** Terry asked for step 12
  to become a thick double-headed arrow: *"Plugin really does drive the browser and really does read   US-ENGLISH-EXEMPT: quoting Terry
  token back out"*. I made the change without checking it against the journey text, which is exactly
  the failure this section is about.

  | Says | |
  |---|---|
  | Step 12 | "Lightroom plug-in opens the browser to link itself. **It never calls Flickr**" |
  | Step 13 | "Lightroom plug-in **polls for its token**, then queues a batch in one call" |

  **So the token comes back on the plug-in-to-Worker edge, not through the browser.**
  `LrHttp.openUrlInBrowser` is fire-and-forget and there is no return channel — the device flow in
  `docs/LRC-CLIENT-NOTES.md` has the plug-in polling `POST /api/v001/device/poll`. `e18` is already
  double-headed and is where the token actually arrives.

  **Three ways this resolves, and Terry picks:**

  1. **`e19` goes back to one head.** Matches steps 12 and 13 as written, and matches the device
     flow. The "reads token back out" is true of the plug-in, but of a different arrow.
  2. **`e19` stays double-headed and step 12's text changes** to describe what returns.
  3. **The design changes** to an `LrSocket` localhost callback, where the browser really would
     answer the plug-in directly. That is a real option the SDK supports and it is not what is
     designed today.

  **Option 1 unless Terry says otherwise.** Nothing is changed yet — the diagram is parked until
  2026-08-16.
