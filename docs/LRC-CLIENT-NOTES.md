# LrC FGA client — notes

**RFC 2119 keywords. MUST and MUST NOT are absolute. SHOULD is a strong default a good argument may
overrule. MAY is optional.**

## Status: NOT a decision. Nothing is committed.

**This file records where an investigation got to. It is not an ADR, it creates no obligation, and
`docs/architecture/DECISIONS.md` does not reference it.** Terry's framing on 2026-08-14: *"I'm not
committed to this path, but want to note where we got."*

**A later session MUST NOT read this as approval to build.** **The technical blocker is gone and
the decision is not made** — those are different things, and 2026-08-15 changed only the first.

**Feasibility: PROVEN 2026-08-15.** The premise the whole design rested on was measured at runtime
and came back confirmed. See "The load-bearing premise" below. **What remains is Terry's call on
whether to build, and the design questions at the end of this file — authentication above all,
which is a new credential class and would become an ADR.**

Started 2026-08-14.

## Why this came up

**The project goal, stated by Terry on 2026-08-14 and previously written down nowhere:** *"Goal of
this project is to make my life easier as someone who posts photos to Flickr and uses groups to help
people discover my art."*

His actual workflow: *"I do all my culling, editing, and posting to Flickr (using a built in plugin
from Adobe) to publish my photos."*

The proposal: *"if after I publish I could open up a dialog in LR and add the new photo to my FGA
queues per pool/group, that it speeds up my workflow. No need to pop out of LR and use my browser to
log into FGA and queue up group adds."*

**So the web UI is one client, not the product.** ADR-18's Svelte app was built before this goal was
recorded. Work SHOULD be judged against the workflow rather than against the codebase.

## Verdict so far: feasible, one premise short of proven

Lightroom Classic plug-ins are Lua. The SDK gives a plug-in everything an API client needs, and —
critically — lets it read publish services **belonging to other plug-ins**.

### The chain

```lua
catalog:getPublishServices( nil )        -- nil = ALL services, ANY plug-in
  service:getPluginId()                  -- match Adobe's Flickr service
  service:getChildCollections()          -- LrPublishedCollection[]
    collection:getPublishedPhotos()      -- LrPublishedPhoto[]
      publishedPhoto:getRemoteId()       -- the Flickr photo ID
      publishedPhoto:getRemoteUrl()
      publishedPhoto:getPhoto()          -- back to the LrPhoto
```

`photo:getContainedPublishedCollections()` walks the same graph backwards from a selection.

**`getPublishServices` MUST be called inside an `LrTasks` async task**, and so MUST
`getContainedPublishedCollections`.

### What the SDK 15.3 reference actually says

Read from `API Reference/modules/LrCatalog.html` in the downloaded SDK, **not from a web mirror** —
the archived copies online are LR5-era.

> Retrieves the publish services defined by a particular plug-in, **or all publish services in this
> catalog.** [...] `pluginId` (string) Unique identifier of a plug-in, **or nil to get all
> services.**

First supported in SDK 3.0. Still current at 15.3.

### Adobe's own Flickr sample confirms two things

The SDK ships `Sample Plugins/flickr.lrdevplugin`. It is the reference implementation of a Flickr
publish service.

**The remote ID is the Flickr photo ID.** `FlickrExportServiceProvider.lua:1079`:

```lua
-- Record this Flickr ID with the photo so we know to replace instead of upload.
rendition:recordPublishedPhotoId( flickrPhotoId )
```

**The plug-in identifier is `com.adobe.lightroom.export.flickr`**, from that sample's `Info.lua`
`LrToolkitIdentifier`. **A plug-in SHOULD verify this at runtime rather than hardcode it** — the
sample and the shipped built-in service are closely related and have not been proven identical.

**That caution earned its place on 2026-08-15, and the reason is worth reading before anyone
matches on an identifier.** Terry's real catalog was read directly as SQLite, and the publish
service's `AgLibraryPublishedCollection.creationId` is **`com.adobe.ag.export.service.connection`**
— a generic "this row is an export service connection" marker, **not a plug-in identity at all.**

`com.adobe.lightroom.export.flickr` IS in the catalog, in three other places:

| Where | What it looks like |
|---|---|
| `AgPhotoPropertySpec.sourcePlugin` | the identifier, plainly |
| `AgLibraryPublishedCollectionContent.content` | settings keys namespaced `["com.adobe.lightroom.export.flickr_addToPhotoset"]` |
| `Adobe_variablesTable.name` | `AgSdkUpgradeFunctionSucceeded_com.adobe.lightroom.export.flickr` |

