"""Parse `docs/WORK-LOG.md`. One implementation, shared by everything that reads it.

RFC 2119 keywords, and the capitals are load-bearing.

**This module exists because TWO tools read the log and a second parser would
drift.** `worklog-sync-check.py` compares it to the harness task panel and
`worklog-server.py` renders it in a browser. **If those disagreed about what a row
is, the browser could show Terry a list the checker calls in sync** -- which is the
exact failure the sync contract exists to prevent, arriving one level down.

**The module name uses an underscore because the rest of this directory cannot.**
Every other script here is run and never imported, so a hyphen costs them nothing.
This one is imported, and `import worklog-server` is a syntax error. Same reasoning
as `diagram_sheets.py`.

**The log's own contract is at the top of `docs/WORK-LOG.md` and it governs.** This
file only knows how to read the tables.
"""

import pathlib
import re
from typing import NamedTuple

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG = ROOT / "docs" / "WORK-LOG.md"

# **The Open table.** `| n | `status` | `subject` | detail |` -- the backticks are
# what make status and subject exact rather than judged, and the detail cell is
# deliberately free prose.
OPEN_RE = re.compile(r"^\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|\s*$")

# **The Landed table** carries a date rather than a number, and a note rather than a
# pointer. The placeholder row uses em dashes and no backticks, so it does not match
# and an empty Landed table parses as zero rows rather than as one fake one.
LANDED_RE = re.compile(r"^\|\s*([0-9]{4}-[0-9]{2}-[0-9]{2})\s*\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|\s*$")

OPEN_HEADING = "## Open"
LANDED_HEADING = "## Landed"
# Any of these ends a table's region. Listed rather than "the next `## `" so a new
# section between them cannot silently swallow rows.
END_HEADINGS = ("## Landed", "## Not an item yet", "## Open")

# A log state maps to a panel status plus a subject prefix. **`completed` is absent
# on purpose** -- it never reaches the panel, and a lookup miss is how the checker
# notices a completed row left sitting in the Open table.
PANEL: dict[str, tuple[str, str]] = {
    "not_started": ("pending", ""),
    "in_progress": ("in_progress", ""),
    "blocked": ("pending", "BLOCKED: "),
}

# Every state the Open table may legally carry, including the one that means the row
# should have moved to Landed.
STATES = (*PANEL, "completed")


class Row(NamedTuple):
    """One row of the Open table.

    `key` is the row number as written, kept as text because it is an identifier in
    a document rather than a quantity.
    """

    key: str
    status: str
    subject: str
    detail: str


class Landed(NamedTuple):
    """One row of the Landed table."""

    date: str
    subject: str
    note: str


def _region(text: str, heading: str) -> list[str]:
    """The lines under `heading`, up to the next section heading.

    **Headings are matched EXACTLY, not by prefix, and that was a real defect.**
    The first version used `startswith`, so `## Open questions` -- an entirely
    ordinary section to add later -- would have been read as the Open table and its
    prose scanned for rows. **Found 2026-08-18 while trying to BREAK the parser on
    purpose: renaming the heading to `## Open items (deliberately broken heading)`
    changed nothing, because it still started with `## Open`.**

    So the test that was meant to prove the empty-list banner fires instead found
    the bug that would have stopped it firing. A prefix match is the wrong tool for
    a heading, which is an exact string in a document somebody edits.
    """
    out: list[str] = []
    inside = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == heading:
            inside = True
            continue
        if inside and stripped in END_HEADINGS:
            break
        if inside:
            out.append(line)
    return out


def read(path: pathlib.Path | None = None) -> str:
    return (path or LOG).read_text(encoding="utf-8")


def open_rows(text: str | None = None) -> list[Row]:
    """Every row of the Open table, in file order.

    **File order IS the priority order**, and the panel renders it by task id, so
    the caller MUST preserve this sequence.
    """
    body = text if text is not None else read()
    return [Row(m.group(1), m.group(2), m.group(3), m.group(4))
            for line in _region(body, OPEN_HEADING)
            for m in [OPEN_RE.match(line)] if m]


def landed_rows(text: str | None = None) -> list[Landed]:
    """Every row of the Landed table, oldest first."""
    body = text if text is not None else read()
    return [Landed(m.group(1), m.group(2), m.group(3))
            for line in _region(body, LANDED_HEADING)
            for m in [LANDED_RE.match(line)] if m]


def panel_subject(row: Row) -> str:
    """The subject this row MUST carry in the harness panel.

    **`blocked` has no panel status of its own**, so it renders as `pending` with a
    `BLOCKED: ` prefix. That prefix is the only thing making it visible in the few
    lines Terry gets.
    """
    return PANEL.get(row.status, ("", ""))[1] + row.subject


def panel_status(row: Row) -> str:
    """The harness status this row MUST carry, or empty when it does not belong."""
    return PANEL.get(row.status, ("", ""))[0]
