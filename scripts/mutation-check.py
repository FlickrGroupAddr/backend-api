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
#
# **A name SHOULD open with the ADR it attacks.** `scripts/traceability.py` reads the ADR
# out of the name, so an untagged mutation defends nothing in `docs/TRACEABILITY.md` --
# the matrix then reports `-` for a decision that IS mutation-covered. The name is also
# what the operator reads when one survives, so the tag earns its place twice.
#
# **Two are deliberately untagged, and that is honest rather than an oversight.** No ADR
# states that one user MUST NOT withdraw another's request, and none states the
# `needs_relink` exclusion -- both are described in code comments only. A forced link is
# worse than an admitted gap, which is the same rule TRACE-EXEMPT follows for tests.
MUTATIONS = [
    (
        "ADR-01: retry a photo that reached a moderator",
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
        "ADR-11: drop HttpOnly from the session cookie",
        "src/session.ts",
        "\thttpOnly: true,",
        "\thttpOnly: false,",
    ),
    (
        "ADR-11: set SameSite=None on the session cookie",
        "src/session.ts",
        '\tsameSite: "Lax",',
        '\tsameSite: "None",',
    ),
    (
        "ADR-11: drop the __Host- cookie prefix",
        "src/session.ts",
        '\tprefix: "host",',
        "",
    ),
    (
        "ADR-10: stop pinning the JWS algorithm",
        "src/session.ts",
        '\t\t\talgorithms: ["HS256"],',
        "",
    ),
    (
        "ADR-11: reflect the request Origin in CORS",
        "src/index.ts",
        "\t\torigin: (origin) => (origin === c.env.UI_ORIGIN ? c.env.UI_ORIGIN : null),",
        "\t\torigin: (origin) => origin,",
    ),
    (
        "ADR-09: unbind the NSID from the ciphertext",
        "src/crypto/tokens.ts",
        "function aad(nsid: string): Uint8Array {\n\treturn new TextEncoder().encode(nsid);",
        "function aad(_nsid: string): Uint8Array {\n\treturn new TextEncoder().encode(\"fixed\");",
    ),
    (
        "ADR-09: reuse one IV forever",
        "src/crypto/tokens.ts",
        "\tconst iv = crypto.getRandomValues(new Uint8Array(IV_BYTES));",
        "\tconst iv = new Uint8Array(IV_BYTES);",
    ),
    (
        "ADR-01: drop the state='pending' guard from withdraw",
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
        "ADR-19: stop recording the attempt on the immediate path",
        "src/routes/api.ts",
        "\t\tawait recordAttempt(c.env.DB, id);",
        "",
    ),
    (
        "ADR-14: use encodeURIComponent without the five-character fix",
        "src/oauth/signature.ts",
        "\treturn encodeURIComponent(value).replace(\n\t\t/[!'()*]/g,\n\t\t(char) => `%${char.charCodeAt(0).toString(16).toUpperCase()}`,\n\t);",
        "\treturn encodeURIComponent(value);",
    ),
    (
        "ADR-14: drop the trailing ampersand in the signing key",
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
        "ADR-08: return the login secret more than once",
        "src/oauth/login-attempt.ts",
        "\t\tawait this.ctx.storage.deleteAll();\n\t\treturn { requestTokenSecret: attempt.requestTokenSecret };",
        "\t\treturn { requestTokenSecret: attempt.requestTokenSecret };",
    ),
    (
        "ADR-17: cap the pagination limit at nothing",
        "src/routes/api.ts",
        "\tlimit: z.coerce.number().int().min(1).max(200).default(50),",
        "\tlimit: z.coerce.number().int().min(1).default(50),",
    ),
    (
        # The ORIGINAL defect, restored exactly: stop after page one and call it the
        # whole list. It shipped this way and nothing could see it.
        "ADR-17: return only the first page of the Flickr group list",
        "src/flickr/api.ts",
        "\t\tif (page >= pages) return { kind: \"ok\", groups: collected };",
        "\t\treturn { kind: \"ok\", groups: collected };",
    ),
    (
        # The tempting softening. A truncated list with a flag reads as helpful and is
        # the exact thing ADR-17 now forbids -- nobody can see which entries are missing.
        "ADR-17: soften the ceiling into a truncated list instead of a refusal",
        "src/routes/api.ts",
        "\tif (listed.kind === \"too-many\") {",
        "\tif (false as boolean) {",
    ),
    (
        # The defect only shows in production, where the assets binding exists and this
        # route wins the race for `/`. Locally it looks like a working diagnostic page.
        "ADR-18: claim / in the Worker, shadowing the app shell",
        "src/index.ts",
        'app.get("/api/debug", async (c) => {',
        'app.get("/", async (c) => {',
    ),
    (
        # The most dangerous edit on the admin surface. An unset secret reading as "no
        # restriction" opens operational data to every signed-in user, and reports
        # nothing anywhere -- the dashboard simply works, for everybody.
        "ADR-19: make a missing allowlist fail OPEN",
        "src/admin/allowlist.ts",
        'return { admin: false, configError: "ADMIN_NSIDS is not set" };',
        'return { admin: true, configError: "ADMIN_NSIDS is not set" };',
    ),
    (
        # 403 confirms the admin surface exists and that this account is merely not on
        # the list. The page still "works correctly" with this mutation applied.
        "ADR-19: answer 403 instead of 404, confirming the surface exists",
        "src/middleware/admin.ts",
        'if (!admin) return c.json({ error: "not_found" }, 404);',
        'if (!admin) return c.json({ error: "forbidden" }, 403);',
    ),
    (
        # Preflight stops being scoped to the caller. Every status it returns is still
        # correct-looking, and it silently becomes a way to ask whether SOMEBODY ELSE's
        # photo reached a moderator.
        "ADR-20: let preflight read another account's moderation history",
        "src/db/requests.ts",
        "       WHERE nsid = ? AND photo_id = ? AND group_id IN (${holes})`,\n\t\t)\n\t\t.bind(nsid, photoId, ...groupIds)\n\t\t.all<{ group_id: string; flickr_code: number; first_seen_at: number }>();",
        "       WHERE photo_id = ? AND group_id IN (${holes})`,\n\t\t)\n\t\t.bind(photoId, ...groupIds)\n\t\t.all<{ group_id: string; flickr_code: number; first_seen_at: number }>();",
    ),
    (
        # ADR-04's precedence inverted: a photo already IN the pool gets warned about.
        # A false warning spends exactly the credibility the real one needs.
        "ADR-20: warn about a photo that is already in the pool",
        "src/routes/api.ts",
        'const status = inPool.has(groupId)\n\t\t\t\t? "already_in_pool"',
        'const status = false\n\t\t\t\t? "already_in_pool"',
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
