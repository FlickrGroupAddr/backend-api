# The Lightroom Classic plug-in

**RFC 2119 keywords. MUST and MUST NOT are absolute. SHOULD is a strong default a good argument may
overrule. MAY is optional.**

**This is where the plug-in investigation got to. It is not an ADR and it creates no obligation.**
The decisions that DID get made are ADR-23 and ADR-24 in `docs/architecture/DECISIONS.md`; where this
file and an ADR disagree, **the ADR wins.**

---

## PICK UP HERE

**The backend was FINISHED on 2026-08-18. The Lua client was WRITTEN on 2026-08-19 and
NOBODY HAS RUN IT.**

| | |
|---|---|
| **The Lua client** | **Written, plug-in 0.17.** `DeviceLink.lua` holds the flow, `DeviceLinkProbe.lua` holds the dialogs |
| **What is proven** | It parses under the real `luac` 5.1, `selene` is clean, and every SDK member it calls is documented in the pinned archive |
| **What is NOT proven** | **Every single runtime claim.** No `LrHttp.post` has been watched, no browser has opened, no token has reached the keychain |

**That distinction is the whole point of this section.** A gate-clean plug-in and a working
plug-in are different claims, and this project has already paid for confusing them — the
publish-service premise only became a fact when somebody ran it.

**The menu item is `FGA: link this Lightroom to FGA`, in both menus.**

**`Info.lua` changed, so REMOVE AND ADD.** Lightroom re-reads `Info.lua` only on Add; disable
and re-enable leaves the new menu item missing and everything else looking fine.

### The JSON library, and where it came from

**`json.lua` is rxi's, MIT, vendored beside the plug-in rather than in `vendor/`.**

| | |
|---|---|
| Source | `github.com/rxi/json.lua`, commit `11077824d7cfcd28a4b2f152518036b295e7e4ce` |
| Size | 9,638 bytes |
| SHA2-256 | `0EACCDA57FABC0330736DE25F45CF589821A42B5E0FE02E4E3125F7DC0BF2B7E` |
| License | MIT, copied verbatim to `json.LICENSE.txt` beside it |

**It is committed, and the Adobe SDK is not, and the difference is the license.** MIT permits
redistribution with the notice attached. Adobe's archive does not, which is why `.gitignore`
line 275 excludes `vendor/*` and MUST keep doing so.

**It lives in the plug-in folder because Lightroom loads plug-in files from there.** A copy in
`vendor/` would have to be copied in at build time, which is the same fact stored twice.

**`selene` excludes it and `luac` still parse-checks it.** Patching a vendored file turns every
future update into a merge, so the two warnings it produces are excluded rather than fixed —
`selene.toml` carries the reasoning.

**Why a library rather than a hand-rolled decoder.** Terry, 2026-08-19: *"the API surface is
simple enough we should be able to hand roll JSON. If there is an open source Lua library for
JSON, that is in line with integrate-before-innovate standing order."* The survey on board card
#14 found one, so the standing order settles it.

**AN EARLIER SESSION GOT THIS WRONG AND IT IS WORTH REMEMBERING.** Card #14 recorded a decision
of *"XML on the wire for the plug-in"*, and a session acted on it by adding `Accept:
application/xml` negotiation to the Worker. **Terry's actual position was that XML is for
ON-DISK state.** His approval of `LrXml` as a TOOL had been read as a choice of where to point
it. The Worker change was reverted the same turn.

**The approval page shipped**, in the Worker rather than in Svelte. An earlier version of this table
said *"Svelte. ADR-18 gives `/` to the app shell"* and pointed at `/link` — **a page that was never
built.** `parse()` in `web/src/lib/router.ts` resolves exactly `/`, `/queue` and `/admin`, so the
plug-in's `verificationUri` sent people to a "no such page" screen and device linking could not
complete. Nothing failed and every test passed.

**Terry ruled it belongs to the Worker, and the reason is structural:** the session cookie is
`HttpOnly`, so a static SPA page cannot tell whether you are signed in. Only the server can, and the
page's first job is to redirect a signed-out visitor to `/auth/flickr/login`.

**Every route the plug-in needs now exists and is named as the diagram draws it:**

```
POST /auth/device-link/start              no credential, returns deviceCode + userCode
POST /auth/device-link/poll               deviceCode is the credential
GET  /auth/device-link/enter-user-code    the page a person visits
POST /auth/device-link/{approve,deny}     browser session only
GET  /api/v001/me                         reports clientType, so the plug-in can confirm
```

