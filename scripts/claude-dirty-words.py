#!/usr/bin/env python3
"""Fail the build on words Terry does not want to read. THREE lists, one gate.

    python scripts/claude-dirty-words.py

    1. British spellings          his standing order is US English
    2. House phrases              say CLIENT TYPE, never "kind"
    3. House terms                name the hash family: SHA2-256, never bare

Exit 0 when clean. Exit 1 lists every hit as `file:line`, which the terminal
renders as a clickable link.

**RENAMED FROM `us-english.py` on 2026-08-16, at Terry's suggestion:** *"should we
rename that hook... as UK english is only ONE of the things caught by that script   DIRTY-WORDS-EXEMPT: quoting Terry
now?"* He is right, and a name describing one of three jobs is the kind of drift
this repository keeps catching elsewhere. The exemption marker moved with it, from
`US-ENGLISH-EXEMPT` to `DIRTY-WORDS-EXEMPT`, because a marker naming a scope the   DIRTY-WORDS-EXEMPT: naming the old marker
file no longer has is the same defect one level down.

WHY A CHECK AND NOT A REMINDER. The rule is stated in the global CLAUDE.md and
in the output-style hook that fires on every prompt, and it still slipped
repeatedly -- `scripts/build-diagram.py` printed "badge colour distinct from   DIRTY-WORDS-EXEMPT: quoting the defect
tile fills" on every run for days, in front of everyone. A rule that depends on
somebody noticing is not enforced, it is merely written down.

WHAT THIS CANNOT DO, stated so nobody mistakes its silence for coverage. It reads
FILES. It cannot see conversation, and it cannot see a commit message that has
already been written. Those are the surfaces the rule actually slips on most.

THE WORD LIST IS EXPLICIT, NEVER A PATTERN. A regex for `-ise` matches `precise`,
`advertise`, `surprise`, `expertise` and `otherwise`, all of which are correct.
A checker that cries wolf gets ignored, which costs more than the rule it
guards. **Add words deliberately; never widen this into a pattern.**

`analysis` is CORRECT in US English. Only `analyse`, `analysed`, `analysing` and   DIRTY-WORDS-EXEMPT: naming the banned forms
`analyser` are not. That distinction is why this file lists words rather than   DIRTY-WORDS-EXEMPT: naming the banned forms
stems.

EXEMPTIONS. Put `DIRTY-WORDS-EXEMPT` on the line, with a reason. Legitimate uses
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
    "colour": "color", "colours": "colors", "coloured": "colored",  # DIRTY-WORDS-EXEMPT: the table
    "colourful": "colorful", "behaviour": "behavior",  # DIRTY-WORDS-EXEMPT: the table
    "behaviours": "behaviors", "favour": "favor", "favours": "favors",  # DIRTY-WORDS-EXEMPT: the table
    "favourite": "favorite", "honour": "honor", "honours": "honors",  # DIRTY-WORDS-EXEMPT: the table
    "defence": "defense", "offence": "offense", "licence": "license",  # DIRTY-WORDS-EXEMPT: the table
    "centre": "center", "centres": "centers", "centred": "centered",  # DIRTY-WORDS-EXEMPT: the table
    "metre": "meter", "metres": "meters", "fibre": "fiber",  # DIRTY-WORDS-EXEMPT: the table
    "grey": "gray", "greyed": "grayed", "greyscale": "grayscale",  # DIRTY-WORDS-EXEMPT: the table
    "catalogue": "catalog", "catalogues": "catalogs",  # DIRTY-WORDS-EXEMPT: the table
    "programme": "program", "storey": "story",  # DIRTY-WORDS-EXEMPT: the table
    "analyse": "analyze", "analysed": "analyzed", "analysing": "analyzing",  # DIRTY-WORDS-EXEMPT: the table
    "analyser": "analyzer", "organise": "organize", "organised": "organized",  # DIRTY-WORDS-EXEMPT: the table
    "organising": "organizing", "recognise": "recognize",  # DIRTY-WORDS-EXEMPT: the table
    "recognised": "recognized", "recognising": "recognizing",  # DIRTY-WORDS-EXEMPT: the table
    "optimise": "optimize", "optimised": "optimized",  # DIRTY-WORDS-EXEMPT: the table
    "optimising": "optimizing", "initialise": "initialize",  # DIRTY-WORDS-EXEMPT: the table
    "initialised": "initialized", "initialising": "initializing",  # DIRTY-WORDS-EXEMPT: the table
    "normalise": "normalize", "normalised": "normalized",  # DIRTY-WORDS-EXEMPT: the table
    "normalising": "normalizing", "serialise": "serialize",  # DIRTY-WORDS-EXEMPT: the table
    "serialised": "serialized", "summarise": "summarize",  # DIRTY-WORDS-EXEMPT: the table
    "summarised": "summarized", "prioritise": "prioritize",  # DIRTY-WORDS-EXEMPT: the table
    "prioritised": "prioritized", "apologise": "apologize",  # DIRTY-WORDS-EXEMPT: the table
    "characterise": "characterize", "characterised": "characterized",  # DIRTY-WORDS-EXEMPT: the table
    "rationalise": "rationalize", "theorise": "theorize",  # DIRTY-WORDS-EXEMPT: the table
    "realise": "realize", "realised": "realized", "realising": "realizing",  # DIRTY-WORDS-EXEMPT: the table
    "customise": "customize", "customised": "customized",  # DIRTY-WORDS-EXEMPT: the table
    "authorise": "authorize", "authorised": "authorized",  # DIRTY-WORDS-EXEMPT: the table
    "minimise": "minimize", "minimised": "minimized",  # DIRTY-WORDS-EXEMPT: the table
    "maximise": "maximize", "maximised": "maximized",  # DIRTY-WORDS-EXEMPT: the table
    "utilise": "utilize", "travelling": "traveling",  # DIRTY-WORDS-EXEMPT: the table
    "whilst": "while", "amongst": "among",  # DIRTY-WORDS-EXEMPT: the table
}

SUFFIXES = {".ts", ".py", ".md", ".svelte", ".css", ".sql", ".html", ".lua",
            ".jsonc", ".sh", ".yml", ".yaml"}

# Generated, vendored, or somebody else's to spell.
SKIP_DIRS = {"node_modules", ".git", ".wrangler", "dist", "vendor",
             "__pycache__", ".claude"}
SKIP_FILES = {"package-lock.json", "worker-configuration.d.ts"}

EXEMPT = re.compile(r"DIRTY-WORDS-EXEMPT", re.IGNORECASE)
WORDS = re.compile(r"[A-Za-z]+")

# House vocabulary, checked as PHRASES rather than words.
#
# **Terry, 2026-08-16: *"I want to be consistent on purging 'kind' where we mean
# 'lrc plugin or JS clients'."*** Migration 0005 records why: *"'Session kinds' pulls a  DIRTY-WORDS-EXEMPT: quoting the objection
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

# House TERMS, matched CASE-SENSITIVELY.
#
# **Standing order, Terry, 2026-08-16: the bare three-letter form is never allowed,   DIRTY-WORDS-EXEMPT: this block names the forms it bans
# and the SHA-2 family MUST carry its family number.** In his words: *"every single   DIRTY-WORDS-EXEMPT: quoting Terry
# time my OCPD fires and I get an intrusive thought of 'WHICH SHA, goddamn it; there   DIRTY-WORDS-EXEMPT: quoting Terry
# are like 50 combinations of SHA1/2/3 and key lengths'."*   DIRTY-WORDS-EXEMPT: quoting Terry
#
# **He is right that `SHA-256` does not settle it either.** SHA3-256 exists and is a   DIRTY-WORDS-EXEMPT: naming the banned form
# completely different algorithm, so the family is implied by convention rather than
# stated. `SHA2-256` states it.
#
# THREE THINGS THIS MUST NOT TOUCH, and each one would be a real bug:
#
#   * `"SHA-256"` inside quotes is the Web Crypto API's own identifier --
#     `crypto.subtle.digest("SHA-256", ...)`. Rewriting it breaks the call.
#   * `LrDigest.SHA256` is Adobe's identifier. Same.
#   * `HMAC-SHA1` is RFC 5849's wire value for `oauth_signature_method`. It goes on
#     the wire exactly like that.
#
# So the pattern refuses a match preceded by a quote, a dot or a hyphen, which
# excludes all three without needing an exemption on every line.
#
# **Naming a family without a size is ALSO flagged**, per Terry's widening on
# 2026-08-16. Write out the members instead: not "SHA-3 is unavailable" but   DIRTY-WORDS-EXEMPT: naming the banned form
# "SHA3-256, SHA3-384 and SHA3-512 are unavailable". More words, no ambiguity.
#   * `HMAC-SHA1` is RFC 5849's wire value for `oauth_signature_method`. It goes on
#     the wire exactly like that.
#
# The lookbehind refuses a match preceded by a quote, a dot or a hyphen, which
# excludes all three without needing an exemption on every line.
#
# **The lookahead refuses a following letter OR UNDERSCORE.** Letters keep `SHAPE`
# out. The underscore was added after this check flagged `SHA_TOKEN` and
# `SHA_VALID` -- its OWN variable names, three lines below. A checker that cannot
# read its own source is one whose false positives nobody has looked for.
SHA_TOKEN = re.compile(r"(?<![\"'.\w-])SHA[-0-9]*(?![A-Za-z_])")  # DIRTY-WORDS-EXEMPT: the pattern must spell what it matches

# **The ONLY acceptable shape: family AND size, every time.** Terry, 2026-08-16:
# *"I want sha, sha family, and keysize EVERY TIME -- telling me 'I computed the   DIRTY-WORDS-EXEMPT: quoting Terry
# SHA2' hash has the exact same rage reaction."*   DIRTY-WORDS-EXEMPT: quoting Terry
#
# So `SHA2-256` and `SHA3-512` pass. Everything else -- the bare three letters,   DIRTY-WORDS-EXEMPT: naming the banned forms
# `SHA2`, `SHA256`, `SHA-256`, `SHA-2` -- does not.   DIRTY-WORDS-EXEMPT: naming the banned forms
SHA_VALID = re.compile(r"^SHA[123]-\d+$")  # DIRTY-WORDS-EXEMPT: the pattern must spell what it accepts
TERMS = {"SHA": "family AND size, every time -- SHA2-256, SHA3-512, SHA1-160"}


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


def term_hits_in(text: str) -> list[tuple[int, str, str]]:
    """Return (line number, offending term, replacement) for one file's text."""
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        if EXEMPT.search(line):
            continue
        for match in SHA_TOKEN.finditer(line):
            token = match.group(0)
            if SHA_VALID.match(token):
                continue
            found.append((number, token, TERMS["SHA"]))
            break
    return found


