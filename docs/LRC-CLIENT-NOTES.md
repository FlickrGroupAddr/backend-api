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

**IT IS IN THIS REPO, at `vendor/LrC_15.3_202604090947-8f3672ed.release_SDK.zip`.**

**An earlier version of this line said the opposite**, and the way it was wrong is the lesson. The
search looked for filenames matching `*Lightroom*SDK*` and `luac*.exe`. The archive is named
`LrC_...`, and `luac.exe` lives INSIDE the zip rather than on disk, so neither pattern could ever
have matched. **A search that finds nothing is not evidence that nothing is there** — and Terry knew
where it was while the docs asserted it did not exist. See [[justified-premises-go-unchecked]].

`npm run lua` now **extracts `Lua Compiler/win/luac.exe` on demand** into a temp file and parse-checks
every plug-in file for real. `vendor/` stays an archive and a 386 KB binary stays out of git.

**`scripts/lua-balance.py` keeps its block-balance pass as a FALLBACK**, for a machine without the
archive, and it announces which instrument ran. A block-balance pass and a real parse are very
different assurances; identical output would hide the swap.

### Four SDK traps, all found by READING on 2026-08-15

**Reading was the only QA available** — no Lightroom to run, no `luac` to parse-check. It found four
real defects in code written the same evening, three of which would have cost a full load-and-test
cycle each. **Budget a careful re-read of any Lua before handing it over**, because the feedback loop
through Lightroom is minutes long and the person paying for it is Terry.

| Trap | What it would have done |
|---|---|
| **`\u{25CF}` is a Lua 5.3 escape** | Lightroom runs 5.1, where it is a **syntax error**. The whole file fails to load, not just the glyph |
| **`simple_list.value` may be a scalar** | With `allows_multiple_selection = false`. `("abc")[1]` is nil, so the observer runs `selected[nil] = true` and **dies on the first click** |
| **`os.clock()` is CPU time** | An HTTP request is almost all waiting, so a 15-second timeout would report a few milliseconds. Use `LrDate.currentTime()` for fractional wall seconds |
| **An unguarded `io.open`** | A read-only desktop or a locked file would throw and take the HTTP result with it. The measurement MUST outlive the convenience of saving it |

**And one thing deliberately NOT done.** `font = "<system/bold>"` on the picker's two headings is
almost certainly valid `LrView` — and *almost certainly* is recall, with no SDK on this machine to
check against. **An unknown attribute fails the whole dialog rather than rendering plain**, so being
wrong costs a full cycle to learn something cosmetic. It is out. Add it once the reference is on
hand.

### Loading spike 0.6

The plug-in lives at `C:\Photography\FgaSpike.lrdevplugin`, mirrored into
`docs/lrc-spike/plugin/` so it is under version control.

**`Info.lua` changed, so this needs Remove then Add** — see the rule above. Four menu items appear
under both File > Plug-in Extras and Library > Plug-in Extras:

| Item | What it does |
|---|---|
| Dump publish services | The original premise probe. Unchanged |
| Group picker probe — one list | **0.4, kept as the control.** The design Terry rejected |
| Group picker — TWO LISTS | **0.5.** The redesign. Synthetic data, no network |
| Connectivity probe | **0.6.** Two real calls to flickrgroupaddr.com, no credentials |

**Only the connectivity probe touches the network**, and it sends nothing but a `User-Agent`. The
two pickers generate their groups locally.

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

## The UI toolkit, read from the SDK reference on 2026-08-15

**25 widget constructors. No table, no tree, no multi-column list, nothing virtualized, no built-in
filter. Every dialog is modal except `presentFloatingDialog`.**

| Category | Widgets |
|---|---|
| Layout | `row`, `column`, `group_box`, `scrolled_view`, `tab_view`, `tab_view_item`, `separator`, `spacer`, `view` |
| Input | `edit_field`, `password_field`, `checkbox`, `radio_button`, `popup_menu`, `combo_box`, `simple_list`, `slider`, `color_well`, `push_button` |
| Display | `static_text`, `picture`, `catalog_photo` |

**`simple_list` is the one that decides the picker**, and it is better than it first looks:

> `value` : an array of the values corresponding to **each selected list item**
> `items` : table of items, each with a localizable `title` and a `value`
> `allows_multiple_selection` : True if the list supports selection of multiple items at one time
> `height` : default 150, will not be allowed smaller than 80

So a scrolling, flat, **multi-select** list of title/value pairs with bindable `items`. No columns,
no per-row widgets, no icons.

**`combo_box` is NOT a searchable object picker.** The reference calls it "an editable text field
and a pop-up menu of predefined **text** values". Typing filters nothing. **The web UI's
type-ahead-and-chips picker does not port.**

**`catalog_photo` renders a real thumbnail from the catalog**, so a dialog can show the photos it is
about to queue.

