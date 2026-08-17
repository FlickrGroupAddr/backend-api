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
        # The opaque design's whole point. Storing the id itself makes a D1 leak hand
        # over directly usable bearer tokens for every live session.
        # **The anchor went stale on 2026-08-15** when the bind call was reformatted to
        # carry `client_type`, and the harness reported the mutation as a SURVIVOR rather
        # than as unapplied. That is the right way round -- a mutation that cannot run is
        # a hole until somebody looks -- but it means an anchor is a maintenance burden,
        # and the narrowest one that stays unique is the cheapest to keep.
        "sessions: store the raw id instead of its hash",
        "src/session.ts",
        "\t\t\tawait idHash(id),",
        "\t\t\tid,",
    ),
    (
        # **Turns the allow-list back into a deny-list**, which is the mistake it was
        # built to prevent rather than a random break. Every endpoint added later would
        # silently become reachable by a 90-day credential living on a laptop, and
        # nothing would look wrong until somebody audited it.
        "ADR-19: let a plug-in token reach any route, not just its allow-list",
        "src/middleware/session.ts",
        "\t\tif (!allowed) {",
        "\t\tif (false as boolean) {",
    ),
    (
        # Without the MAC gate a forger reaches D1 on every sprayed cookie, and leaking
        # SESSION_KEY stops being survivable.
        "sessions: skip the HMAC gate and go straight to the database",
        "src/session.ts",
        "\tif (presented.length !== expected.length) return null;",
        "\tif (false as boolean) return null;",
    ),
    (
        # Expiry is the only bound on a stolen handle that nobody has noticed is stolen.
        "sessions: honor an expired handle",
        "src/session.ts",
        "\tif (row.expires_at <= Date.now()) return null;",
        "\tif (false as boolean) return null;",
    ),
    (
        # Revocation is what ADR-10 could not do, and logout is where it is spent.
        "sessions: make logout clear the cookie without revoking the row",
        "src/routes/oauth.ts",
        "\tif (cookie !== undefined) await revokeSession(c.env.DB, cookie);",
        "",
    ),
    (
        # The load-bearing property of the batch endpoint. Forty sequential
        # groups.pools.add calls on one token is the discourtesy ADR-01 refuses.
        "ADR-03: let the batch attempt immediately even when many groups were asked for",
        "src/routes/api.ts",
        "\t\tgroupIds.length === 1 && minted.length === 1 ? minted[0] : undefined;",
        "\t\tminted.length >= 1 ? minted[0] : undefined;",
    ),
    (
        # A warned pair MUST NOT be queued without an explicit per-group acknowledgement.
        "ADR-04: queue a batch group that already reached a moderator",
        "src/routes/api.ts",
        "\t\t} else if (seen !== undefined && !acknowledged.has(groupId)) {",
        "\t\t} else if (false as boolean) {",
    ),
    (
        # ADR-05. A pair already in the pool must never be resubmitted.
        "ADR-05: queue a batch group whose photo is already in the pool",
        "src/routes/api.ts",
        # **The line below is part of the anchor, and it has to be.** The
        # preflight route grew an identical condition at one deeper indent on
        # 2026-08-17, when its nested ternary became an if-chain -- and this
        # two-tab form is a SUBSTRING of that three-tab one. Naming what the
        # branch DOES is what tells the two apart.
        (
            '\t\tif (inPool.has(groupId) || succeeded.has(groupId)) {\n'
            '\t\t\tdecided.push({ groupId, status: "already_in_pool" });'
        ),
        (
            '\t\tif (false as boolean) {\n'
            '\t\t\tdecided.push({ groupId, status: "already_in_pool" });'
        ),
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
        # **Anchor re-cut 2026-08-16**, when `consume` grew a `returnPath` and the old
        # anchor stopped matching. The harness reported it SKIPPED rather than passing,
        # which is the design working -- a mutation whose anchor has drifted defends
        # nothing, and a silent skip would have read as coverage.
        "ADR-08: return the login secret more than once",
        "src/oauth/login-attempt.ts",
        "\t\tawait this.ctx.storage.deleteAll();\n\t\treturn {",
        "\t\treturn {",
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
        # **The most dangerous simplification available in the newest endpoint**, and it
        # reads as tidying up. "Flickr did not answer" and "the photo is in no groups"
        # are different facts. Collapsing them shows the Lightroom picker an empty
        # right-hand list, so the user queues adds for groups the photo is ALREADY in --
        # and a duplicate add can reach a moderator, which ADR-01 calls terminal.
        "ADR-17: report an unknown pool lookup as an empty group list",
        "src/routes/api.ts",
        'return c.json({ error: "flickr_unavailable" }, 502);',
        "return c.json({ groups: [] });",
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
        # Re-cut 2026-08-17: the nested ternary this used to anchor on became an
        # if-chain when Biome's `noNestedTernary` was enabled. **The condition is
        # unchanged; only its spelling moved**, which is exactly the case the
        # anchor rule in CLAUDE.md is about.
        (
            '\t\t\tif (inPool.has(groupId) || succeeded.has(groupId)) {\n'
            '\t\t\t\tstatus = "already_in_pool";'
        ),
        (
            '\t\t\tif (false as boolean) {\n'
            '\t\t\t\tstatus = "already_in_pool";'
        ),
    ),
    (
        # The open redirect. Drop the origin check and `returnTo=https://evil.com`
        # resolves to somebody else's site -- with the session cookie already set,
        # because the callback sets it before it redirects.
        "ADR-11: let returnTo escape our origin",
        "src/oauth/return-to.ts",
        "\tif (resolved.origin !== base.origin) return null;",
        "\tif (false && resolved.origin !== base.origin) return null;",
    ),
    (
        # ADR-17's bound on the destination list. Without it any same-origin path is
        # a landing spot, which is safe today only because no path is dangerous today.
        "ADR-11: accept any path as a login destination",
        "src/oauth/return-to.ts",
        "\tif (!ALLOWED_RETURN_PATHS.has(resolved.pathname)) return null;",
        "\tif (false) return null;",
    ),
    (
        # **The regression itself.** This IS the defect found on 2026-08-16: the
        # callback ignored where the login started and always went to the app root,
        # so a user who signed in mid-device-link arrived home with the code gone.
        "ADR-11: send every login back to the app root",
        "src/routes/oauth.ts",
        'return c.redirect(uiUrl(c.env, "ok", attempt.returnPath), 302);',
        'return c.redirect(uiUrl(c.env, "ok"), 302);',
    ),
    (
        # **The escalation.** A plug-in token that can approve a device link can mint
        # another plug-in token, and a stolen laptop renews itself forever.
        "ADR-24: let a plug-in token approve a device link",
        "src/routes/device.ts",
        '\t"/api/v001/device/approve",\n\trequireSession,\n\trequireBrowserSession,\n);',
        '\t"/api/v001/device/approve",\n\trequireSession,\n);',
    ),
    (
        # Hand the token to anyone holding the userCode -- which is read off a screen.
        # The whole reason deviceCode exists as a second, secret value.
        #
        # **Anchor re-cut 2026-08-16**, an hour after it was written: inserting the
        # poll throttle between the code check and its neighbor drifted an anchor that
        # spanned both. It now targets the CONDITION rather than the code around it,
        # which is what an anchor should have done in the first place -- a mutation
        # anchored to its neighbors breaks whenever a neighbor moves.
        "ADR-24: collect a token without proving you started the flow",
        "src/device/link-attempt.ts",
        (
            "\t\t\tgot.byteLength !== want.byteLength ||\n"
            "\t\t\t!crypto.subtle.timingSafeEqual(got, want)"
        ),
        "\t\t\tfalse",
    ),
    (
        # Single use is what stops a replayed poll re-minting a credential.
        "ADR-24: let an approved link be collected more than once",
        "src/routes/device.ts",
        'if (state.kind !== "approved") {',
        'if (state.kind === "never-happens") {',
    ),
    (
        # Mint at approval instead of at collection, so an abandoned link leaves a
        # live 90-day credential nobody asked for.
        "ADR-24: mint the plug-in token with a browser lifetime",
        "src/routes/device.ts",
        '\t\t"lrc15_plugin",\n\t);',
        '\t\t"browser",\n\t);',
    ),
    (
        # `pollAfter` becomes advice nobody enforces, and a plug-in in a tight loop
        # hammers the Durable Object for the whole ten-minute window.
        "ADR-24: stop throttling the poll server-side",
        "src/device/link-attempt.ts",
        "const MIN_POLL_INTERVAL_MS = 2000;",
        "const MIN_POLL_INTERVAL_MS = 0;",
    ),
    (
        # A throttled poll that MOVES the window means a client polling in a tight
        # loop refuses itself forever instead of recovering after one honest wait.
        # A refusal must be STICKY. Drop the `denied` guard and a second click, a
        # double submit, or anybody else holding the code can reverse a person's no.
        "ADR-24: let an approval override a denial",
        "src/device/link-attempt.ts",
        "if (attempt === undefined || attempt.denied) return false;",
        "if (attempt === undefined) return false;",
    ),
    (
        # Every reply from these routes carries a bearer credential in its body, and
        # mounting deviceRoutes ahead of apiRoutes means ADR-12's blanket no-store
        # never runs for them. The header was genuinely absent until 2026-08-16.
        "ADR-12: let a credential-bearing device reply be cached",
        "src/routes/device.ts",
        '\tc.header("Cache-Control", "private, no-store");',
        "\t// mutation",
    ),
    (
        "ADR-24: let a throttled poll push the window forward",
        "src/device/link-attempt.ts",
        "\t\t\treturn { kind: \"slow_down\" };",
        (
            "\t\t\tawait this.ctx.storage.put<StoredAttempt>(\"attempt\", {\n"
            "\t\t\t\t...attempt,\n\t\t\t\tlastPolledAt: now,\n\t\t\t});\n"
            "\t\t\treturn { kind: \"slow_down\" };"
        ),
    ),
]


def read(path: Path) -> str:
    """`newline=""` keeps line endings exactly as they are on disk.

    **Path.read_text() and write_text() do NOT round-trip on Windows.** The read
    translates CRLF to LF and the write translates LF back to os.linesep, so a file that
    was LF comes back CRLF -- a silent reformat of every mutated file, which is precisely
    the damage a restore is supposed to avoid. Caught by Biome after the first run.
    """
    with open(path, encoding="utf-8", newline="") as handle:
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
