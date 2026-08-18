"""Every Python script MUST parse its arguments with `argparse`. Nothing else.

    python scripts/argparse-check.py

**Standing order, Terry, 2026-08-18, and it is GLOBAL: *"all Python cmdline arg
parsing RFC-MUST be done with argparse module, zero exceptions."*** His words on
the state that prompted it: *"I saw some of your scripts using Python sys.argv and
I fucking hate it. personal pref but I fucking hate it."*
<!-- DIRTY-WORDS-EXEMPT: quoting Terry -->

## THE EXEMPTION IS TERRY'S, AND CLAUDE MUST NOT WRITE ONE

**He softened "zero exceptions" the same day:** *"Can add an EXEMPT tag but unlike
most EXEMPT tags, Terry owns the sys.argv EXEMPT tag. Only I can authorize its use."*
And on the existing offenders: *"I didn't mean to force you to blow up the world, I
will grandfather where needed, it's not retroactive."*

**So `ARGV-EXEMPT: <reason>` on the offending line suppresses it -- and Claude MUST
NOT add one.** Not to make a build green, not to grandfather a file it judges old,
not with a good reason. **Convert it, or leave the check red and say so.** This
mirrors the RFC 2119 exemption rule in `~/.claude/CLAUDE.md`: an exemption anybody
can grant is not an exemption, it is an opinion.

**Every exemption in the tree is PRINTED on every run**, never silently honored. A
suppression nobody sees is how a rule quietly stops applying.

## It reads the AST, not the text, and that is the whole reason it is usable

**A regex for `sys.argv` matches this file's own docstring, every comment that
explains the rule, and every commit message quoted in a docstring.** Half this
repository's scripts discuss argument handling in prose. **A checker that fires on
the sentence describing it gets switched off within a day**, which is the failure
`claude-dirty-words.py` already documents from the other direction.

So this parses each file and looks for the real thing:

  * `sys.argv` as an attribute access, however it is spelled
  * `from sys import argv`, and any later use of the bare name
  * `import getopt` and `import optparse`, the two stdlib predecessors

**Reading `sys.argv[0]` is NOT parsing.** A script asking its own program name is
doing something argparse also does internally, and failing it would be a rule about
a substring rather than about behavior. That carve-out is in the code below and it
is the one place this checker forgives anything.

## What it deliberately does not do

**It does not require that a script HAVE arguments.** Most of these take none, and
demanding an `ArgumentParser` in a script with nothing to parse would be ceremony.
The rule is about HOW arguments are read, not whether they exist.
"""

import argparse
import ast
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The two stdlib modules argparse replaced. Importing either is the same defect as
# hand-rolling, one layer up.
SUPERSEDED = frozenset({"getopt", "optparse"})

# **Terry's marker, and only he may add it.** See the docstring. It is matched on the
# raw source line, since a comment does not survive into the AST.
EXEMPT = "ARGV-EXEMPT:"


class Finding(ast.NodeVisitor):
    """Every place a file reads argv or imports a superseded parser."""

    def __init__(self, parent_of: dict[int, ast.AST]) -> None:
        self.parent_of = parent_of
        self.hits: list[tuple[int, str]] = []
        # `from sys import argv` binds a bare name, so later uses look like any
        # other identifier. Tracking the import is what makes those findable.
        self.bare_argv = False

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name in SUPERSEDED:
                self.hits.append((node.lineno, f"import {alias.name}"))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module in SUPERSEDED:
            self.hits.append((node.lineno, f"from {node.module} import ..."))
        if node.module == "sys" and any(a.name == "argv" for a in node.names):
            self.bare_argv = True
            self.hits.append((node.lineno, "from sys import argv"))
        self.generic_visit(node)

    def _is_index_zero(self, node: ast.AST) -> bool:
        """True when this argv reference is the `[0]` program-name read."""
        parent = self.parent_of.get(id(node))
        if not isinstance(parent, ast.Subscript):
            return False
        idx = parent.slice
        return isinstance(idx, ast.Constant) and idx.value == 0

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # **`sys.argv[0]` is the program's own name, not an argument.** argparse
        # reads it too, for the usage line. Failing it would make this a rule about
        # a substring rather than about how arguments get parsed.
        if (node.attr == "argv"
                and isinstance(node.value, ast.Name)
                and node.value.id == "sys"
                and not self._is_index_zero(node)):
            self.hits.append((node.lineno, "sys.argv"))
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if self.bare_argv and node.id == "argv" and not self._is_index_zero(node):
            self.hits.append((node.lineno, "argv"))
        self.generic_visit(node)


def parents(tree: ast.AST) -> dict[int, ast.AST]:
    """A child-to-parent map, keyed by `id()`.

    **`ast` gives no parent link and nodes take no new attributes**, so this is a
    side table rather than a stamp. Without it `sys.argv[0]` and `sys.argv[1:]` are
    the same attribute access and there is no way to forgive one.
    """
    return {id(child): parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)}