**Supporting machinery, all confirmed present:** `LrDialogs.presentModalDialog` takes a full
`LrView` hierarchy, `LrProgressScope` gives a cancelable progress bar, `LrBinding` and
`LrObservableTable` give reactive property tables, `LrPrefs.prefsForPlugin` persists settings, and
`LrPasswords.store` / `retrieve` is encrypted storage keyed to the plug-in ID.

## Design settled 2026-08-15

### TWO CLIENTS, BOTH FIRST-CLASS, RELEASED IN LOCKSTEP

**Terry's decision, 2026-08-15. FGA has exactly two client classes and MUST treat both as
first-class:**

| Client | Surface |
|---|---|
| **Browser** | The Svelte app shell, ADR-18, served from the same Worker |
| **Lightroom Classic plug-in** | Lua, talks only to `/api/v001/*` |

**Neither is a secondary client, and neither MAY be allowed to rot.** The plug-in is not a
convenience wrapper around the "real" web product, and the web app is not a fallback for people
without Lightroom. **They are two front doors to one queue.**

**They MUST be released in lockstep.** An API change that serves the browser and breaks the plug-in
is a broken release, not a plug-in problem to fix later. In practice that means:

- **A breaking API change MUST land with both clients updated**, or it does not land.
- **A new capability SHOULD reach both**, and where it cannot, the asymmetry gets written down here
  rather than discovered.
- **The plug-in version and the API's `/api/v001` contract move together.** ADR-16's zero-padded
  path version is what buys room to break the contract deliberately if it ever comes to that.

**Why this is worth stating rather than assuming.** Terry's framing: *"very relevant for
Terry-of-2031 who forgot 'oh shit right that LrC plug-in is fuggin amazing'."* **The failure mode is
not malice, it is absence.** A future session works on the web app because that is what is open in
the editor, ships an API change that suits it, and nobody notices the Lua client for eight months —
by which time the plug-in is broken, undiagnosed, and looks abandoned rather than neglected.

**And per [[fga-goal-is-terrys-lightroom-workflow]] the plug-in is arguably the MORE important of
the two**, because the stated goal is queueing adds without leaving Lightroom. The web UI was built
first; that is an accident of order, not a ranking.

### The architecture diagram SHOWS the client, as of 2026-08-15

**Terry overruled a deferral, deliberately, and the record matters more than the outcome.**

**The argument against drawing it was the read-replica lesson.** D1 was once drawn as primary plus
replica so a consistency failure had somewhere to live; when read replication left the architecture,
the tile went with it, and the recorded conclusion was that **depicting something the system does
not have is worse than silence** — a reader in five years designs around it. By that argument a
first-class LrC client on the canvas tells Terry-of-2031 it shipped, and if it never does, the
diagram lies.

**Terry's counter, and it is a fair one: the diagram is his artifact and its job is to remind him
what this project IS.** He is not at risk of forgetting whether the plug-in exists; he is at risk of
forgetting that it was ever the point. **So the tile is a deliberate choice rather than an
oversight, and that is written here so nobody "corrects" it later.**

**If the plug-in is ever abandoned, the tile comes out** — same rule that removed the replica.

**What was drawn:**

- The `users` actor became **`Browser client`**, keeping its geometry exactly — `e12` and `e13`
  attach to it and are asserted dead level, so moving it would have broken two assertions for a
  relabel.
- **Lightroom Classic is an OUTER card containing an inner `FGA plug-in` tile**, mirroring how the
  Flickr card contains the Flickr API tile. Terry's reasoning: *"want to show all we're changing is
  a plug-in within LrC."* The card is `lrcapp`, the plug-in is `lrc`.
- **A `Catalog` tile sits inside the same card**, holding "Published photo IDs". **The SDK is
  deliberately NOT drawn** — Terry raised it and called it possibly "below the radar horizon of this
  diagram", which is right. **The catalog is a store, the SDK is a library**, and this diagram's own
  rule is to say what a thing holds rather than what it does. Same reason the canvas shows D1 and
  not a D1 client.
- Both clients connect to the API Worker. **Only the browser connects to the app shell and to
  DNS**, since the plug-in fetches no HTML.
- **Auth is drawn as THREE HOPS, decided 2026-08-15.** Terry challenged an earlier line reading "the
  plug-in gets no edge to Flickr", correctly — that left the canvas silent on how a plug-in ever
  gets a credential. **The resolution is that Flickr appears in the plug-in's journey, but the
  arrow starts at the browser, not at the plug-in:**

  | Edge | Meaning |
  |---|---|
  | Plug-in → API Worker | Its only NETWORK edge |
  | **Plug-in → Browser client** | `LrHttp.openUrlInBrowser`. **A launch, not a request** — label it so |
  | Browser client → Flickr | Already on the canvas as `e11` |

  **The one-hop shortcut — a dashed plug-in-to-Flickr edge — was considered and refused.** It reads
  cleaner and asserts the exact thing the design is built to avoid: that Lua holds Flickr
  credentials. **A future session reading that diagram might implement it.** Adobe's plug-in really
  does call `flickr.auth.getFrob` over HTTP, because Adobe has no server; FGA has one, so the frob
  equivalent is `POST /api/v001/device/start` and the plug-in never speaks to Flickr at all.
