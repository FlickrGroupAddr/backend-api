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

### Feedback is preflight. Commitment is one batch submit.

**Clicking a group fires a debounced `POST /api/v001/photos/:photoId/preflight`** and marks the chip
`seen by a moderator` / `already in` / `already queued`. **It commits nothing**, costs one Flickr
call regardless of group count, and is ADR-20 doing exactly the job it was built for.

**An explicit button then submits the whole selection in one call.**

**That button is a COMMITMENT BOUNDARY under ADR-01, not latency overhead.** It is the moment the
person says *yes, I mean it*, and it is the only checkpoint between a stray click and a volunteer's
review queue.

### The batch submit endpoint FGA does not yet have

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

### The one thing still unmeasured

**Does rebinding `simple_list.items` clear or corrupt the current selection?** Everything above is
implementable either way because of the merge model, but the *feel* differs — a widget that visibly
drops highlighting on every keystroke is unpleasant even when the model underneath is correct.

**Also unmeasured: how a 372-item `simple_list` performs and looks**, and whether `height` accepts a
large value. The reference states a minimum of 80 and names no maximum.

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
