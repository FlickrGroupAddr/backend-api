# The Lightroom Classic spike, and the evidence it produced

**RFC 2119 keywords. MUST and MUST NOT are absolute. SHOULD is a strong default a good argument may
overrule. MAY is optional.**

## 0.4 adds a SECOND probe, and it measures the picker

**`PickerProbe.lua` answers the two questions `docs/LRC-CLIENT-NOTES.md` records as unmeasured**,
and it answers them by being used rather than by being read:

1. **Does rebinding `simple_list.items` clear or corrupt the selection?**
2. **How does a 372-item list look and perform**, and does `height` accept a large value? The
   reference states a minimum of 80 and names no maximum.

**The merge selection model is correct either way, which is why it is the design regardless of the
answer.** What differs is the FEEL — a widget that visibly drops its highlighting on every keystroke
is unpleasant even when the model underneath is right, and feel cannot be read out of a reference
manual.

**It makes no network call and touches no catalog.** The 372 groups are generated in the file, with
deliberately long repetitive names: a picker that looks fine with `Group 12` and falls apart with
`Canada Landscapes - pool 214` has not been tested.

### How to run it

**Remove then Add in the Plug-in Manager. Disable and re-enable is NOT enough** — `Info.lua`
changed, and that combination once updated the version number while the new menu item never
appeared.

Then **File > Plug-in Extras > FGA: group picker probe (File)**. The File entry works in every
module; the Library entry needs the Library module active.

**What to look for:** type in the filter box and watch whether highlighted rows stay highlighted as
the list narrows and widens. The line under the list reports `showing N of 372 · selected N`, which
is the model's view — **if the count holds while the highlighting does not, the widget is dropping
`value` on rebind and the merge model is doing its job.**

## This is EVIDENCE, not a decision

**Nothing here commits FlickrGroupAddr to building a Lightroom client.** `docs/LRC-CLIENT-NOTES.md`
holds that status and still says the decision is Terry's and unmade. **The technical blocker is
gone; that is a different sentence.**

**These files are archived because they proved something, and the proof took three attempts and a
Lightroom crash to obtain.** Losing them would mean re-deriving a measurement that needed a 1.8 GB
catalog, a working plug-in, and a human clicking a menu item.

## What was established, 2026-08-15

**A third-party Lightroom plug-in CAN enumerate Adobe's Flickr publish service and read its
published photos.** That was the single premise the whole client design rested on, and it had never
been watched working.

`RESULT-2026-08-15.txt` is the raw, unedited output of the run. Read it rather than this summary if
the two ever disagree.

| Call | Answer |
|---|---|
| `catalog:getPublishServices( nil )` | 1 service, created by another plug-in |
| `service:getPluginId()` | `com.adobe.lightroom.export.flickr` |
| `service:getName()` | `Terry Flickr` |
| `service:getChildCollections()` | 96 |
| `collection:getPublishedPhotos()` | 15 and 12 on the sampled collections |
| `publishedPhoto:getRemoteId()` | `42717931314` — the Flickr photo id |
| `publishedPhoto:getRemoteUrl()` | the full `flickr.com/photos/...` URL |

Lightroom Classic **15.5**, against `C:\Photography\LR Catalog\TDO Lightroom Catalog.lrcat`.

**Two independent instruments agree.** `probe-catalog.py` read the same `42717931314` out of the
catalog's `AgRemotePhoto` table an hour before the plug-in returned it through the SDK.

## The files

| | |
|---|---|
| `plugin/Info.lua` | Plug-in manifest, version 0.3. Registers the menu item in **both** menu tables |
| `plugin/DumpPublishServices.lua` | The measurement. Read-only, no network. Its header documents the `pcall` trap in full |
| `RESULT-2026-08-15.txt` | Raw output of the confirming run |
| `probe-catalog.py` | Reads a `.lrcat` directly as SQLite, read-only. Answers the precondition without launching Lightroom |

**The in-script label reads `0.2` while `Info.lua` reads `0.3`.** That is accurate rather than
sloppy: 0.3 changed only the menu registration, and the script that produced the result was
unchanged from 0.2.

## Running it

**Load the copy on local disk, NOT this one.** `X:` is an SMB share that already breaks git
ownership, Node file watching and Lightroom catalogs. A plug-in loaded over SMB adds a variable to
a measurement, and this directory is an archive rather than a working copy.

```
Plug-in Manager -> Add -> C:\Photography\FgaSpike.lrdevplugin
File > Plug-in Extras > FGA: dump publish services (File)
```

**Changing `Info.lua` requires Remove then Add.** Disable and re-enable is NOT enough — the version
number updates while the menu registration does not rebuild, so the manager will show the new
version and the menu item will be missing.

```
python docs/lrc-spike/probe-catalog.py
```

**It refuses to run while Lightroom is open**, because it opens the catalog with `immutable=1` and
that is a promise the caller makes.

## The four mechanics that cost the time

**Never wrap a yielding SDK call in Lua's bare `pcall`.** Lightroom runs plug-in code as coroutines
and catalog calls yield; Lua 5.1 cannot yield across a `pcall` boundary. Use `LrTasks.pcall`, which
the SDK documents as existing for exactly this. **The defensive wrapper was the defect.**

**A measurement tool MUST have three verdicts.** Version 0.1 had two, so its own breakage came out
as `VERDICT: REFUTED` — one label away from killing this design on a bug in its own error handling.
An error is `INCONCLUSIVE` and says so.

**Register a menu item in both `LrLibraryMenuItems` and `LrExportMenuItems`.** The first is Library
module only; the second works everywhere.

**The SDK ships `Lua Compiler/win/luac.exe`.** `luac -p` parse-checks a plug-in without Lightroom.
**Prove it fails on deliberately broken input before trusting a clean pass.**

## What is still NOT measured

**A confirmed premise is not a confirmed design.** Never exercised: `publishedPhoto:getPhoto()`,
`photo:getContainedPublishedCollections()`, and anything that writes. The known restriction stands
— **only the plug-in that defines a custom metadata field may change it** — and this design only
reads, so it has never been tested against.

**Authentication is unsolved and would become an ADR.** ADR-10's session is a `__Host-` cookie
minted for a browser, and a Lua plug-in is not a browser. See `docs/LRC-CLIENT-NOTES.md`.

**Any client MUST call ADR-20's preflight and surface the ADR-04 warning before it submits.** A
faster queueing path raises the volume reaching volunteer moderators, so ADR-01 gets more
load-bearing rather than less.