- The User Journey key gains the device-link steps, and **`scripts/build-diagram.py` requires the
  journey row count to equal the badge count**, so both move together.

**Expect the build to fight the change, correctly.** A new tile becomes an obstacle for every
straight edge, `e12` and `e13` currently attach to `users` and are asserted dead level, and the
badge-to-edge map and badge overlap checks all key off those positions.

### The plug-in talks ONLY to FGA. It makes no Flickr calls, ever.

**It has no Flickr credentials and MUST NOT acquire any.** FGA already holds the user's Flickr token,
AES-GCM encrypted in D1 under ADR-09, and that is the credential that does the work.

**The decisive reason is ADR-06's sweep**, not tidiness. The cron runs at 00:15 UTC with Lightroom
closed, so a token living in a Lightroom catalog is invisible to the thing that needs it. Adobe's
plug-in talks to Flickr directly because it has no server; ours has one.

**The photo id costs nothing.** `getRemoteId()` is a local catalog read — no network, no
credentials, already measured.

### Authentication: the frob pattern, aimed at FGA instead of Flickr

**Adobe's own Flickr plug-in already ships this shape**, and reading its source settled the
question. `FlickrAPI.openAuthUrl()` requests a frob, opens a browser at Flickr's auth URL carrying
it, and exchanges the frob for a durable `auth_token` afterwards.

**That IS a device-code flow.** So the design is Adobe's, with FGA one hop over:

| Adobe → Flickr | FGA plug-in → FGA |
|---|---|
| `flickr.auth.getFrob` | `POST /api/v001/device/start` → code |
| `LrHttp.openUrlInBrowser( auth?frob=… )` | `LrHttp.openUrlInBrowser( /link?code=… )` |
| user approves at flickr.com | user approves at flickrgroupaddr.com, signing in with Flickr if needed |
| exchange frob → `auth_token` | poll → FGA plug-in token |

**The existing Flickr OAuth does the identity leg unchanged** — ADR-08's Durable Object, ADR-07's
"the Flickr account is the identity". The plug-in never sees a Flickr credential.

**Storage is a preference, not a requirement.** `LrPasswords` is encrypted and costs two lines;
`LrPrefs` is what Adobe uses and would be defensible, since the stored value is an FGA token scoped
to one product and revocable server-side. **An earlier draft of this file claimed `LrPasswords` was
necessary on security grounds. It is not, and that claim was made before reading Adobe's source.**

**This still becomes an ADR** — it is a new credential class with its own revocation story, and
ADR-10's cookie assumptions do not cover it.

#### The contracts, proposed 2026-08-15. NOT built, and NOT decided.

**Three endpoints. None exists yet.**

| | |
|---|---|
| `POST /api/v001/device/start` | No auth. Returns `{ code, userCode, expiresAt, pollAfter }` |
| `GET /link?code=…` | The browser page. **Session cookie required**, so ADR-10 does the identity work |
| `POST /api/v001/device/poll` | Body `{ code }`. Returns `pending`, `denied`, `expired`, or `{ token }` |

**Two codes, not one, and the split is the whole security design.**

- **`code` is the polling handle** — 32 bytes from `crypto.getRandomValues`, base64url. The plug-in
  holds it and never shows it.
- **`userCode` is what a human reads** — short, unambiguous, and **displayed in Lightroom**. It is
  the thing the person compares against the browser page.

**State lives in a Durable Object, one per flow**, exactly like ADR-08's OAuth Request Token. Same
argument: a short-lived single-writer object with an alarm that deletes itself beats a D1 row that
needs sweeping, and the polling is naturally serialized by the single writer.

#### The phishing weakness is REAL, and FGA's version of it is worse than most

**Every device flow has this hole.** An attacker starts a flow on their own machine, sends the
victim `flickrgroupaddr.com/link?code=…`, and the victim — already signed in — approves it. The
attacker's plug-in then polls and collects a token for the victim's account.

**PKCE does NOT close it.** The attacker started the flow, so the attacker holds the verifier. PKCE
protects against an intercepted code, which is a different attack.

**And the usual "the blast radius is small" consolation does not apply here.** ADR-01 says a request
that reached a moderator is terminal. So a phished token can push a stranger's photos into volunteer
review queues, and **that effect cannot be taken back** — not by revoking the token, not by deleting
the requests. **The irreversibility is the reason this needs more care than a typical device flow,
not less.**

**Three mitigations, and the first is the one that matters:**

1. **The `/link` page MUST display the `userCode` and require the person to confirm it matches what
   Lightroom is showing.** A victim who never started a flow has no code on screen to match, which
   is the moment the attack becomes visible. Prefilling from the query string is fine for
   convenience; **auto-approving from it is not.**
