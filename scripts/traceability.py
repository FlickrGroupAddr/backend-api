#!/usr/bin/env python3
"""Generate the requirements traceability matrix, and fail on a gap.

A waterfall RTM is a document somebody maintains by hand, so it drifts the first week
and lies quietly afterwards. This one is DERIVED. It cannot disagree with the tests
because it is built from them.

Two directions, both of which have to hold:

    FORWARD   every ADR is verified by at least one test block.
              A gap means the project decided something nothing checks.

    BACKWARD  every test block cites at least one ADR, or is explicitly exempt.
              A gap means a test nobody can defend -- work no decision asked for.

Third column, which a classic RTM does not have: **which ADRs a mutation can break.**
A test proves the code does the right thing today. A mutation proves the test would
NOTICE the code doing the wrong thing. See scripts/mutation-check.py.

    python scripts/traceability.py            rewrite docs/TRACEABILITY.md
    python scripts/traceability.py --check    verify only, touch nothing

Exit 0 when both directions hold. Exit 1 lists the gaps.

## Granularity, and why it is the `describe` block

Per-test tagging would mean 156 annotations and would rot. A `describe` block is one
coherent risk, which is the unit an ADR actually maps onto. A block inherits any ADR
cited in its own body or in the file's header comment.

## Exemptions are explicit, because a forced link is worse than an honest gap

Some checks are hygiene rather than requirement. `/health` answers 200 because a health
endpoint should, not because an ADR says so. Those carry `TRACE-EXEMPT: <reason>` and are
listed in the matrix as exempt rather than quietly mapped to the nearest ADR. **Pretending
otherwise is how a real RTM becomes decoration.**
"""

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DECISIONS = ROOT / "docs" / "architecture" / "DECISIONS.md"
MATRIX = ROOT / "docs" / "TRACEABILITY.md"
MUTATIONS_FILE = ROOT / "scripts" / "mutation-check.py"

ADR_HEADING = re.compile(r"^##\s+(ADR-\d+)\s+—\s+(.+?)\s*$", re.MULTILINE)
ADR_REF = re.compile(r"ADR-\d+")
DESCRIBE = re.compile(r'^(describe|it)\(\s*"([^"]+)"', re.MULTILINE)
# **Accepts `//` and block comments alike, and takes the reason to end of LINE.**
#
# The previous pattern was `TRACE-EXEMPT:\s*(.+?)\s*(?:\*/|$)` with no `re.MULTILINE`,
# so `$` meant end of STRING. In practice the reason had to sit on one line ending in
# a block-comment close, or be the last thing in the file. **Every other spelling
# parsed as no exemption at all, silently.**
#
# Measured 2026-08-15: `worker.test.ts`'s `/health` exemption had been inert since it
# was written -- a `//` comment the pattern could never match. It passed the gate only
# because two ADRs leaked into it from the next block's lead-in comment, so fixing
# `trim_lead_in` is what exposed it. **Two bugs had been cancelling out.**
EXEMPT = re.compile(r"TRACE-EXEMPT:\s*(.+?)\s*(?:\*/)?\s*$", re.MULTILINE)


def read(path: Path) -> str:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


VERIFICATION = re.compile(r"\*\*Verification:\s*([A-Za-z]+)")


def adrs_declared() -> dict[str, dict]:
    """Every ADR the decisions document defines, with its verification method.

    **Method matters, and this is the VCRM column a plain RTM lacks.** Not every decision
    is verified by running something. ADR-13 pins toolchain versions and ADR-15 says where
    state lives -- both are verified by INSPECTION, and demanding a unit test for them
    would force a fake link. A missing test is only a gap for a decision whose method is
    Test, which is the default when an ADR says nothing.
    """
    text = read(DECISIONS)
    marks = list(ADR_HEADING.finditer(text))
    declared: dict[str, dict] = {}
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[mark.start() : end]
        found = VERIFICATION.search(body)
        declared[mark.group(1)] = {
            "title": mark.group(2),
            "method": found.group(1).capitalize() if found else "Test",
        }
    return declared


def comment_only(line: str) -> bool:
    """True for the line shapes this suite's comments actually use."""
    stripped = line.strip()
    return stripped.startswith(("//", "/*", "*"))


