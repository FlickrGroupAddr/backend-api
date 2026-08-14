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
EXEMPT = re.compile(r"TRACE-EXEMPT:\s*(.+?)\s*(?:\*/|$)")


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
            body = text[mark.start() : end]
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
    it is what the operator reads when one survives."""
    text = read(MUTATIONS_FILE)
    inside = re.search(r"MUTATIONS = \[(.*?)\n\]", text, re.DOTALL)
    if not inside:
        return []
    return [
        {"name": name, "adrs": sorted(set(ADR_REF.findall(name)))}
        for name in re.findall(r'^\s{8}"([^"]+)",', inside.group(1), re.MULTILINE)
    ]


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

    # ORDER: a reference document is scanned by number, not read front to back. This was
    # ordered by importance once and Terry could not find anything in it.
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    text, gaps = build()

    if not args.check:
        with open(MATRIX, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        print(f"Wrote {MATRIX.relative_to(ROOT)}")

    if gaps:
        print(f"\n{len(gaps)} traceability gap(s):")
        for gap in gaps:
            print(f"  {gap}")
        return 1

    print("Traceability holds in both directions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
