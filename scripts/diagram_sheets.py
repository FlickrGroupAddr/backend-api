"""The sheets the architecture diagram is generated onto, and how to find them.

RFC 2119 keywords, and the capitals are load-bearing.

**One drawing, three sheets.** `scripts/build-diagram.py` authors the content
once, at tabloid size, and writes the other two as the SAME drawing translated so
it sits centered on its sheet. **The AUTHORED content is never rescaled** -- the page-size block
in that file says why baking a scale into the coordinates is the wrong fix, and a
rigid translation keeps every font size, every hand-set box height and every
absolute threshold in the check suite meaning exactly what it meant before.

**This module exists because four scripts globbed the artifact's filename by
hand, and adding the sheet suffix broke all four at once.** Three of them took
`sorted(glob)[-1]` and called it "the newest date". That stopped being true the
moment two files shared a date: ASCII sorts `-11x17` before `-16x9` before
`-8.5x14`, so the live preview would have silently switched to the legal sheet
and `badge-positions.py` would have measured translated coordinates. The fourth,
`check-diagram-date.py`, read the date out of the name and would have reported
three dated copies where it expects one.

**Every consumer MUST call `authored_diagram()`, never a glob of its own.** The
tabloid sheet is the only one whose coordinates are the authored ones.

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
# **THE FIRST ENTRY IS THE AUTHORED SHEET, and the order here is the order the
# build reports them in.** Tabloid is first because the content is laid out for
# it and fits it exactly.
SHEETS = (
    Sheet("11x17", "Tabloid landscape, 17 x 11 in", 1700, 1100, 30),
    Sheet("8.5x14", "Legal landscape, 14 x 8.5 in", 1400, 850, 30),
    Sheet("16x9", "Monitor, 3840 x 2160 (4K) at 100%", 3840, 2160, 40, scale_up=True),
)

AUTHORED = SHEETS[0]

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


def authored_diagram(root: pathlib.Path) -> pathlib.Path:
    """The tabloid sheet of the newest date -- the one the content is authored on.

    **Every consumer wants THIS file.** The other sheets hold the same drawing
    moved, so measuring one of them answers a question nobody asked.
    """
    rows = found_sheets(root)
    if not rows:
        raise SystemExit(f"No diagram found under {arch_dir(root)}")
    newest = rows[-1][0]
    for date, slug, path in rows:
        if date == newest and slug == AUTHORED.slug:
            return path
    raise SystemExit(
        f"No {AUTHORED.slug} sheet dated {newest} under {arch_dir(root)}. "
        f"Run python scripts/build-diagram.py."
    )