def tracked_python() -> list[pathlib.Path]:
    """Every `.py` git tracks, so a scratch file cannot fail the build.

    **`git ls-files` rather than a glob**, for the same reason the diagram build
    derives its rosters: a glob picks up anything sitting in the tree, and a
    throwaway probe in the working directory is not this rule's business.
    """
    out = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT,
                         capture_output=True, text=True, check=True)
    return [ROOT / line for line in out.stdout.splitlines() if line.strip()]


def scan(path: pathlib.Path) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """(offenders, exempted) for one file.

    **The exemption is matched against the SOURCE LINE, not the AST**, because a
    comment is exactly what the AST throws away. That is the one place this checker
    reads text, and it is deliberate.
    """
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines()
    tree = ast.parse(src, filename=str(path))
    finder = Finding(parents(tree))
    finder.visit(tree)
    # **One line can hold two reads**, so identical (line, what) pairs are collapsed.
    # Reporting `probe-catalog.py:161 sys.argv` twice reads as two defects.
    bad: list[tuple[int, str]] = []
    ok: list[tuple[int, str]] = []
    for line, what in sorted(set(finder.hits)):
        text = lines[line - 1] if 0 < line <= len(lines) else ""
        (ok if EXEMPT in text else bad).append((line, what))
    return bad, ok


def self_test() -> bool:
    """Prove it fires AND that it stays quiet, because half-validated is useless.

    **The quiet half matters more here.** This checker's whole viability rests on
    not flagging the prose that describes the rule, and a file full of the word
    `argv` in comments is exactly what it must pass.
    """
    must_fire = [
        ("plain read", "import sys\nx = sys.argv[1]\n"),
        ("slice", "import sys\nargs = sys.argv[1:]\n"),
        ("membership", "import sys\nif '--check' in sys.argv:\n    pass\n"),
        ("bare import", "from sys import argv\nx = argv[1]\n"),
        ("getopt", "import getopt\n"),
        ("optparse", "import optparse\n"),
    ]
    must_pass = [
        ("argparse", "import argparse\np = argparse.ArgumentParser()\np.parse_args()\n"),
        ("program name", "import sys\nprint(sys.argv[0])\n"),
        ("prose only", "'''Do not use sys.argv here, use argparse.'''\nimport argparse\n"),
        ("comment only", "import argparse  # never sys.argv\n"),
        ("unrelated attr", "import types\nx = types.argv if False else 1\n"),
    ]
    ok = True
    for name, src in must_fire:
        tree = ast.parse(src)
        f = Finding(parents(tree))
        f.visit(tree)
        if not f.hits:
            print(f"    SELF-TEST FAILED: {name!r} should have fired")
            ok = False
    for name, src in must_pass:
        tree = ast.parse(src)
        f = Finding(parents(tree))
        f.visit(tree)
        if f.hits:
            print(f"    SELF-TEST FAILED: {name!r} should have been quiet, got {f.hits}")
            ok = False
    print(f"  Self-test: {len(must_fire)} must fire, {len(must_pass)} must not"
          f" -- {'all pass' if ok else 'FAILED'}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--list", action="store_true",
                        help="Print every scanned file rather than only the offenders.")
    args = parser.parse_args()

    if not self_test():
        return 1

    files = tracked_python()
    offenders: list[tuple[pathlib.Path, list[tuple[int, str]]]] = []
    exempted: list[tuple[pathlib.Path, list[tuple[int, str]]]] = []
    for path in files:
        bad, ok = scan(path)
        if bad:
            offenders.append((path, bad))
        if ok:
            exempted.append((path, ok))
        if args.list and not bad:
            print(f"    ok   {path.relative_to(ROOT)}")

    # **Printed even when the run passes.** A suppression nobody sees is how a rule
    # quietly stops applying, and these are Terry's to review.
    for path, hits in exempted:
        for line, what in hits:
            print(f"    EXEMPT {path.relative_to(ROOT)}:{line}  {what}  (Terry-authorized)")

    for path, hits in offenders:
        rel = path.relative_to(ROOT)
        for line, what in hits:
            print(f"    FAIL {rel}:{line}  {what}")

    print(f"  Checked {len(files)} tracked .py file(s) for hand-rolled argument parsing"
          f"{f', {sum(len(h) for _, h in exempted)} exempt' if exempted else ''}.")
    if offenders:
        print("  Terry's standing order: all Python cmdline arg parsing MUST use argparse.")
        print("  Convert it, or leave this red -- CLAUDE MUST NOT add an ARGV-EXEMPT marker.")
        return 1
    print("  All argument parsing goes through argparse.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
