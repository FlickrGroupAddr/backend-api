# vendor/ — third-party archives, kept out of git on purpose

**RFC 2119 keywords. MUST and MUST NOT are absolute.**

**Everything in this directory except this file is gitignored, and that MUST stay true.** This
repository is public. The contents here belong to somebody else.

## What is here

| | |
|---|---|
| File | `LrC_15.3_202604090947-8f3672ed.release_SDK.zip` |
| What | Adobe Lightroom Classic SDK, **v15.3, April 2026** |
| Size | 8,756,604 bytes |
| SHA-256 | `5A33BA3F7DCA01EBB0EFD4348F4E7C1F2148947DC62DCB7611AC43B52430BFF0` |
| Verified | 2026-08-15 — hash matched the source, and the archive opened clean at 215 entries |

## Why it is stored rather than re-downloaded

**Re-obtaining it needs Terry's Adobe login**, so it cannot be fetched unattended by a script, a
build, or a session working alone. Until 2026-08-15 the only copy on the machine sat in
`~/Downloads`, which is one cleanup away from gone — and it is the authoritative source for every
API shape in `docs/lrc-spike/`.

**Download path:** Adobe Developer Console → APIs and services → Downloads → search "Lightroom" →
View downloads.

## Why it MUST NOT be committed

**It is Adobe's to license and not ours to redistribute.** Committing it would publish 8.35 MB of
someone else's copyrighted material from a repository carrying Terry's name.

The `.gitignore` entry is `vendor/*` with `!vendor/README.md`, and the reasoning sits beside it
there. **A negation cannot rescue a file whose parent directory is excluded**, which is why the
pattern ends in `/*` rather than `/`.

## What it is used for

**The archive is the authoritative source for Lightroom SDK API shapes.** Read it rather than any
web mirror — the archived copies online are LR5-era and wrong about current method signatures.

It also ships a Lua 5.1 compiler at `Lua Compiler/win/luac.exe`, which parse-checks a plug-in
without launching Lightroom:

```
luac -p docs/lrc-spike/plugin/Info.lua
```

**Prove it can fail on deliberately broken input before trusting a clean pass.**

## Note on the location

**This lives on `X:`, which is an SMB share on the NAS at `//192.168.1.152/Personal`.** That is
fine for a file that is only ever read and copied. It would not be fine for a Lightroom catalog, a
git repository's locks, or anything a Node file watcher has to see — that share breaks all three.
