--[[
  The device-link client: how this plug-in gets an FGA credential without ever
  holding a Flickr one.

  ADR-24 designs the flow and `src/routes/device.ts` serves it. This file is the
  Lightroom half, and it is deliberately UI-FREE -- it makes HTTP calls, waits, and
  stores a token. `DeviceLinkProbe.lua` owns every dialog. The split is the same one
  `HostVersion.lua` and `HostVersionProbe.lua` already use here, and it exists so the
  flow can be reasoned about without a modal in the way.

  THE FOUR STEPS, and the server names all of them:

    1. POST /auth/device-link/start   -> deviceCode, userCode, verificationUri
    2. LrHttp.openUrlInBrowser( verificationUri )
    3. POST /auth/device-link/poll    -> pending | slow_down | approved | denied | expired
    4. LrPasswords.store( ... )       -> the session token, in the OS keychain

  ADR-01 GOVERNS STEP 3, AND IT IS THE ONE RULE HERE THAT MUST NOT BEND.
  `denied` means a PERSON pressed "Not mine -- deny". It is TERMINAL. This file
  MUST NOT poll again after it, MUST NOT re-open the browser, and MUST NOT start a
  fresh attempt on the user's behalf. A refusal is an answer, not a failure.

  `LrTasks.pcall`, never bare `pcall`. Lightroom runs plug-in code as coroutines and
  SDK calls yield; Lua 5.1 cannot yield across a `pcall` boundary.
]]

local LrHttp = import("LrHttp")
local LrTasks = import("LrTasks")
local LrPasswords = import("LrPasswords")
local LrDate = import("LrDate")

--[[ rxi/json.lua, MIT, vendored beside this file. The LrC SDK ships NO JSON parser
     -- checked against the pinned archive rather than assumed -- and Terry chose a
     surveyed library over a hand-rolled decoder under the integrate-before-innovate
     standing order. Provenance and the update procedure are in
     docs/LRC-CLIENT-NOTES.md. ]]
local json = require("json")

local DeviceLink = {}

DeviceLink.BASE = "https://flickrgroupaddr.com"

--[[ Lightroom's `LrHttp` has no documented default timeout, and a hung request
     inside a modal is indistinguishable from a frozen Lightroom. ]]
local TIMEOUT = 15

local USER_AGENT = "FGA-LrC-spike/0.17 (device link)"

--[[ **The keychain entry.** `LrPasswords` puts this in the OS credential store,
     which is the only place a long-lived bearer token belongs on a laptop. ]]
local TOKEN_KEY = "fga.session.token"

--[[ **Salt and pluginId are both nil ON PURPOSE, and the reason is honesty.**
     The SDK reference says a nil salt defaults to the plug-in ID and a nil pluginId
     means the running plug-in. A hardcoded salt in a PUBLIC repository would derive
     from a string anybody can read, exactly like the plug-in ID does -- so it would
     add no protection while looking like it did. The real protection is the OS
     keychain, and inventing a decorative secret beside it would mislead the next
     reader about what is actually defending this token. ]]
local TOKEN_SALT = nil
local TOKEN_PLUGIN = nil

--[[ **A safety cap on the whole wait, NOT an expiry check.** The server owns
     expiry and answers `expired`, so this exists only so a server that kept saying
     `pending` forever could not spin a modal until Lightroom is force-quit. ]]
local MAX_WAIT_SECONDS = 15 * 60