2. **The page MUST say plainly what it grants** — that a Lightroom plug-in will be able to queue
   group adds as them — rather than "authorize this device".
3. **Short TTL and a rate limit.** Ten minutes, and `pollAfter` tells the plug-in how long to wait.
   A plug-in that ignores it should be throttled server-side rather than trusted.

#### Three things a future session MUST settle before writing code

- **What the token authorizes.** It is not a session. It SHOULD reach the queueing and preflight
  endpoints and nothing else — no account settings, no revocation of other tokens, no Flickr
  credential access.
- **Revocation, and where the user sees it.** A credential a user cannot list is a credential they
  cannot revoke. There is no UI for this today.
- **Whether the token expires.** Adobe's `auth_token` does not. A non-expiring credential on a
  laptop is a real exposure, and [[threat-model-the-thief-not-the-owner]] applies: the question is
  not what Terry knows, it is who else ends up holding the catalog.

**Terry decides all three.** Nothing here is built.

### Spike 0.6, `ConnectivityProbe.lua`: can the plug-in reach FGA at all?

**Every design in this file rests on `LrHttp` reaching flickrgroupaddr.com over TLS and handing back
a readable status code, and that is written down from the SDK reference rather than watched.** It is
the same shape as the publish-service premise, which came back confirmed **only because somebody ran
it**.

**The Worker is live.** `GET https://flickrgroupaddr.com/health` answered `200 {"status":"ok"}` from
this machine on 2026-08-15, so the probe has something real to talk to.

It calls two endpoints and sends no credentials:

| Call | Expected |
|---|---|
| `GET /health` | 200, public. If this fails nothing else in the report means anything |
| `GET /api/v001/me` | **Expected to FAIL** — the plug-in holds no session |

**The failing call is the more valuable one.** A client that works on the happy path and produces an
unreadable mess on the sad path is not usable, and the sad path is where a real user lives — expired
session, no network, a hotel captive portal. A well-behaved API answers 401 with JSON rather than an
HTML login page, and this reports which one Lightroom actually receives.

**Two `LrHttp` details the probe handles and a naive client would not:**

- **A transport failure returns a nil body and puts the reason in `headersTable.error`**, so "no
  status" covers both a refused connection and a served 500 unless both are handled.
- **There is no documented default timeout.** A hung request inside a modal is indistinguishable
  from a frozen Lightroom, so the probe passes 15 seconds explicitly.

It writes its report to `fga-connectivity.txt` on the desktop as well as showing it, because a modal
cannot be copy-pasted and this output is evidence that belongs in this file.

### The picker's data path, audited 2026-08-15: one gap and one arithmetic problem

**`GET /api/v001/groups` already serves the left list.** It returns exactly what a picker needs —
`id`, `name`, `photos`, `members`, `poolModerated`, `inviteOnly` — after deliberately dropping the
979 KB of descriptions and rules the raw Flickr reply carries. **No new endpoint is needed for the
group list**, which was not obvious until it was checked.

**But nothing serves the RIGHT list.** The two-list picker opens pre-populated with the groups the
photo is already in, and there is no endpoint that answers "which groups is this photo in".

**The obvious workaround does not fit, and the arithmetic is the reason.** `POST
/photos/:photoId/preflight` caps `groupIds` at **200**. Terry belongs to **372** groups. So
pre-population by preflight is **two round trips** — and the cap buys nothing upstream, because
preflight makes **one** `getAllContexts` call no matter how many groups it is asked about.
`getAllContexts` is per-photo, not per-group.

**BUILT 2026-08-15: `GET /api/v001/photos/:photoId/groups`.** One `getAllContexts` call, returning
the pools the photo is in as `{ id, title }`. Terry approved it and named the reason better than
this note originally did: *"we made SURE we don't keep the user's long term flickr creds in the
plugin, which would have let us query flickr API directly. I'm good proxying that through our API as
a middleman."* **The proxy is a consequence of the credential design, not overhead.**

**The title comes free.** Flickr sends each pool's title in the same reply, so naming a group costs
no second call. `getPhotoPoolsDetailed` keeps it; `getPhotoPools` is now a thin wrapper returning
ids only, because four callers depend on that shape and ADR-05's authoritative check is one of them.

**`MAX_PHOTO_POOLS` is 500**, and it is a sanity ceiling rather than a model of Flickr's rule —
Flickr's per-photo limits vary by account type and are not reliably documented. ADR-17 requires a
stated bound, not a correct guess at somebody else's.

**Null stays UNKNOWN.** A failed `getAllContexts` answers 502, never an empty list. Reporting empty
would tell the picker the photo is in no groups, and the user would queue adds for groups it is
already in — straight into ADR-01, because a duplicate add can reach a moderator.

- It is the question the picker actually asks on open. Preflight answers a different one — *what
  would happen if I submitted these* — and that is the right call at commit time, not at open time.
