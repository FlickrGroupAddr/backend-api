#!/usr/bin/env python3
"""Break the source on purpose. A suite that does not scream is not a safety net.

`npm run check` going green proves the suite AGREES with the code. It does not prove the
suite would NOTICE the code being wrong. Those are different claims, and only the second
one matters when the suite is about to be rewritten.

Each mutation below is a real defect this project has decided against, several of them
security-relevant. For every one: apply it, run the suite, restore the file. **A mutation
the suite survives is a hole.**

    python scripts/mutation-check.py            run them all
    python scripts/mutation-check.py --list     show them without running

Exit 0 when every mutation is caught. Exit 1 names the survivors.
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (name, file, find, replace) -- `find` MUST appear exactly once, which is checked.
MUTATIONS = [
    (
        "fail-polite: retry a photo that reached a moderator",
        "src/adds/classify.ts",
        "const RETRYABLE = new Set([5, 105, 106]);",
        "const RETRYABLE = new Set([5, 6, 105, 106]);",
    ),
    (
        "ADR-02: make an unrecognized code retryable",
        "src/adds/classify.ts",
        "\treturn { kind: \"terminal\", code, relink: false };",
        "\treturn { kind: \"retry\", code };",
    ),
    (
        "ADR-01 transport: make an unanswered call retryable",
        "src/adds/classify.ts",
        "\t\t\treturn { kind: \"unconfirmed\", detail: result.detail };",
        "\t\t\treturn { kind: \"retry\", code: 105 };",
    ),
    (
        "ADR-03: keep walking a queue past a throttle",
        "src/sweep.ts",
        "\t\t\t\tstoppedOnThrottle++;\n\t\t\t\tbreak;",
        "\t\t\t\tstoppedOnThrottle++;\n\t\t\t\thead = await nextInQueue(db, head.nsid, head.groupId);\n\t\t\t\tcontinue;",
    ),
    (
        "cookie: drop HttpOnly",
        "src/session.ts",
        "\thttpOnly: true,",
        "\thttpOnly: false,",
    ),
    (
        "cookie: SameSite=None",
        "src/session.ts",
        '\tsameSite: "Lax",',
        '\tsameSite: "None",',
    ),
    (
        "cookie: drop the __Host- prefix",
        "src/session.ts",
        '\tprefix: "host",',
        "",
    ),
    (
        "session: stop pinning the JWS algorithm",
        "src/session.ts",
        '\t\t\talgorithms: ["HS256"],',
        "",
    ),
    (
        "CORS: reflect the request Origin",
        "src/index.ts",
        "\t\torigin: (origin) => (origin === c.env.UI_ORIGIN ? c.env.UI_ORIGIN : null),",
        "\t\torigin: (origin) => origin,",
    ),
    (
        "crypto: unbind the NSID from the ciphertext",
        "src/crypto/tokens.ts",
        "function aad(nsid: string): Uint8Array {\n\treturn new TextEncoder().encode(nsid);",
        "function aad(_nsid: string): Uint8Array {\n\treturn new TextEncoder().encode(\"fixed\");",
    ),
    (
        "crypto: reuse one IV forever",
        "src/crypto/tokens.ts",
        "\tconst iv = crypto.getRandomValues(new Uint8Array(IV_BYTES));",
        "\tconst iv = new Uint8Array(IV_BYTES);",
    ),
    (
        "withdraw: drop the state='pending' guard",
        "src/db/requests.ts",
        "       WHERE public_id = ? AND nsid = ? AND state = 'pending'",
        "       WHERE public_id = ? AND nsid = ?",
    ),
    (
        "withdraw: let one user withdraw another's request",
        "src/db/requests.ts",
        "\t\t.bind(Date.now(), publicId, nsid)",
        "\t\t.bind(Date.now(), publicId, nsid ? nsid : nsid)",
    ),
    (
        "sweep: stop excluding users flagged needs_relink",
        "src/db/requests.ts",
        "         AND u.needs_relink = 0\n",
        "",
    ),
    (
        "immediate path: stop recording the attempt",
        "src/routes/api.ts",
        "\t\tawait recordAttempt(c.env.DB, id);",
        "",
    ),
    (
        "OAuth: use encodeURIComponent without the five-character fix",
        "src/oauth/signature.ts",
        "\treturn encodeURIComponent(value).replace(\n\t\t/[!'()*]/g,\n\t\t(char) => `%${char.charCodeAt(0).toString(16).toUpperCase()}`,\n\t);",
        "\treturn encodeURIComponent(value);",
    ),
    (
        "OAuth: drop the trailing ampersand in the signing key",
        "src/oauth/signature.ts",
        "\treturn `${percentEncode(consumerSecret)}&${percentEncode(tokenSecret)}`;",
        "\treturn tokenSecret\n\t\t? `${percentEncode(consumerSecret)}&${percentEncode(tokenSecret)}`\n\t\t: percentEncode(consumerSecret);",
    ),
    (
        "ADR-04: stop writing the permanent moderated-pair record",
        "src/db/requests.ts",
        "\tif (reachedAModerator(disposition)) {",
        "\tif (false as boolean) {",
    ),
    (
        "login attempt: return the secret more than once",
        "src/oauth/login-attempt.ts",
        "\t\tawait this.ctx.storage.deleteAll();\n\t\treturn { requestTokenSecret: attempt.requestTokenSecret };",
        "\t\treturn { requestTokenSecret: attempt.requestTokenSecret };",
    ),
    (
        "pagination: cap the limit at nothing",
        "src/routes/api.ts",
        "\tlimit: z.coerce.number().int().min(1).max(200).default(50),",
        "\tlimit: z.coerce.number().int().min(1).default(50),",
    ),
    (
        # The defect only shows in production, where the assets binding exists and this
        # route wins the race for `/`. Locally it looks like a working diagnostic page.
        "ADR-18: claim / in the Worker, shadowing the app shell",
        "src/index.ts",
        'app.get("/api/debug", async (c) => {',
        'app.get("/", async (c) => {',
    ),
]


def read(path: Path) -> str:
    """`newline=""` keeps line endings exactly as they are on disk.

    **Path.read_text() and write_text() do NOT round-trip on Windows.** The read
    translates CRLF to LF and the write translates LF back to os.linesep, so a file that
    was LF comes back CRLF -- a silent reformat of every mutated file, which is precisely
    the damage a restore is supposed to avoid. Caught by Biome after the first run.
    """
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def write(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def run_suite() -> bool:
    """True when the suite passes."""
    done = subprocess.run(
        ["npm", "run", "test", "--silent"],
        cwd=ROOT, capture_output=True, text=True, shell=True,
    )
    return done.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        for i, (name, path, _, _) in enumerate(MUTATIONS, 1):
            print(f"  {i:2}. {name}  [{path}]")
        return 0

    survivors = []
    print(f"Running {len(MUTATIONS)} mutations. A SURVIVOR is a hole in the suite.\n")

    for i, (name, rel, find, replace) in enumerate(MUTATIONS, 1):
        target = ROOT / rel
        original = read(target)

        if original.count(find) != 1:
            print(f"  {i:2}. {name}\n      SKIPPED -- anchor appears "
                  f"{original.count(find)} times in {rel}")
            survivors.append((name, "anchor not unique"))
            continue

        write(target, original.replace(find, replace, 1))
        try:
            passed = run_suite()
        finally:
            write(target, original)

        verdict = "SURVIVED -- suite did not notice" if passed else "caught"
        print(f"  {i:2}. {name:<58} {verdict}")
        if passed:
            survivors.append((name, rel))

    print()
    if survivors:
        print(f"{len(survivors)} of {len(MUTATIONS)} mutations SURVIVED:")
        for name, where in survivors:
            print(f"  - {name}  [{where}]")
        return 1

    print(f"All {len(MUTATIONS)} mutations caught. The suite bites.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
