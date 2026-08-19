--[[
  ADR-20's warning, for one real photo against every group you are in.

  IT COMMITS NOTHING. `preflight` is advisory by design -- it queues no request,
  sends nothing to Flickr on your behalf, and writes nothing to the catalog. The
  server makes one `getAllContexts` call per slice to learn which pools the photo
  is already in, and that is a read.

  SELECT ONE PHOTO FIRST -- one that is published to Flickr. The probe uses the
  first selected photo that resolves to a Flickr id and says which one it picked.

  ## What it is really testing

  Three layers at once, and it is the first thing here that stacks them:

    PhotoIds  -> a Flickr photo id out of the catalog
    FgaApi    -> the group list, with the stored credential
    QueueAdds -> preflight in slices of 200, merged

  **The four buckets ARE the picker's design.** Ready, already in the pool,
  already queued, and needs acknowledgement. If those numbers look wrong against
  what you know about your own account, the picker built on them would be wrong in
  the same way and much harder to see.

  **`poolsKnown = false` is NOT "the photo is in no pools".** ADR-04: presence
  proves approval, absence proves nothing. The report says so out loud rather than
  rendering an unknown as a clean `ready`.
]]

local LrDialogs = import("LrDialogs")
local LrTasks = import("LrTasks")
local LrPathUtils = import("LrPathUtils")
local LrDate = import("LrDate")

local PhotoIds = require("PhotoIds")
local FgaApi = require("FgaApi")
local QueueAdds = require("QueueAdds")

local function firstResolved(rows)
	for _, row in ipairs(rows) do
		if row.flickrId ~= nil then
			return row
		end
	end
	return nil
end

local function run()
	local report = { "FGA preflight probe (ADR-20)", "" }

	local rows = PhotoIds.forSelection()
	report[#report + 1] = string.format("Selected: %d photo(s)", #rows)

	local target = firstResolved(rows)
	if target == nil then
		report[#report + 1] = ""
		report[#report + 1] = "STOPPED: no selected photo resolved to a Flickr ID."
		report[#report + 1] =
			"Select a photo you have published to Flickr, then run this again."
		LrDialogs.message(
			"FGA preflight probe",
			table.concat(report, "\n"),
			"info"
		)
		return
	end

	report[#report + 1] = string.format(
		"Using photo %s (%s)",
		tostring(target.flickrId),
		tostring(target.collectionName)
	)
	report[#report + 1] = ""

	local started = LrDate.currentTime()
	local groupList, failure, _, detail = FgaApi.groups()
	if groupList == nil then
		report[#report + 1] = string.format("FAILED at GET /groups: %s", tostring(failure))
		report[#report + 1] = (FgaApi.explain(failure, detail):gsub("%s+", " "))
		LrDialogs.message("FGA preflight probe", table.concat(report, "\n"), "critical")
		return
	end

	local ids = {}
	local nameOf = {}
	for _, group in ipairs(groupList.groups or {}) do
		ids[#ids + 1] = group.id
		nameOf[group.id] = group.name
	end

	report[#report + 1] = string.format("Groups: %d", #ids)
	report[#report + 1] = string.format(
		"Slices of %d: %d call(s)",
		QueueAdds.CHUNK,
		math.max(1, math.ceil(#ids / QueueAdds.CHUNK))
	)

	if #ids == 0 then
		report[#report + 1] = ""
		report[#report + 1] = "STOPPED: the account is in no groups, so there is nothing to ask about."
		LrDialogs.message("FGA preflight probe", table.concat(report, "\n"), "info")
		return
	end

	local result, pfFailure, pfDetail = QueueAdds.preflight(target.flickrId, ids)
	local elapsed = (LrDate.currentTime() - started) * 1000

	if result == nil then
		report[#report + 1] = string.format("FAILED at preflight: %s", tostring(pfFailure))
		report[#report + 1] = (FgaApi.explain(pfFailure, pfDetail):gsub("%s+", " "))
		LrDialogs.message("FGA preflight probe", table.concat(report, "\n"), "critical")
		return
	end

	local buckets = QueueAdds.bucket(result)

	report[#report + 1] = string.format("Answered in %.0f ms", elapsed)
	report[#report + 1] = ""
	report[#report + 1] = string.format("  ready                  %d", #buckets.ready)
	report[#report + 1] =
		string.format("  already in the pool    %d", #buckets.alreadyInPool)
	report[#report + 1] =
		string.format("  already queued         %d", #buckets.alreadyQueued)
	report[#report + 1] = string.format(
		"  NEEDS ACKNOWLEDGEMENT  %d",
		#buckets.needsAcknowledgement
	)
	report[#report + 1] = ""

	--[[ **The load-bearing line of the whole report.** ADR-04: absence of a pool
	     record proves nothing, so an unknown MUST NOT be presented as clean. ]]
	if result.poolsKnown then
		report[#report + 1] =
			"poolsKnown = true -- Flickr answered, so 'already in the pool' is trustworthy."
	else
		report[#report + 1] = "poolsKnown = FALSE -- Flickr did not answer."
		report[#report + 1] =
			"  Absence of a pool record proves NOTHING (ADR-04). Warnings may be understated."
	end

	if #buckets.needsAcknowledgement > 0 then
		report[#report + 1] = ""
		report[#report + 1] = "Groups that already reached a moderator with one of your photos:"
		for i, entry in ipairs(buckets.needsAcknowledgement) do
			if i > 12 then
				report[#report + 1] = string.format(
					"  ... and %d more",
					#buckets.needsAcknowledgement - 12
				)
				break
			end
			report[#report + 1] = string.format(
				"  %s (%s)",
				tostring(nameOf[entry.groupId] or "?"),
				tostring(entry.groupId)
			)
		end
		report[#report + 1] = ""
		report[#report + 1] =
			"A real picker MUST show these and get a per-group yes before submitting."
	end

	report[#report + 1] = ""
	report[#report + 1] = "NOTHING WAS QUEUED. This probe never calls /requests/batch."

	local text = table.concat(report, "\n")

	local out = LrPathUtils.child(
		LrPathUtils.getStandardFilePath("desktop"),
		"fga-preflight.txt"
	)
	local wrote = LrTasks.pcall(function()
		local handle = assert(io.open(out, "w"))
		handle:write(text)
		handle:close()
	end)
	if not wrote then
		out = "(could not write the file -- the report above is the result)"
	end

	LrDialogs.message("FGA preflight probe", text .. "\n\nWritten to:\n" .. out, "info")
end

LrTasks.startAsyncTask(function()
	local ok, err = LrTasks.pcall(run)
	if not ok then
		LrDialogs.message("FGA preflight probe FAILED", tostring(err), "critical")
	end
end)