def trim_lead_in(body: str) -> str:
    r"""Drop a trailing comment block, because it belongs to the NEXT block.

    **A block's slice runs from its own `describe(` to the next one, so the doc
    comment introducing the next block lands inside the previous block's body.**
    Every `ADR-nn` in that comment was then credited to the wrong test.

    **Measured 2026-08-15**: `worker.test.ts`'s `/health` test was recorded as
    verifying ADR-07 and ADR-14. It verifies neither. Those come from the comment
    two lines above the `describe` that follows it -- *"ADR-14 chose `hono/html`...
    and ADR-07 makes the Flickr username the only identity"* -- which is a correct
    comment about the diagnostic page, attributed to a health check.

    **The matrix said a decision was verified by a test that never touched it**,
    which is the one failure a traceability matrix cannot survive.

    **A LINE WALK, NOT A REGEX, AND THE FIRST ATTEMPT PROVES WHY.** That version used
    `(?:^[ \t]*(?:/\*[\s\S]*?\*/|//[^\n]*)[ \t]*\n)+[ \t\r\n]*\Z`. `[\s\S]*?` is lazy
    but backtracks across newlines to the LAST `*/` in the slice whenever that makes
    the overall match succeed -- so one comment swallowed the entire block body and
    `/health` was trimmed down to its own `it(` line. **It removed the exemption it was
    supposed to preserve.** This version cannot reach past a non-comment line.
    """
    lines = body.split("\n")
    end = len(lines)

    def drop_blanks() -> None:
        nonlocal end
        while end > 0 and lines[end - 1].strip() == "":
            end -= 1

    drop_blanks()
    while end > 0 and comment_only(lines[end - 1]):
        end -= 1
    drop_blanks()

    return "\n".join(lines[:end])


def blocks() -> list[dict]:
    """Top-level `describe` and `it` blocks across the suite, with the ADRs they cite."""
    found = []
    for path in sorted((ROOT / "test").glob("*.test.ts")):
        text = read(path)
        # Everything before the first top-level block is the file header.
        first = DESCRIBE.search(text)
        header = text[: first.start()] if first else text
        header_adrs = set(ADR_REF.findall(header))

        marks = list(DESCRIBE.finditer(text))
        for i, mark in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            body = trim_lead_in(text[mark.start() : end])
            exempt = EXEMPT.search(body) or EXEMPT.search(header)
            found.append(
                {
                    "file": path.name,
                    "kind": mark.group(1),
                    "name": mark.group(2),
                    "adrs": sorted(set(ADR_REF.findall(body)) | header_adrs),
                    "exempt": exempt.group(1) if exempt else None,
                }
            )
    return found


def mutations() -> list[dict]:
    """Mutation names and the ADRs they name. The name carries the tag on purpose --
    it is what the operator reads when one survives.

    **Parsed with `ast`, because Python owns Python and a regex here was wrong.** The
    previous version matched `^\\s{8}"([^"]+)",` against the MUTATIONS block, and every
    element of a tuple sits at that indentation -- name, path, `find` and `replace`
    alike. So it counted 79 "mutations" for 25, and listed `src/adds/classify.ts` and
    raw source lines as mutation names in the generated matrix.

    **Nothing failed, which is why it lasted.** The gap checks never read this count, so
    the only symptom was a wrong number in a document nobody re-derives.
    """
    tree = ast.parse(read(MUTATIONS_FILE))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "MUTATIONS"
            for target in node.targets
        ):
            return [
                {"name": name, "adrs": sorted(set(ADR_REF.findall(name)))}
                for name, *_ in ast.literal_eval(node.value)
            ]
    return []