**So the identifier is right and the obvious column is wrong.** The catalog stores plug-in identity
indirectly, which means the SDK performs a mapping this file cannot see. **`service:getPluginId()`
MUST therefore be read at runtime and MUST NOT be predicted from the schema.**

**The sample declares `LrSdkVersion = 3.0`, from roughly 2010, and Adobe has not modernized it. Read
it for the mechanism, never as a style template.**

### `getRemoteId()` reads LOCAL records, which makes testing cheap

**It returns what Lightroom wrote into the catalog at publish time. It does not call Flickr.**

So a catalog whose Flickr publish service is expired, disconnected or never re-authorized still
carries every ID. **Any test of this needs no Flickr credentials, no network and no upload.**

**Measured against real data on 2026-08-15, which upgrades this from inference to fact.** Adobe's
sample code said the remote ID is the Flickr photo ID; Terry's catalog proves it, because the ID
appears literally inside the URL stored beside it:

```
remoteId = '42717931314'
url      = 'https://www.flickr.com/photos/146878425@N05/42717931314/in/set-72157693295162860'
```

**834 published photos, and 834 of 834 carry a Flickr URL and a numeric id of 8+ digits.** No
exceptions, no nulls. The NSID is `146878425@N05`, the same value `vitest.config.ts` already stubs.

### The client side

```lua
LrHttp.get( url, headers, timeout )
LrHttp.post( url, postBody, headers, method, timeout, totalSize )
-- headers = { { field = 'Authorization', value = '...' } }
-- returns  body, headersTable    where headersTable.status is the HTTP status
LrHttp.openUrlInBrowser( url )
```

HTTPS, custom request headers and a readable status code. `LrSocket` exists if a localhost callback
is ever wanted. Pass `{ field = 'Content-Type', value = 'skip' }` to suppress Lightroom's automatic
`Content-Type: text/plain`.

Menu registration, in `Info.lua`:

```lua
LrLibraryMenuItems = {
  { title = "Add published photos to FGA queues...", file = "QueueToFga.lua" },
}
```

## What the SDK cannot do

**No post-publish hook exists for a third-party plug-in.** Nothing fires when Adobe's Flickr service
finishes uploading.

**Export filters do not solve it.** They run on the rendered file *before* upload, so no remote ID
exists yet.

**So the flow is: publish as normal, then invoke one menu item.** The better shape of that is a menu
item that finds everything published since the plug-in last ran, which `getPublishedPhotos()` makes
cheap, rather than one that requires a selection.

## The load-bearing premise: CONFIRMED at runtime, 2026-08-15

**A third-party plug-in CAN enumerate Adobe's Flickr publish service and read its published
photos.** Measured, not reasoned. `com.flickrgroupaddr.spike` created no publish service and was
handed Adobe's anyway.

```
VERDICT: CONFIRMED -- 1 service(s) returned to a plug-in that created none of them.

[1] getPluginId() = com.adobe.lightroom.export.flickr
     getName()     = Terry Flickr
     child collections = 96
     collection 2017-08-11: Canada - Alberta - Lake Louise -> 15 published photo(s)
       [1] getRemoteId()  = 42717931314
           getRemoteUrl() = https://www.flickr.com/photos/146878425@N05/42717931314/in/set-...
```

Lightroom Classic 15.5, against `C:\Photography\LR Catalog\TDO Lightroom Catalog.lrcat`.

### Every link in the chain is now measured

| Call | Result |
|---|---|
| `catalog:getPublishServices( nil )` | **1 service**, created by another plug-in |
| `service:getPluginId()` | **`com.adobe.lightroom.export.flickr`** |
| `service:getName()` | `Terry Flickr` |
| `service:getChildCollections()` | **96** |
| `collection:getPublishedPhotos()` | 15 and 12 on the two sampled collections |
| `publishedPhoto:getRemoteId()` | `42717931314` — the Flickr photo id |
| `publishedPhoto:getRemoteUrl()` | the full `flickr.com/photos/...` URL |

**Two independent instruments agree.** `42717931314` is the same value the catalog's `AgRemotePhoto`
table returned when read as SQLite. The SDK and the database tell the same story.

### `getPluginId()` returns the REAL identifier, and this settles the earlier worry

**The SDK answers `com.adobe.lightroom.export.flickr`** — exactly what Adobe's sample predicted, and
**not** the `com.adobe.ag.export.service.connection` that `AgLibraryPublishedCollection.creationId`
holds. So the schema hides plug-in identity and the SDK exposes it.

**Matching on `com.adobe.lightroom.export.flickr` at runtime is therefore viable**, and the standing
instruction to read it rather than predict it from the database is now proven correct rather than
merely cautious.

### What is still NOT measured

