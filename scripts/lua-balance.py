"""A crude Lua 5.1 block-balance check, because this machine has no luac.

**It is not a parser and MUST NOT be described as one.** It catches exactly one
class of error: a block left open or closed too many times. That class is worth
catching because it already bit -- a `for` loop was closed with `}` instead of
`end`, JavaScript muscle memory, and Lightroom's only report was a load failure.

**It is validated against a file known to LOAD in Lightroom.** A checker whose
clean verdict has never been compared to a working file is a checker whose clean
verdict means nothing.
"""

import os
import re
import sys

OPEN = {"function", "if", "for", "while", "do"}
CLOSE = {"end", "until"}


def strip_noise(src: str) -> str:
    """Remove long comments, line comments and strings, preserving line count."""
    out, i, n = [], 0, len(src)
    while i < n:
        # Long bracket, comment or string: [[ ]] or [==[ ]==]
        m = re.match(r"(--)?\[(=*)\[", src[i:])
        if m:
            eq = m.group(2)
            end = src.find(f"]{eq}]", i + m.end())
            end = n if end < 0 else end + len(eq) + 2
            out.append("\n" * src.count("\n", i, end))
            i = end
            continue
        if src.startswith("--", i):
            end = src.find("\n", i)
            end = n if end < 0 else end
            out.append(" " * (end - i))
            i = end
            continue
        if src[i] in "\"'":
            quote, j = src[i], i + 1
            while j < n and src[j] != quote:
                j += 2 if src[j] == "\\" else 1
            out.append(" " * (min(j, n - 1) - i + 1))
            i = j + 1
            continue
        out.append(src[i])
        i += 1
    return "".join(out)


def check(path: str) -> list[str]:
    with open(path, encoding="utf-8", newline="") as handle:
        src = strip_noise(handle.read())
    depth, trace, problems = 0, [], []
    for lineno, line in enumerate(src.split("\n"), 1):
        for word in re.findall(r"\b[a-z]+\b", line):
            if word == "do":
                # `for ... do` and `while ... do` are already counted by their
                # own keyword, so only a BARE `do` opens a block.
                if trace and trace[-1][0] in ("for", "while"):
                    trace[-1] = ("do-consumed", trace[-1][1])
                    continue
                depth += 1
                trace.append(("do", lineno))
            elif word in OPEN:
                depth += 1
                trace.append((word, lineno))
            elif word in CLOSE:
                depth -= 1
                if depth < 0:
                    problems.append(f"line {lineno}: '{word}' with nothing open")
                    depth = 0
                elif trace:
                    trace.pop()

    if depth != 0:
        where = ", ".join(f"{w} at line {ln}" for w, ln in trace[-3:])
        problems.append(f"{depth} block(s) left OPEN; innermost: {where}")
    return problems


def expand(args: list[str]) -> list[str]:
    """Accept files OR directories.

    Naming each file in `package.json` meant a NEW plug-in file would simply go
    unchecked, and nothing would say so -- the same silent-coverage hole that let
    the diagram's text estimator measure three tiles out of thirteen.
    """
    import os

    paths = []
    for arg in args:
        if os.path.isdir(arg):
            paths.extend(os.path.join(arg, name)
                         for name in sorted(os.listdir(arg))
                         if name.endswith(".lua"))
        else:
            paths.append(arg)
    return paths


# Where the plug-in actually runs. The repo copy is a MIRROR, and a mirror nobody
# compares is a record that quietly stops being true -- five hand copies in one
# evening is five chances to miss one.
LIVE = r"C:\Photography\FgaSpike.lrdevplugin"


