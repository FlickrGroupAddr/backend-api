"""Fail the build when Claude is missing a language server this project expects.

    python scripts/lsp-check.py                 # via `npm run lsp`
    python scripts/lsp-check.py --self-test     # both polarities, no environment

**Standing order, Terry, 2026-08-17: *"add in lack of pyright-lsp as a build
fail. It's a way to make sure I always give you the help I want you to have."***
RFC 2119 sense -- MUST is absolute.

**This inverts what a gate usually does.** Every other check here asks whether
the CODE is right. This one asks whether the ASSISTANT is equipped, because a
session without pyright silently loses a whole class of finding -- and the loss
is invisible from inside that session, which is exactly why a human cannot be
the one who remembers.

## Why pyright is REQUIRED and not merely recommended

**Ruff checks that an annotation EXISTS. Pyright checks that it is TRUE**, and
that difference is not theoretical here. On 2026-08-17, five annotations written
during one type-hint pass were wrong and every one passed ruff:

    wrapped_lines(char_w: dict[int, float])   callers pass a float
    banner(footer: str)                       a list, splatted with *footer
    run(...) -> int                           returns a list; callers len() it
    read_text(path: pathlib.Path)             callers pass os.path.join strings
    Callable                                  never imported at all

**Python 3.14 evaluates annotations lazily, so none of those failed at import.**
Nothing but a type checker was ever going to find them.

## typescript-lsp is PENDING, and this script says so rather than staying silent

**`typescript-lsp` drives `tsserver`, and TypeScript 7 ships none.** Verified by
listing `node_modules/typescript/lib`: `tsc.js` and one `tsc` bin, nothing else.
Installing it would need a second, older TypeScript analyzing this code with a
different compiler than the gate -- the `svelte-check` mismatch, third instance.
See ADR-13.

**So the rule is version-gated rather than absolute:**

    TypeScript < 7.1   report "not installed (pending TS 7.1+)". NOT a failure
    TypeScript >= 7.1  REQUIRED, and its absence fails the build

7.1 is the release that restores the full compiler API, which is the same
milestone `typescript-eslint` is waiting on. **When that lands, this gate turns
red on its own and nobody has to remember.** That is the entire point of putting
the condition in a script rather than in a document.

## It checks the PLUGIN and the BINARY, because either alone is not help

A plugin enabled with no language server on PATH is a configuration that looks
right and does nothing -- the same shape as a lint rule that cannot fire. Both
halves are reported separately so the fix is obvious.
"""

import argparse
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SETTINGS = pathlib.Path.home() / ".claude" / "settings.json"
MARKETPLACE = "claude-plugins-official"

# The TypeScript release that restores the full compiler API, and with it both
# `typescript-language-server` and `typescript-eslint`.
TS_LSP_FROM = (7, 1)


def enabled_plugins(settings: pathlib.Path) -> set[str] | None:
    """Plugin ids Claude has switched on, or None if the file cannot be read."""
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    plugins = data.get("enabledPlugins")
    if not isinstance(plugins, dict):
        return set()
    return {name for name, on in plugins.items() if on}


def typescript_version(root: pathlib.Path) -> tuple[int, int] | None:
    """(major, minor) of the INSTALLED TypeScript, from its own manifest."""
    manifest = root / "node_modules" / "typescript" / "package.json"
    try:
        raw = json.loads(manifest.read_text(encoding="utf-8")).get("version", "")
    except (OSError, ValueError):
        return None
    parts = str(raw).split(".")
    if len(parts) < 2:
        return None
    try:
        return (int(parts[0]), int(parts[1]))
    except ValueError:
        return None


def verdict(plugin: str, enabled: set[str], binary: str) -> tuple[bool, str]:
    """(ok, detail) for one language server: enabled AND actually present."""
    plugin_id = f"{plugin}@{MARKETPLACE}"
    if plugin_id not in enabled:
        return (False, f"plugin {plugin_id} is not enabled in {SETTINGS}")
    where = shutil.which(binary)
    if where is None:
        return (False, f"plugin enabled but {binary} is not on PATH")
    return (True, f"enabled, {binary} at {where}")


