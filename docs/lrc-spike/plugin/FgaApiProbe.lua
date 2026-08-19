--[[
  Does the stored credential actually work? Measured, not assumed.

  `DeviceLinkProbe.lua` puts a token in the keychain. Nothing has ever spent one.
  This makes three READ-ONLY calls with it and reports exactly what came back.

    GET /api/v001/me       -- and it checks clientType, not just the status code
    GET /api/v001/groups   -- the picker's candidate list
    GET /api/v001/queue    -- the user's own pending rows

  IT WRITES NOTHING. No preflight, no batch, no catalog change, no Flickr call
  from here -- though the server makes one on its own behalf for `groups`.

  **THE `me` CHECK IS THE VALUABLE ONE, and it is not the status code.** "Am I
  authenticated" and "did I end up with the credential I think I did" are different
  questions. A device link that silently minted a BROWSER session would answer 200
  here and be wrong in a way nothing else in this plug-in could see. So the probe
  asserts `clientType == "lrc15_plugin"` and says so out loud either way.

  `LrTasks.pcall`, never bare `pcall`.
]]

local LrDialogs = import("LrDialogs")
local LrTasks = import("LrTasks")
local LrPathUtils = import("LrPathUtils")
local LrDate = import("LrDate")

local FgaApi = require("FgaApi")

local EXPECTED_CLIENT_TYPE = "lrc15_plugin"

--[[ Runs one call and turns it into report lines. The elapsed time comes from
     `LrDate.currentTime()` deltas -- `os.clock()` measures CPU time, and an HTTP
     request is almost entirely waiting, so it would report a few milliseconds for
     a thirty-second timeout. ]]
local function describe(label, fn)
	local started = LrDate.currentTime()
	local value, failure, status, detail = fn()
	local elapsed = (LrDate.currentTime() - started) * 1000

	local lines = { label }
	lines[#lines + 1] = string.format("  status   %s", tostring(status))
	lines[#lines + 1] = string.format("  elapsed  %.0f ms", elapsed)

	if failure ~= nil then
		lines[#lines + 1] = string.format("  FAILED   %s", tostring(failure))
		lines[#lines + 1] = string.format(
			"  meaning  %s",
			(FgaApi.explain(failure, detail):gsub("%s+", " "))
		)
		return table.concat(lines, "\n"), nil
	end

	return table.concat(lines, "\n"), value
end

local function run()
	local report = {
		"FGA authenticated API probe",
		string.format("Base: %s", FgaApi.BASE),
		"",
	}

	local meText, me = describe("GET /api/v001/me", function()
		return FgaApi.me()
	end)
	report[#report + 1] = meText

	if me ~= nil then
		report[#report + 1] = string.format("  nsid     %s", tostring(me.nsid))
		report[#report + 1] =
			string.format("  client   %s", tostring(me.clientType))

		--[[ **The assertion this probe exists for.** A 200 proves the token is
		     valid. Only this proves it is the RIGHT KIND of token. ]]
		if me.clientType == EXPECTED_CLIENT_TYPE then
			report[#report + 1] =
				string.format("  VERDICT  correct -- this is a %s token", EXPECTED_CLIENT_TYPE)
		else
			report[#report + 1] = string.format(
				"  VERDICT  WRONG -- expected %s, the device link minted the wrong kind",
				EXPECTED_CLIENT_TYPE
			)
		end
	end

	report[#report + 1] = ""

	local groupsText, groups = describe("GET /api/v001/groups", function()
		return FgaApi.groups()
	end)
	report[#report + 1] = groupsText

	if groups ~= nil and type(groups.groups) == "table" then
		report[#report + 1] =
			string.format("  groups   %d returned", #groups.groups)

		local moderated = 0
		for _, group in ipairs(groups.groups) do
			if group.poolModerated then
				moderated = moderated + 1
			end
		end
		--[[ Worth counting rather than merely listing: a moderated pool is where
		     ADR-01 turns on, so this is the population the fail-polite rule
		     actually governs. ]]
		report[#report + 1] =
			string.format("  of those %d are pool-moderated", moderated)

		local first = groups.groups[1]
		if first ~= nil then
			report[#report + 1] = string.format(
				"  first    %s (%s)",
				tostring(first.name),
				tostring(first.id)
			)
		end
	end

	report[#report + 1] = ""

	local queueText, queue = describe("GET /api/v001/queue", function()
		return FgaApi.queue("pending", 50)
	end)
	report[#report + 1] = queueText

	--[[ **The reply is GROUPED BY GROUP, not a flat list** -- `queues` is an array
	     of `{ groupId, requests }`, which mirrors ADR-03's FIFO being per
	     (user, group) rather than global. Counting it means summing the inner
	     lists. An earlier draft of this probe read `queue.requests` and would have
	     silently reported zero forever. ]]
	if queue ~= nil and type(queue.queues) == "table" then
		local rows = 0
		for _, entry in ipairs(queue.queues) do
			if type(entry.requests) == "table" then
				rows = rows + #entry.requests
			end
		end
		report[#report + 1] = string.format(
			"  pending  %d row(s) across %d group queue(s)",
			rows,
			#queue.queues
		)
		report[#report + 1] =
			string.format("  more     %s", tostring(queue.nextCursor))
	end

	report[#report + 1] = ""
	report[#report + 1] = "What this establishes:"
	report[#report + 1] = "  * Whether the stored credential is accepted at all"
	report[#report + 1] = "  * Whether it is a plug-in token rather than a browser one"
	report[#report + 1] = "  * Whether the picker's candidate list is reachable and how big it is"
	report[#report + 1] = "  * How long each call takes from inside Lightroom"

	local text = table.concat(report, "\n")

	--[[ **The write is guarded, and the guard is the point.** The measurement is
	     the HTTP result; the file is a convenience. A read-only desktop MUST NOT
	     throw away an answer the probe just spent thirty seconds getting. ]]
	local out = LrPathUtils.child(
		LrPathUtils.getStandardFilePath("desktop"),
		"fga-api-probe.txt"
	)
	local wrote = LrTasks.pcall(function()
		local handle = assert(io.open(out, "w"))
		handle:write(text)
		handle:close()
	end)
	if not wrote then
		out = "(could not write the file -- the report above is the result)"
	end

	LrDialogs.message(
		"FGA authenticated API probe",
		text .. "\n\nWritten to:\n" .. out,
		"info"
	)
end

LrTasks.startAsyncTask(function()
	local ok, err = LrTasks.pcall(run)
	if not ok then
		LrDialogs.message("FGA API probe FAILED", tostring(err), "critical")
	end
end)