--[[ Used only if the server omits `pollAfter`. RFC 8628's own default shape. ]]
local FALLBACK_POLL_SECONDS = 5

--[[ **How many CONSECUTIVE transport failures end the wait.** One is not enough:
     a laptop that slept, a hotel portal, or a Worker cold start produces a single
     failed poll and the flow should survive it. Unlimited is worse -- a plug-in
     that polls a dead host for fifteen minutes tells the user nothing. ]]
local MAX_CONSECUTIVE_FAILURES = 5

--[[ **A transport failure and a refusal MUST stay distinguishable**, which is why
     this returns `nil, message` rather than a status string. Collapsing "the
     network is down" into the same channel as "a person said no" is precisely the
     ADR-01 mistake, one layer down. ]]
local function postJson(path, payload)
	local body = json.encode(payload)

	local headers = {
		{ field = "Content-Type", value = "application/json" },
		{ field = "Accept", value = "application/json" },
		{ field = "User-Agent", value = USER_AGENT },
	}

	local responseBody, responseHeaders =
		LrHttp.post(DeviceLink.BASE .. path, body, headers, "POST", TIMEOUT)

	if responseHeaders == nil then
		return nil, "No response at all from " .. path
	end

	if responseHeaders.error then
		local why = responseHeaders.error.name
			or responseHeaders.error.errorCode
			or "unknown"
		return nil, "Transport failure: " .. tostring(why)
	end

	if responseBody == nil then
		return nil, string.format("Empty body, status %s", tostring(responseHeaders.status))
	end

	--[[ rxi's decoder RAISES on malformed input rather than returning nil, so the
	     call is wrapped. An HTML error page from a proxy is the realistic case, and
	     it MUST NOT surface as a Lua stack trace in front of a photographer. ]]
	local decoded
	local ok = LrTasks.pcall(function()
		decoded = json.decode(responseBody)
	end)

	if not ok or type(decoded) ~= "table" then
		return nil,
			string.format(
				"Unreadable reply, status %s: %s",
				tostring(responseHeaders.status),
				tostring(responseBody):sub(1, 120)
			)
	end

	return decoded, nil, responseHeaders.status
end

--[[ Step 1. No credential is sent, and none is required -- obtaining one is the
     whole point of the flow. ]]
function DeviceLink.start()
	--[[ The server reads no body here, and says so in its own comment. An empty
	     table keeps `LrHttp.post` sending something well-formed. ]]
	local reply, err = postJson("/auth/device-link/start", {})
	if reply == nil then
		return nil, err
	end

	if type(reply.deviceCode) ~= "string" or type(reply.userCode) ~= "string" then
		return nil, "The server did not return a device code."
	end

	if type(reply.verificationUri) ~= "string" then
		--[[ **Never built in Lua, always taken from the reply.** The server
		     constructs it from its own config precisely so a crafted response or a
		     stale constant cannot point a person at somebody else's approval
		     page. A missing one is a server bug and MUST fail loudly. ]]
		return nil, "The server did not return a verification URL."
	end

	return reply, nil
end

--[[ Step 2. Opens the person's default browser at the server's own URL. ]]
function DeviceLink.openApprovalPage(session)
	LrHttp.openUrlInBrowser(session.verificationUri)
end

--[[ Step 3, one call. `deviceCode` is the credential; it never travels in a URL. ]]
function DeviceLink.poll(session)
	return postJson("/auth/device-link/poll", {
		userCode = session.userCode,
		deviceCode = session.deviceCode,
	})
end

--[[ Step 3, the loop.

     Returns one of `approved`, `denied`, `expired`, `canceled`, `timeout` or
     `failed`, plus a second value -- the token when approved, a message when
     failed.

     `opts.isCanceled` is asked BEFORE every sleep and every request, so a person
     who gives up does not wait out the current interval. `opts.onTick` receives the
     status the server last reported, so the caller can keep a caption honest
     without this file importing a dialog. ]]
function DeviceLink.await(session, opts)
	opts = opts or {}

	local interval = tonumber(session.pollAfter) or FALLBACK_POLL_SECONDS
	local started = LrDate.currentTime()
	local failures = 0

	--[[ **Elapsed time is measured as a DELTA, never against `expiresAt`.**
	     `LrDate.currentTime()` is a Cocoa stamp -- seconds since 2001-01-01 -- and
	     the server sends `expiresAt` as a Unix stamp in MILLISECONDS. Comparing
	     them directly is wrong by about 31 years, and it would be wrong in the
	     dangerous direction: every attempt would read as already expired. ]]
	while (LrDate.currentTime() - started) < MAX_WAIT_SECONDS do
		if opts.isCanceled and opts.isCanceled() then
			return "canceled"
		end

		LrTasks.sleep(interval)

		if opts.isCanceled and opts.isCanceled() then
			return "canceled"
		end

		local reply, err = DeviceLink.poll(session)

		if reply == nil then
			failures = failures + 1
			if failures >= MAX_CONSECUTIVE_FAILURES then
				return "failed", err
			end
			if opts.onTick then
				opts.onTick("retrying", failures)
			end
		else
			--[[ Consecutive, so a blip in the middle of a healthy wait does not
			     accumulate toward the limit. ]]
			failures = 0

			if reply.status == "approved" then
				if type(reply.token) ~= "string" then
					return "failed", "Approved, but the server sent no token."
				end
				return "approved", reply.token
			end

			--[[ **ADR-01. A person pressed deny, and that is the end of it.**
			     No retry, no fresh attempt, no reopened browser. ]]
			if reply.status == "denied" then
				return "denied"
			end

			if reply.status == "expired" then
				return "expired"
			end

			--[[ `pending` and `slow_down` both continue, and the server decides the
			     new interval. It raises it after `slow_down`, so simply obeying the
			     reply implements RFC 8628's throttle without this file tracking
			     why the number changed. ]]
			interval = tonumber(reply.pollAfter) or interval

			if opts.onTick then
				opts.onTick(tostring(reply.status), 0)
			end
		end
	end

	return "timeout"
end

--[[ Step 4. The token is a bearer credential, so it goes to the OS keychain and
     never to a preference file or the catalog. ]]
function DeviceLink.saveToken(token)
	LrPasswords.store(TOKEN_KEY, token, TOKEN_SALT, TOKEN_PLUGIN)
end

function DeviceLink.loadToken()
	local token = LrPasswords.retrieve(TOKEN_KEY, TOKEN_SALT, TOKEN_PLUGIN)
	--[[ `retrieve` answers an empty string for a key that was cleared, and callers
	     care about "do I have a credential" rather than about that distinction. ]]
	if type(token) ~= "string" or token == "" then
		return nil
	end
	return token
end

--[[ **Overwritten with an empty string rather than deleted**, because `LrPasswords`
     exposes no delete. The empty string is what `loadToken` reads as absent. ]]
function DeviceLink.clearToken()
	LrPasswords.store(TOKEN_KEY, "", TOKEN_SALT, TOKEN_PLUGIN)
end

return DeviceLink
