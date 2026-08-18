"""Is the harness task panel a faithful rendering of `docs/WORK-LOG.md`?

    python scripts/worklog-sync-check.py

**Standing order, Terry, 2026-08-18: *"having our two views of outstanding work
out of sync is worse than not having any lists at all."*** `docs/WORK-LOG.md` is
the single source of truth and the panel is a FILTERED rendering of it. The full
contract is at the top of that file.

**This exists because the two of us are blind to each other's view.** Terry sees
the panel and cannot open the file mid-conversation; Claude writes the file and
cannot see the panel. **Neither of us can spot a divergence**, so the only honest
check reads the task store off disk rather than trusting either impression.

**The two views differ on purpose.** The file is a permanent append-only log and
keeps `completed` rows forever; the panel shows only what has not landed. **So
this compares the panel against the OPEN table only, and additionally refuses to
let a `completed` row sit there.**

**The store is `~/.claude/tasks/<session-id>/<n>.json`**, one JSON file per task,
and the session id is the directory most recently modified. That is an observed
layout rather than a documented one, so this script is deliberately forgiving
about not finding it.

**IT IS NOT IN `npm run check`, ON PURPOSE.** The panel is per-session and lives
outside the repository, so a gate step would fail on a fresh clone, in CI, and in
any session that has not built it yet. **A check that fires when nobody can act is
the warning that teaches people to ignore warnings** -- this project's own loudness
rule, applied to itself.

Exit codes: 0 in sync, 1 diverged, 0 with a note when there is no store to read.
"""

import json
import pathlib
import sys

import worklog

STORE = pathlib.Path.home() / ".claude" / "tasks"

# Terry sees roughly five lines of panel. Over that is a note, never a failure --
# a long list is a fact about the work, not a defect in the sync.
PANEL_BUDGET = 5

# Placeholder when the panel holds more tasks than the log has open rows.
MISSING_ROW = "<no row in the log>"


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
    rows = worklog.open_rows()
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
        row = rows[i] if i < len(rows) else worklog.Row("-", "-", MISSING_ROW, "")
        task = tasks[i] if i < len(tasks) else ("-", "<no task in the panel>", "-")
        want_subject = worklog.panel_subject(row)
        want_status = worklog.panel_status(row)
        same = (row.subject != MISSING_ROW
                and want_subject == task[1]
                and want_status == task[2])
        ok = ok and same
        print(f"    {'ok  ' if same else 'DIFF'} {row.key:>2}  [{row.status}] {want_subject}")
        if not same:
            print(f"         task {task[0]:>2}  [{task[2]}] {task[1]}")

    # **One active item is the DEFAULT, not a rule.** Terry's working memory is
    # serial, and he walked the absolute back himself: *"multi in progress isn't
    # fatal if I have it written down and can context switch."* `in_progress` is
    # also a one-way flip, so a new priority STACKS rather than demoting what it
    # interrupted -- which makes two actives the normal state, not an exception.
    #
    # **So this reports and never fails.** A check that fires on something he
    # legitimately chose is the check he learns to scroll past.
    active = [r for r in rows if r.status == "in_progress"]
    if len(active) > 1:
        print()
        print(f"    NOTE: {len(active)} items are in_progress.")
        print("          Normal -- in_progress is a one-way flip, so a new priority stacks")
        print("          on top rather than demoting what it interrupted.")
        for r in active:
            print(f"            row {r.key}  {r.subject}")

    # A `completed` row belongs under Landed. Left in Open it would be rendered
    # into the panel, which is the one thing the panel must never carry.
    stranded = [r for r in rows if r.status not in worklog.PANEL]
    for r in stranded:
        print(f"    row {r.key} has state {r.status!r}. A completed row belongs under Landed.")
    ok = ok and not stranded

    print()
    if ok:
        print(f"  IN SYNC. {len(rows)} open item(s).")
        if len(rows) > PANEL_BUDGET:
            print(f"  NOTE: {len(rows)} rows against a ~{PANEL_BUDGET}-line panel. "
                  f"The web view at scripts/worklog-server.py has no such limit.")
        return 0
    print("  OUT OF SYNC. docs/WORK-LOG.md leads -- rebuild the panel from it.")
    print("  A heavyweight rebuild is always acceptable: delete every task, re-add from the file.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