**`verificationUri` in the `start` reply is the URL to open.** Do not build it in Lua — it comes
from the server precisely so a plug-in cannot be pointed somewhere else.

**The confirmation step is not cosmetic.** Showing the `userCode` and making the person say it
matches their Lightroom screen **is the only defense against device-flow phishing.** The backend
deliberately cannot substitute: nothing auto-approves, and approval is always a POST a person had to
cause.

### The picker is blocked on one SDK question

**Does `checkbox.title` accept `LrView.bind`?** If it does not, the slot-based rendering design below
is impossible and the picker needs rethinking. **Check before building.**

**What works today**, measured on your machine: batch add across non-adjacent rows, unchecking,
pruning (364 candidates from 372, the 8 already-in groups removed), **744 views built in 9–12 ms**,
and `LrHttp` reaching the live Worker.

**What is broken:** `visible = false` hides a view but **keeps its space** — see the SDK section
below. The filtered pane fills with white gaps and the design is unusable rather than merely ugly.

**The fix, designed and not built: a fixed window of about 25 rows plus paging.** Bind each row's
`title` to a property rather than fixing it at build time, fill the slots from the filtered list, and
page instead of scrolling. **Everything except rendering survives** — the selection model, batch add,
pruning, staging, the report, and the add-only scoping.

---

## Why this exists

**Your words, and this is the north star for the whole project:**

> Goal of this project is to make my life easier as someone who posts photos to Flickr and uses
> groups to help people discover my art.
>
> I do all my culling, editing, and posting to Flickr (using a built in plugin from Adobe) to publish
> my photos. If after I publish I could open up a dialog in LR and add the new photo to my FGA queues
> per pool/group, that it speeds up my workflow. No need to pop out of LR and use my browser to log
> into FGA and queue up group adds.

**So the web UI is one client, not the product.** ADR-18's Svelte app was built before this goal was
written down. **Judge work against the workflow, not against the codebase.**

### Two clients, both first-class, released in lockstep

**Your decision. FGA has exactly two client classes and MUST treat both as first-class:** the Svelte
app shell (ADR-18) and the Lightroom Classic plug-in. **Neither is a convenience wrapper around the
other. They are two front doors to one queue.**

- **A breaking API change MUST land with both clients updated**, or it does not land.
- **A new capability SHOULD reach both**, and where it cannot, write the asymmetry down here.
- ADR-16's zero-padded `/api/v001` path version is what buys room to break the contract deliberately.

**Your framing on why this needed saying out loud:** *"very relevant for Terry-of-2031 who forgot 'oh
shit right that LrC plug-in is fuggin amazing'."* **The failure mode is absence, not malice.** A
session works on the web app because that is what is open in the editor, ships an API change that
suits it, and nobody notices the Lua client for eight months.

**The plug-in is arguably the MORE important of the two.** The web UI was built first; that is an
accident of order, not a ranking.

---

## The load-bearing premise, CONFIRMED at runtime

**A third-party plug-in CAN enumerate Adobe's Flickr publish service and read its published photos.**
Measured against your real catalog, not reasoned. `com.flickrgroupaddr.spike` created no publish
service and was handed Adobe's anyway.

```lua
catalog:getPublishServices( nil )        -- nil = ALL services, ANY plug-in
  service:getPluginId()                  -- com.adobe.lightroom.export.flickr
  service:getChildCollections()          -- LrPublishedCollection[]
    collection:getPublishedPhotos()      -- LrPublishedPhoto[]
      publishedPhoto:getRemoteId()       -- the Flickr photo ID
      publishedPhoto:getRemoteUrl()
      publishedPhoto:getPhoto()          -- back to the LrPhoto
```

`photo:getContainedPublishedCollections()` walks the same graph backwards from a selection. **Both
MUST be called inside an `LrTasks` async task.**

**Two independent instruments agree.** The SDK returned remote id `42717931314`; reading the catalog
directly as SQLite returned the same value from `AgRemotePhoto`. **834 published photos, 834 carrying
a Flickr URL and an 8+ digit numeric id.** No exceptions, no nulls.

**Raw evidence is archived at `docs/lrc-spike/`** — both Lua files and `RESULT-2026-08-15.txt`. **Read
the raw file rather than any summary if the two ever disagree.**

### `getRemoteId()` reads LOCAL records, which makes testing free

