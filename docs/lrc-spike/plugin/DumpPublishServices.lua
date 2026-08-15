--[[
  Answers one question: does a plug-in that did NOT create a publish service
  get to enumerate it and read its published photos?

  VERSION 0.2. Version 0.1 answered "REFUTED" and was WRONG -- it reported a
  fault in itself as a fact about Lightroom.

  WHAT WENT WRONG, because it is the whole lesson of this file. 0.1 wrapped
  every SDK call in Lua's standard `pcall`, to be defensive. Lightroom runs
  plug-in tasks as COROUTINES, and catalog calls YIELD. Lua 5.1 cannot yield
  across a `pcall` boundary, so the call died with:

      Yielding is not allowed within a C or metamethod call

  The SDK provides the fix by name. From API Reference/modules/LrTasks.html:

      LrTasks.pcall( func, ... )
        Simulates Lua's standard pcall(), but in a way that allows a call to
        LrTasks.yield() to occur inside it.

  So: NEVER use bare `pcall` around anything that touches the catalog. Use
  LrTasks.pcall. The defensive wrapper was the defect.

  THE VERDICT IS NOW THREE-WAY, and that is the second lesson. 0.1 could only
  say CONFIRMED or REFUTED, so its own breakage came out as "the premise is
  false" -- a test whose failure is indistinguishable from the thing it tests
  is worth nothing. An error is now INCONCLUSIVE and says so.

  Still read-only. Nothing is written to the catalog and no network call is
  made. The report is flushed to disk after every step, so a crash mid-run
  still leaves everything learned up to that point.
]]

local LrApplication = import("LrApplication")
local LrDialogs = import("LrDialogs")
local LrTasks = import("LrTasks")
local LrPathUtils = import("LrPathUtils")

local OUT = LrPathUtils.child(
	LrPathUtils.getStandardFilePath("desktop"),
	"fga-spike-output.txt"
)

local lines = {}

--- Rewrite the report after every step, so a crash cannot cost what was learned.
local function flush()
	local handle = io.open(OUT, "w")
	if handle then
		handle:write(table.concat(lines, "\n"))
		handle:close()
	end
end

local function say(fmt, ...)
	local n = select("#", ...)
	lines[#lines + 1] = n > 0 and string.format(fmt, ...) or fmt
	flush()
end

--- Yield-safe accessor. MUST be LrTasks.pcall, never bare pcall.
local function try(obj, method)
	local ok, value = LrTasks.pcall(function()
		return obj[method](obj)
	end)
	if not ok then
		return nil, string.format("<%s() ERRORED: %s>", method, tostring(value))
	end
	return value, tostring(value)
end

LrTasks.startAsyncTask(function()
	say("FGA spike 0.2 -- publish services visible to com.flickrgroupaddr.spike")
	say("Lightroom version: %s", tostring(LrApplication.versionString()))

	local catalog = LrApplication.activeCatalog()
	say("catalog: %s", tostring(catalog:getPath()))
	say("")

	local ok, services = LrTasks.pcall(function()
		return catalog:getPublishServices(nil)
	end)

	if not ok then
		say("VERDICT: INCONCLUSIVE -- the CALL failed, which is not an answer.")
		say("  %s", tostring(services))
		say("  This is a fault in the spike or the harness, NOT evidence that")
		say("  the SDK withholds another plug-in's services. Fix and re-run.")
	elseif services == nil then
		say("VERDICT: REFUTED -- getPublishServices(nil) returned nil")
	elseif #services == 0 then
		say("VERDICT: REFUTED -- getPublishServices(nil) returned an EMPTY list")
		say("  The catalog's SQLite holds one service, so an empty list here means")
		say("  the SDK is withholding another plug-in's services from this one.")
	else
		say("VERDICT: CONFIRMED -- %d service(s) returned to a plug-in that", #services)
		say("created none of them.")
		say("")

		for i, service in ipairs(services) do
			local _, pluginId = try(service, "getPluginId")
			local _, name = try(service, "getName")
			say("[%d] getPluginId() = %s", i, pluginId)
			say("     getName()     = %s", name)

			local cols = select(1, try(service, "getChildCollections"))
			if type(cols) ~= "table" then
				say("     getChildCollections() did not return a table")
			else
				say("     child collections = %d", #cols)

				local shown = 0
				for _, col in ipairs(cols) do
					local photos = select(1, try(col, "getPublishedPhotos"))
					if type(photos) == "table" and #photos > 0 then
						local _, colName = try(col, "getName")
						say("     collection %s -> %d published photo(s)", colName, #photos)
						for j = 1, math.min(3, #photos) do
							local pp = photos[j]
							local _, remoteId = try(pp, "getRemoteId")
							local _, remoteUrl = try(pp, "getRemoteUrl")
							say("       [%d] getRemoteId()  = %s", j, remoteId)
							say("           getRemoteUrl() = %s", remoteUrl)
						end
						shown = shown + 1
						if shown >= 2 then
							break
						end
					end
				end

				if shown == 0 then
					say("     NO collection returned a published photo.")
					say("     The catalog holds 834 rows in AgRemotePhoto, so this would")
					say("     mean reading is blocked one level deeper than enumeration.")
				end
			end
			say("")
		end
	end

	say("-- end of report --")

	LrDialogs.message(
		"FGA spike 0.2 -- publish services",
		table.concat(lines, "\n") .. "\n\nWritten to:\n" .. OUT,
		"info"
	)
end)