def build() -> tuple[str, list[str]]:
    declared = adrs_declared()
    test_blocks = blocks()
    muts = mutations()
    gaps: list[str] = []

    by_adr: dict[str, list[dict]] = {tag: [] for tag in declared}
    for block in test_blocks:
        for tag in block["adrs"]:
            by_adr.setdefault(tag, []).append(block)

    mut_by_adr: dict[str, list[str]] = {}
    for mut in muts:
        for tag in mut["adrs"]:
            mut_by_adr.setdefault(tag, []).append(mut["name"])

    # FORWARD: an ADR nothing verifies. Only a Test-method decision can fail this.
    for tag, meta in declared.items():
        if meta["method"] == "Test" and not by_adr.get(tag):
            gaps.append(f"FORWARD  {tag} is verified by no test block")

    # BACKWARD: a test block defending nothing.
    for block in test_blocks:
        if not block["adrs"] and not block["exempt"]:
            gaps.append(
                f"BACKWARD {block['file']} > \"{block['name']}\" cites no ADR "
                f"and is not TRACE-EXEMPT"
            )

    # An ADR cited by a test that does not exist is a typo, and a silent one.
    for tag in sorted(set(by_adr) - set(declared)):
        gaps.append(f"UNKNOWN  tests cite {tag}, which DECISIONS.md does not define")

    # MAPPING: the old-to-new renumbering table MUST survive.
    #
    # Numbers were renumbered once, on 2026-08-14, so ADR-01 is now the governing
    # decision. 167 ADR mentions across 65 commit messages still use the old numbering
    # and cannot be rewritten. **That table is the only thing keeping them readable**, so
    # deleting it silently breaks every commit written before that date.
    if "## Renumbered 2026-08-14" not in read(DECISIONS):
        gaps.append(
            "MAPPING  DECISIONS.md lost the old-to-new renumbering table; "
            "65 commit messages depend on it"
        )

    # ORDER: numbers now encode importance, so ascending order IS the reading order.
    # A reference is scanned by number, and this was ordered by importance-without-numbers
    # once, which Terry could not navigate at all.
    numbers = [int(tag.split("-")[1]) for tag in declared]
    if numbers != sorted(numbers):
        out_of_place = [
            tag
            for tag, want in zip(declared, sorted(declared, key=lambda t: int(t.split("-")[1])))
            if tag != want
        ]
        gaps.append(
            "ORDER    DECISIONS.md sections are not in ascending ADR order; "
            f"first wrong: {out_of_place[0] if out_of_place else '?'}"
        )

    lines = [
        "# Traceability matrix",
        "",
        "**Generated. Do not edit.** Rebuild with `python scripts/traceability.py`.",
        "",
        "Every decision is verified by a test. Every test defends a decision, or says why",
        "it does not. **`--check` fails the build on either gap.**",
        "",
        "| Column | Answers |",
        "|---|---|",
        "| Verified by | Does anything actually check this decision? |",
        "| Mutation | Would the test NOTICE the code breaking it? |",
        "",
        f"**{len(declared)} decisions · {len(test_blocks)} test blocks · "
        f"{len(muts)} mutations**",
        "",
        "## Forward: decision to verification",
        "",
        "**Method** follows MIL-STD practice. `Test` runs something. `Inspection` is verified",
        "by reading code or config, because there is no runtime behavior to exercise.",
        "",
        "| ADR | Decision | Method | Verified by | Mutation |",
        "|---|---|---|---|---|",
    ]

    for tag, meta in declared.items():
        cover = by_adr.get(tag, [])
        where = (
            "<br>".join(f"`{b['file']}` {b['name']}" for b in cover)
            if cover
            else ("*by inspection*" if meta["method"] != "Test" else "**NONE**")
        )
        breaks = mut_by_adr.get(tag)
        lines.append(
            f"| **{tag}** | {meta['title']} | {meta['method']} | {where} | "
            f"{'yes' if breaks else '—'} |"
        )

    lines += [
        "",
        "## Backward: every test block defends something",
        "",
        "| File | Block | Defends |",
        "|---|---|---|",
    ]
    for block in test_blocks:
        defends = (
            ", ".join(block["adrs"])
            if block["adrs"]
            else f"*exempt — {block['exempt']}*"
        )
        lines.append(f"| `{block['file']}` | {block['name']} | {defends} |")

    lines += ["", "## Mutations, and the decision each one attacks", "",
              "| Mutation | Attacks |", "|---|---|"]
    for mut in muts:
        lines.append(
            f"| {mut['name']} | {', '.join(mut['adrs']) if mut['adrs'] else '—'} |"
        )
    lines.append("")

    return "\n".join(lines), gaps


def staleness_gaps(expected: str) -> list[str]:
    """Is the COMMITTED matrix what this script would generate right now?

    **This closes the hole that let ADR-23 sit missing from the matrix for hours
    while `--check` reported "Traceability holds in both directions".** The check
    validated the ADR-to-test relationship, which was genuinely intact, and never
    looked at the generated document. Terry asked on 2026-08-16; the gap was
    already real when he did.

    **The generator is the checker.** `build()` produces the exact text, so
    comparing it to disk needs no second implementation to drift out of step --
    which is the same argument this file already makes for generating the matrix
    at all rather than maintaining it.

    **Newlines are normalized on both sides deliberately.** The writer emits LF;
    `core.autocrlf` on this machine hands back CRLF. Comparing raw bytes would
    fail on every Windows checkout and teach everybody to ignore the check, which
    is worse than not having it.
    """
    if not MATRIX.exists():
        return [
            f"{MATRIX.relative_to(ROOT)} is MISSING. "
            "Run `python scripts/traceability.py` to write it."
        ]

    with open(MATRIX, encoding="utf-8", newline="") as handle:
        on_disk = handle.read().replace("\r\n", "\n")

    if on_disk == expected:
        return []

    # **Name the ADRs that are absent, because "the file is stale" is not
    # actionable.** This is the specific failure worth calling out: a decision
    # that exists and is invisible in the matrix everyone reads.
    missing = [
        adr for adr in adrs_declared() if f"**{adr}**" not in on_disk
    ]
    detail = (
        f" ADR(s) absent from it: {', '.join(sorted(missing))}."
        if missing
        else " Its content differs; the ADR list itself is complete."
    )
    return [
        f"{MATRIX.relative_to(ROOT)} is STALE -- it is not what this script "
        f"generates.{detail} Run `python scripts/traceability.py`."
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    text, gaps = build()

    if not args.check:
        with open(MATRIX, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        print(f"Wrote {MATRIX.relative_to(ROOT)}")
    else:
        gaps.extend(staleness_gaps(text))

    if gaps:
        print(f"\n{len(gaps)} traceability gap(s):")
        for gap in gaps:
            print(f"  {gap}")
        return 1

    print("Traceability holds in both directions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