- The reply is naturally small. A photo is in a handful of groups, not hundreds, so **ADR-17 is
  satisfied by the upstream shape rather than by a cap** — but the ceiling MUST still be stated
  rather than assumed, per ADR-17's second kind of list.
- It leaves preflight alone. Raising its 200 cap to `MAX_USER_GROUPS` (5000) would work and is
  worse: it grows the response for every caller to serve one caller's opening screen.

**Not built, and it needs Terry.** It is a new endpoint, so it is a new row in the traceability
matrix and wants a test naming the ADR it serves.

### Feedback is preflight. Commitment is one batch submit.

**Clicking a group fires a debounced `POST /api/v001/photos/:photoId/preflight`** and marks the chip
`seen by a moderator` / `already in` / `already queued`. **It commits nothing**, costs one Flickr
call regardless of group count, and is ADR-20 doing exactly the job it was built for.

**An explicit button then submits the whole selection in one call.**

**That button is a COMMITMENT BOUNDARY under ADR-01, not latency overhead.** It is the moment the
person says *yes, I mean it*, and it is the only checkpoint between a stray click and a volunteer's
review queue.

### The batch submit endpoint — BUILT 2026-08-15

**`POST /api/v001/requests/batch` exists.** Body is `{ photoId, groupIds[],
acknowledgedModeration?[] }`, capped at 200 groups like ADR-20's preflight. It answers `202` with a
per-group array in the order asked, using the same four statuses preflight returns.

**`acknowledgedModeration` is a LIST, not a flag.** A blanket boolean would let one click
acknowledge warnings the user never saw, which is exactly what ADR-20 exists to prevent.

**It does NOT attempt at batch scale**, and the immediate path is narrower than first built: the
caller must have **asked for exactly one group**, not merely ended up with one eligible after
filtering. Keying off the eligible count meant a forty-group batch with thirty-nine already queued
would attempt — so identical requests behaved differently depending on state the caller cannot see.
**Predictable beats marginally faster**, and one eligible group is one Flickr call either way.

**NO CLIENT CALLS IT YET, and that is worth saying out loud.** `web/src/lib/submission.ts` still
loops one `POST /api/v001/requests` per group — see its `for (const groupId of groupIds)`. So the
endpoint that exists to turn forty round trips into one is, today, dead code with tests.

**That is a deliberate order rather than an oversight.** The endpoint had to exist before either
client could adopt it, and the Lightroom plug-in is the client the batch shape was designed for.

**IT IS NOT A DROP-IN TRANSPORT SWAP, checked 2026-08-15.** An earlier line here called the change
small. It is not, and the reason is worth stating before somebody starts it at the end of an
evening.

| Endpoint | Statuses a caller must render |
|---|---|
| `POST /requests` | `queued`, `resolved`, `needs_acknowledgement` |
| `POST /requests/batch` | those three **plus `already_in_pool` and `already_queued`** |

`web/src/lib/submission.ts` models exactly the first three in its `ItemState` union, and `toState`
switches over them exhaustively. The two extra statuses need **new UI states and new sentences**,
and those sentences live in `web/src/lib/outcomes.ts` — which `CLAUDE.md` names as *"ADR-01's
promise, as the sentences a user reads"*.

**So the work is user-facing ADR-01 copy, not plumbing.** It also has to keep ADR-20's per-group
acknowledgement intact, because the browser is where a person actually reads the moderation warning.
**Twelve seconds of latency is not worth rushing that**, and the single-POST path is correct today —
merely slow.

**The section below is the design it was built from, kept because the reasoning still governs
changes to it.**

### The design, as argued before it was built

**`POST /api/v001/requests` takes one `photoId` and one `groupId`.** Forty groups is forty POSTs —
`web/src/lib/submission.ts` measures that at roughly twelve seconds. A one-round-trip client needs a
batch endpoint, and it needs one guard rail.

**It MUST NOT inherit ADR-03's immediate-attempt behavior at batch scale.** That path attempts
straight away when a request is alone in its queue, which is right for one photo into one group.
Applied to forty, a single Worker invocation makes forty sequential `groups.pools.add` calls on one
user's token — `submission.ts` calls that "the same discourtesy wearing a performance costume".
**Enqueue, return, and let the nightly sweep do the work.** The one exception worth keeping: a batch
of exactly one group whose queue is empty may take the existing immediate path.

**Atomic in D1, NOT atomic in outcome.** `db.batch()` should put the inserts in one transaction. The
result is still per-group: queue the clean ones, refuse and report anything needing acknowledgement,
same four statuses ADR-20's preflight already returns. **Rejecting all forty because three carry a
warning would hold thirty-seven good ones hostage**, and the partial result is the safe direction
anyway — nothing reaches a moderator unanswered.

**`resolveRequest`'s existing pairing MUST survive any batch path** — the request update and the
`moderated_pairs` insert go in one `db.batch()` so a request cannot be marked resolved without the
record that a person saw it.