**It returns what Lightroom wrote into the catalog at publish time. It does not call Flickr.** So a
catalog whose Flickr publish service is expired or never re-authorized still carries every ID, and
**any test of this needs no Flickr credentials, no network and no upload.**

### The catalog hides plug-in identity, so read it at runtime

**`AgLibraryPublishedCollection.creationId` is `com.adobe.ag.export.service.connection`** — a generic
"this row is an export service connection" marker, **not a plug-in identity.** The real identifier
lives elsewhere in the schema (`AgPhotoPropertySpec.sourcePlugin`, namespaced settings keys), so the
SDK performs a mapping the database does not expose.

**`service:getPluginId()` MUST be read at runtime and MUST NOT be predicted from the schema.**

### What the SDK cannot do

**No post-publish hook exists for a third-party plug-in.** Nothing fires when Adobe's Flickr service
finishes uploading, and export filters run on the rendered file *before* upload, so no remote ID
exists yet.

**So the flow is: publish as normal, then invoke one menu item.** The better shape is a menu item
that finds everything published since the plug-in last ran, which `getPublishedPhotos()` makes cheap,
rather than one requiring a selection.

---

## The design

### The plug-in talks ONLY to FGA. It makes no Flickr calls, ever

**It has no Flickr credentials and MUST NOT acquire any.** FGA already holds the Flickr token,
AES-GCM encrypted in D1 under ADR-09.

**The decisive reason is ADR-06's sweep, not tidiness.** The cron runs at 00:15 UTC with Lightroom
closed, so a token living in a Lightroom catalog is invisible to the thing that needs it. **Adobe's
plug-in talks to Flickr directly because Adobe has no server. FGA has one.**

**A dashed plug-in-to-Flickr edge on the architecture diagram was considered and refused.** It reads
cleaner and asserts the exact thing this design avoids. **A future session reading that diagram might
implement it.**

### Authentication is Adobe's own frob pattern, aimed at FGA instead of Flickr

Reading Adobe's sample settled the design. `FlickrAPI.openAuthUrl()` requests a frob, opens a browser
carrying it, and exchanges the frob for a durable token afterwards. **That IS a device-code flow.**

| Adobe → Flickr | FGA plug-in → FGA |
|---|---|
| `flickr.auth.getFrob` | `POST /auth/device-link/start` |
| `LrHttp.openUrlInBrowser( auth?frob=… )` | `LrHttp.openUrlInBrowser( /link?userCode=… )` |
| User approves at flickr.com | User approves at flickrgroupaddr.com |
| Exchange frob → `auth_token` | Poll → FGA plug-in token |

**ADR-24 is the decision and `src/routes/device.ts` is the code.** Two things from the design work are
worth keeping here because the ADR states the rule and not the reasoning:

**Two codes, not one, and the split is the whole security design.** `deviceCode` is the polling
handle — 32 bytes, **never in a URL.** `userCode` is what a human reads and compares, and it is the
only code `/link` may carry. **An early draft put the polling credential in the query string**, which
would have exposed it to browser history, synced history, any extension with `tabs` permission, and
TLS-inspecting proxies. RFC 8628 does not do this. **A parameter named `code` invites exactly that
mistake, which is why it is named `deviceCode`.**

**`approve` and `deny` are separate routes because a refusal MUST NOT look like a failure** — the
waiting plug-in is told `denied` rather than left to time out. That is ADR-01's habit on a new
surface.

### The phishing weakness is real, and FGA's version is worse than most

**Every device flow has this hole.** An attacker starts a flow, sends the victim
`flickrgroupaddr.com/link?userCode=…`, and the victim — already signed in — approves it. **PKCE does
not close it**, because the attacker started the flow and holds the verifier.

**The usual "the blast radius is small" consolation does not apply.** ADR-01 says a request that
reached a moderator is terminal, so a phished token can push a stranger's photos into volunteer
queues **and that cannot be taken back** — not by revoking the token, not by deleting the requests.

**The confirmation step on `/link` is the mitigation that matters.** A victim who never started a
flow has no code on screen to match, which is the moment the attack becomes visible. **Prefilling
from the query string is fine. Auto-approving from it is not.**

### Group selection: the full list with a filter box. No group sets

**You belong to 372 groups, and the count moved from 330 to 372 in one day, so it MUST NOT be
cached.**

**Saved group sets were proposed and rejected**, in your words:

