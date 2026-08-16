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
	-- **0.7 FIXES A DEAD ROW, and the version number is the point of this bump.**
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
			title = "FGA: connectivity probe (Library)",
			file = "ConnectivityProbe.lua",
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
			title = "FGA: connectivity probe (File)",
			file = "ConnectivityProbe.lua",
		},
	},

	VERSION = { major = 0, minor = 7, revision = 0 },
}
