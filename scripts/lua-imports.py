#!/usr/bin/env python3
"""Refuse any `import("Lr...")` the Lightroom SDK does not document. ADR-23 Rule 3.

**The objection is the missing API CONTRACT, not the cryptography.** An undocumented
namespace carries no version guarantee, no behavior guarantee and no deprecation path,
so Adobe may remove it in a point release without breaking a promise it never made.
`LrUUID` is the instance that prompted this; the rule is general because the reason is.

WHY A CHECKED-IN JSON LIST RATHER THAN READING THE ZIP EVERY TIME
----------------------------------------------------------------
`vendor/LrC_*.zip` is gitignored -- it is Adobe's to license and this repository is
public -- so **a fresh clone has no SDK at all.** A checker that needs the archive
would be unrunnable on the machine most likely to need it.

So the module list is generated ONCE into `scripts/lrc-sdk-modules.json` and committed.
It is an index of API surface names that this script derives, not Adobe's documentation.

**When the archive IS present the two are cross-checked**, which catches the failure
this design would otherwise introduce: a stale JSON after an SDK bump, silently
approving a namespace the new SDK dropped. The script announces which of the two
instruments ran, because "verified against the SDK" and "verified against a file
somebody generated in April" are very different assurances -- the same reason
`lua-balance.py` says whether it ran `luac` or its fallback.

WHAT THIS CHECKS, AND WHAT IT DELIBERATELY DOES NOT
---------------------------------------------------
**Namespace level only.** `import("LrFoo")` is checkable against a list of filenames.
`LrFoo.someUndocumentedFunction()` is not -- it needs HTML parsing per module plus
alias tracking through local variables, and a half-working version would report
confident nonsense. ADR-23 states the function-level rule as SHOULD and says plainly
that nothing enforces it. **A rule that cannot be checked is a promise, and calling it
a MUST would be a lie told by a build script.**

The Lua 5.1 standard library needs no carve-out HERE, because `string`, `table`, `io`
and `os` are never reached through `import()`. ADR-23's prose carves it out for the
human rule; this file simply never sees them.

EXEMPTION
---------
Put `SDK-UNDOCUMENTED-EXEMPT: <reason>` on the same line as the import.
`EntropyProbe.lua` uses it to MEASURE `LrUUID` inside `LrTasks.pcall`, where absence is
a reported outcome rather than a crash. **That is measurement, not dependency**, and
ADR-23 requires it to keep working.

Windows newline note: every write uses newline="" so a CRLF file is not silently
rewritten, per the rule in ~/.claude/CLAUDE.md.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import zipfile

REPO = pathlib.Path(__file__).resolve().parent.parent
MODULE_LIST = REPO / "scripts" / "lrc-sdk-modules.json"
API_LIST = REPO / "scripts" / "lrc-sdk-api.json"
VENDOR = REPO / "vendor"

# `local Foo = import("LrBar")` -- the alias map that makes member checking possible.
# Lua has no types, so this is the ONLY reliable way to know what a dotted call targets.
ALIAS = re.compile(r"""local\s+([A-Za-z_]\w*)\s*=\s*import\s*\(?\s*["']([^"']+)["']""")
# `Foo.bar` where Foo is a known alias.
MEMBER = re.compile(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)")
# `thing:method(` -- an instance method on an object the SDK returned. UNCHECKABLE
# without type inference, and counted rather than judged.
INSTANCE_CALL = re.compile(r"\b([A-Za-z_]\w*):([A-Za-z_]\w*)\s*\(")

# Members proven to exist at RUNTIME and proven absent from the whole SDK archive.
# Measured 2026-08-16 on Lightroom Classic 15.5 by EntropyProbe.lua's pairs() sweep,
# cross-checked by a literal substring search of every file in the archive.
#
# **This list is what makes the gate precise rather than merely strict.** A member here
# gets a message naming it as a known undocumented function; anything else absent from
# the docs gets the generic message, which is likelier to be a typo.
KNOWN_UNDOCUMENTED = {
    "LrUUID": ["generateUUID"],
    "LrDigest": ["SHA384"],
    "LrSystemInfo": [
        "gatherSystemInfoForPerformance", "getCachedSize", "getDisplaySize",
        "getRamUsage", "getRamUsagePercent", "getSystemDiskFreeSpaceAvailable",
        "getSystemOs", "getVirtualMemoryUsage", "initiateSystemInfoRecording",
        "machineName", "pushInitialCatalogInfo", "recordSystemInformationInPerfDB",
    ],
}

EXEMPT = re.compile(r"SDK-UNDOCUMENTED-EXEMPT:\s*(\S.*)")

# Lua accepts `import "X"` as well as `import("X")`, so both forms are matched. A
# pattern that only knew the parenthesized form would pass a file that used the other
# one -- a false NEGATIVE, which is the dangerous direction for a gate.
IMPORT = re.compile(r"""import\s*\(?\s*["']([^"']+)["']""")

# **A DYNAMIC import is the hole this gate would otherwise leave wide open.**
# `import(name)` with a variable is invisible to a literal-string pattern, so a
# namespace list in a table plus a loop defeats the whole check -- and that is not
# hypothetical: EntropyProbe.lua is written exactly that way, and the first run of this
# script reported "0 undocumented" on a file whose entire purpose is importing LrUUID.
#
# So a non-literal argument is UNVERIFIABLE rather than fine, and it needs the same
# explicit exemption. A gate that silently ignores what it cannot read is worse than no
# gate, because the clean line reads as coverage.
DYNAMIC_IMPORT = re.compile(r"""import\s*\(\s*([A-Za-z_][\w.\[\]"']*)\s*\)""")

LONG_COMMENT = re.compile(r"--\[(=*)\[.*?\]\1\]", re.DOTALL)
LINE_COMMENT = re.compile(r"--[^\n]*")


def blank_comments(text: str) -> str:
    """Replace comment characters with spaces, preserving length and newlines.

    **Preserving offsets is the point.** Deleting comments would renumber every line
    after the first block comment, and this script reports line numbers a human then
    has to find. Spaces keep `text.splitlines()` aligned with the original.

    KNOWN LIMIT, stated rather than hidden: a `--` inside a string literal is treated
    as a comment. No file here does that, and the self-test below pins the behavior so
    a future change to this function has to confront it.
    """

    def spaces(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    return LINE_COMMENT.sub(spaces, LONG_COMMENT.sub(spaces, text))


def documented_modules_from_zip() -> tuple[set[str], str] | None:
    """Every `API Reference/modules/*.html` basename in the vendored SDK archive."""
    archives = sorted(VENDOR.glob("LrC_*_SDK.zip")) + sorted(VENDOR.glob("LrC_*.zip"))
    for archive in archives:
        try:
            with zipfile.ZipFile(archive) as z:
                names = {
                    entry.rsplit("/", 1)[-1][:-5]
                    for entry in z.namelist()
                    if "/modules/" in entry and entry.endswith(".html")
                }
            # A namespace is one word. The reference also ships pages like
            # "LrView view properties", which describe a table of properties rather
            # than an importable module, so they are dropped.
            modules = {n for n in names if n.startswith("Lr") and " " not in n}
            if modules:
                return modules, archive.name
        except (zipfile.BadZipFile, OSError):
            continue
    return None


def load_module_list() -> tuple[set[str], str]:
    """The committed list, cross-checked against the archive when one is present."""
    if not MODULE_LIST.exists():
        sys.exit(
            f"MISSING {MODULE_LIST.relative_to(REPO)}.\n"
            "Regenerate it from the vendored SDK: python scripts/lua-imports.py --regenerate"
        )

    with open(MODULE_LIST, encoding="utf-8") as fh:
        data = json.load(fh)
    committed = set(data["modules"])

    from_zip = documented_modules_from_zip()
    if from_zip is None:
        return committed, (
            f"the committed list ({len(committed)} modules, SDK {data['sdkVersion']}). "
            "NO ARCHIVE PRESENT, so it was not cross-checked"
        )

    live, archive_name = from_zip
    if live != committed:
        missing = sorted(live - committed)
        extra = sorted(committed - live)
        sys.exit(
            f"DRIFT: {MODULE_LIST.name} disagrees with {archive_name}.\n"
            f"  In the SDK and not the list: {missing or 'none'}\n"
            f"  In the list and not the SDK: {extra or 'none'}\n"
            "Regenerate: python scripts/lua-imports.py --regenerate"
        )
    return committed, (
        f"the committed list, CROSS-CHECKED against {archive_name} "
        f"({len(committed)} modules)"
    )


def write_json(path: pathlib.Path, payload: dict) -> None:
    """Write, then hand the file to Biome to format.

    **`npm run check` lints these generated files, so the generator has to produce what
    the formatter wants or the build fails on a file it just wrote.** Tabs alone are not
    enough: Biome collapses a short array onto one line and expands a long one by
    measured width, and reimplementing that rule here would be a second formatter to
    keep in step with the first.

    So Biome formats its own input. If Biome is missing the file is still valid JSON and
    the caller is told, rather than the failure surfacing later as a mystery lint error.
    """
    with open(path, "w", encoding="utf-8", newline="") as fh:
        json.dump(payload, fh, indent="\t")
        fh.write("\n")
    # **Call the installed binary, not `npx`.** Two `npx` attempts exited 0 and
    # formatted nothing -- once because a bare `npx` with shell=True mangles an argument
    # list on Windows, and once for a reason never established. Either way `npm run
    # check` then failed on a file this script had just written.
    #
    # `node_modules/.bin/biome.cmd` is one process, needs no resolution step, and is the
    # same binary `npm run lint` uses -- so the formatter and the linter cannot disagree.
    binary = REPO / "node_modules" / ".bin" / ("biome.cmd" if os.name == "nt" else "biome")
    if not binary.exists():
        print("  NOTE: biome is not installed. The JSON is valid but unformatted.")
        return
    try:
        result = subprocess.run(
            [str(binary), "format", "--write", str(path)],
            cwd=REPO, capture_output=True, text=True,
        )
        # **A subprocess that exits 0 without doing the job is the quiet kind of
        # broken**, so success is confirmed from the output rather than the status.
        #
        # "Formatted N files" means it RAN. "Fixed N file" means it CHANGED something,
        # and a file that was already correct legitimately reports no fix. An earlier
        # version required "Fixed" and warned on every already-correct write -- crying
        # wolf about a success, in a script whose whole subject is checkers that do that.
        if result.returncode != 0 or "Formatted" not in result.stdout:
            print(f"  NOTE: biome format did not run (exit {result.returncode}). "
                  f"Verify with `npm run lint` before trusting this file.")
            if result.stderr.strip():
                print(f"        {result.stderr.strip().splitlines()[0]}")
    except OSError as exc:
        print(f"  NOTE: could not run biome ({exc}). The JSON is valid but unformatted.")


def scrape_api() -> tuple[dict[str, list[str]], str] | None:
    """Every `LrNamespace.member` named anywhere in the SDK archive.

    **No trailing-paren requirement, and that is the whole lesson of this function.**
    The first version matched only `LrFoo.bar (`, which sees a member written as a CALL
    and misses one named in prose. The LrDigest page says *"provides the following
    hashing factories: LrDigest.SHA256 and LrDigest.SHA512"* with no parens anywhere, so
    that version reported LrDigest as having ONE documented member against seven at
    runtime -- and I had quoted that exact sentence out of this archive an hour earlier.
    Terry caught it. **The instrument disagreed with something already known and the
    instrument was believed.**

    Over-inclusive is the SAFE direction here. A spurious entry loosens the gate by one
    name; a missing one rejects working code, and a checker that cries wolf gets ignored.
    """
    from_zip = documented_modules_from_zip()
    if from_zip is None:
        return None
    modules, archive_name = from_zip

    archives = sorted(VENDOR.glob("LrC_*.zip"))
    dotted = re.compile(r"\b(Lr[A-Za-z0-9]+)\.([A-Za-z_][A-Za-z0-9_]*)")
    found: dict[str, set[str]] = {}
    with zipfile.ZipFile(archives[0]) as z:
        for entry in z.namelist():
            if not entry.endswith((".html", ".txt", ".lua")):
                continue
            raw = z.read(entry).decode("utf-8", "replace")
            body = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
            body = re.sub(r"<[^>]+>", " ", body)
            for m in dotted.finditer(body):
                if m.group(1) in modules:
                    found.setdefault(m.group(1), set()).add(m.group(2))
    return {k: sorted(v) for k, v in sorted(found.items())}, archive_name


def regenerate_api() -> int:
    result = scrape_api()
    if result is None:
        print(f"No LrC SDK archive found in {VENDOR.relative_to(REPO)}. Nothing to read.")
        return 1
    api, archive_name = result
    version = re.search(r"LrC_([\d.]+)_", archive_name)
    payload = {
        "_comment": (
            "Generated by scripts/lua-imports.py --regenerate-api. Do not hand-edit. "
            "An index of API surface names derived from the vendored SDK archive, which "
            "is gitignored. A namespace with NO entry here is object-oriented -- its "
            "members are instance methods reached with a colon, so there is nothing of "
            "the Namespace.member shape to check."
        ),
        "sdkVersion": version.group(1) if version else "unknown",
        "sourceArchive": archive_name,
        "namespaces": api,
    }
    write_json(API_LIST, payload)
    total = sum(len(v) for v in api.values())
    print(f"Wrote {API_LIST.relative_to(REPO)}: {total} members across {len(api)} namespaces")
    return 0


def regenerate() -> int:
    from_zip = documented_modules_from_zip()
    if from_zip is None:
        print(f"No LrC SDK archive found in {VENDOR.relative_to(REPO)}. Nothing to read.")
        return 1
    modules, archive_name = from_zip
    version = re.search(r"LrC_([\d.]+)_", archive_name)
    payload = {
        "_comment": (
            "Generated by scripts/lua-imports.py --regenerate. Do not hand-edit. "
            "This is an index of API surface names derived from the vendored SDK "
            "archive, which is gitignored; committing the index is what lets the "
            "ADR-23 Rule 3 gate run on a fresh clone."
        ),
        "sdkVersion": version.group(1) if version else "unknown",
        "sourceArchive": archive_name,
        "modules": sorted(modules),
    }
    write_json(MODULE_LIST, payload)
    print(f"Wrote {MODULE_LIST.relative_to(REPO)}: {len(modules)} modules from {archive_name}")
    return 0


def self_test(documented: set[str]) -> None:
    """Prove the extractor finds imports AND that the verdict can fail.

    **A checker validated in one direction is half-validated.** `lua-balance.py`'s first
    version cried wolf on three files Lightroom loads fine, and the fix was to test both
    polarities. These cases pin both, plus the comment-blanking that a false negative
    would hide behind.
    """
    cases = [
        ('local d = import("LrDialogs")', ["LrDialogs"], "parenthesized"),
        ("local d = import 'LrDialogs'", ["LrDialogs"], "bare string argument"),
        ('-- import("LrDialogs")', [], "line comment is not an import"),
        ('--[[ import("LrDialogs") ]]', [], "block comment is not an import"),
        ('local a = import("LrTasks")\nlocal b = import("LrHttp")',
         ["LrTasks", "LrHttp"], "two on two lines"),
    ]
    for source, want, why in cases:
        got = [m.group(1) for m in IMPORT.finditer(blank_comments(source))]
        if got != want:
            sys.exit(f"SELF-TEST FAILED ({why}): got {got}, want {want}")

    # Line numbers must survive comment blanking, or every report points at the wrong
    # line and the message becomes actively misleading.
    numbered = '--[[ a\nb\nc ]]\nlocal x = import("LrHttp")'
    blanked = blank_comments(numbered)
    line_of = blanked[: blanked.index("LrHttp")].count("\n") + 1
    if line_of != 4:
        sys.exit(f"SELF-TEST FAILED (line numbers): import reported on line {line_of}, want 4")

    # The verdict itself must be able to say NO.
    if "LrUUID" in documented:
        sys.exit(
            "SELF-TEST FAILED: LrUUID is in the documented module list, so this gate "
            "could never fire on the namespace it was written for. Read ADR-23."
        )
    if "LrDialogs" not in documented:
        sys.exit("SELF-TEST FAILED: LrDialogs is absent, so the list is not a real SDK index.")

    print(f"  Self-test: {len(cases) + 3}/{len(cases) + 3} passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", help="Directory of .lua files to check")
    parser.add_argument("--regenerate", action="store_true",
                        help="Rewrite the module list from the vendored SDK archive")
    parser.add_argument("--regenerate-api", action="store_true",
                        help="Rewrite the per-namespace member list from the archive")
    args = parser.parse_args()

    if args.regenerate:
        return regenerate()
    if args.regenerate_api:
        return regenerate_api()
    if not args.directory:
        parser.error("a directory is required unless --regenerate is given")

    documented, provenance = load_module_list()
    print("ADR-23 Rule 3: every imported namespace is documented in the LrC SDK.")
    print(f"  Source: {provenance}")
    self_test(documented)

    root = pathlib.Path(args.directory)
    files = sorted(root.rglob("*.lua"))
    # **Refusing to pass on an empty match is the rule lua-balance.py already carries.**
    # A moved directory would otherwise make this gate report success forever.
    if not files:
        print(f"  No .lua files under {root}. A gate that checks nothing MUST NOT pass.")
        return 1

    if API_LIST.exists():
        with open(API_LIST, encoding="utf-8") as fh:
            api_data = json.load(fh)
        api = {k: set(v) for k, v in api_data["namespaces"].items()}
        api_provenance = (
            f"{sum(len(v) for v in api.values())} members, SDK {api_data['sdkVersion']}"
        )
    else:
        api, api_provenance = {}, "NO MEMBER LIST -- run --regenerate-api"

    problems = 0
    exemptions = 0
    checked = 0
    dynamic = 0
    members = 0
    instance_calls = 0
    for path in files:
        raw = path.read_text(encoding="utf-8")
        lines = raw.splitlines()
        code = blank_comments(raw)

        def report(line_no: int, what: str, detail: str, *,
                   lines: list[str] = lines,
                   path: pathlib.Path = path) -> bool:
            """True when the line carries an exemption. Prints either way.

            `lines` and `path` are bound as keyword defaults so the closure
            captures THIS iteration's values rather than the loop variable.
            """
            line = lines[line_no - 1] if line_no <= len(lines) else ""
            exempt = EXEMPT.search(line)
            if exempt:
                print(f"  EXEMPT  {path.name}:{line_no} {what} -- {exempt.group(1)}")
                return True
            print(f"  {detail}")
            return False

        for match in IMPORT.finditer(code):
            namespace = match.group(1)
            checked += 1
            if namespace in documented:
                continue
            line_no = raw[: match.start()].count("\n") + 1
            if report(line_no, f'import("{namespace}")',
                      f'UNDOCUMENTED  {path.name}:{line_no} import("{namespace}")\n'
                      f"                Not in the LrC SDK reference. ADR-23 Rule 3 forbids it.\n"
                      f"                Exempt a deliberate measurement with "
                      f"SDK-UNDOCUMENTED-EXEMPT: <reason> on that line."):
                exemptions += 1
            else:
                problems += 1

        for match in DYNAMIC_IMPORT.finditer(code):
            argument = match.group(1)
            dynamic += 1
            line_no = raw[: match.start()].count("\n") + 1
            if report(line_no, f"import({argument}) -- dynamic",
                      f"UNVERIFIABLE  {path.name}:{line_no} import({argument})\n"
                      f"                The argument is not a string literal, so this gate\n"
                      f"                cannot tell which namespace is imported. ADR-23 Rule 3\n"
                      f"                treats that as unverified, never as allowed."):
                exemptions += 1
            else:
                problems += 1

        # --- Member level. Only possible because `local X = import("Y")` is traceable.
        aliases = {m.group(1): m.group(2) for m in ALIAS.finditer(code)}
        for match in MEMBER.finditer(code):
            alias, member = match.group(1), match.group(2)
            namespace = aliases.get(alias)
            if namespace is None:
                continue
            members += 1
            allowed = api.get(namespace)
            # **A namespace with no entry is OBJECT-ORIENTED, not undocumented.**
            # LrPhoto's surface is `photo:getRawMetadata()`, reached with a colon, so
            # there is nothing of this shape to check and an empty list MUST NOT be
            # read as "nothing is allowed".
            if not allowed:
                continue
            if member in allowed:
                continue
            line_no = raw[: match.start()].count("\n") + 1
            known = member in KNOWN_UNDOCUMENTED.get(namespace, ())
            detail = (
                f"UNDOCUMENTED MEMBER  {path.name}:{line_no} {namespace}.{member}\n"
                f"                Measured present at runtime and absent from the entire\n"
                f"                SDK archive. ADR-23 Rule 3: no contract, no dependency."
                if known else
                f"UNKNOWN MEMBER  {path.name}:{line_no} {namespace}.{member}\n"
                f"                Not named anywhere in the SDK archive. Most likely a typo;\n"
                f"                if it is real but undocumented, ADR-23 Rule 3 forbids it."
            )
            if report(line_no, f"{namespace}.{member}", detail):
                exemptions += 1
            else:
                problems += 1

        instance_calls += len(INSTANCE_CALL.findall(code))

    print(f"  Checked {checked} literal import(s) and {dynamic} dynamic one(s) "
          f"across {len(files)} file(s); {exemptions} exempt, {problems} unresolved.")
    print(f"  Checked {members} namespace member call(s) against {api_provenance}.")
    # **Reported, never failed.** An instance method needs type inference Lua cannot
    # give, so this number is the honest size of what the gate does NOT cover. Silence
    # here would read as coverage.
    print(f"  {instance_calls} instance-method call(s) (obj:method) NOT checked -- "
          f"ADR-23 Rule 3 states function level as SHOULD for exactly this reason.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
