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
| Current? | **YES as of 2026-08-15.** v15.3 is the newest offered for App Version 2026 |

### The release history, read off the console on 2026-08-15

| SDK | Released |
|---|---|
| **v15.3** | Apr 2026 — **what is vendored here, and still the newest** |
| v15.2 | Feb 2026 |
| v15.1 | Dec 2025 |
| v15.0 | Oct 2025 |

**Two facts worth having, and both correct guesses made before the data arrived.**

**The cadence is about every two months, not "a few times a year."** Four releases in six months.

**But it STOPPED.** v15.3 shipped in April and nothing has followed it in the four months since,
while Lightroom Classic itself moved on to 15.5. **So the SDK genuinely does not track the
application**, and this is the evidence rather than an assertion — see the rejected shortcut below.

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

## NOT in the daily toolchain freshness check, and that is a decision

**Terry raised it on 2026-08-15**, reasoning that the Adobe Developer Console download is
cookie-authenticated so a check could reach it. **The answer is no, and the reason is his own
loudness rule rather than the difficulty.**

> Loud requires all three: the network answered, the answer is a confirmed behind, and Terry can act
> this minute.

**A new SDK fails the third condition.** Re-obtaining the archive needs his Adobe login, so no
unattended run can fetch it. Every firing would land in the "could not confirm / cannot act" bucket,
which that rule says MUST stay quiet — and **a check whose loud path can never legitimately fire is
scenery.** It would spend the banner's credibility and return nothing.

**Three more reasons, in descending weight:**

- **The SDK is nearly impossible to fall dangerously behind.** Adobe's own bundled Flickr sample
  declares `LrSdkVersion = 3.0`, from roughly 2010, and it still runs against 15.3. Terry's own
  framing: *"the Adobe Flickr plugin uses API version zero.ancient, I'm not too worried about big   US-ENGLISH-EXEMPT: quoting Terry
  drift"*.
- **Cadence mismatch.** Measured at roughly one release every two months, so a daily check is about
  60 runs per change. **This figure was guessed at "a few times a year" before Terry supplied the
  console's release list**, which is a reminder that a cadence claim is a measurement like any
  other.
- **`luac` cannot go stale.** `npm run check` now depends on `Lua Compiler/win/luac.exe` from this
  archive, which is the one real build dependency here — and **Lua 5.1.5 has had no release since
  2012.**

**What replaces it: this file.** The version, date, SHA-256, byte count and download path above are
the durable record. **Verify the archive rather than its freshness** — an intact known-good copy is
worth more here than a current one.

### The obvious cheap check is a FALSE POSITIVE GENERATOR, and Terry killed it

**The tempting shortcut is "compare against the current Lightroom Classic release", because the
console page needs a login and the release notes do not.** It rests on the SDK version tracking the
application version.

**It does not.** Terry, 2026-08-15: *"LrC is currently 15.5 but SDK is 15.3."* The release table
above is the proof: the SDK's last release was April, and the application has shipped twice since.

So that check would report **behind** on every Lightroom point release the SDK did not follow, and
the SDK does not follow most of them. **It would fire, be wrong, and be wrong repeatedly** — which
is the precise mechanism by which a banner stops being read.

**Anyone reviving this MUST first find a source that states the SDK's own version.** Not
Lightroom's. The two are related and are not the same number, and the shortcut is convincing enough
that it needs saying out loud.

## Note on the location

**This lives on `X:`, which is an SMB share on the NAS at `//192.168.1.152/Personal`.** That is
fine for a file that is only ever read and copied. It would not be fine for a Lightroom catalog, a
git repository's locks, or anything a Node file watcher has to see — that share breaks all three.
