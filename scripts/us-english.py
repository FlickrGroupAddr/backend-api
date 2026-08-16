#!/usr/bin/env python3
"""Fail the build on British spellings. Terry's standing order is US English.

    python scripts/us-english.py

Exit 0 when clean. Exit 1 lists every hit as `file:line`, which the terminal
renders as a clickable link.

WHY A CHECK AND NOT A REMINDER. The rule is stated in the global CLAUDE.md and
in the output-style hook that fires on every prompt, and it still slipped
repeatedly -- `scripts/build-diagram.py` printed "badge colour distinct from   US-ENGLISH-EXEMPT: quoting the defect
tile fills" on every run for days, in front of everyone. A rule that depends on
somebody noticing is not enforced, it is merely written down.

WHAT THIS CANNOT DO, stated so nobody mistakes its silence for coverage. It reads
FILES. It cannot see conversation, and it cannot see a commit message that has
already been written. Those are the surfaces the rule actually slips on most.

THE WORD LIST IS EXPLICIT, NEVER A PATTERN. A regex for `-ise` matches `precise`,
`advertise`, `surprise`, `expertise` and `otherwise`, all of which are correct.
A checker that cries wolf gets ignored, which costs more than the rule it
guards. **Add words deliberately; never widen this into a pattern.**

`analysis` is CORRECT in US English. Only `analyse`, `analysed`, `analysing` and   US-ENGLISH-EXEMPT: naming the banned forms
`analyser` are not. That distinction is why this file lists words rather than   US-ENGLISH-EXEMPT: naming the banned forms
stems.

EXEMPTIONS. Put `US-ENGLISH-EXEMPT` on the line, with a reason. Legitimate uses
exist: quoting somebody else's text, naming a third-party package, or a table
like the one below that must spell what it forbids.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Every entry is a word this project MUST NOT use, mapped to the one it should.
# Each line carries its own exemption, because this table has to spell the very
# words it bans -- which is the check dogfooding its own escape hatch.
BRITISH: dict[str, str] = {
    "colour": "color", "colours": "colors", "coloured": "colored",  # US-ENGLISH-EXEMPT: the table
    "colourful": "colorful", "behaviour": "behavior",  # US-ENGLISH-EXEMPT: the table
    "behaviours": "behaviors", "favour": "favor", "favours": "favors",  # US-ENGLISH-EXEMPT: the table
    "favourite": "favorite", "honour": "honor", "honours": "honors",  # US-ENGLISH-EXEMPT: the table
    "defence": "defense", "offence": "offense", "licence": "license",  # US-ENGLISH-EXEMPT: the table
    "centre": "center", "centres": "centers", "centred": "centered",  # US-ENGLISH-EXEMPT: the table
    "metre": "meter", "metres": "meters", "fibre": "fiber",  # US-ENGLISH-EXEMPT: the table
    "grey": "gray", "greyed": "grayed", "greyscale": "grayscale",  # US-ENGLISH-EXEMPT: the table
    "catalogue": "catalog", "catalogues": "catalogs",  # US-ENGLISH-EXEMPT: the table
    "programme": "program", "storey": "story",  # US-ENGLISH-EXEMPT: the table
    "analyse": "analyze", "analysed": "analyzed", "analysing": "analyzing",  # US-ENGLISH-EXEMPT: the table
    "analyser": "analyzer", "organise": "organize", "organised": "organized",  # US-ENGLISH-EXEMPT: the table
    "organising": "organizing", "recognise": "recognize",  # US-ENGLISH-EXEMPT: the table
    "recognised": "recognized", "recognising": "recognizing",  # US-ENGLISH-EXEMPT: the table
    "optimise": "optimize", "optimised": "optimized",  # US-ENGLISH-EXEMPT: the table
    "optimising": "optimizing", "initialise": "initialize",  # US-ENGLISH-EXEMPT: the table
    "initialised": "initialized", "initialising": "initializing",  # US-ENGLISH-EXEMPT: the table
    "normalise": "normalize", "normalised": "normalized",  # US-ENGLISH-EXEMPT: the table
    "normalising": "normalizing", "serialise": "serialize",  # US-ENGLISH-EXEMPT: the table
    "serialised": "serialized", "summarise": "summarize",  # US-ENGLISH-EXEMPT: the table
    "summarised": "summarized", "prioritise": "prioritize",  # US-ENGLISH-EXEMPT: the table
    "prioritised": "prioritized", "apologise": "apologize",  # US-ENGLISH-EXEMPT: the table
    "characterise": "characterize", "characterised": "characterized",  # US-ENGLISH-EXEMPT: the table
    "rationalise": "rationalize", "theorise": "theorize",  # US-ENGLISH-EXEMPT: the table
    "realise": "realize", "realised": "realized", "realising": "realizing",  # US-ENGLISH-EXEMPT: the table
    "customise": "customize", "customised": "customized",  # US-ENGLISH-EXEMPT: the table
    "authorise": "authorize", "authorised": "authorized",  # US-ENGLISH-EXEMPT: the table
    "minimise": "minimize", "minimised": "minimized",  # US-ENGLISH-EXEMPT: the table
    "maximise": "maximize", "maximised": "maximized",  # US-ENGLISH-EXEMPT: the table
    "utilise": "utilize", "travelling": "traveling",  # US-ENGLISH-EXEMPT: the table
    "whilst": "while", "amongst": "among",  # US-ENGLISH-EXEMPT: the table
}

SUFFIXES = {".ts", ".py", ".md", ".svelte", ".css", ".sql", ".html", ".lua",
            ".jsonc", ".sh", ".yml", ".yaml"}

# Generated, vendored, or somebody else's to spell.
SKIP_DIRS = {"node_modules", ".git", ".wrangler", "dist", "vendor",
             "__pycache__", ".claude"}
SKIP_FILES = {"package-lock.json", "worker-configuration.d.ts"}

EXEMPT = re.compile(r"US-ENGLISH-EXEMPT", re.IGNORECASE)
WORDS = re.compile(r"[A-Za-z]+")

# House vocabulary, checked as PHRASES rather than words.
#
# **Terry, 2026-08-16: *"I want to be consistent on purging 'kind' where we mean
# 'lrc plugin or JS clients'."*** Migration 0005 records why: *"'Session kinds' pulls a  US-ENGLISH-EXEMPT: quoting the objection
# 404 in my brain, I can't decipher what that is."* The column is `client_type`, the type
# is `SessionClientType`, and the prose kept saying `kind` anyway.
#
# **THE LIST IS PHRASES, AND THAT IS THE WHOLE DESIGN.** `kind` is a legitimate and
# heavily used word in this codebase -- it is the discriminant on `classify`'s
# dispositions, on `flickr/api`'s results, and on `LinkState`. It is also ordinary
# English: *"the kind thing to do"*, *"that kind of thing"*, *"kind of comically huge"*.
# **A checker that flagged the bare word would fire on roughly sixty correct uses and be
# switched off within a day**, which is the same argument that keeps the British-spelling
# list explicit instead of a regex for `-ise`.
#
# So each entry names a phrase that can only mean the client type.
PHRASES: dict[str, str] = {
    r"kinds? of credential": "client type",
    r"credential'?s? kinds?": "client type",
    r"sessions? kinds?": "client type",
    r"clients? kinds?": "client type",
    r"tokens? kinds?": "client type",
}
PHRASE_PATTERNS = [(re.compile(p, re.IGNORECASE), better)
                   for p, better in PHRASES.items()]


def hits_in(text: str) -> list[tuple[int, str, str]]:
    """Return (line number, offending word, replacement) for one file's text."""
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        if EXEMPT.search(line):
            continue
        for word in WORDS.findall(line):
            better = BRITISH.get(word.lower())
            if better is not None:
                found.append((number, word, better))
    return found