### The carve-out that breaks "everything is deferred"

**ADR-03 lets the API attempt immediately when a request is the sole unresolved one in its queue.**
Three lines in `src/routes/api.ts`.

**That single permission is why no client may treat submission as deferred**, and it is not obvious
from the outside — the product looks like a queue that drains at midnight. **Any design reasoning
"nothing happens until the sweep, so this is reversible" is wrong because of those three lines.**

### Group selection: DECIDED 2026-08-15. The full list, with a filter box. No group sets.

**Terry belongs to 372 groups** — see `docs/FLICKR.md`, and the count moved from 330 to 372 in one
day, so it **MUST NOT** be cached.

**Saved group sets were proposed and REJECTED**, in his words:

> The pass to assign all groups to sets would annoy me far more than a UX of picking which of the
> 372 groups to add a pic to. And each time I joined a new group, I'd resent having to tag it.

**The rejection is about the ONGOING tax, not the one-time setup**, and that is the part a future
session will miss. A taxonomy is not paid for once — every new group joined is a fresh decision
about where it belongs, forever, for a person who joined 42 groups in a single day.

**And the wall is a familiar model, not a novel one.** *"The massive wall of groups to pick from is
exactly how the Flickr web UI works, except it's slow as fuck."* **So the bar is the same UX and
faster, which is reachable — rather than a better UX, which is speculative.**

### What the picker must do

| Requirement | |
|---|---|
| Scroll the full list | `simple_list` scrolls natively |
| Filter box | `edit_field` bound to a filter string |
| Match rule | **Case-insensitive plain substring against the group NAME.** Typing `canada` shows only groups with `canada` anywhere in the title |
| Multi-select | `simple_list` with `allows_multiple_selection`, `value` returns an array |

**`string.find` MUST be called with `plain = true`.** Lua's default is PATTERN matching, so a group
name or a search term containing `-`, `(`, `)`, `%` or `.` would either match wrongly or throw.
Group names contain all of those. `name:lower():find(needle:lower(), 1, true)`.

**Lowercase the names ONCE, not per keystroke.** 372 `:lower()` calls on every character typed is
waste that a precomputed shadow list removes.

### Filtering is REALTIME, and `immediate = true` is what makes it so

**Terry's requirement, 2026-08-15: *"filtering should be realtime, so each keypress causes a new
substring search to fire and limit/expand the list."*** No debounce, no Enter to apply.

**The `edit_field` property that delivers it is `immediate`**, documented as *"True to validate the
value as the user is typing."* **Without it the binding updates only on commit** — Enter or moving
focus away — so a user would type `canada`, watch nothing happen, and conclude the box is broken.
**It fails as a no-op rather than an error, which is why it is written down here.**

`placeholder_string` is also available for the hint text, though on Windows the placeholder clears
when the field takes focus rather than when text is entered.

**The search cost is nothing; the rebind is the thing to watch.** 372 precomputed-lowercase plain
`find` calls per keystroke is microseconds of Lua. Rebuilding the `items` table and pushing it
through the binding on every character is the part that could feel sluggish, and it is the part to
measure.

**Do NOT confuse this with the preflight debounce. They are different controls on different
events.**

| | Fires on | Cost | Debounce |
|---|---|---|---|
| Filter | Every keystroke in the search box | Local, microseconds | **None. Realtime** |
| Preflight | A change to the SELECTED set | A network round trip | **Yes** |

**Typing in the filter box MUST NOT trigger preflight** — filtering changes what is visible, never
what is chosen.

### The selection model, and why the widget MUST NOT own it

**Filtering rebinds `items`, and the plug-in MUST keep its own selected set rather than trusting
`value` to survive that.** When the filter narrows, groups selected but no longer visible must stay
selected; when it widens, they must come back.

**So `value` is an input, never the source of truth**, and the update is a merge rather than a
replace:

```
selected = (selected MINUS currentlyVisible) UNION value
```

**Whether rebinding `items` actually clears `value` is UNMEASURED** — see below. The merge model is
correct either way, which is why it is the design regardless of the answer.

### `simple_list` has no per-row widgets, so state goes in the TITLE

**Items are `{ title, value }` and nothing else.** No badges, no icons, no columns. So "this pool is
moderated" and ADR-20's "already seen by a moderator" have to be rendered into the title text:

```
Canada Landscapes — moderated, already seen
```

**Which means `items` rebinds when preflight returns, not only when the filter changes** — a second
reason the selection model must survive a rebind.

### MEASURED 2026-08-15. Both questions answered, both favorably

**Terry ran `PickerProbe.lua` against a synthetic 372-group list in Lightroom Classic 15.5.** The
probe generates its own groups, makes no network call and touches no catalog, so this measures the
widget rather than the workflow.