**Do not read a confirmed premise as a confirmed design.** These were never exercised:

- `publishedPhoto:getPhoto()`, back to the `LrPhoto`.
- `photo:getContainedPublishedCollections()`, walking the graph backwards from a selection.
- Anything that WRITES. The known restriction stands: **only the plug-in that defines a custom
  metadata field may change it.** This design only reads, so it has not been tested against.

### The spike, and where the evidence is archived

**Working copy:** `C:\Photography\FgaSpike.lrdevplugin\`, version 0.3. **On local disk rather than
`X:`, deliberately** — that share already breaks git ownership, Node file watching and Lightroom
catalogs, and a plug-in loaded over SMB would have added a variable to the one measurement
everything waited on.

**Archived copy, in this repository: `docs/lrc-spike/`.** Both Lua files, the raw unedited output as
`RESULT-2026-08-15.txt`, and `probe-catalog.py` for reading a `.lrcat` directly. **It lived only in
one folder on `C:` and in a session scratchpad until it was committed** — a measurement that took
three versions and a Lightroom crash to obtain, one disk failure from gone.

**Read `RESULT-2026-08-15.txt` rather than any summary if the two ever disagree.**

**It SHOULD ship permanently as a diagnostic** rather than be thrown away, because Terry runs the
latest GA Lightroom Classic and takes every Adobe regression on day one. Re-proving this chain after
an update should cost ten seconds.

## Four mechanics that cost real time, recorded so they cost none next time

**Never wrap a yielding SDK call in Lua's bare `pcall`.** Lightroom runs plug-in code as coroutines
and catalog calls yield; Lua 5.1 cannot yield across a `pcall` boundary. Version 0.1 died with
`Yielding is not allowed within a C or metamethod call` — **and reported it as `VERDICT: REFUTED`,
nearly killing this design on a bug in its own error handling.** The SDK names the fix:
`LrTasks.pcall`, which `API Reference/modules/LrTasks.html` describes as *"Simulates Lua's standard
pcall(), but in a way that allows a call to LrTasks.yield() to occur inside it."*

**A measurement tool MUST distinguish "the answer is no" from "I broke".** 0.1 had two verdicts and
so its own failure read as a finding. 0.2 has three, and an error is `INCONCLUSIVE`.

**Changing `Info.lua` needs Remove then Add in the Plug-in Manager.** Disable and re-enable is NOT
enough — the version number updated while the new menu item never appeared. Terry found this.

**Register a menu item in BOTH `LrLibraryMenuItems` and `LrExportMenuItems`.** The first lands under
Library > Plug-in Extras and exists only in the Library module; the second lands under File >
Plug-in Extras and works everywhere.

**The SDK ships a Lua 5.1 compiler** at `Lua Compiler/win/luac.exe` inside the archive. `luac -p`
parse-checks a plug-in file without Lightroom. **Prove it can fail on deliberately broken input
before trusting a clean pass.**

**If the spike ships, it SHOULD ship permanently as a diagnostic menu item** rather than be thrown
away. Terry always runs the latest GA Lightroom Classic, so the plug-in gets every Adobe regression
on day one, and re-proving the chain after an update should cost seconds.

## Versions

| | |
|---|---|
| Terry's Lightroom Classic | **15.5**, build `202607291506-b8869fa7`, current GA |
| Newest published SDK | **v15.3, April 2026** |
| Also offered under App Version 2026 | v15.2 Feb 2026, v15.1 Dec 2025, v15.0 Oct 2025 |
| Target | `LrSdkVersion = 15.3` |

**The SDK trails the app by two point releases, and that is normal.** The app version MUST NOT be
used to derive the SDK version.

Download path: **Adobe Developer Console → APIs and services → Downloads → search "Lightroom" →
View downloads.** It requires Terry's Adobe login, so it cannot be checked unattended. The archive
is `LrC_15.3_202604090947-8f3672ed.release_SDK.zip`, 8,756,604 bytes.

**Backed up 2026-08-15 to `vendor/` on the NAS**, because the only copy lived in `~/Downloads` and
nothing unattended can replace it. **The zip is gitignored and MUST stay so — it is Adobe's to
license and this repository is public.** `vendor/README.md` carries the checksum and the reasoning.

## The rig

Lightroom Classic is installed at `C:\Program Files\Adobe\Adobe Lightroom Classic`. **Terry does not
edit on this laptop**, but he put his real catalog here on 2026-08-15 specifically to unblock this
work, and Lightroom Classic 15.5 upgraded it to the current catalog format.

| Catalog | State 2026-08-15 |
|---|---|
| **`C:\Photography\LR Catalog\TDO Lightroom Catalog.lrcat`** | **PRESENT, 1,801.8 MB. The real one, and LrC opens it by default** |
| `C:\Travel\LR Catalog\Full Catalog\TDO Lightroom Catalog.lrcat` | Missing |
| `C:\Travel\Lightroom Catalog\Current\TDO Lightroom Catalog.lrcat` | Missing |
| `C:\Temp\LRCat-Test\LRCat-Test.lrcat` | Present, 2 MB. Not useful — no publish service |
| `C:\Users\TDO-XPS15-2024\Pictures\Lightroom\Lightroom Catalog.lrcat` | Present, 1.7 MB. Same |

The recent-catalog list lives in
`%APPDATA%\Adobe\Lightroom\Preferences\Lightroom Classic CC 7 Preferences.agprefs`.

### A `.lrcat` reads as ordinary SQLite, and it can be read SAFELY without a copy

**Confirmed 2026-08-15 on the 1.8 GB catalog.** Open it with `mode=ro` **and** `immutable=1`:

```python
uri = "file:" + urllib.parse.quote(path.as_posix()) + "?mode=ro&immutable=1"
sqlite3.connect(uri, uri=True)
```

**`immutable=1` is the load-bearing half.** It tells SQLite the file cannot change, so it takes no
locks and creates no `-wal`, `-shm` or journal sidecar. Nothing is written and the original cannot
be touched — which is what makes reading a 182,576-image catalog acceptable without first copying
1.8 GB.

**Lightroom MUST be closed first, and that MUST be checked rather than assumed**, because
`immutable=1` is a promise the caller makes. `Get-Process -Name Lightroom*` answers it.

The tables worth knowing: `AgLibraryPublishedCollection` (services and collections),
`AgLibraryPublishedCollectionImage`, `AgRemotePhoto` (`remoteId`, `url`, `photo`),
`AgPhotoPropertySpec.sourcePlugin`, and `Adobe_images` for scale.

**A catalog MUST be on a local writable volume.** Adobe's error names the condition: *"Lightroom
cannot launch with this catalog. It is either on a network volume or on a volume on which Lightroom
cannot save changes."* **`X:` is a NAS share, so a catalog MUST be copied off it before opening.**
Photos MAY stay on the NAS; the `.lrcat` may not.

**A newer Lightroom offers to upgrade an older catalog.** That writes a new file and leaves the
original intact.

## Design questions, unresolved, IF this proceeds

### Authentication is a new credential class

**ADR-10's session is a `__Host-` cookie minted for a browser, and a Lua plug-in is not a browser.**
Candidates, none chosen:

| Option | Cost |
|---|---|
| A long-lived token generated in the web UI and pasted into plug-in settings | One endpoint, one table, a revocation story |
| A device-code flow — plug-in shows a code, user enters it at the site, plug-in polls | Better UX, more endpoints |
| Browser plus a localhost callback over `LrSocket` | A listening socket and a second redirect target |

**Whichever wins becomes an ADR.**

### Group selection MUST NOT be a checkbox list

**Terry belongs to 372 groups** — see `docs/FLICKR.md`. A dialog with 372 checkboxes recreates the
2021 UI failure ADR-18 already names. Saved group sets, chosen once and reused, are the obvious
shape.

### ADR-01 gets MORE load-bearing, not less

**A faster queueing path raises the volume flowing into volunteer moderator queues.**

**Any client MUST call ADR-20's preflight and surface the "this already reached a moderator" warning
before it submits.** Skipping it because a Lua dialog is awkward would quietly undercut the rule this
project is organized around. The server would still refuse, so the user would see confusing failures
rather than a clean warning.

## Considered and rejected

| Option | Why not |
|---|---|
| **Lightroom Services** cloud API | Addresses the Lightroom **cloud** library, not a Classic catalog. Also gated behind *"Requires Adobe review"* |
| **Lightroom API - Firefly Services** | Same wrong target. `Create project` is disabled for Terry's account |
| An export filter to catch the publish | Filters run on the rendered file **before** upload, so no remote ID exists yet |
| Calling Flickr from the plug-in to find the photo | Needs its own Flickr auth, and the catalog already knows the answer |

**Neither cloud API can see a Classic catalog on local disk**, which is where every record this
design needs actually lives. The plug-in path is not merely easier; it is the only one that reaches
the IDs.

## Sources

The SDK archive is authoritative and is the only source that should be quoted for API shapes.
Everything else here was measured on this machine on 2026-08-14, except where marked.

**Unverified, and worth one look:** a search summary claimed the 15.x line included SDK fixes to
photo-collection methods, which is exactly the area this design leans on. That came from a search
result rather than from Adobe. Read the real release notes before trusting or dismissing it.