def phrase_hits_in(text: str) -> list[tuple[int, str, str]]:
    """Return (line number, offending phrase, replacement) for one file's text."""
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        if EXEMPT.search(line):
            continue
        for pattern, better in PHRASE_PATTERNS:
            match = pattern.search(line)
            if match is not None:
                found.append((number, match.group(0), better))
    return found


def phrase_self_test() -> None:
    """Prove it fires on the client-type sense AND stays silent on every other one.

    **The second half is the load-bearing half.** `kind` is a discriminated-union tag
    all over this codebase and an ordinary English word besides, so a check that cannot
    tell those apart is a check that gets disabled.
    """
    cases = [
        ("the wrong kind of credential", True),  # US-ENGLISH-EXEMPT: fixture
        ("reports the credential's kind", True),  # US-ENGLISH-EXEMPT: fixture
        ("Session kinds pull a 404", True),  # US-ENGLISH-EXEMPT: fixture
        ("the client kind is plugin", True),  # US-ENGLISH-EXEMPT: fixture
        # Every one of these is correct and MUST NOT be flagged.
        ("switch (disposition.kind) {", False),
        ("return { kind: 'retry', code };", False),
        ("if (result.kind !== 'ok') return null;", False),
        ("a 400 would punish the victim, so this is the kind thing to do", False),
        ("that kind of thing gets remembered vaguely", False),
        ("the current text is kind of comically huge", False),
        ("| Kind | Example | Who sets the size |", False),
        ("a kind of credential US-ENGLISH-EXEMPT: quoted", False),
    ]
    for text, expected in cases:
        got = bool(phrase_hits_in(text))
        if got != expected:
            raise SystemExit(
                f"PHRASE SELF-TEST FAILED: {text!r} -> got {got}, want {expected}"
            )
    print(f"  Phrase self-test: {len(cases)}/{len(cases)} passed")