| Question | Answer |
|---|---|
| Does rebinding `simple_list.items` clear the selection? | **The WIDGET's, yes. The plug-in's, no** |
| How does a 372-item list look and perform? | Renders cleanly, scrollbar behaves, filtering felt instant |
| Does `height` accept a large value? | **Yes, 420 works.** The reference only ever promised a minimum of 80 |
| `allows_multiple_selection` | Works, and gives OS-NATIVE semantics — **shift-click spans and ctrl-click discontiguous both work** |

**The merge model is confirmed end to end, and it earned its place exactly as designed.** With four
groups selected, typing `canada` narrowed the list to 16 and every highlight vanished — because none
of the four matched. **The counter still read `selected 4`.** Clearing the filter brought all four
back highlighted.

**So the widget DOES drop `value` on rebind, and it does not matter**, because
`selected = (selected MINUS visible) UNION value` never trusted it. **The design was written to be
correct either way, and that is why the answer changed nothing.**

**Shift-click is a bigger finding than it looks.** Forty groups selected one click at a time is the
2021 UI's problem restated. A span select turns that into two clicks, and it came free from the
platform widget rather than needing anything built.

### The UX gap the probe exposed, which is a DESIGN question rather than a defect

**While `canada` was typed, four groups were selected and INVISIBLE.** The counter said so; the list
offered no way to review or deselect them without clearing the filter first.

**On a 372-group wall, with a habit of typing to narrow, that is how somebody submits a group they
forgot they picked** — and under ADR-01 a submission that reaches a moderator cannot be pulled back.

**A "show selected only" toggle answers it**, and costs almost nothing: it is a different `items`
filter over the same list, and the merge model already keeps the truth outside the widget.
**Undecided; recorded so the next session does not rediscover it.**

### Both open questions: MEASURED 2026-08-15, by Terry driving the spike

**Rebinding `simple_list.items` DOES clear the widget's `value`, and the merge model absorbs it.**
Terry filtered to `canada`, watched the highlighting disappear, cleared the filter, and the four
selections came back — *"If I clear the filter box, they come back."* **So the model was right and
the screen was wrong**, which is precisely why the two-list redesign above replaced it. A correct
model the user cannot see is not a working picker.

**A 372-item `simple_list` renders and scrolls fine at `height=420`.** No lag, no truncation. The
reference states a minimum of 80 and names no maximum, and 420 is comfortably inside whatever the
real ceiling is.

**Shift-click span select and ctrl-click multi-select both work natively**, confirmed by screenshot
at 14 rows and at a scattered selection. **They are being dropped anyway** — see the two-list
section below, where Terry chose single-row moves deliberately after seeing both work.

### The picker is TWO LISTS, decided by Terry 2026-08-15 after driving the spike

**Terry replaced the single filtered list with a side-by-side transfer picker**, in his words:
*"Left side is alphabetical (case insensitive) sorting of groups with the filtering applied titled
'Unselected groups'. Right side is 'selected groups'. As we click rows on either side, the group
moves to the other side."*

| | Left | Right |
|---|---|---|
| Title | `Unselected groups` | `Selected groups` |
| Holds | Every group the photo is NOT in and has not been picked for | Every group the photo WILL be in |
| Sort | Case-insensitive ascending | Case-insensitive ascending |
| The filter box | **Applies** | **MUST NOT apply** |
| A click | Moves the row right | Moves the row left |

**The filter MUST NOT touch the right list, and that is the whole point of the redesign.** Terry
drove the single-list spike, typed `canada`, and watched four selections vanish from view — the
model held them correctly and the screen said otherwise. **A list that shows what you have chosen
cannot be allowed to hide what you have chosen.**

**Single-row moves only. Range select and multi-select are GONE, and Terry chose that**, having
tested both working: *"I'm glad to lose range select and multi-select. Single row hopping at a time
is more intuitive."* **A later session MUST NOT reintroduce shift-click as an improvement.** It also
removes an unmeasured risk — whether `simple_list` fires its observer once per commit or once per
intermediate change during a shift-drag, which would have decided whether span-move worked at all.

**Three counts, and each names what it counts:**

| List | Shows |
|---|---|
| Left | `Groups displayed: N` and `Groups hidden by filter: N` |
| Right | `Number of groups currently selected: N` |

#### Built as spike 0.5, `TransferPicker.lua`, 2026-08-15

**`PickerProbe.lua` (0.4) stays registered on purpose.** It is the control. Comparing the two side
by side is how the redesign gets judged, and deleting the thing you measure against is how a spike
stops being evidence.

**The dialog is a STAGING AREA, and that is the answer to the removal risk below.** Nothing reaches
Flickr until the user clicks Save. So a click is free, a mis-click costs one more click, and the
dangerous action needs a deliberate commit. **This is better than a per-row confirm**, which would
put a modal in front of the one interaction the whole design exists to make fast.

**Three implementation facts a later session will need:**

