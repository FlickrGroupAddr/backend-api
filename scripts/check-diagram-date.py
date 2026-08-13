"""SessionStart check: is the architecture diagram's date current, and consistent?

Emits JSON on stdout for the Claude Code hook runner.

Deliberately does NOT bump the date. Dates are versions on this project, so the
date must record when the diagram's CONTENT last changed. Auto-stamping today on
every session would turn it into "date of last session", which is not a version
and destroys the scheme it pretends to serve. The hook reports; a human or Claude
decides.

Volume tracks actionability:
  - filename date != in-file date  -> LOUD. That is drift, and it is a real bug.
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

ROOT = pathlib.Path(__file__).resolve().parent.parent
PATTERN = "FlickrGroupAddr-Architecture-*.drawio"
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def emit(context: str, system: str | None = None) -> None:
    out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}
    if system:
        out["systemMessage"] = system
    print(json.dumps(out))
    sys.exit(0)


def main() -> None:
    arch = ROOT / "docs" / "architecture"
    files = sorted(arch.glob(PATTERN))
    if not files:
        # Silent: this hook is project-scoped, and a missing diagram is not this
        # check's business to complain about.
        sys.exit(0)

    if len(files) > 1:
        names = ", ".join(f.name for f in files)
        emit(
            f"Multiple architecture diagrams present: {names}. Dates are versions here, so "
            f"there should normally be exactly one. Confirm which is current before editing.",
            f"Architecture diagram: {len(files)} dated copies found, expected 1.",
        )

    diagram = files[0]
    today = datetime.date.today()

    m = DATE_RE.search(diagram.name)
    if not m:
        emit(f"Architecture diagram {diagram.name} has no date in its filename; expected one.")
    file_date = m.group(1)

    text = diagram.read_text(encoding="utf-8", errors="replace")
    cell = re.search(r'id="date"\s+value="([^"]*)"', text)
    cell_date = cell.group(1) if cell else None

    if cell_date is None:
        emit(
            f"Architecture diagram {diagram.name} has no date cell to compare against the "
            f"filename date {file_date}.",
            "Architecture diagram: no date cell found.",
        )

    # Loud: the two dates disagree. This is the failure the single DATE constant
    # in build-diagram.py exists to prevent, so it means something bypassed it.
    if cell_date != file_date:
        emit(
            f"ARCHITECTURE DIAGRAM DATE DRIFT. Filename says {file_date}, the slide's date cell "
            f"says {cell_date}. They are generated from one DATE constant in "
            f"scripts/build-diagram.py, so a mismatch means the file was hand-edited or a rename "
            f"was missed. Fix before changing anything else in the diagram.",
            f"Architecture diagram date drift: filename {file_date} vs slide {cell_date}.",
        )

    try:
        age = (today - datetime.date.fromisoformat(file_date)).days
    except ValueError:
        emit(f"Architecture diagram date {file_date} is not a valid ISO date.")

    if age == 0:
        emit(f"Architecture diagram is dated today ({file_date}). No action needed.")

    plural = "day" if age == 1 else "days"
    emit(
        f"Architecture diagram is dated {file_date} ({age} {plural} ago); today is "
        f"{today.isoformat()}. This is correct as long as the diagram has not changed since -- "
        f"the date records when its CONTENT last changed, not the current date. "
        f"IF THE DIAGRAM IS EDITED THIS SESSION: set DATE = \"{today.isoformat()}\" in "
        f"scripts/build-diagram.py, git mv "
        f"docs/architecture/FlickrGroupAddr-Architecture-{file_date}.drawio to the new date, "
        f"then rerun the build so the filename and the slide stay in step."
    )


if __name__ == "__main__":
    main()