def term_self_test() -> None:
    """Prove it fires on prose AND stays silent on every API identifier.

    **The silent half is the load-bearing half.** `"SHA-256"` is a Web Crypto
    constant, `LrDigest.SHA256` is Adobe's, and `HMAC-SHA1` goes on the wire. A
    check that rewrote any of the three would break working code, which is a far
    worse outcome than the ambiguity it was fixing.
    """
    cases = [
        # **Family AND size, every time.** Each of these is missing one or both.
        ("Only SHA-256 of the id is stored", True),  # DIRTY-WORDS-EXEMPT: fixture
        ("hashed with SHA-512 before storage", True),  # DIRTY-WORDS-EXEMPT: fixture
        ("the SHA is checked first", True),  # DIRTY-WORDS-EXEMPT: fixture
        ("pinned to the commit SHA", True),  # DIRTY-WORDS-EXEMPT: fixture
        ("I computed the SHA2 hash", True),  # DIRTY-WORDS-EXEMPT: fixture
        ("stored as a SHA256 digest", True),  # DIRTY-WORDS-EXEMPT: fixture
        ("the SHA-2 family", True),  # DIRTY-WORDS-EXEMPT: fixture
        ("SHA3 is not SHA2", True),  # DIRTY-WORDS-EXEMPT: fixture
        # Correct: family and size both present.
        ("SHA2-256 of the id", False),
        ("SHA3-512 is a sponge", False),
        ("SHA1-160 is retired here", False),
        # API identifiers and wire values. Rewriting one breaks a call.
        ('crypto.subtle.digest("SHA-256", bytes)', False),
        ('{ name: "HMAC", hash: "SHA-256" }', False),
        ("LrDigest.SHA256.digest(x)", False),
        ("oauth_signature_method is HMAC-SHA1", False),
        ("signed HMAC-SHA256 for the header", False),
        # Not a hash at all.
        ("the SHAPE of the response", False),
        ("a .sha256 manifest", False),
        ("SHA-256 DIRTY-WORDS-EXEMPT: quoting a spec", False),
    ]
    for text, expected in cases:
        got = bool(term_hits_in(text))
        if got != expected:
            raise SystemExit(
                f"TERM SELF-TEST FAILED: {text!r} -> got {got}, want {expected}"
            )
    print(f"  Term self-test: {len(cases)}/{len(cases)} passed")


