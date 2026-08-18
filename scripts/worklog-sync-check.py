"""Is the harness task list a faithful rendering of `docs/WORK-LOG.md`?

    python scripts/worklog-sync-check.py

**Standing order, Terry, 2026-08-18: *"having our two views of outstanding work
out of sync is worse than not having any lists at all."*** `docs/WORK-LOG.md` is the
single source of truth and the task panel is a FILTERED rendering of it. The full
contract is at the top of that file.

**The two views differ on purpose.** The file is a permanent append-only log and
keeps `completed` rows forever; the panel shows only what has not landed, because
Terry gets about five lines of it. **So this compares the panel against the OPEN
table only, and additionally asserts that nothing `completed` leaked into it.**

**`blocked` has no panel status of its own**, so it renders as `pending` with the
subject prefixed `BLOCKED: `. That prefix is what makes it visible in five lines.

**This exists because the two of us are blind to each other's view.** Terry sees
the panel and cannot open the file mid-conversation; Claude writes the file and
cannot see the panel. **Neither of us can spot a divergence**, so the only honest
check reads the task store off disk rather than trusting either impression.

**The store is `~/.claude/tasks/<session-id>/<n>.json`**, one JSON file per task,
and the session id is the directory most recently modified. That is an observed
layout rather than a documented one, so this script is deliberately forgiving
about not finding it.

**IT IS NOT IN `npm run check`, ON PURPOSE.** The task list is per-session and
lives outside the repository, so a gate step would fail on a fresh clone, in CI,
and in any session that has not built the panel yet. **A check that fires when
nobody can act is the warning that teaches people to ignore warnings** -- this
project's own loudness rule, applied to itself. Run it by hand, or after editing
`docs/WORK-LOG.md`.

Exit codes: 0 in sync, 1 diverged, 0 with a note when there is no store to read.
"""

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG = ROOT / "docs" / "WORK-LOG.md"
STORE = pathlib.Path.home() / ".claude" / "tasks"

# `| n | `status` | `subject` | detail |`, backticked so the mapping is exact
# rather than judged. The status vocabulary is the task tool's own, so neither
# side needs translating.
ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|")

# Only the Open table feeds the panel. A heading ends the region we read.
OPEN_HEADING = "## Open"
END_HEADINGS = ("## Landed", "## Not an item yet")

# TODO state -> (panel status, subject prefix). `completed` never reaches the panel.
PANEL = {
    "not_started": ("pending", ""),
    "in_progress": ("in_progress", ""),
    "blocked": ("pending", "BLOCKED: "),
}

# Terry sees roughly five lines. Over that is a note, never a failure -- the list
# being long is a fact about the work, not a defect in the sync.
PANEL_BUDGET = 5

# Placeholder when the panel has more tasks than the log has open rows.
MISSING_ROW = "<no row in the log>"


def log_rows() -> list[tuple[str, str, str]]:
    """(number, status, task subject) for every row of the list, in file order."""
    out: list[tuple[str, str, str]] = []
    inside = False
    for line in LOG.read_text(encoding="utf-8").splitlines():
        if line.startswith(OPEN_HEADING):
            inside = True
            continue
        if inside and line.startswith(END_HEADINGS):
            break
        if not inside:
            continue
        m = ROW_RE.match(line)
        if m:
            out.append((m.group(1), m.group(2), m.group(3)))
    return out


def newest_store() -> pathlib.Path | None:
    """The task directory for the most recent session, or None if there is none."""
    if not STORE.is_dir():
        return None
    dirs = [d for d in STORE.iterdir() if d.is_dir()]
    return max(dirs, key=lambda d: d.stat().st_mtime) if dirs else None


def tasks_in(store: pathlib.Path) -> list[tuple[str, str, str]]:
    """(id, subject, status) for every task, ordered by numeric id.

    **Sorted by `int(stem)` rather than by name**, because a plain sort puts task
    10 between 1 and 2 and the order is half of what this script asserts.
    """
    out: list[tuple[str, str, str]] = []
    for f in sorted(store.glob("*.json"), key=lambda p: int(p.stem)):
        d = json.loads(f.read_text(encoding="utf-8"))
        out.append((str(d["id"]), str(d["subject"]), str(d.get("status", "?"))))
    return out


def main() -> int:
    rows = log_rows()
    store = newest_store()
    if store is None:
        print(f"  No task store under {STORE}. Nothing to compare -- not a failure.")
        return 0

    tasks = tasks_in(store)
    print(f"  session store : {store.name}")
    print(f"  log rows      : {len(rows)}")
    print(f"  tasks on disk : {len(tasks)}")
    print()

    ok = len(rows) == len(tasks)
    for i in range(max(len(rows), len(tasks))):
        row = rows[i] if i < len(rows) else ("-", "-", MISSING_ROW)
        task = tasks[i] if i < len(tasks) else ("-", "<no task in the list>", "-")
        want_status, prefix = PANEL.get(row[1], ("<unknown state>", ""))
        same = (row[2] != MISSING_ROW
                and prefix + row[2] == task[1]
                and want_status == task[2])
        ok = ok and same
        print(f"    {'ok  ' if same else 'DIFF'} {row[0]:>2}  [{row[1]}] {prefix}{row[2]}")
        if not same:
            print(f"         task {task[0]:>2}  [{task[2]}] {task[1]}")

    print()
    bad_state = [r for r in rows if r[1] not in PANEL]
    for r in bad_state:
        print(f"    row {r[0]} has state {r[1]!r}, which is not a panel state. "
              f"A completed row belongs under Landed, not Open.")
    ok = ok and not bad_state

    if ok:
        print(f"  IN SYNC. {len(rows)} open item(s).")
        if len(rows) > PANEL_BUDGET:
            print(f"  NOTE: {len(rows)} rows against a ~{PANEL_BUDGET}-line panel. "
                  f"Terry cannot see the tail.")
        return 0
    print("  OUT OF SYNC. docs/WORK-LOG.md leads -- rebuild the task list from it.")
    print("  A heavyweight rebuild is always acceptable: delete every task, re-add from the file.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