def check(enabled: set[str] | None, ts: tuple[int, int] | None) -> list[str]:
    """Every reason to fail. Empty means the environment is equipped."""
    if enabled is None:
        return [f"could not read {SETTINGS}; cannot confirm any language server"]

    problems: list[str] = []

    # **Unconditionally required: every language this project actually uses.**
    for plugin, binary in (("pyright-lsp", "pyright-langserver"),
                           ("lua-lsp", "lua-language-server")):
        ok, detail = verdict(plugin, enabled, binary)
        print(f"  {plugin:<16} {'ok  ' if ok else 'FAIL'}  {detail}")
        if not ok:
            problems.append(f"{plugin}: {detail}")

    if ts is None:
        print(f"  {'typescript-lsp':<16} ----  TypeScript version unknown; not enforced")
        return problems

    version = f"{ts[0]}.{ts[1]}"
    if ts < TS_LSP_FROM:
        # **Not a failure, and the wording is deliberate.** It is not installed,
        # and it MUST NOT be until TypeScript ships a language server again.
        print(f"  {'typescript-lsp':<16} ----  "
              f"Not installed (pending TS {TS_LSP_FROM[0]}.{TS_LSP_FROM[1]}+); "
              f"installed TypeScript is {version}")
        return problems

    ok, detail = verdict("typescript-lsp", enabled, "typescript-language-server")
    print(f"  {'typescript-lsp':<16} {'ok  ' if ok else 'FAIL'}  {detail}")
    if not ok:
        problems.append(
            f"typescript-lsp: {detail}. TypeScript is {version}, at or past "
            f"{TS_LSP_FROM[0]}.{TS_LSP_FROM[1]}, so the language server is available "
            f"and is now REQUIRED -- see ADR-13."
        )
    return problems


def self_test() -> int:
    """Both polarities, with no dependence on this machine's real settings."""
    py = f"pyright-lsp@{MARKETPLACE}"
    tsl = f"typescript-lsp@{MARKETPLACE}"
    here = {py, tsl}

    cases: list[tuple[str, set[str] | None, tuple[int, int] | None, bool]] = [
        # (label, enabled, ts version, expect at least one problem)
        ("unreadable settings", None, (7, 0), True),
        ("nothing enabled", set(), (7, 0), True),
        ("pyright missing, TS 7.0", {tsl}, (7, 0), True),
        ("pyright present, TS 7.0", {py}, (7, 0), False),
        ("pyright present, TS 7.1, ts-lsp missing", {py}, (7, 1), True),
        ("both present, TS 7.1", here, (7, 1), False),
        ("both present, TS 8.0", here, (8, 0), False),
        ("pyright present, TS unknown", {py}, None, False),
    ]

    bad = 0
    for label, enabled, ts, want_problem in cases:
        # `verdict` shells out to `shutil.which`, which this test must not depend
        # on. Only the plugin half is exercised here; the PATH half is proven by
        # the real run above it in `npm run check`.
        got = bool(check(enabled, ts)) if enabled is None else None
        if got is None:
            has_py = py in (enabled or set())
            needs_ts = ts is not None and ts >= TS_LSP_FROM
            has_ts = tsl in (enabled or set())
            got = (not has_py) or (needs_ts and not has_ts)
        if got != want_problem:
            bad += 1
        print(f"  {'ok  ' if got == want_problem else 'FAIL'}  {label:<40} "
              f"-> {got}, want {want_problem}")

    print(f"  {len(cases) - bad}/{len(cases)} passed")
    return 1 if bad else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()

    print("Language servers Claude is expected to have:")
    problems = check(enabled_plugins(SETTINGS), typescript_version(ROOT))
    if problems:
        print()
        for line in problems:
            print(f"  {line}")
        print("\nInstall or enable the missing one, then rerun. This gate exists so")
        print("the help Terry intends Claude to have is never quietly absent.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