> The pass to assign all groups to sets would annoy me far more than a UX of picking which of the 372
> groups to add a pic to. And each time I joined a new group, I'd resent having to tag it.

**The rejection is about the ONGOING tax, not the one-time setup**, and that is the part a future
session will miss. A taxonomy is never paid for once.

**The bar is a familiar model, not a novel one:** *"The massive wall of groups to pick from is exactly
how the Flickr web UI works, except it's slow as fuck."* **Same UX and faster is reachable. Better UX
is speculative.**

### The picker is TWO LISTS, and the right one is an ADD LIST

| | Left | Right |
|---|---|---|
| Title | `Unselected groups` | `Selected groups` |
| Sort | Case-insensitive ascending | Case-insensitive ascending |
| The filter box | **Applies** | **MUST NOT apply** |
| A click | Moves the row right | Moves the row left |

**The filter MUST NOT touch the right list, and that is the whole reason for the redesign.** You drove
the single-list spike, typed `canada`, and watched four selections vanish from view while the counter
still read 4. **A list that shows what you have chosen cannot hide what you have chosen.**

**Single-row moves only. Range and multi-select are gone, and you chose that having tested both
working:** *"I'm glad to lose range select and multi-select. Single row hopping at a time is more
intuitive."* **A later session MUST NOT reintroduce shift-click as an improvement.**

**FGA HAS NO REMOVAL CAPABILITY.** The only Flickr write in the entire codebase is
`flickr.groups.pools.add`. Your decision: *"can only add groups, not remove. If a pic is in a group   <!-- DIRTY-WORDS-EXEMPT: quoting Terry -->
when the dialog comes up, we just prune it from the initial candidate list."*

**Add-only scoping deleted three real problems** a desired-state endpoint would have created: an etag
to stop a stale read destroying a membership added while the dialog sat open; what a reconcile should
do with a queued-but-unsent add; and **a remove-then-add cycle laundering away ADR-04's memory that a
pair already reached a moderator** — exactly the harm ADR-01 exists to prevent.

**The dialog is a STAGING AREA.** Nothing reaches Flickr until Save, so a click is free and a
mis-click costs one more click. **That beats a per-row confirm**, which would put a modal in front of
the one interaction the design exists to make fast.

### Feedback is preflight. Commitment is one batch submit

**Clicking a group fires a debounced `POST /api/v001/photos/:photoId/preflight`.** It commits nothing
and costs one Flickr call regardless of group count.

**The submit button is a COMMITMENT BOUNDARY under ADR-01, not latency overhead.** It is the only
checkpoint between a stray click and a volunteer's review queue.

**`POST /api/v001/requests/batch` exists and NO CLIENT CALLS IT YET.** `web/src/lib/submission.ts`
still loops one POST per group. **That is deliberate order, not oversight** — the endpoint had to
exist before either client could adopt it, and the plug-in is the client the batch shape was designed
for.

**Adopting it is NOT a drop-in transport swap.** Batch returns two statuses the single endpoint does
not — `already_in_pool` and `already_queued` — and those need **new UI states and new sentences** in
`web/src/lib/outcomes.ts`, which is ADR-01's promise as the words a user reads. **The work is
user-facing copy, not plumbing.**

### Any client MUST call preflight before submitting

**A faster queueing path raises the volume flowing into volunteer moderator queues.** Skipping
ADR-20's preflight because a Lua dialog is awkward would quietly undercut the rule this project is
organized around — and the server would still refuse, so the user sees confusing failures rather than
a clean warning.

---

## SDK facts that cost real time

### `LrView` builds its view tree ONCE, and `visible = false` keeps the space

**The single most expensive SDK fact here**, because a whole picker design was built on the opposite
assumption. The reference says it outright: *"TIP: An item still affects layout, even when it is
hidden."*

**Bindings change values, never structure.** So hiding is the only way to change what a list shows,
and **a filtered list of 364 rows is always 364 rows tall.**

**744 views build in 9–12 ms**, so the row count was never the risk. Rendering was.

### `simple_list` selection

- **`value` is an ARRAY even when `allows_multiple_selection` is false** — and it may also arrive as
  a bare value. Read both shapes. Indexing a string with `[1]` returns nil, so a naive reader runs
  `selected[nil] = true` and dies on the first click.
- **Without `value_equal` the widget keeps a POSITIONAL selection**, which survives an `items`
  rebind. The consequence is functional: the widget believes the highlighted row is already selected,
  so clicking it fires no observer and the row is dead.