def phrase_self_test() -> None:
    """Prove it fires on the client-type sense AND stays silent on every other one.

    **The second half is the load-bearing half.** `kind` is a discriminated-union tag
    all over this codebase and an ordinary English word besides, so a check that cannot
    tell those apart is a check that gets disabled.
    """
    cases = [
        ("the wrong kind of credential", True),  # DIRTY-WORDS-EXEMPT: fixture
        ("reports the credential's kind", True),  # DIRTY-WORDS-EXEMPT: fixture
        ("Session kinds pull a 404", True),  # DIRTY-WORDS-EXEMPT: fixture
        ("the client kind is plugin", True),  # DIRTY-WORDS-EXEMPT: fixture
        # Every one of these is correct and MUST NOT be flagged.
        ("switch (disposition.kind) {", False),
        ("return { kind: 'retry', code };", False),
        ("if (result.kind !== 'ok') return null;", False),
        ("a 400 would punish the victim, so this is the kind thing to do", False),
        ("that kind of thing gets remembered vaguely", False),
        ("the current text is kind of comically huge", False),
        ("| Kind | Example | Who sets the size |", False),
        ("a kind of credential DIRTY-WORDS-EXEMPT: quoted", False),
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
        ("The colour is wrong", True),  # DIRTY-WORDS-EXEMPT: fixture, must be misspelled
        ("We centred the box", True),  # DIRTY-WORDS-EXEMPT: fixture, must be misspelled
        ("Whilst reading", True),  # DIRTY-WORDS-EXEMPT: fixture, must be misspelled
        # The false positives an `-ise` pattern would produce. Every one of
        # these is correct US English and MUST NOT be flagged.
        ("This analysis is precise", False),
        ("Advertise the surprise, otherwise the enterprise", False),
        ("Expertise and merchandise", False),
        ("A colour here DIRTY-WORDS-EXEMPT: quoted", False),
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
    term_self_test()

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
        for number, term, better in term_hits_in(text):
            house.append(f"{rel}:{number}  {term!r} should be {better!r}")

    print(f"  Checked {len(scanned)} files against {len(BRITISH)} words,"
          f" {len(PHRASES)} house phrases and {len(TERMS)} house terms")

    if problems:
        print(f"\n{len(problems)} British spelling(s):")
        for problem in problems:
            print(f"  {problem}")
        print("\nFix them, or add DIRTY-WORDS-EXEMPT with a reason to the line.")

    if house:
        print(f"\n{len(house)} house-vocabulary slip(s) -- say CLIENT TYPE:")
        for slip in house:
            print(f"  {slip}")
        print("\nThe column is `client_type` and the type is `SessionClientType`.")
        print("Quoting somebody? Add DIRTY-WORDS-EXEMPT with a reason to the line.")

    if problems or house:
        return 1

    print("  US English and house vocabulary hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
