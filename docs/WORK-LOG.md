# Work log

**RFC 2119 keywords. MUST and MUST NOT are absolute. SHOULD is a strong default a good argument may
overrule.**

**THIS FILE IS THE SINGLE SOURCE OF TRUTH FOR OUTSTANDING WORK, and it is a PERMANENT, APPEND-ONLY
LOG.** The harness task list Terry sees is a filtered rendering of it, never the other way round.

---

## THE SYNC CONTRACT. Read this before touching either list

**Standing order, Terry, 2026-08-18, verbatim: *"having our two views of outstanding work out of
sync is worse than not having any lists at all."*** RFC 2119 sense, and the capitals are
load-bearing.

**The reason it needs a contract is that WE ARE BLIND TO EACH OTHER'S VIEW.** Terry sees the task
panel and cannot open this file mid-conversation. Claude writes this file and cannot see the
rendered panel. **Neither of us can notice a divergence, so neither of us will.**

### THE WEB VIEW IS THE ONE TO OPEN, and it cannot diverge

```
python scripts/worklog-server.py     # once, in the background
```

**Then open `http://127.0.0.1:8792/` and leave it open.** Every write to this file
repaints that tab within 400 ms -- no commit, no push, nothing to copy. A bar across the
top carries the open counts, the file's write time and a **reload counter**, because a
list that did not change and a server that stopped answering produce the identical
screenshot.

**It reads THIS FILE, so it cannot drift from it.** That is the whole reason it exists,
in Terry's words: *"if we could get it to auto-refresh on every .md write that claude
makes, do we have a better system?"* **Yes -- because the sync problem below only exists
where there are two copies, and the web view is not a copy.**

**It also has no size limit**, so the log is written for a reader rather than trimmed to
fit somebody's five lines. `Hide landed` defaults to on and the toggle sticks per browser.

**The harness panel is still synced, and it is now the convenience copy** -- it lives in
the terminal Terry is already looking at, and its `activeForm` drives the spinner while
Claude works. **Everything below governs that copy.**

### The two views are DELIBERATELY different, and that is the whole design

| | This file | Terry's panel |
|---|---|---|
| Holds | **Everything, forever.** Append-only | **Only what has not landed yet** |
| `completed` rows | **Kept, with the date** | **PURGED** |
| Size | Grows without limit | **About five lines.** It MUST stay scannable |

**Terry's words: *"it needs to stay trimmed to shit we have not landed yet."*** The panel is a
working surface with a hard size budget, and this file is the record. **A completed item MUST be
marked `completed` here and REMOVED from the panel in the same turn.**

### The duty is entirely Claude's

- **Any change to this file MUST be followed, in the SAME TURN, by re-syncing the panel.**
- **A request to "add to the task list" means: write THIS FILE first, then sync.** The file leads,
  always. **Claude MUST NOT create a task that has no row here.**
- **Claude MUST verify by READING the task store, never from memory of the calls it just made.**
  The store is `~/.claude/tasks/<session-id>/<n>.json`, and the session id is the directory most
  recently modified. **A `TaskCreate` that returned success is not evidence the panel matches this
  file.** `python scripts/worklog-sync-check.py` does the comparison and names every mismatch.
- **A heavyweight rebuild is ALWAYS acceptable** -- delete every task and re-add from the Open table
  top to bottom. Terry blessed it explicitly. **The panel orders by task id, so inserting a row
  anywhere but the end REQUIRES a rebuild.**
- **A fresh session starts with an empty panel**, because the task list does not survive one.
  Rebuild it from this file before reporting on outstanding work.

### The four states, and `blocked` is strict

| State here | In the panel | Meaning |
|---|---|---|
| `not_started` | `pending` | Nobody has begun |
| `in_progress` | `in_progress` | Being worked now |
| **`blocked`** | `pending`, **subject prefixed `BLOCKED: `** | **NEITHER of us can move it**, because of something outside our control. Terry keeps it in view so he can push when he can |
| `completed` | **ABSENT** | Landed. Row stays here with its date |

### `in_progress` IS A ONE-WAY BIT FLIP

**Standing order, Terry, 2026-08-18: *"once in progress always in progress -- that's a one way bit
flip."*** RFC 2119 sense -- **MUST NOT is absolute.**

**A row MUST NOT go back from `in_progress` to `not_started`.** The only move out of `in_progress`
is `completed`, or `blocked` when something outside our control stops it.

