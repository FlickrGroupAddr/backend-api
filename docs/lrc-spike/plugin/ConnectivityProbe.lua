--[[
  Can a Lightroom plug-in actually reach FGA? Measured, not assumed.

  Every design in docs/LRC-CLIENT-NOTES.md rests on `LrHttp` reaching
  flickrgroupaddr.com over TLS and handing back a readable status code. That is
  written down from the SDK reference. NOBODY HAS WATCHED IT WORK from inside
  Lightroom, which is the same gap that made the publish-service premise worth
  a probe of its own -- and that one came back confirmed only because it was
  actually run.

  READ-ONLY AND UNAUTHENTICATED. It calls two endpoints:

    GET /health          -- public, expected 200 {"status":"ok"}
    GET /api/v001/me     -- expected to FAIL, because this plug-in has no session

  **The second call is the more valuable one.** A client library that succeeds
  on the happy path and produces an unreadable mess on the sad path is not
  usable, and the sad path is where a real user lives: expired session, no
  network, hotel wi-fi captive portal. This probe reports exactly what Lightroom
  hands back when a request is refused.

  It sends no credentials, writes nothing to the catalog, and queues nothing.

  `LrTasks.pcall`, never bare `pcall`. Lightroom runs plug-in code as coroutines
  and SDK calls yield; Lua 5.1 cannot yield across a `pcall` boundary.
]]

local LrDialogs = import("LrDialogs")
local LrHttp = import("LrHttp")
local LrTasks = import("LrTasks")
local LrPathUtils = import("LrPathUtils")
local LrFileUtils = import("LrFileUtils")

local BASE = "https://flickrgroupaddr.com"

--[[ Lightroom's `LrHttp` has no documented default timeout, and a hung request
     inside a modal is indistinguishable from a frozen Lightroom. 15 seconds is
     long enough for a cold Worker start and short enough to stay a UI. ]]
local TIMEOUT = 15

--[[ **Identify the client.** A Worker that starts seeing unexplained traffic
     should be able to name it, and a plug-in that hides behind a default agent
     string makes its own logs useless. ]]
local HEADERS = {
	{ field = "User-Agent", value = "FGA-LrC-spike/0.6 (connectivity probe)" },
	{ field = "Accept", value = "application/json" },
}

--[[ `headersTable.status` carries the HTTP status. On a TRANSPORT failure --
     no route, TLS refused, timeout -- Lightroom returns a nil body and puts the
     reason in `headersTable.error`, so both have to be handled or the probe
     reports "no status" for two very different situations. ]]
local function describe(label, path)
	local started = os.clock()
	local body, headers = LrHttp.get(BASE .. path, HEADERS, TIMEOUT)
	local elapsed = (os.clock() - started) * 1000

	local lines = { string.format("%s  ->  GET %s", label, path) }

	if headers == nil then
		lines[#lines + 1] = "  TRANSPORT FAILURE: no headers table at all"
	elseif headers.error then
		lines[#lines + 1] = string.format(
			"  TRANSPORT FAILURE: %s",
			tostring(headers.error.name or headers.error.errorCode or "unknown")
		)
	else
		lines[#lines + 1] = string.format("  status   %s", tostring(headers.status))
	end

	lines[#lines + 1] = string.format("  elapsed  %.0f ms", elapsed)

	if body == nil then
		lines[#lines + 1] = "  body     nil"
	else
		local shown = body
		if #shown > 300 then
			shown = shown:sub(1, 300) .. string.format(" ... (%d bytes total)", #body)
		end
		-- Newlines in a body would wreck the report's alignment.
		lines[#lines + 1] = string.format("  body     %s", (shown:gsub("%s+", " ")))
	end

	--[[ Content-Type decides whether a real client can parse the reply, and it
	     is the field most likely to be quietly wrong behind a proxy. ]]
	if headers ~= nil and not headers.error then
		for _, h in ipairs(headers) do
			if type(h) == "table" and type(h.field) == "string" then
				local f = h.field:lower()
				if f == "content-type" or f == "cf-ray" then
					lines[#lines + 1] = string.format("  %-8s %s", f, tostring(h.value))
				end
			end
		end
	end

	return table.concat(lines, "\n")
end

local function run()
	local report = {
		"FGA connectivity probe",
		string.format("Base: %s", BASE),
		string.format("Timeout: %d s", TIMEOUT),
		"",
		--[[ The public endpoint proves TLS, DNS and routing. If this fails,
		     nothing else in the report means anything. ]]
		describe("PUBLIC   ", "/health"),
		"",
		--[[ **This one is EXPECTED to fail**, and how it fails is the finding.
		     The plug-in holds no session cookie, so a well-behaved API answers
		     401 with a JSON body rather than an HTML login page. ]]
		describe("NO AUTH  ", "/api/v001/me"),
		"",
		"What this establishes:",
		"  * Whether LrHttp reaches flickrgroupaddr.com over TLS at all",
		"  * Whether headersTable.status is readable, as the SDK reference claims",
		"  * What an unauthenticated call looks like from inside Lightroom",
	}

	local text = table.concat(report, "\n")

	--[[ Written to a file as well as shown. A modal dialog cannot be
	     copy-pasted usefully, and this output is evidence that belongs in
	     docs/LRC-CLIENT-NOTES.md rather than in a screenshot. ]]
	local out = LrPathUtils.child(LrPathUtils.getStandardFilePath("desktop"), "fga-connectivity.txt")
	local ok = LrFileUtils.writeFile and true or false
	if ok then
		local handle = io.open(out, "w")
		if handle then
			handle:write(text)
			handle:close()
		else
			out = "(could not write file)"
		end
	end

	LrDialogs.message("FGA connectivity probe", text .. "\n\nWritten to:\n" .. out, "info")
end

LrTasks.startAsyncTask(function()
	local ok, err = LrTasks.pcall(run)
	if not ok then
		LrDialogs.message("FGA connectivity probe FAILED", tostring(err), "critical")
	end
end)