- **A list whose contents change MUST supply `value_equal`** and clear the selection with a sentinel
  matching no item.
- **Rebinding `items` clears the widget's `value`**, so the plug-in MUST own the selected set:
  `selected = (selected MINUS visible) UNION value`.
- **No per-row widgets, no columns, no icons.** State goes in the title string.

### Four Lua and SDK traps

| Trap | What it does |
|---|---|
| **`\u{25CF}` is a Lua 5.3 escape** | Lightroom runs 5.1, where it is a **syntax error** and the whole file fails to load. Write raw UTF-8 bytes |
| **Bare `pcall` cannot yield** | Catalog calls yield and Lua 5.1 cannot yield across `pcall`. Use **`LrTasks.pcall`** |
| **`os.clock()` is CPU time** | An HTTP request is almost all waiting. Use `LrDate.currentTime()` for wall seconds |
| **`string.find` defaults to PATTERN matching** | Group names contain `-`, `(`, `)`, `%` and `.`. Pass `plain = true` |

**An unknown `LrView` attribute fails the whole dialog rather than rendering plain**, so guessing one
costs a full load-and-test cycle. `wraps` is an edit-field property; on `static_text`,
**`height_in_lines = -1` plus a width is the wrap instruction.**

**Non-ASCII glyphs substitute silently.** `✅` rendered as a monochrome `☑` from a fallback font.
**Never let a glyph carry meaning alone.**

### Reloading a plug-in

**ALWAYS Remove then Add. Any change, every time.** Your rule: *"always add/remove, it's just safer
and won't get weirdness."* **The argument that MUST NOT reopen it is "only a menu file changed, so a
lighter reload is fine"** — that is exactly the reasoning that failed.

**Lightroom re-reads a menu-item file on every invocation and CACHES a `require`d module.** Editing a
module and its caller together, then re-running the menu item, picks up only the caller — producing a
**new layout driven by old logic**, which reads as a bug in code that is correct on disk.

**Mitigation: a shared module carries a stamp the UI prints.** A stamp on screen disagreeing with the
one in the editor is the fastest read on "Lightroom is running something else."

**Register a menu item in BOTH `LrLibraryMenuItems` and `LrExportMenuItems`.** The first is Library
module only; the second works everywhere.

### The SDK ships a Lua compiler, and it is in this repo

**`Lua Compiler/win/luac.exe` lives inside the SDK archive**, which is vendored at
`vendor/LrC_15.3_202604090947-8f3672ed.release_SDK.zip`. `npm run lua` extracts it on demand and
parse-checks every plug-in file for real.

