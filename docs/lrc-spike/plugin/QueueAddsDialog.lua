--[[
  The thing this whole project is for.

  Terry, in his own words, and it is the north star:

    "I do all my culling, editing, and posting to Flickr ... If after I publish I
     could open up a dialog in LR and add the new photo to my FGA queues per
     pool/group, that speeds up my workflow. No need to pop out of LR and use my
     browser to log into FGA and queue up group adds."

  This is that dialog. Select a published photo, pick groups, queue the adds.

  ## IT WRITES. This is the first thing in the plug-in that can reach a person

  Everything else here reads, reports, or links. This queues real requests that a
  nightly sweep sends to Flickr, and a moderated pool puts a photo in front of an
  unpaid volunteer. **ADR-01 is why the confirmation below is not decoration.**

  ## ONE PHOTO PER RUN, and that is a stated limit rather than an oversight

  `POST /requests/batch` is one photo into many groups. Multi-select would need a
  warning MATRIX -- ADR-20's warnings are per (photo, group) pair, so ten photos
  across forty groups is four hundred separate decisions. **Doing that half-way
  would be worse than not doing it**, so this takes the first selected photo that
  resolves to a Flickr id and says which one it took.

  ## PREFLIGHT RUNS BEFORE THE PICKER OPENS, and that is the cheap way round

  The first design fetched groups, showed a picker, then preflighted the checked
  ones. **Preflight costs ONE Flickr call per slice no matter how many groups it
  carries**, because `getAllContexts` is per-photo. So asking about everything up
  front costs the same as asking about a subset, and it buys three things at once:

    * the picker can PRUNE groups the photo is already in (Terry's add-only rule)
    * the picker can PRUNE groups already queued
    * ADR-20's warnings are known BEFORE anything is on screen

  ## THE WARNED SECTION IS THE ACKNOWLEDGEMENT, and that is deliberate

  Groups that already had one of your photos reach a moderator are listed in their
  own section, under a heading that says what that means. **Checking a box there IS
  the per-group acknowledgement**, and only those ids go into
  `acknowledgedModeration`. A single "I understand" for the whole dialog would be
  the blanket flag ADR-20 refuses.

  `LrTasks.pcall`, never bare `pcall`.
]]

local LrDialogs = import("LrDialogs")
local LrView = import("LrView")
local LrBinding = import("LrBinding")
local LrFunctionContext = import("LrFunctionContext")
local LrTasks = import("LrTasks")

local PhotoIds = require("PhotoIds")
local FgaApi = require("FgaApi")
local QueueAdds = require("QueueAdds")

--[[ Measured, not guessed. 0.13 shipped 320 and group names clipped with a
     horizontal scrollbar to prove it; 0.14 widened to 400 against the longest real
     name. The 44 is the checkbox glyph plus its padding. ]]
local PANE_WIDTH = 400
local PANE_HEIGHT = 420
local ROW_WIDTH = PANE_WIDTH - 44

local function fail(title, message)
	LrDialogs.message(title, message, "critical")
end

local function note(title, message)
	LrDialogs.message(title, message, "info")
end

--[[ Builds the picker and returns the ids the person checked, split into plain
     picks and acknowledged-warning picks. Returns nil if they cancelled. ]]
local function pick(context, target, ready, warned, nameOf)
	local factory = LrView.osFactory()
	local props = LrBinding.makePropertyTable(context)

	local function keyFor(prefix, index)
		return string.format("%s%d", prefix, index)
	end

	local readyRows = {}
	for i, entry in ipairs(ready) do
		props[keyFor("ready", i)] = false
		readyRows[#readyRows + 1] = factory:checkbox({
			title = tostring(nameOf[entry.groupId] or entry.groupId),
			value = LrView.bind(keyFor("ready", i)),
			width = ROW_WIDTH,
		})
	end

	local warnedRows = {}
	for i, entry in ipairs(warned) do
		props[keyFor("warned", i)] = false
		warnedRows[#warnedRows + 1] = factory:checkbox({
			title = tostring(nameOf[entry.groupId] or entry.groupId),
			value = LrView.bind(keyFor("warned", i)),
			width = ROW_WIDTH,
		})
	end

	--[[ An empty section would render as a heading over nothing, which reads as a
	     bug. A sentence in its place says the same thing honestly. ]]
	if #readyRows == 0 then
		readyRows[1] = factory:static_text({
			title = "Nothing here. Every other group is already handled below.",
			width = ROW_WIDTH,
		})
	end

	local contents = factory:column({
		spacing = 8,
		bind_to_object = props,

		factory:static_text({
			title = string.format(
				"Photo %s, from %s",
				tostring(target.flickrId),
				tostring(target.collectionName)
			),
			width = PANE_WIDTH,
		}),

		factory:separator({ fill_horizontal = 1 }),

		factory:static_text({
			title = string.format("Ready to queue (%d)", #ready),
			width = PANE_WIDTH,
		}),
		factory:scrolled_view({
			width = PANE_WIDTH,
			height = PANE_HEIGHT,
			factory:column({ spacing = 2, unpack(readyRows) }),
		}),

		factory:separator({ fill_horizontal = 1 }),

		--[[ **ADR-20 on screen.** The heading has to say what checking a box here
		     means, because checking it IS the acknowledgement. ]]
		factory:static_text({
			title = string.format(
				"Already reached a moderator (%d) -- checking one asks again",
				#warned
			),
			width = PANE_WIDTH,
		}),
		factory:static_text({
			title = "One of your photos in these groups is already waiting on a"
				.. " volunteer. Queueing another asks the same person twice.",
			width = PANE_WIDTH,
			height_in_lines = 2,
		}),
		factory:scrolled_view({
			width = PANE_WIDTH,
			height = 120,
			factory:column({
				spacing = 2,
				unpack(
					#warnedRows > 0 and warnedRows
						or {
							factory:static_text({
								title = "None. Nothing here has reached a moderator.",
								width = ROW_WIDTH,
							}),
						}
				),
			}),
		}),
	})

	local answer = LrDialogs.presentModalDialog({
		title = "Add this photo to FlickrGroupAddr queues",
		contents = contents,
		actionVerb = "Review",
		cancelVerb = "Cancel",
	})

	if answer ~= "ok" then
		return nil
	end

	local picked = {}
	local acknowledged = {}

	for i, entry in ipairs(ready) do
		if props[keyFor("ready", i)] then
			picked[#picked + 1] = entry.groupId
		end
	end

	for i, entry in ipairs(warned) do
		if props[keyFor("warned", i)] then
			picked[#picked + 1] = entry.groupId
			--[[ **Only a box checked in the WARNED section becomes an
			     acknowledgement.** This is the one line ADR-20 turns on. ]]
			acknowledged[#acknowledged + 1] = entry.groupId
		end
	end

	return picked, acknowledged
end

--[[ The last screen before anything is written. It names the counts and, when a
     warning is involved, names that too. ]]
local function confirm(picked, acknowledged, poolsKnown, nameOf)
	local lines = {
		string.format("Queue this photo into %d group(s)?", #picked),
		"",
	}

	if #acknowledged > 0 then
		lines[#lines + 1] = string.format(
			"%d of them already have one of your photos waiting on a moderator:",
			#acknowledged
		)
		for i, id in ipairs(acknowledged) do
			if i > 8 then
				lines[#lines + 1] = string.format("  ... and %d more", #acknowledged - 8)
				break
			end
			lines[#lines + 1] = string.format("  %s", tostring(nameOf[id] or id))
		end
		lines[#lines + 1] = ""
	end

	if not poolsKnown then
		--[[ ADR-04. Absence proves nothing, so an unknown MUST be said out loud
		     rather than rendered as a clean list. ]]
		lines[#lines + 1] =
			"Flickr did not answer when asked which pools this photo is already in,"
		lines[#lines + 1] =
			"so some of these may already be there. FlickrGroupAddr will not add a"
		lines[#lines + 1] = "duplicate, but the list above may be understated."
		lines[#lines + 1] = ""
	end

	lines[#lines + 1] = "Queued adds are sent overnight. Nothing goes to Flickr now."

	return LrDialogs.confirm(
		"Confirm",
		table.concat(lines, "\n"),
		string.format("Queue %d add(s)", #picked),
		"Go back"
	) == "ok"
end

local function run()
	local rows = PhotoIds.forSelection()

	local target = nil
	for _, row in ipairs(rows) do
		if row.flickrId ~= nil then
			target = row
			break
		end
	end

	if target == nil then
		local why = #rows == 0 and "Nothing is selected."
			or PhotoIds.explain(rows[1] and rows[1].reason)
		fail(
			"No Flickr photo to queue",
			"FlickrGroupAddr can only queue photos that are already on Flickr.\n\n" .. why
		)
		return
	end

	local groupList, failure, _, detail = FgaApi.groups()
	if groupList == nil then
		fail("Could not read your groups", FgaApi.explain(failure, detail))
		return
	end

	local ids = {}
	local nameOf = {}
	for _, group in ipairs(groupList.groups or {}) do
		ids[#ids + 1] = group.id
		nameOf[group.id] = group.name
	end

	if #ids == 0 then
		note("No groups", "Your Flickr account is not in any groups yet.")
		return
	end

	local result, pfFailure, pfDetail = QueueAdds.preflight(target.flickrId, ids)
	if result == nil then
		fail("Could not check this photo", FgaApi.explain(pfFailure, pfDetail))
		return
	end

	local buckets = QueueAdds.bucket(result)

	if #buckets.ready == 0 and #buckets.needsAcknowledgement == 0 then
		note(
			"Nothing left to add",
			string.format(
				"This photo is already in %d of your groups and queued for %d more."
					.. "\n\nThere is nothing new to queue.",
				#buckets.alreadyInPool,
				#buckets.alreadyQueued
			)
		)
		return
	end

	local picked, acknowledged
	LrFunctionContext.callWithContext("fga-queue-adds", function(context)
		picked, acknowledged =
			pick(context, target, buckets.ready, buckets.needsAcknowledgement, nameOf)
	end)

	if picked == nil then
		return
	end

	if #picked == 0 then
		note("Nothing picked", "No groups were checked, so nothing was queued.")
		return
	end

	if not confirm(picked, acknowledged, result.poolsKnown, nameOf) then
		return
	end

	local submitted, subFailure, subDetail =
		QueueAdds.submit(target.flickrId, picked, acknowledged)

	if submitted == nil then
		local howFar = ""
		if type(subDetail) == "table" and subDetail.submittedGroups then
			--[[ **How far it got, in the message.** Without this a person cannot
			     tell whether re-running would queue the same groups twice, and
			     under ADR-01 that means asking a volunteer again. ]]
			howFar = string.format(
				"\n\n%d of %d groups were already submitted before this failed."
					.. "\nRe-running would queue those a second time.",
				subDetail.submittedGroups,
				subDetail.totalGroups
			)
		end
		fail(
			"Some adds may not have been queued",
			FgaApi.explain(subFailure, type(subDetail) == "table" and subDetail.detail)
				.. howFar
		)
		return
	end

	--[[ **Counted by INDEX over the list we sent, never with `ipairs`.** The reply array
	     can carry a `null` for a group the server neither decided nor minted, that
	     decodes to Lua `nil`, and `ipairs` stops dead at the hole -- so an `ipairs`
	     count here would silently report only the groups before the first gap. See
	     `appendAnswers` in `QueueAdds.lua` for the measurement. ]]
	local answers = submitted.groups or {}
	local resolved = 0
	for index = 1, #picked do
		local entry = answers[index]
		if entry ~= nil and entry.status == "resolved" then
			resolved = resolved + 1
		end
	end

	note(
		"Queued",
		string.format(
			"%d add(s) queued for photo %s.%s\n\nThey are sent overnight."
				.. " You can watch them on the FlickrGroupAddr website.",
			tonumber(submitted.queuedCount) or #picked,
			tostring(target.flickrId),
			resolved > 0 and string.format("\n%d were sent immediately.", resolved) or ""
		)
	)
end

LrTasks.startAsyncTask(function()
	local ok, err = LrTasks.pcall(run)
	if not ok then
		fail("FGA queue adds FAILED", tostring(err))
	end
end)