**Why, and it is not bookkeeping:** started work leaves residue -- a branch, a half-edited file, a
decision already taken. **Marking it `not_started` claims a clean slate that does not exist**, and
the next session believes it. Deprioritizing is not un-starting; the row simply moves down.

**So a new top priority does NOT demote the item it interrupts.** Both stay `in_progress` and the
order carries the priority, which is the case the rule below deliberately permits.

### ONE ROW SHOULD BE `in_progress`, and more is allowed

**Terry, 2026-08-18: *"My brain is exceedingly serial. I need exactly one active thing in front of
me supplemented with a reliable written list. If you ask me to remember a queue of 2 items it's no
bueno and things get dropped in a hurry."*** **SHOULD, in the RFC 2119 sense.**

**He walked back the absolute himself, the same day, and the correction matters:** *"multi in
progress isn't fatal if I have it written down and can context switch."*

**So the risk is UNWRITTEN parallel work, not parallel work.** One active item is the right default
and a second is a judgment call he is entitled to make. `scripts/worklog-sync-check.py` therefore
prints a NOTE and does not fail -- **a check that fires on something legitimate is the check he
learns to scroll past**, which is this project's own loudness rule pointed at itself.

**Two consequences for how Claude works:**

- **Never hand him a queue in prose.** *"Once X is done, also do Y and Z"* is three things in his
  head and two are already gone. **Give him X.** The log holds Y and Z.
- **When something new arrives mid-task, write it here and SAY that you wrote it.** Do not ask him
  to hold it, and do not ask whether to switch unless it genuinely blocks the active item.

**`blocked` is a strict definition and MUST NOT be used loosely.** Terry's own: it means outside
forces beyond our control, not "waiting on a decision" and not "hard". **Anything either of us could
pick up right now is `not_started`.** The panel carries no blocked status of its own, so the prefix
is what makes it visible in his five lines.

---

## Open

**One task per row, same order, subject character for character. `scripts/worklog-sync-check.py`
asserts it.**

| # | Status | Task subject | Where the detail is |
|---|---|---|---|
| 1 | `in_progress` | `Build the shared work-log web view` | **Top priority, nothing derails it.** Terry's call, 2026-08-18: the diagram preview already proves the pattern -- Claude writes a file, the browser tab redraws itself, and we both read the same artifact. Doing the same for this log removes the two-view sync problem rather than policing it, and lifts the ~5-line panel budget. Model it on `scripts/preview-server.py`. Needs a `hide landed` toggle, defaulting to ON. **NOT DONE until the current list renders in a browser tab we can both read** |
| 2 | `in_progress` | `Clean up toolchain output` | `~/.claude/hooks/fga-toolchain-check.py` renders two tiers with different row formats -- clean is `name  latest <ver>  installed <ver>`, behind is `name : verdict (version)` in a 21-char label column. Terry is redesigning the rows and wants both consistent. `--force-loud-output` renders the behind tier on a current machine |
| 3 | `not_started` | `Settle the 8.5x14 page size` | `DIAGRAM-NOTES.md`, *"SETTLED 2026-08-17: the derived sheets export oversized"*. Legal prints at 76% and 7.7 pt, under the 7.9 pt floor Terry measured. Settled once as acceptable, so reopening it is his call |
| 4 | `not_started` | `Convert Python sys.argv handling to argparse` | `~/.claude/hooks/fga-toolchain-check.py` hand-rolls membership tests for its three flags. There is no `--help`, and **an unknown flag is silently ignored** -- measured 2026-08-18, `--nonsense-flag` runs the human check and exits 3. Survey this repository's own `scripts/*.py` first |
| 5 | `not_started` | `Rework horizontal space on the non-11x17 sheets` | `DIAGRAM-NOTES.md`, *"One open question on the `16x9` spread"*. The spread is even across three gaps, so the drawing reads as four islands. The alternative is weighting it toward the three text panels, which tolerate a wide gutter where the arrows do not |

## Landed

**Append-only. Rows arrive here and never leave.** Newest last.

| Landed | Task subject | Note |
|---|---|---|
| — | — | Nothing yet under this contract |

## Not an item yet, recorded so it is not rediscovered

- **`--probe` run outside a registered project reports `could not reach tsc`.** The root comes from
  the working directory, so a wrong-directory mistake looks like a network failure.