**A session once searched `C:\` six levels deep, found nothing, and wrote "no luac on this machine"
into two files** — while `vendor/README.md` documented all of it. The filters were `*Lightroom*SDK*`
and `luac*.exe` against an archive named `LrC_...` holding the binary inside a zip. **Neither pattern
could ever have matched, so a clean result meant the filter was wrong, not the thing absent.**

### The SDK version and the Lightroom version are DIFFERENT NUMBERS

**Lightroom Classic is ahead of the SDK, normally by two point releases.** `Info.lua`'s
`LrSdkVersion` names the **SDK**.

**The live risk: a capability added in a newer application release is invisible to the vendored
reference**, so this file can say "the SDK does not support X" when the running application does.
**Remember that before concluding something is impossible.**

### The crypto surface

**Measured by sweeping twelve namespaces against Lightroom Classic 15.5.**

| Namespace | What is really there |
|---|---|
| `LrDigest` | `SHA256`, `SHA384`, `SHA512`, `HMAC`. **`SHA384` is undocumented** <!-- DIRTY-WORDS-EXEMPT: Adobe identifiers --> |
| `LrStringUtils` | `encodeBase64` and `decodeBase64`, among 12 functions |
| `LrPasswords` | `store` and `retrieve`, OS-backed and **scoped by plug-in ID** |
| `LrMath` | `bitAnd`, `bitOr`, `bitXor`. **That is the entire namespace** |
| `LrRandom`, `LrCrypto`, `LrSecurity`, `LrSecureRandom` | **Absent** |

**`LrSystemInfo` exposes `ipAddress`, `machineName`, `numCPUs` and `getRamUsage`.** Named here so
nobody mistakes them for seed material — they are stable identifiers and observable state, the exact
sources Netscape's 1995 SSL PRNG used before Goldberg and Wagner broke it.

**`LrUUID` is present and UNDOCUMENTED. ADR-23 refuses it entirely** — not for credentials, not for
correlation ids, not for temp filenames. **The reason is the missing API contract, not the
cryptography:** Adobe may remove it in a point release without breaking any promise, and
`import("LrUUID")` raises when a namespace is gone, so **a file importing it for something trivial
does not degrade — it fails to load and every menu item in it disappears.**

**ADR-23 names "`LrUUID` exists and looks correct" as the argument that MUST NOT reopen it**, because
that is exactly what was measured and exactly what lost.

---

## The rig

**Your real catalog is at `C:\Photography\LR Catalog\TDO Lightroom Catalog.lrcat`**, 1.8 GB, and
Lightroom opens it by default. **You do not edit on this laptop** — it is here to unblock this work.

**A `.lrcat` reads as ordinary SQLite, safely, without copying it:**

```python
uri = "file:" + urllib.parse.quote(path.as_posix()) + "?mode=ro&immutable=1"
sqlite3.connect(uri, uri=True)
```

**`immutable=1` is the load-bearing half.** It tells SQLite the file cannot change, so it takes no
locks and creates no `-wal`, `-shm` or journal sidecar. **Lightroom MUST be closed first, and that
MUST be checked rather than assumed**, because `immutable=1` is a promise the caller makes.

Tables worth knowing: `AgLibraryPublishedCollection`, `AgLibraryPublishedCollectionImage`,
`AgRemotePhoto` (`remoteId`, `url`, `photo`), `AgPhotoPropertySpec.sourcePlugin`, `Adobe_images`.

**A catalog MUST be on a local writable volume. `X:` is a NAS share**, so a catalog MUST be copied off
it before opening. Photos MAY stay on the NAS; the `.lrcat` may not.

### Connectivity is measured, and the two numbers matter

```
GET /health          200   160 ms   {"status":"ok"}
GET /api/v001/me     401    14 ms   {"error":"not_authenticated"}
```

**160 ms then 14 ms on the same connection.** The first call pays TLS setup and a cold Worker.
**So the group list fetch should be the FIRST call** — pay the cold cost while the dialog is still
opening.

**A refused call is legible**: 401 with a JSON body, not an HTML login page.

**Two `LrHttp` details a naive client gets wrong.** A transport failure returns a nil body and puts
the reason in `headersTable.error`. And **there is no documented default timeout** — a hung request
inside a modal is indistinguishable from a frozen Lightroom, so pass one explicitly.

### The one Lightroom crash

**One, on the very first plug-in run. None since**, across roughly eight loads and versions 0.1
through 0.8. **The obvious suspect — the bare `pcall` — is argued against by the record**, because
that defect caught its error and reported a verdict rather than crashing.

**The honest state is one unexplained crash and no recurrence**, so a future session hitting a crash
should treat it as NEW rather than as a known flaky plug-in.

---

## Considered and rejected

| Option | Why not |
|---|---|
| **Lightroom Services** cloud API | Addresses the Lightroom **cloud** library, not a Classic catalog. Also gated behind Adobe review |
| **Lightroom API — Firefly Services** | Same wrong target |
| An export filter to catch the publish | Filters run on the rendered file **before** upload, so no remote ID exists yet |
| Calling Flickr from the plug-in to find the photo | Needs its own Flickr auth, and the catalog already knows the answer |
| **Per-click submission with a queue, rescind by clicking again** | **Read this before re-proposing it.** Under ADR-01 an add that reaches a moderator resolves at that instant and can NEVER be pulled back — Flickr offers no call to remove a photo from a moderation queue. A rescind can lose that race, and the user would be told "cancelled" while a volunteer is looking at their photo |
| A Cloudflare Queue in front of the D1 insert | **The `requests` table already IS the queue.** A second queue only makes the INSERT async, and that insert carries every safety constraint. ADR-06's promotion bar applies: measure a real limit first |
| A pasted long-lived token, or `LrSocket` on a localhost callback | Both workable, both beaten by the frob pattern. A paste means copying a secret by hand; a socket means a listener, a firewall prompt and a second redirect target |
| Saved group sets | The ongoing tax. See the picker section |

**Neither cloud API can see a Classic catalog on local disk**, which is where every record this design
needs actually lives. **The plug-in path is not merely easier; it is the only one that reaches the
IDs.**