- **A move rebinds both lists, which clears `value`, which fires the observer again.** Without a
  guard that second firing reads as a click on nothing. `TransferPicker.lua` carries a `moving` flag
  around every rebuild, and it MUST wrap every one.
- **`\u{25CF}` is a Lua 5.3 escape and Lightroom runs 5.1**, where it is a SYNTAX ERROR rather than
  a bad glyph — the whole file fails to load. The marker is written as raw UTF-8 bytes,
  `"\226\151\143 "`.
- **`simple_list.value` may be a TABLE or a bare id, and the reference does not settle which.** With
  `allows_multiple_selection = true` it is clearly an array; with it false, the widget may hand back
  the selected value itself. **Indexing a string with `[1]` returns nil**, so a naive reader would
  run `selected[nil] = true` and die on the FIRST click. `TransferPicker.lua` reads both shapes.
  **Which one Lightroom actually sends is still unmeasured** — the code no longer cares, which is
  the point, but the answer is worth writing down when the spike runs.
- **This machine has no `luac`**, so `scripts/lua-balance.py` stands in. It is a block-balance check
  and **NOT a parser**; it catches an unclosed or over-closed block, which is the error that has
  actually bitten. It was validated in both directions — against the three files Lightroom already
  loads, and against deliberately broken fixtures.

**Five things only Terry can answer, by using it:**

1. Does `simple_list` with `allows_multiple_selection = false` fire its observer on **every** click,
   including re-clicking a row that just came back from the other side?
2. Does the `moving` guard hold, or does one click produce a double move?
3. Does a move feel instant at 372 groups? Each one re-sorts and rebinds both lists.
4. Are the `\u{25CF}` and `+` markers readable, or does the distinction need another treatment?
5. Do two 330-wide lists plus the stat lines fit his screen?

#### The right list is MEMBERSHIP, not a shopping basket

**Terry, same session:** *"I may use the plugin to add/remove groups from pics that already have
been added to some groups. In that case the groups the pic is ALREADY in should be pre-populated on
the list to the right."*

**So the right list opens pre-populated from Flickr**, via `flickr.photos.getAllContexts` — a call
FGA already makes, so this needs no new endpoint. Two kinds of row live there and **they MUST be
told apart**:

| Row | Means | Clicking it |
|---|---|---|
| Already at Flickr | The photo is in this group now | **Removes it at Flickr** — a real `flickr.groups.pools.remove` |
| Added this session | Queued, nothing sent yet | Un-picks it, costs nothing |

**`simple_list` gives no per-row styling** — it takes plain strings, so color and badges are not
available. **The marker MUST therefore live inside the string** (`●` for already-in, `+` for newly
added, or equivalent). Hand-building rows from `LrView` primitives would allow real color and costs
the built-in scrolling; that trade has not been made.

**Removing an already-in group is the dangerous click on this dialog, and it is ADR-01 adjacent.**
If the photo sits in a moderated group because a volunteer approved it out of a queue, a removal
throws that approval away — and re-adding puts the photo back in front of a human. **A stray click
MUST NOT be able to do that.** Removals of already-in rows SHOULD be staged and applied on commit,
or gated behind a confirm. **This is not settled and needs Terry.**

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
| **Per-click submission with a Cloudflare Queue, and rescind by clicking again** | **Refused 2026-08-15, and this one is worth reading before re-proposing it.** Under ADR-01 an add that reaches a moderator resolves at that instant and can NEVER be pulled back — Flickr offers no call to remove a photo from a moderation queue, which is why `withdrawRequest` conditions on `state = 'pending'`. A rescind can lose that race, and the user would be told "cancelled" while a volunteer is looking at their photo. It also strands ADR-04, ADR-05, ADR-20 and `idx_requests_one_pending_per_pair`, all of which need a read BEFORE the user is told anything |
| A Cloudflare Queue in front of the D1 insert, for latency | **The `requests` table already IS the queue** — `state='pending'`, ordered by `id`, drained by ADR-06's cron. A second queue only makes the INSERT async, and that insert carries every safety constraint. `env.QUEUE.send()` is a network call too, so it trades a write for a write. **ADR-06's promotion bar applies: measure a real limit first.** None of its three conditions holds |
| A pasted long-lived token, or `LrSocket` on a localhost callback | Both workable, both beaten by the frob pattern above. A paste means generating and copying a secret by hand; a socket means a listener, a firewall prompt and a second redirect target |

**Neither cloud API can see a Classic catalog on local disk**, which is where every record this
design needs actually lives. The plug-in path is not merely easier; it is the only one that reaches
the IDs.

## Sources

The SDK archive is authoritative and is the only source that should be quoted for API shapes.
Everything else here was measured on this machine on 2026-08-14, except where marked.

**Unverified, and worth one look:** a search summary claimed the 15.x line included SDK fixes to
photo-collection methods, which is exactly the area this design leans on. That came from a search
result rather than from Adobe. Read the real release notes before trusting or dismissing it.
