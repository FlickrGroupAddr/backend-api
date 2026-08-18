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

### THE STATE MACHINE, and TERRY OWNS `completed`

**Standing order, Terry, 2026-08-18: *"claude can add tasks and change status on tasks. Only
exception to status change: Terry and only Terry owns COMPLETED. I have signoff on all tasks."***
RFC 2119 sense -- **MUST NOT is absolute.**

```
                 +-----------------------------------+
                 |                                   |
  not_started -->+--> in_progress <--> blocked <--> ready_for_review
                                                          |
                                                          | TERRY'S SIGNOFF ONLY
                                                          v
                                                      completed
```

| State | In the panel | Meaning |
|---|---|---|
| `not_started` | `pending` | Nobody has begun |
| `in_progress` | `in_progress` | Being worked now |
| `blocked` | `pending`, prefixed `BLOCKED: ` | **NEITHER of us can move it**, because of something outside our control |
| `ready_for_review` | **`in_progress`** | **Claude believes it is done and is waiting on Terry.** This is as far as Claude may take anything. **His view shows it as in progress** -- his call, *"ready for review in yours"* -- because from his side the item IS still in flight until he signs it off |
| `completed` | **ABSENT** | Terry signed it off. Row moves to Landed with the signoff timestamp |

**The middle three bounce freely** -- his words, *"no one way arrows on state transition diagram
for following three"*. Work can go back to `in_progress` from review, or become `blocked` from
anywhere. **`not_started` reaches all three.**

**CLAUDE MUST NOT SET `completed`.** Not when the tests pass, not when the deliverable visibly
works, not when it is obvious. **`ready_for_review` is the ceiling**, and Terry's explicit signoff
is the only thing that crosses the last edge.

**Claude datetime-stamps the signoff** in the Landed row, from his message rather than from a guess.

**Why the ceiling matters more than it looks:** twice on 2026-08-18 Claude marked its own work
complete -- the web view and the argparse gate -- and both were wrong, because Terry had said
outright *"we haven't cut over to web tool until I approve it."* **A worker who signs off their own
work has no reviewer**, and the whole value of the shared list is that he sees what is waiting.

### ONE ROW SHOULD BE `in_progress`, and more is allowed

**Terry, 2026-08-18: *"My brain is exceedingly serial. I need exactly one active thing in front of
me supplemented with a reliable written list. If you ask me to remember a queue of 2 items it's no
bueno and things get dropped in a hurry."*** **SHOULD, in the RFC 2119 sense.**

**He walked back the absolute himself, the same day:** *"multi in progress isn't fatal if I have it
written down and can context switch."* **And the state machine above makes several actives normal
rather than exceptional** -- a new priority does not demote what it interrupted.

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
| 1 | `ready_for_review` | `Convert Python sys.argv handling to argparse` | `scripts/argparse-check.py` reads the AST, so prose about the rule does not trip it, and self-tests six must-fire and five must-not cases every run. Wired into `npm run check` as step 5. Converted `build-diagram.py`, `lua-balance.py`, `probe-catalog.py` and `fga-toolchain-check.py` -- all four gained a `--help`, and the hook now REJECTS an unknown flag instead of silently running the human path. `ARGV-EXEMPT:` is Terry's marker alone |
| 2 | `ready_for_review` | `Build the shared work-log web view` | `scripts/worklog-server.py` serves `docs/WORK-LOG.md` at `http://127.0.0.1:8792/`, repainting within 400 ms of every write. Parses the tables through `scripts/worklog.py`, shared with the sync checker so two readers cannot drift. `Hide landed` defaults on and sticks per browser. Verified in a live tab, including the empty-parse banner |
| 3 | `in_progress` | `Clean up toolchain output` | `~/.claude/hooks/fga-toolchain-check.py` renders two tiers with different row formats -- clean is `name  latest <ver>  installed <ver>`, behind is `name : verdict (version)` in a 21-char label column. Terry is redesigning the rows and wants both consistent. `--force-loud-output` renders the behind tier on a current machine |
| 4 | `not_started` | `Make the 8.5x14 export actually BE 8.5x14` | **Terry, 2026-08-18, restating the ask:** the PDF and PNG come out at the right ASPECT RATIO but not at legal size, so printing needs *Fit on page* and *"it's minor but feels stupid"*. **He wants the annoyance gone**, and is open to any route -- including a new drawing space that IS 8.5x14 with the geometry airlifted across and scaled down proportionally, since the drop is 11 in to 8.5 in of height. Today the sheet carries `pageScale` 1.3165, and draw.io sizes an exported page as `pageWidth * pageScale`, which is where the 18.43 x 11.19 in comes from. **The refusal to rescale geometry is a real constraint** -- every font size and every threshold in the check suite would stop meaning what it means -- so a solution has to keep the AUTHORED canvas at 11x17 and do any scaling on the way out. See `DIAGRAM-NOTES.md`, *"SETTLED 2026-08-17"*, which this supersedes |
| 5 | `not_started` | `Rework horizontal space on the non-11x17 sheets` | `DIAGRAM-NOTES.md`, *"One open question on the `16x9` spread"*. The spread is even across three gaps, so the drawing reads as four islands. The alternative is weighting it toward the three text panels, which tolerate a wide gutter where the arrows do not |
| 6 | `not_started` | `Decide on argparse for the nine ~/.claude hooks` | The global standing order covers them, and Terry said it is **not retroactive** -- *"I will grandfather where needed."* `fga-toolchain-check.py` was converted because it was already being worked. **Nine others still read `sys.argv`**: `claude-dirty-words-stop`, `diagrams-readonly-stop`, `git-push-stop`, `hook-health`, `lint-toolchain-check`, `nas-guard-probe`, `orientation-inject`, `rejected-hook-sites-tripwire`, `rust-toolchain-check`. **Converting nine hooks unasked is the "blow up the world" he warned against**, so this is his call: convert, grandfather, or leave until each is next touched. `~/.claude` has no gate to hang a checker on |

## Landed

**Append-only. Rows arrive here and never leave.** Newest last.

| Landed | Task subject | Note |
|---|---|---|
| — | — | Nothing signed off yet |

## Not an item yet, recorded so it is not rediscovered

- **`--probe` run outside a registered project reports `could not reach tsc`.** The root comes from
  the working directory, so a wrong-directory mistake looks like a network failure.
