--[[
  The authenticated half of the client: everything under /api/v001/*.

  `DeviceLink.lua` obtains the credential. This file spends it. The split matters
  because the two have different failure modes -- a device link fails because a
  person declined, and an API call fails because a token died or Flickr is down,
  and telling a photographer the wrong one wastes their evening.

  UI-FREE, like `DeviceLink.lua`. Every function returns a value and an error, and
  every dialog lives in a probe.

  WHAT A PLUG-IN TOKEN MAY CALL is not this file's opinion -- `PLUGIN_ALLOWED` in
  `src/middleware/session.ts` is the list, and anything outside it answers
  `403 not_allowed_for_plugin`. The six below are that list:

    GET  /api/v001/me                          who am I, and what am I holding
    GET  /api/v001/groups                      the picker's candidate list
    GET  /api/v001/groups/{id}                 one group's detail
    GET  /api/v001/photos/{id}/groups          what to prune from the picker
    POST /api/v001/photos/{id}/preflight       ADR-20's warning
    POST /api/v001/requests/batch              the commitment
    GET  /api/v001/queue                       what happened afterwards

  ADR-20 SAYS THE WARNING ARRIVES BEFORE THE COMMITMENT, FROM EVERY CLIENT.
  Call `preflight` and show the result BEFORE calling `batch`. The server re-checks
  everything and a forged preflight buys nothing, so this is about informed consent
  rather than about security -- which is exactly why a client can quietly skip it
  and nothing will break except the promise.
]]

local LrHttp = import("LrHttp")
local LrTasks = import("LrTasks")

local json = require("json")
local DeviceLink = require("DeviceLink")

local FgaApi = {}

FgaApi.BASE = "https://flickrgroupaddr.com"

local TIMEOUT = 30

local USER_AGENT = "FGA-LrC-spike/0.17 (api client)"

--[[ **Every failure gets a NAME, and the names are the point.**

     A caller that only sees "it did not work" must guess what to tell the user,
     and it will guess wrong -- offering a re-link when Flickr is down, or a
     "try again" when the account has no Flickr credentials at all.

     `notAuthenticated` is the only one that means "link again". ]]
FgaApi.FAILURES = {
	transport = "transport", -- No network, TLS refused, timeout
	notAuthenticated = "notAuthenticated", -- 401. The stored token is dead
	notAllowed = "notAllowed", -- 403. A bug here, not a user problem
	noFlickr = "noFlickr", -- 409. The account never connected Flickr
	tooManyGroups = "tooManyGroups", -- 502. ADR-17's refusal
	flickrDown = "flickrDown", -- 502. Flickr, not us
	badRequest = "badRequest", -- 400. A bug here
	unreadable = "unreadable", -- The reply was not JSON
	unexpected = "unexpected", -- Anything else
}

--[[ Maps a status and an error body onto one of the names above.

     **A 502 is TWO different situations and they need different sentences.**
     `too_many_groups` is ADR-17 refusing to render a wall the user cannot read;
     `flickr_unavailable` is Flickr being Flickr. Collapsing them would tell
     somebody with 6,000 groups to try again later, forever. ]]
local function classify(status, decoded)
	local code = type(decoded) == "table" and decoded.error or nil

	if status == 401 then
		return FgaApi.FAILURES.notAuthenticated
	elseif status == 403 then
		return FgaApi.FAILURES.notAllowed
	elseif status == 400 then
		return FgaApi.FAILURES.badRequest
	elseif status == 409 and code == "no_flickr_credentials" then
		return FgaApi.FAILURES.noFlickr
	elseif status == 502 and code == "too_many_groups" then
		return FgaApi.FAILURES.tooManyGroups
	elseif status == 502 then
		return FgaApi.FAILURES.flickrDown
	end

	return FgaApi.FAILURES.unexpected
end

--[[ Returns `decoded, nil, status` on a 2xx, and `nil, failureName, status` on
     anything else. The decoded body comes back on a failure too, as the fourth
     value, because `too_many_groups` carries the numbers a user needs to see. ]]
local function request(method, path, bodyTable)
	local token = DeviceLink.loadToken()
	if token == nil then
		return nil, FgaApi.FAILURES.notAuthenticated, nil, nil
	end

	local headers = {
		--[[ `presentedToken` in the session middleware accepts a case-insensitive
		     scheme and EXACTLY ONE SPACE -- its pattern is `^Bearer (\S+)$`. Two
		     spaces or a tab fails to match and answers 401, which would look
		     exactly like an expired token. ]]
		{ field = "Authorization", value = "Bearer " .. token },
		{ field = "Accept", value = "application/json" },
		{ field = "User-Agent", value = USER_AGENT },
	}

	local body = nil
	if bodyTable ~= nil then
		body = json.encode(bodyTable)
		headers[#headers + 1] =
			{ field = "Content-Type", value = "application/json" }
	end

	local responseBody, responseHeaders
	if method == "GET" then
		responseBody, responseHeaders = LrHttp.get(FgaApi.BASE .. path, headers, TIMEOUT)
	else
		--[[ `LrHttp.post( url, postBody, headers, method, timeout, totalSize )`,
		     read out of the vendored SDK reference. The 4th argument carries the
		     verb, so POST and PUT share one call. ]]
		responseBody, responseHeaders =
			LrHttp.post(FgaApi.BASE .. path, body or "", headers, method, TIMEOUT)
	end

	if responseHeaders == nil then
		return nil, FgaApi.FAILURES.transport, nil, nil
	end

	if responseHeaders.error then
		local why = responseHeaders.error.name
			or responseHeaders.error.errorCode
			or "unknown"
		return nil, FgaApi.FAILURES.transport, nil, tostring(why)
	end

	local status = tonumber(responseHeaders.status)

	local decoded
	if responseBody ~= nil and responseBody ~= "" then
		--[[ rxi's decoder RAISES rather than returning nil. A proxy's HTML error
		     page is the realistic case and MUST NOT reach a photographer as a Lua
		     stack trace. ]]
		local ok = LrTasks.pcall(function()
			decoded = json.decode(responseBody)
		end)
		if not ok then
			decoded = nil
		end
	end

	if status ~= nil and status >= 200 and status < 300 then
		if type(decoded) ~= "table" then
			return nil, FgaApi.FAILURES.unreadable, status, nil
		end
		return decoded, nil, status, nil
	end

	return nil, classify(status, decoded), status, decoded
end

FgaApi.request = request

--[[ **The permanent diagnostic ADR-25 and the /me comment both ask for.**

     "Am I authenticated" and "did I end up with the credential I THINK I did" are
     different questions. A device link that minted a browser session would answer
     the first correctly and be wrong in a way nothing else here could see, so the
     probe checks `clientType` rather than merely checking for a 200. ]]
function FgaApi.me()
	return request("GET", "/api/v001/me")
end

--[[ The picker's candidate list. ONE Flickr call server-side, however many groups.

     **A `tooManyGroups` failure MUST NOT be softened into a truncated list.**
     ADR-17 refuses on purpose: a picker showing most of a wall hides which entries
     are missing, which is worse than showing none. ]]
function FgaApi.groups()
	return request("GET", "/api/v001/groups")
end

function FgaApi.group(groupId)
	return request("GET", "/api/v001/groups/" .. tostring(groupId))
end

--[[ What the photo is already in, so the picker can PRUNE rather than display and
     disable. Terry, 2026-08-18: add-only, and groups the photo is already in are
     removed from the candidate list. ]]
function FgaApi.photoGroups(photoId)
	return request("GET", "/api/v001/photos/" .. tostring(photoId) .. "/groups")
end

--[[ ADR-20. **Call this and SHOW the result before ever calling `batch`.**

     It answers ADR-04's question for every group in one round trip. Each entry
     comes back as `ready`, `already_in_pool`, `already_queued` or
     `needs_acknowledgement`.

     **`poolsKnown = false` is not "the photo is in no pools".** ADR-04: presence
     proves approval and absence proves nothing. Rendering an unknown as a clean
     `ready` would suppress a warning the server then raises at submit time. ]]
function FgaApi.preflight(photoId, groupIds)
	return request(
		"POST",
		"/api/v001/photos/" .. tostring(photoId) .. "/preflight",
		{ groupIds = groupIds }
	)
end

--[[ The commitment, and the reason this plug-in exists.

     **`acknowledgedModeration` is a LIST, never a flag, and that is ADR-20 in the
     type.** A blanket boolean would let one click acknowledge warnings the person
     never saw. Pass exactly the group ids whose warning was shown and accepted.

     Answers 202 with one entry per group, in the order asked, so a caller can zip
     the reply against its own list. ]]
function FgaApi.batch(photoId, groupIds, acknowledgedModeration)
	return request("POST", "/api/v001/requests/batch", {
		photoId = photoId,
		groupIds = groupIds,
		acknowledgedModeration = acknowledgedModeration,
	})
end

--[[ Read-only, and the user's own rows. `state` is `pending` or `all`. ]]
function FgaApi.queue(state, limit)
	local query = string.format(
		"?state=%s&limit=%d",
		tostring(state or "pending"),
		tonumber(limit) or 50
	)
	return request("GET", "/api/v001/queue" .. query)
end

--[[ One sentence per failure, so a probe or a dialog never has to invent one.

     **Each names what the PERSON can do**, which is the whole reason the failures
     are named rather than numbered. ]]
function FgaApi.explain(failure, detail)
	local F = FgaApi.FAILURES

	if failure == F.notAuthenticated then
		return "Lightroom is not linked to FlickrGroupAddr, or the link expired."
			.. "\n\nRun 'FGA: link this Lightroom to FGA' again."
	elseif failure == F.noFlickr then
		return "Your FlickrGroupAddr account is not connected to Flickr."
			.. "\n\nSign in on the FlickrGroupAddr website to connect it."
	elseif failure == F.tooManyGroups then
		local total = type(detail) == "table" and detail.total or "a lot of"
		return string.format(
			"Your Flickr account is in %s groups, which is more than the picker can"
				.. " show.\n\nFlickrGroupAddr refuses to show a partial list, because you"
				.. " could not tell which groups were missing.",
			tostring(total)
		)
	elseif failure == F.flickrDown then
		return "Flickr did not answer. This is Flickr rather than FlickrGroupAddr."
			.. "\n\nTry again in a few minutes."
	elseif failure == F.transport then
		return "Could not reach flickrgroupaddr.com."
			.. "\n\nCheck your network connection."
			.. (detail and ("\n\nDetail: " .. tostring(detail)) or "")
	elseif failure == F.notAllowed then
		return "The plug-in asked for something it is not allowed to do."
			.. "\n\nThis is a bug in the plug-in. Please report it."
	elseif failure == F.badRequest then
		return "The server rejected the request as malformed."
			.. "\n\nThis is a bug in the plug-in. Please report it."
	elseif failure == F.unreadable then
		return "The server's reply could not be read."
			.. "\n\nThis is a bug in the plug-in. Please report it."
	end

	return "Something unexpected went wrong."
end

return FgaApi
