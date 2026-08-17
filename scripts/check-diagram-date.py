"""SessionStart check: is the architecture diagram's date current, and consistent?

Emits JSON on stdout for the Claude Code hook runner.

Deliberately does NOT bump the date. Dates are versions on this project, so the
date must record when the diagram's CONTENT last changed. Auto-stamping today on
every session would turn it into "date of last session", which is not a version
and destroys the scheme it pretends to serve. The hook reports; a human or Claude
decides.

**The diagram is one drawing on several SHEETS**, and they all carry one date --
`diagram_sheets.SHEETS` is the roster. This check therefore expects one date
across every sheet, not one file. Before the sheets existed it expected exactly
one file and would have gone loud on every session once there were three.

Volume tracks actionability:
  - filename date != in-file date  -> LOUD. That is drift, and it is a real bug.
  - sheets carrying two dates      -> LOUD. A rename was missed halfway.
  - a sheet missing, or unexpected -> LOUD. The build writes the whole set.
  - diagram older than today       -> quiet note. Only actionable if the diagram
                                      is edited this session.
  - diagram dated today            -> one confirming line, so silence is never
                                      confused with "the check did not run".
"""

import datetime
import json
import pathlib
import re
import sys
import typing

from diagram_sheets import SHEETS, found_sheets

ROOT = pathlib.Path(__file__).resolve().parent.parent


def emit(context: str, system: str | None = None) -> typing.NoReturn:
    """Write the hook payload and END THE PROCESS. This never returns.

    **`NoReturn` is load-bearing, not decoration.** Every caller below treats
    `emit` as terminal -- `if cell is None: emit(...)` and then dereferences
    `cell` on the next line. Annotated `-> None`, a type checker believes control
    falls through and reports six phantom errors: three `"group" is not a known
    attribute of "None"` and three `"age" is possibly unbound`. **All six were the
    annotation lying, not the code.**
    """
    out: dict[str, object] = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }
    if system:
        out["systemMessage"] = system
    print(json.dumps(out))
    sys.exit(0)


def main() -> None:
    rows = found_sheets(ROOT)
    if not rows:
        # Silent: this hook is project-scoped, and a missing diagram is not this
        # check's business to complain about.
        sys.exit(0)

    # **The LOCAL date is the right one, and the tz argument is what says so.**
    # This compares against a date a human typed into a filename, so it must be
    # the date on Terry's wall, not UTC.
    today = datetime.datetime.now(tz=datetime.UTC).astimezone().date()

    # Loud: dates are versions here, so two dates across the sheets means a rename
    # stopped halfway and half the set is a previous version of the drawing.
    dates = sorted({date for date, _, _ in rows})
    if len(dates) > 1:
        listing = ", ".join(f"{slug} {date}" for date, slug, _ in rows)
        emit(
            f"ARCHITECTURE DIAGRAM SHEETS CARRY {len(dates)} DIFFERENT DATES: {listing}. They are "
            f"one drawing on several sheets and MUST share one date. A rename was missed. Fix "
            f"before changing anything else in the diagram.",
            f"Architecture diagram: sheets split across {len(dates)} dates.",
        )
    file_date = dates[0]

    # Loud: the build writes the whole roster, so a gap means somebody deleted a
    # sheet or the build stopped early with CHECKS_ENABLED off.
    present = {slug for _, slug, _ in rows}
    expected = {sheet.slug for sheet in SHEETS}
    if present != expected:
        missing = ", ".join(sorted(expected - present)) or "none"
        extra = ", ".join(sorted(present - expected)) or "none"
        emit(
            f"ARCHITECTURE DIAGRAM SHEET SET IS WRONG for {file_date}. Missing: {missing}. "
            f"Unexpected: {extra}. scripts/build-diagram.py writes every sheet in "
            f"diagram_sheets.SHEETS, and it writes only the authored one when CHECKS_ENABLED is "
            f"off. Rerun the build.",
            f"Architecture diagram: {len(present)} of {len(expected)} sheets present.",
        )

    # Loud: a filename and its own slide disagree. This is the failure the single
    # DATE constant in build-diagram.py exists to prevent, so it means something
    # bypassed it -- a hand edit, or a rename without a rebuild.
    for date, slug, path in rows:
        text = path.read_text(encoding="utf-8", errors="replace")
        cell = re.search(r'id="date"\s+value="([^"]*)"', text)
        if cell is None:
            emit(
                f"Architecture diagram sheet {path.name} has no date cell to compare against the "
                f"filename date {date}.",
                f"Architecture diagram: no date cell in the {slug} sheet.",
            )
        if cell.group(1) != date:
            emit(
                f"ARCHITECTURE DIAGRAM DATE DRIFT on the {slug} sheet. Filename says {date}, the "
                f"slide's date cell says {cell.group(1)}. They are generated from one DATE "
                f"constant in scripts/build-diagram.py, so a mismatch means the file was "
                f"hand-edited or a rename was missed. Fix before changing anything else in the "
                f"diagram.",
                f"Architecture diagram date drift: {slug} filename {date} "
                f"vs slide {cell.group(1)}.",
            )

    try:
        age = (today - datetime.date.fromisoformat(file_date)).days
    except ValueError:
        emit(f"Architecture diagram date {file_date} is not a valid ISO date.")

    sheets = ", ".join(slug for _, slug, _ in rows)
    if age == 0:
        emit(
            f"Architecture diagram is dated today ({file_date}), on {len(rows)} sheets "
            f"({sheets}). No action needed."
        )

    plural = "day" if age == 1 else "days"
    emit(
        f"Architecture diagram is dated {file_date} ({age} {plural} ago), on {len(rows)} sheets "
        f"({sheets}); today is {today.isoformat()}. This is correct as long as the diagram has not "
        f"changed since -- the date records when its CONTENT last changed, not the current date. "
        f"Adding or resizing a SHEET is not a content change and MUST NOT bump it. "
        f"IF THE DRAWING ITSELF IS EDITED THIS SESSION: set DATE = \"{today.isoformat()}\" in "
        f"scripts/build-diagram.py, git mv ALL {len(rows)} sheets under docs/architecture/ to the "
        f"new date, then rerun the build so every filename and the slide stay in step."
    )


if __name__ == "__main__":
    main()