def self_test() -> None:
    """Prove the detector can FIRE before believing that it found nothing.

    A checker that has never caught anything reads identical to one that cannot.
    This is the same guard `scripts/build-diagram.py` puts on its collision
    detector, for the same reason.
    """
    cases = [
        ("The colour is wrong", True),  # US-ENGLISH-EXEMPT: fixture, must be misspelled
        ("We centred the box", True),  # US-ENGLISH-EXEMPT: fixture, must be misspelled
        ("Whilst reading", True),  # US-ENGLISH-EXEMPT: fixture, must be misspelled
        # The false positives an `-ise` pattern would produce. Every one of
        # these is correct US English and MUST NOT be flagged.
        ("This analysis is precise", False),
        ("Advertise the surprise, otherwise the enterprise", False),
        ("Expertise and merchandise", False),
        ("A colour here US-ENGLISH-EXEMPT: quoted", False),
    ]
    for text, expected in cases:
        got = bool(hits_in(text))
        if got != expected:
            raise SystemExit(
                f"SELF-TEST FAILED: {text!r} -> got {got}, want {expected}"
            )
    print(f"  Detector self-test: {len(cases)}/{len(cases)} passed")


def files() -> list[Path]:
    out = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in SUFFIXES:
            continue
        if path.name in SKIP_FILES:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        out.append(path)
    return sorted(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="Show the word table")
    args = parser.parse_args()

    if args.list:
        for british, american in sorted(BRITISH.items()):
            print(f"  {british:16} -> {american}")
        return 0

    self_test()
    phrase_self_test()

    scanned = files()
    problems = []
    house = []
    for path in scanned:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(ROOT).as_posix()
        for number, word, better in hits_in(text):
            problems.append(f"{rel}:{number}  {word!r} should be {better!r}")
        for number, phrase, better in phrase_hits_in(text):
            house.append(f"{rel}:{number}  {phrase!r} should be {better!r}")

    print(f"  Checked {len(scanned)} files against {len(BRITISH)} words"
          f" and {len(PHRASES)} house phrases")

    if problems:
        print(f"\n{len(problems)} British spelling(s):")
        for problem in problems:
            print(f"  {problem}")
        print("\nFix them, or add US-ENGLISH-EXEMPT with a reason to the line.")

    if house:
        print(f"\n{len(house)} house-vocabulary slip(s) -- say CLIENT TYPE:")
        for slip in house:
            print(f"  {slip}")
        print("\nThe column is `client_type` and the type is `SessionClientType`.")
        print("Quoting somebody? Add US-ENGLISH-EXEMPT with a reason to the line.")

    if problems or house:
        return 1

    print("  US English and house vocabulary hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
