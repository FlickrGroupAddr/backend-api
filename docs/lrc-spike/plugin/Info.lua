--[[
  FGA spike -- can a THIRD-PARTY plug-in read Adobe's Flickr publish service?

  READ-ONLY. It enumerates publish services, prints what it finds, and writes a
  text file. It writes nothing to the catalog and makes no network call.

  This exists to measure ONE unproven premise, recorded in
  docs/LRC-CLIENT-NOTES.md: the SDK documents `catalog:getPublishServices(nil)`
  as returning every service from every plug-in, and nobody has watched that
  work at runtime. Reading the catalog's SQLite proves the DATA is there; it
  does not prove the SDK hands it to a plug-in that did not create it.

  LrSdkMinimumVersion is set to the current SDK on purpose. Terry always runs
  the latest GA Lightroom Classic, so there is no back-compat to serve, and a
  high minimum fails CLOSED -- on an older Lightroom the plug-in refuses to
  load and says so, rather than loading and misbehaving in a way that looks
  like an FGA bug.
]]

return {
	LrSdkVersion = 15.3,
	LrSdkMinimumVersion = 15.3,

	LrToolkitIdentifier = "com.flickrgroupaddr.spike",
	LrPluginName = "FGA spike -- publish service reader",

	-- REGISTERED IN BOTH MENUS ON PURPOSE, 0.3.
	--
	-- 0.2's item did not appear under Library > Plug-in Extras, and the cause was
	-- never established -- Info.lua was intact and both files parsed clean under
	-- the SDK's own Lua 5.1 compiler. Rather than guess at a cause, the same
	-- script is now registered twice so the "which menu" question disappears.
	--
	--   LrLibraryMenuItems -> Library > Plug-in Extras   (Library module only)
	--   LrExportMenuItems  -> File > Plug-in Extras      (every module)
	--
	-- The File entry is the one that matters here: it does NOT depend on the
	-- Library module being active, so it shows up wherever Lightroom happens to
	-- open. Two lines to delete a whole class of uncertainty.
	-- 0.4 ADDS THE PICKER PROBE, and it measures rather than demonstrates.
	--
	-- Two questions decide how the real group picker feels, and both are
	-- recorded UNMEASURED in docs/LRC-CLIENT-NOTES.md: whether rebinding
	-- `simple_list.items` clears the selection, and how a 372-item list looks
	-- and performs. The merge selection model is correct either way -- what
	-- differs is the feel, and feel cannot be read out of a reference manual.
	--
	-- It makes no network call and touches no catalog. The 372 groups are
	-- generated in the file.
	-- **0.16 ADDS THE HOST VERSION BADGE. ADR-25, and it is a NUDGE rather than a
	-- gate.**
	--
	-- Terry, 2026-08-16: *"It's a nudge to future Terry to recompile per LR major
	-- version, test, then upgrade... As major versions are yearly, this is a minor
	-- recurring time impact."*
	--
	-- `HostVersion.lua` holds `TESTED_AGAINST_MAJOR`, an integer somebody set after
	-- WATCHING the plug-in work on that Lightroom major. It is compared against
	-- `LrApplication.versionTable().major` and the badge reads `supported` or
	-- `major version unsupported`.
	--
	-- **The plug-in keeps working either way.** `LrSdkMinimumVersion` above already
	-- fails CLOSED on an older Lightroom, where the APIs are genuinely absent. This
	-- fails OPEN on a newer one, where the code probably works and is merely
	-- unproven -- refusing there would strand Terry on release day for a problem
	-- that usually does not exist.
	-- **0.15 ADDS THE ENTROPY PROBE, and it exists to close a question rather
	-- than to open one.**
	--
	-- The vendored SDK reference documents NO randomness at all: no `LrUUID`, no
	-- `getRandomValues`, and `LrMath` carries only `bitAnd`, `bitOr`, `bitXor`.
	-- Terry's question is the right one -- **absent from the documentation is not
	-- absent from the runtime**, and Adobe ships namespaces it does not document.
	--
	-- Nothing outside Lightroom can answer it. `luac -p` parse-checks the file and
	-- only the application can execute `import("LrUUID")`.
	--
	-- It sweeps twelve candidate namespaces AND enumerates `_G`, because guessing
	-- names finds only what you thought of. If a generator turns up it draws 1024
	-- values and checks for collisions and version-4 shape.
	--
	-- **A pass would NOT settle the design.** Shape is not provenance: a
	-- clock-seeded generator masked into UUID layout passes every check in the
	-- file. A collision, or an absent namespace, IS decisive -- which is the
	-- outcome this is really built to catch.
	-- **0.14 fixes three layout defects 0.13 shipped, all found by looking.**
	--
	-- Panes were 320 wide and group names clipped, with a horizontal scrollbar
	-- to prove it. The left stats line ran past its column and truncated mid
	-- word at "Pic". Both are the same mistake: a width guessed rather than
	-- measured against the longest real string.
	--
	-- **744 rows build in 12 ms**, measured on Terry's machine. That was the one
	-- risk in the checkbox design and it is not a risk.
	--
	-- **0.13 WENT ADD ONLY. Groups the pic is already in are PRUNED, not shown.**
	--
	-- Terry: *"I am going to stop complicating my life -- can only add groups,
	-- not remove. If a pic is in a group when the dialog comes up, we just prune
	-- it from the initial candidate list."*
	--
	-- FGA has no removal capability -- the only Flickr write in the codebase is
	-- flickr.groups.pools.add -- and 0.12 staged removals nothing could execute.
	-- Scoping the picker to match deletes three problems a desired-state endpoint
	-- would have created: an etag against a stale read destroying a membership,
	-- the question of what to do with a queued-but-unsent add, and the risk of a
	-- remove-then-add cycle laundering away ADR-04's memory.
	--
	-- The right pane is now the ADD LIST rather than membership. Removing from it
	-- un-stages a pick and never touches Flickr.
	--
	-- **0.12 RETIRED `simple_list` FOR THE PICKER. Checkboxes, two panes, arrows.**
	--
	-- Terry's design: *"check things on left side and click add arrow to move
	-- right"*, two panes rather than one combined list, and the filter touching
	-- the left pane only.
	--
	-- A checkbox is a bound boolean, so a toggle always changes the value and
	-- always fires. The dead-row class of bug disappears rather than being
	-- worked around -- and the arrows now act on EVERY checked row at once,
	-- which is a batch move that neither earlier design could do.
	--
	-- **LrView builds its view tree ONCE**, so all 744 rows exist up front and
	-- `visible` decides what is on screen. Build time is the risk, so the dialog
	-- times itself and reports it.
	--
	-- **0.11 STOPPED DISAGREEING WITH THE WIDGET, and it was still simple_list.**
	--
	-- Four versions tried to clear simple_list's selection after a move and none
	-- could: value = {}, value = "", the reference's own value_equal hook, and
	-- then buttons that ignored the selection entirely. The widget goes on
	-- highlighting whatever slid into the vacated slot, and it will not fire for
	-- a row it already considers selected -- so that row was dead every time.
	--
	-- 0.11 adopts it instead. The widget says that row is selected; the plug-in
	-- now says so too. Nothing asks the widget to change anything, which is
	-- exactly why this works where four attempts did not. It reads better as
	-- well: after a move the next row is already armed.
	--
	-- **0.10 fixed the button arrows, which 0.9 rendered as garbage.**
	--
	-- 0.9 wrote them as decimal byte escapes and something in the toolchain read
	-- the digits as OCTAL:  octal is 0x96, \ octal is a backslash, f
	-- octal is "f". So "Add ->" arrived as "Add" plus a stray byte and a literal
	-- . They are plain ASCII now -- a spike does not need to win that argument.
	--
	-- **0.9 STOPPED FIGHTING THE WIDGET: buttons move rows, clicks only select.**
	--
	-- 0.6, 0.7 and 0.8 each tried to make click-to-move work and each failed the
	-- same way on Terry's machine. simple_list keeps a POSITIONAL selection that
	-- survives an items rebind, and the list a row DEPARTS from keeps it -- so
	-- clicking that row produces no change, no observer, and a dead control.
	--
	-- A button click always fires. Two clicks per group is a real cost against
	-- what Terry asked for, and it beats a control that can go dead.
	--
	-- **0.8 TRIED the reference's own value_equal hook, and it did not clear it.**
	--
	-- 0.7 was a guess and it failed identically to 0.6. The reference settles it:
	-- `simple_list.value` is an ARRAY, so 0.7's bare string was the wrong TYPE and
	-- the widget ignored it. And `value_equal` is the documented hook that decides
	-- which row is selected -- *"If no item returns true, no item is selected in
	-- the list."* 0.8 supplies one, and a sentinel no item can match.
	--
	-- The reference was in vendor/ the whole time. Two of Terry's test cycles went
	-- to guesses that reading it first would have prevented.
	--
	-- **0.7 TRIED to fix the dead row, and the version number is the point of the bump.**
	--
	-- 0.6 shipped, Terry loaded it, clicked a row, and the row that slid into the
	-- vacated slot stayed highlighted AND stopped responding. The fix went out
	-- without a version bump, which would have left him loading "0.6" twice and
	-- having to remember which one he had. Terry: a version number is "a warm fuzzy
	-- for the meat sac known as Terry's brain". Lightroom may not care. He does,
	-- and he is the one who has to tell two builds apart.
	--
	-- 0.6 ADDED THE CONNECTIVITY PROBE: two real calls to flickrgroupaddr.com with
	-- no credentials, because LrHttp reaching FGA had only ever been read from the
	-- reference and never watched.
	--
	-- 0.5 ADDS THE TRANSFER PICKER, which is Terry's redesign after driving 0.4.
	--
	-- 0.4's single filtered list hid selections behind the filter. He typed
	-- "canada" and four choices vanished from view -- the merge model held them
	-- correctly and the screen said otherwise, which is the worst combination
	-- because a user cannot see a correct model.
	--
	-- 0.5 is two lists with a row hopping between them, and the right list is
	-- the photo's MEMBERSHIP rather than a shopping basket: it opens holding
	-- what Flickr already reports for the photo.
	--
	-- **0.4 STAYS REGISTERED on purpose.** It is the control. Comparing the two
	-- side by side is how the redesign gets judged, and deleting the thing you
	-- are measuring against is how a spike stops being evidence.
	LrLibraryMenuItems = {
		{
			title = "FGA: dump publish services (Library)",
			file = "DumpPublishServices.lua",
		},
		{
			title = "FGA: group picker probe -- one list (Library)",
			file = "PickerProbe.lua",
		},
		{
			title = "FGA: group picker -- TWO LISTS (Library)",
			file = "TransferPicker.lua",
		},
		{
			title = "FGA: group picker -- CHECKBOXES (Library)",
			file = "CheckboxPicker.lua",
		},
		{
			title = "FGA: connectivity probe (Library)",
			file = "ConnectivityProbe.lua",
		},
		{
			title = "FGA: entropy probe -- is LrUUID real? (Library)",
			file = "EntropyProbe.lua",
		},
		{
			title = "FGA: Lightroom version -- tested against? (Library)",
			file = "HostVersionProbe.lua",
		},
	},

	LrExportMenuItems = {
		{
			title = "FGA: dump publish services (File)",
			file = "DumpPublishServices.lua",
		},
		{
			title = "FGA: group picker probe -- one list (File)",
			file = "PickerProbe.lua",
		},
		{
			title = "FGA: group picker -- TWO LISTS (File)",
			file = "TransferPicker.lua",
		},
		{
			title = "FGA: group picker -- CHECKBOXES (File)",
			file = "CheckboxPicker.lua",
		},
		{
			title = "FGA: connectivity probe (File)",
			file = "ConnectivityProbe.lua",
		},
		{
			title = "FGA: entropy probe -- is LrUUID real? (File)",
			file = "EntropyProbe.lua",
		},
		{
			title = "FGA: Lightroom version -- tested against? (File)",
			file = "HostVersionProbe.lua",
		},
	},

	VERSION = { major = 0, minor = 16, revision = 0 },
}