def mirror_drift(repo_dir: str) -> tuple[list[str], bool]:
    """Compare the repo mirror against the live plug-in, when the live one exists.

    **Silent on a machine that has no live copy**, because that is a different
    developer rather than a problem. It reports what it did either way, so
    "checked nothing" never reads as "found nothing".
    """
    import hashlib
    import os

    if not os.path.isdir(repo_dir) or not os.path.isdir(LIVE):
        return [], False

    def digest(path: str) -> str:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()

    problems = []
    for name in sorted(os.listdir(repo_dir)):
        if not name.endswith(".lua"):
            continue
        live = os.path.join(LIVE, name)
        if not os.path.exists(live):
            problems.append(f"{name}: in the repo, MISSING from {LIVE}")
        elif digest(live) != digest(os.path.join(repo_dir, name)):
            problems.append(f"{name}: repo copy DIFFERS from the live plug-in")
    problems.extend(
        f"{name}: live, MISSING from the repo mirror"
        for name in sorted(os.listdir(LIVE))
        if name.endswith(".lua") and not os.path.exists(os.path.join(repo_dir, name))
    )
    return problems, True


# **The REAL Lua 5.1 compiler ships in the SDK archive this repo already vendors.**
# An earlier version of this file said no luac existed on this machine. That was a
# search with the wrong filter -- it looked for names matching `*Lightroom*SDK*`
# while the archive is `LrC_...`, and `luac.exe` lives INSIDE the zip rather than
# on disk. Terry knew it was here. **A search that found nothing is not evidence
# that nothing is there.**
VENDOR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendor"
)
LUAC_IN_ZIP = "Lua Compiler/win/luac.exe"


def find_luac() -> str | None:
    """Return a path to luac.exe, extracting it from the vendored SDK if needed.

    Extracted to a temp directory rather than into the tree: `vendor/` is somebody
    else's archive and MUST stay one, and a 386 KB binary does not belong in git.
    """
    import glob
    import tempfile
    import zipfile

    cached = os.path.join(tempfile.gettempdir(), "fga-luac-5.1.exe")
    if os.path.exists(cached):
        return cached

    zips = glob.glob(os.path.join(VENDOR, "*SDK*.zip"))
    for path in zips:
        try:
            with zipfile.ZipFile(path) as archive:
                if LUAC_IN_ZIP not in archive.namelist():
                    continue
                with archive.open(LUAC_IN_ZIP) as src, open(cached, "wb") as dst:
                    dst.write(src.read())
                return cached
        except (OSError, zipfile.BadZipFile):
            continue
    return None


def parse_check(luac: str, paths: list[str]) -> list[tuple[str, str]]:
    """`luac -p` -- the authoritative answer, not an approximation."""
    import subprocess

    problems = []
    for path in paths:
        done = subprocess.run(
            [luac, "-p", path], capture_output=True, text=True, check=False
        )
        if done.returncode != 0:
            detail = (done.stderr or done.stdout).strip().splitlines()
            problems.append((path, detail[-1] if detail else "parse failed"))
    return problems


if __name__ == "__main__":
    targets = expand(sys.argv[1:])
    if not targets:
        print("No .lua files found -- refusing to report success on nothing.")
        sys.exit(1)
    # **Prefer the real compiler; fall back only if it is genuinely absent.**
    luac = find_luac()
    bad = False
    if luac is not None:
        print(f"Parse-checking {len(targets)} Lua file(s) with luac 5.1:")
        for path, detail in parse_check(luac, targets):
            bad = True
            print(f"  FAILED  {os.path.basename(path)}: {detail}")
        if not bad:
            for path in targets:
                print(f"  ok      {os.path.basename(path)}")
    else:
        # **Say which instrument ran.** A block-balance pass and a real parse are
        # very different assurances, and identical output would hide the swap.
        print("luac not found -- falling back to a BLOCK BALANCE check, not a parse.")
        print(f"Checking {len(targets)} Lua file(s) for block balance:")
    for path in [] if luac is not None else targets:
        problems = check(path)
        name = path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
        if problems:
            bad = True
            print(f"{name}: {len(problems)} problem(s)")
            for p in problems:
                print(f"  {p}")
        else:
            print(f"{name}: balanced")

    import os

    for arg in sys.argv[1:]:
        if not os.path.isdir(arg):
            continue
        drift, compared = mirror_drift(arg)
        if not compared:
            print("Mirror check skipped: no live plug-in directory on this machine.")
        elif drift:
            bad = True
            print(f"Mirror DRIFT against {LIVE}:")
            for line in drift:
                print(f"  {line}")
        else:
            print(f"Mirror matches {LIVE}.")

    sys.exit(1 if bad else 0)
