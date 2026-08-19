--[[
  The device-link flow, driven by a person. ADR-24, end to end.

  This is the UI half. `DeviceLink.lua` holds the flow and imports no dialog; this
  file holds every dialog and no HTTP. Same split as HostVersion / HostVersionProbe.

  WHAT IT DOES, and it is the first thing in this plug-in that WRITES anything:

    * Calls the live Worker at flickrgroupaddr.com. No Flickr call, ever.
    * Opens the default browser at the server's own approval URL.
    * Stores one session token in the OS keychain via `LrPasswords`.

  It touches no photo, no collection and no catalog field.

  ADR-24 SAYS THE CONFIRMATION STEP IS THE SECURITY CONTROL, so this file MUST
  show the userCode BEFORE opening the browser and MUST NOT auto-approve anything.
  A device flow is phished by getting somebody to approve a code that is on the
  ATTACKER'S screen; the whole defense is the person comparing two screens.
]]

local LrDialogs = import("LrDialogs")
local LrFunctionContext = import("LrFunctionContext")
local LrTasks = import("LrTasks")

local DeviceLink = require("DeviceLink")

--[[ Shown while waiting. The code stays on screen the entire time, because the
     person needs to compare it against the web page they are looking at. ]]
local function waitCaption(session, status)
	local friendly = status
	if status == "pending" then
		friendly = "Waiting for you to approve it in the browser"
	elseif status == "slow_down" then
		friendly = "Waiting -- the server asked us to slow down"
	elseif status == "retrying" then
		friendly = "Waiting -- the network hiccupped, still trying"
	end

	return string.format("Code: %s\n\n%s", session.userCode, friendly)
end

--[[ Every outcome gets a sentence a photographer can act on.

     **`denied` is deliberately NOT an error dialog.** ADR-01's habit, pointed at
     this surface: a person said no, and telling them that went WRONG would be a
     lie about their own decision. It reports as information, and the plug-in
     stops. ]]
local function report(status, payload)
	if status == "approved" then
		LrDialogs.message(
			"Lightroom is linked to FlickrGroupAddr",
			"The link worked, and the credential is stored in your operating system's"
				.. " keychain.\n\nYou will not have to do this again unless you sign out.",
			"info"
		)
	elseif status == "denied" then
		LrDialogs.message(
			"Link declined",
			"You denied the request in the browser, so Lightroom was not linked."
				.. "\n\nNothing was stored. Run this again if you change your mind.",
			"info"
		)
	elseif status == "canceled" then
		LrDialogs.message(
			"Link canceled",
			"You stopped waiting, so Lightroom was not linked. Nothing was stored.",
			"info"
		)
	elseif status == "expired" then
		LrDialogs.message(
			"That code expired",
			"The code timed out before it was approved. Run this again to get a new one.",
			"info"
		)
	elseif status == "timeout" then
		LrDialogs.message(
			"Stopped waiting",
			"Lightroom waited 15 minutes and the code was never approved."
				.. "\n\nRun this again to get a new one.",
			"info"
		)
	else
		LrDialogs.message(
			"Could not link Lightroom",
			tostring(payload or "The server did not answer as expected."),
			"critical"
		)
	end
end

local function run()
	--[[ **Say what is already there before asking for another.** A person who
	     re-runs this by accident should not silently mint a second credential. ]]
	local existing = DeviceLink.loadToken()
	if existing ~= nil then
		--[[ **Three answers, because two of them are not the same "no".** Leaving it
		     alone and forgetting it are opposite intentions, and a dialog that offers
		     only "link again" or "cancel" gives a person no way to sign out at all --
		     which would leave `DeviceLink.clearToken` unreachable. ]]
		local again = LrDialogs.confirm(
			"Lightroom is already linked",
			"This plug-in already holds an FGA credential."
				.. "\n\nLinking again replaces it. The old one keeps working until it expires.",
			"Link again",
			"Leave it alone",
			"Forget the stored credential"
		)

		if again == "other" then
			DeviceLink.clearToken()
			--[[ **Local only, and the wording MUST say so.** Clearing the keychain
			     entry does not revoke the session server-side, and telling somebody
			     they are signed out everywhere would be false. Revocation is a
			     different endpoint and this plug-in does not call it. ]]
			LrDialogs.message(
				"Forgotten on this computer",
				"Lightroom no longer holds the credential."
					.. "\n\nThe session itself is not revoked, and it stays valid until it"
					.. " expires. Sign out on the FlickrGroupAddr website to end it everywhere.",
				"info"
			)
			return
		end

		if again ~= "ok" then
			return
		end
	end

	local session, err = DeviceLink.start()
	if session == nil then
		report("failed", err)
		return
	end

	--[[ **The code is shown BEFORE the browser opens, and the person presses the
	     button.** ADR-24: prefilling a code is fine, approving from a link is the
	     attack. This dialog is the Lightroom half of "do these two screens
	     match". ]]
	local go = LrDialogs.confirm(
		"Approve this code in your browser",
		string.format(
			"Lightroom will open your browser at FlickrGroupAddr.\n\n"
				.. "Your code is:\n\n        %s\n\n"
				.. "Check the browser shows the SAME code before you approve it."
				.. " If a code ever arrives by email or message, do not approve it.",
			session.userCode
		),
		"Open the approval page",
		"Cancel"
	)

	if go ~= "ok" then
		report("canceled")
		return
	end

	DeviceLink.openApprovalPage(session)

	local status, payload
	LrFunctionContext.callWithContext("fga-device-link", function(context)
		local progress = LrDialogs.showModalProgressDialog({
			title = "Linking Lightroom to FlickrGroupAddr",
			caption = waitCaption(session, "pending"),
			cancelable = true,
			functionContext = context,
		})

		--[[ There is no meaningful percentage here -- the plug-in is waiting on a
		     human, and a bar that crept along would be inventing progress. ]]
		progress:setIndeterminate()

		status, payload = DeviceLink.await(session, {
			isCanceled = function()
				return progress:isCanceled()
			end,
			onTick = function(reported)
				progress:setCaption(waitCaption(session, reported))
			end,
		})

		progress:done()
	end)

	if status == "approved" then
		DeviceLink.saveToken(payload)
	end

	report(status, payload)
end

LrTasks.startAsyncTask(function()
	local ok, err = LrTasks.pcall(run)
	if not ok then
		LrDialogs.message("FGA device link FAILED", tostring(err), "critical")
	end
end)
