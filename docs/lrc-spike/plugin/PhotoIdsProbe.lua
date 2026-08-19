--[[
  What Flickr IDs does my current Lightroom selection resolve to?

  READ-ONLY. No network, no Flickr call, no catalog write. `getRemoteId()` reads
  records Lightroom already wrote at publish time, so this costs nothing and needs
  no credential.

  SELECT SOME PHOTOS FIRST, then run it. A mix is the most useful selection:
  some published to Flickr, one never published, one published somewhere else if
  you have such a thing. The failures are the interesting rows.

  **This is the join the whole product rests on.** FGA's API only ever speaks in
  Flickr photo IDs. Until this resolves, nothing downstream can be called at all.
]]

local LrDialogs = import("LrDialogs")
local LrTasks = import("LrTasks")
local LrPathUtils = import("LrPathUtils")
local LrDate = import("LrDate")

local PhotoIds = require("PhotoIds")

local function run()
	local started = LrDate.currentTime()
	local results = PhotoIds.forSelection()
	local elapsed = (LrDate.currentTime() - started) * 1000

	local report = {
		"FGA photo ID probe",
		string.format("Selected: %d photo(s)", #results),
		string.format("Resolved in %.0f ms", elapsed),
		"",
	}

	local resolved = 0
	local byReason = {}

	for i, row in ipairs(results) do
		if row.flickrId ~= nil then
			resolved = resolved + 1
			report[#report + 1] = string.format(
				"[%d] OK    %s",
				i,
				tostring(row.flickrId)
			)
			report[#report + 1] = string.format(
				"         in %s",
				tostring(row.collectionName)
			)
			report[#report + 1] = string.format("         %s", tostring(row.flickrUrl))
		else
			byReason[row.reason] = (byReason[row.reason] or 0) + 1
			report[#report + 1] = string.format("[%d] NO ID %s", i, tostring(row.reason))
			report[#report + 1] = string.format(
				"         %s",
				(PhotoIds.explain(row.reason):gsub("%s+", " "))
			)
		end
	end

	report[#report + 1] = ""
	report[#report + 1] = string.format(
		"%d of %d resolved to a Flickr photo ID.",
		resolved,
		#results
	)

	for reason, count in pairs(byReason) do
		report[#report + 1] = string.format("  %-14s %d", reason, count)
	end

	report[#report + 1] = ""
	report[#report + 1] = "What this establishes:"
	report[#report + 1] = "  * Whether a selection can be turned into Flickr IDs at all"
	report[#report + 1] = "  * That only Adobe's FLICKR service is read, never another publisher"
	report[#report + 1] = "  * How long the join takes against a real catalog"

	local text = table.concat(report, "\n")

	--[[ Guarded. The measurement is the resolution; the file is a convenience, and
	     a read-only desktop MUST NOT throw the answer away. ]]
	local out = LrPathUtils.child(
		LrPathUtils.getStandardFilePath("desktop"),
		"fga-photo-ids.txt"
	)
	local wrote = LrTasks.pcall(function()
		local handle = assert(io.open(out, "w"))
		handle:write(text)
		handle:close()
	end)
	if not wrote then
		out = "(could not write the file -- the report above is the result)"
	end

	--[[ A long selection would overflow the dialog, so the message is capped and
	     the file carries everything. The cap is on the DIALOG, never on the file. ]]
	local shown = text
	if #shown > 4000 then
		shown = shown:sub(1, 4000) .. "\n\n... truncated. The full report is in the file."
	end

	LrDialogs.message("FGA photo ID probe", shown .. "\n\nWritten to:\n" .. out, "info")
end

LrTasks.startAsyncTask(function()
	local ok, err = LrTasks.pcall(run)
	if not ok then
		LrDialogs.message("FGA photo ID probe FAILED", tostring(err), "critical")
	end
end)
