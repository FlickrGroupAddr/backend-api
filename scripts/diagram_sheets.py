"""The sheets the architecture diagram is generated onto, and how to find them.

RFC 2119 keywords, and the capitals are load-bearing.

**ONE DRAWING, ONE CANVAS, TWO DELIVERABLE SHEETS.** `scripts/build-diagram.py`
authors the content once into a 1700 x 1100 unit `canvas`, then writes each
deliverable as the SAME drawing translated so it sits centered on its page.
**The AUTHORED content is never rescaled** -- the page-size block in that file says
why baking a scale into the coordinates is the wrong fix, and a rigid translation
keeps every font size, every hand-set box height and every absolute threshold in the
check suite meaning exactly what it meant before.

**THE CANVAS IS NOT A PRINT, and calling it `11x17` was the whole confusion.** Terry
retired tabloid on 2026-08-19 after printing legal at a FedEx Office. **No 11x17 is
produced any more.** `CANONICAL` is the legal sheet and is what "the diagram" means to
a reader; `AUTHORED` is the canvas and is what "the coordinates" means to a tool.
**Those were the same file for months and they are different questions.**

**This module exists because four scripts globbed the artifact's filename by
hand, and adding the sheet suffix broke all four at once.** Three of them took
`sorted(glob)[-1]` and called it "the newest date". That stopped being true the
moment two files shared a date: ASCII sorted the suffixes into an order nobody
intended, so the live preview would have silently switched sheets and
`badge-positions.py` would have measured translated coordinates. The fourth,
`check-diagram-date.py`, read the date out of the name and would have reported
several dated copies where it expects one.

**Every consumer MUST call `authored_diagram()` or `canonical_diagram()`, never a
glob of its own**, and MUST pick the one that answers its question:

| The question | Call |
|---|---|
| Where is a shape, in authored units | **`authored_diagram()`** -- the canvas |
| What does Terry print, open or link | **`canonical_diagram()`** -- legal |

**The module name uses an underscore because the rest of this directory cannot.**
Every other script here is run and never imported, so a hyphen costs them
nothing. This one is imported, and `import diagram-sheets` is a syntax error.
"""

import pathlib
import re
from typing import NamedTuple


class Sheet(NamedTuple):
    """One output sheet: its filename suffix, its page, and its margin.

    `width` and `height` are drawing units, and **draw.io uses 100 units per
    inch** -- so 1700 x 1100 IS 17 x 11 inches, and `pageWidth`/`pageHeight` in
    the `<mxGraphModel>` take these numbers unchanged.
    """

    slug: str
    label: str
    width: float
    height: float
    margin: float
    # **May the content be scaled UP to fill this sheet?** Off by default, and that
    # default is load-bearing: tabloid's printable height is 1040 against 1030 of
    # content, so a sheet allowed to fill would grow the AUTHORED drawing by 1%.
    # Everything in the check suite is expressed in authored units, so the reference
    # sheet MUST stay exactly 1:1.
    #
    # **A screen sheet is the opposite case.** draw.io maps one drawing unit to one
    # pixel at 100%, so pixels are the only unit that matters there -- filling the
    # page is how a 4K export comes out 4K without anybody typing a zoom percentage.
    scale_up: bool = False
    # **Does a human ever open this one?** False for the authored canvas, which exists
    # so the generator and the measuring tools have exact coordinates to work in.
    # **A non-deliverable is still WRITTEN** -- `badge-positions.py` reads it and hands
    # Terry geometry to paste back -- it is simply not something to print or link.
    deliverable: bool = True


# **MARGIN IS 30 ON PAPER AND 40 ON GLASS, and the difference is physical rather
# than a taste.** Every printer grips the sheet at its edge and cannot put ink
# there; 0.30 in clears that border plus the placement drift a sheet-fed engine
# is allowed. See DIAGRAM-NOTES.md, "Why 0.30 in and not 0.25 in". A monitor has
# no such border, so the screen gutter is chosen by eye -- it was 20 at 1920 x 1080
# and doubled with the sheet, which keeps the same proportion of the picture.
#
# **THE SCREEN SHEET IS 3840 x 2160, and it is measured in PIXELS rather than
# inches.** Terry, 2026-08-18: *"make sure 16:9 diagram is native 4K/2160p at
# 100%."* draw.io maps one drawing unit to one pixel at 100% zoom, so a 1920-unit
# page could only reach 4K by somebody remembering to type 200% into an export
# dialog. **A 3840-unit page is 4K at 100%, which is what native means here.**
#
# **The 100-units-per-inch convention does NOT apply to this sheet**, and reading
# it as 38.4 x 21.6 inches of paper is a category error. It is a screen target;
# the paper sheets above it are the ones measured in inches.
#
# **THE FIRST ENTRY IS THE AUTHORED DRAWING SPACE, and the order here is the order
# the build reports them in.**
#
# **`canvas` IS NOT A PAPER SIZE, and it used to claim to be one.** It was called
# `11x17` until 2026-08-19, which made a coordinate system look like a deliverable.
# Terry, after printing the legal sheet in color at a FedEx Office: *"legal is the
# right size for this diagram. It reads great and isn't unwieldy huge like 11x17...
# switch the Canonical size to legal and stop producing 11x17."*
#
# **So no 11x17 is produced. What remains is the drawing space, under its own name.**
# Its dimensions are unchanged and MUST stay so: the content is 1640 x 1030 units and
# a 1700 x 1100 space with a 30 margin holds it at exactly 1:1. **Shrinking this to
# legal would rescale every coordinate, every font size and every threshold in the
# check suite** -- the operation `DIAGRAM-NOTES.md` refuses by name.
#
# **`deliverable` is what separates the two ideas.** A deliverable sheet is one Terry
# prints or opens; the canvas is the reference the generator authors in and the tools
# measure. **`badge-positions.py` hands its output to Terry to paste back into
# `build-diagram.py`, so it MUST read exact authored coordinates** -- reconstructing
# them by unscaling a printed sheet round-trips to within 0.0005 units, which is
# excellent and is still not the same as exact.
SHEETS = (
    Sheet("canvas", "Authored drawing space, 1700 x 1100 units. NOT a print",
          1700, 1100, 30, deliverable=False),
    Sheet("8.5x14", "Legal landscape, 14 x 8.5 in", 1400, 850, 30),
    Sheet("16x9", "Monitor, 3840 x 2160 (4K) at 100%", 3840, 2160, 40, scale_up=True),
)

