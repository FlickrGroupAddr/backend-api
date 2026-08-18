# Open work

**RFC 2119 keywords. MUST and MUST NOT are absolute. SHOULD is a strong default a good argument may
overrule.**

**Terry's list of things to come back to.** It holds items that are not yet decisions, so they have
no home in `docs/architecture/DECISIONS.md` and no home in an ADR.

**Each row POINTS rather than restates.** The detail lives where it already lives, and a second copy
is a second thing to keep in step. **A row whose detail is written out here MUST be trimmed back to
a pointer.**

**Closing an item means deleting its row**, not marking it done. `git log` is the record of what was
finished; a file of struck-through lines is a file nobody reads to the bottom.

| # | Item | Where the detail is |
|---|---|---|
| 1 | **The 8.5x14 page size** | `DIAGRAM-NOTES.md`, *"SETTLED 2026-08-17: the derived sheets export oversized"*. Legal prints at 76% and 7.7 pt, under the 7.9 pt floor Terry measured. Settled once as acceptable, so reopening it is his call |
| 2 | **Python `sys.argv` to `argparse`** | `~/.claude/hooks/fga-toolchain-check.py` hand-rolls membership tests for `--probe`, `--hook` and `--force-loud-output`. There is no `--help`, and **an unknown flag is silently ignored** — measured 2026-08-18, `--nonsense-flag` runs the human check and exits 3. Survey this repository's own `scripts/*.py` before writing anything |
| 3 | **Horizontal space on the sheets that are not 11x17** | `DIAGRAM-NOTES.md`, *"One open question on the `16x9` spread"*. The spread is even across three gaps, so the drawing reads as four islands. The alternative is weighting it toward the three text panels, which tolerate a wide gutter where the arrows do not |

## Not an item yet, recorded so it is not rediscovered

- **`--probe` run outside a registered project reports `could not reach tsc`.** The root comes from
  the working directory, so a wrong-directory mistake looks like a network failure.