AUTHORED = SHEETS[0]

# **THE CANONICAL PRINT, and it is legal as of 2026-08-19.** Everything that means
# "the diagram" to a reader -- the preview's default tab, the sheet to print, the one
# to link -- resolves through here rather than through `SHEETS[0]`.
#
# **`AUTHORED` and `CANONICAL` are different questions and were the same answer for
# months.** `AUTHORED` asks *"whose coordinates are the real ones"*; `CANONICAL` asks
# *"which one does Terry look at"*. Conflating them is what let a paper size become
# the name of a coordinate system.
CANONICAL = next(s for s in SHEETS if s.deliverable)

DELIVERABLES = tuple(s for s in SHEETS if s.deliverable)

STEM = "FlickrGroupAddr-Architecture"
GLOB = f"{STEM}-*.drawio"

# `.+` is greedy, and the literal `\.drawio$` anchor is what makes the split
# right anyway. It has to be greedy: the legal sheet's slug is `8.5x14`, which
# carries a dot of its own.
NAME_RE = re.compile(rf"^{re.escape(STEM)}-(\d{{4}}-\d{{2}}-\d{{2}})-(.+)\.drawio$")

_ORDER = {s.slug: i for i, s in enumerate(SHEETS)}


def arch_dir(root: pathlib.Path) -> pathlib.Path:
    return root / "docs" / "architecture"


def sheet_path(root: pathlib.Path, date: str, sheet: Sheet) -> pathlib.Path:
    return arch_dir(root) / f"{STEM}-{date}-{sheet.slug}.drawio"


def found_sheets(root: pathlib.Path) -> list[tuple[str, str, pathlib.Path]]:
    """Every generated sheet on disk, as (date, slug, path), newest date last.

    A name this regex does not recognize is skipped rather than guessed at, so a
    stray file in the directory cannot become "the diagram".
    """
    rows = []
    for path in arch_dir(root).glob(GLOB):
        m = NAME_RE.match(path.name)
        if m:
            rows.append((m.group(1), m.group(2), path))
    return sorted(rows, key=lambda r: (r[0], _ORDER.get(r[1], len(SHEETS))))


def _newest(root: pathlib.Path, sheet: Sheet) -> pathlib.Path:
    """The newest dated copy of one sheet, or a message saying how to make it."""
    rows = found_sheets(root)
    if not rows:
        raise SystemExit(f"No diagram found under {arch_dir(root)}")
    newest = rows[-1][0]
    for date, slug, path in rows:
        if date == newest and slug == sheet.slug:
            return path
    raise SystemExit(
        f"No {sheet.slug} sheet dated {newest} under {arch_dir(root)}. "
        f"Run python scripts/build-diagram.py."
    )


def authored_diagram(root: pathlib.Path) -> pathlib.Path:
    """The CANVAS of the newest date -- the only file whose coordinates are authored.

    **Ask for this when the question is WHERE A SHAPE IS.** Every deliverable holds
    the same drawing translated and scaled onto its page, so measuring one answers a
    question nobody asked -- and it answers it plausibly, which is worse.

    **`badge-positions.py` is the caller that makes this matter.** Its output is
    geometry Terry pastes back into `build-diagram.py`, so it needs the authored units
    exactly rather than reconstructed from a printed sheet.
    """
    return _newest(root, AUTHORED)


def canonical_diagram(root: pathlib.Path) -> pathlib.Path:
    """The sheet that MEANS "the diagram" to a reader. Legal since 2026-08-19.

    **Ask for this when the question is WHAT DOES TERRY LOOK AT** -- the default
    preview tab, the sheet to print, the file to link.

    **This split exists because the two answers stopped being the same file.** Terry
    retired tabloid after printing legal in color: *"legal is the right size for this
    diagram... switch the Canonical size to legal and stop producing 11x17."* The
    canvas kept its dimensions because shrinking it would rescale every coordinate and
    every threshold in the check suite.
    """
    return _newest(root, CANONICAL)
