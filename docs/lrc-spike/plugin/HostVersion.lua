--[[
  Which Lightroom is this, and was the plug-in ever TESTED against it? ADR-25.

  **This is a NUDGE, not a gate.** Terry, 2026-08-16: *"It's a nudge to future
  Terry to recompile per LR major version, test, then upgrade."* The plug-in keeps
  working on an untested major. It just stops claiming it was tested there.

  ## The constant is a CLAIM A HUMAN MAKES, and that is the whole mechanism

  `TESTED_AGAINST_MAJOR` does not describe what the code can do. It records that
  somebody ran this plug-in against that Lightroom major and watched it work.

  **So it MUST NOT be derived, and it MUST NOT be bumped speculatively.** Reading
  the host version and assigning it to the constant would make the badge always
  green and mean nothing -- the check would assert only that Lightroom is the
  version Lightroom says it is. **Bumping it is the last step of testing, never
  the first step of supporting.**

  ## Why MAJOR only

  Adobe lands breaking SDK changes on majors. Terry runs 15.5 against an SDK
  documented at 15.3 and everything works, so a check that compared minors would
  cry wolf on the normal state of his machine -- and a warning that fires when
  nothing is wrong is a warning he learns to scroll past.

  ## It fails toward UNSUPPORTED, deliberately

  If `versionTable()` throws, or returns something without a numeric `major`, the
  answer is "unknown" and the badge is the warning one. **A check that cannot read
  the version MUST NOT report success**, which is the same rule this project
  applies to a grep that finds nothing and a mutation whose anchor drifted.

  ## This does NOT replace `LrSdkMinimumVersion`, and the two point opposite ways

  | | Direction | Behavior |
  |---|---|---|
  | `Info.lua`'s `LrSdkMinimumVersion` | Lightroom OLDER than the SDK we target | **Refuses to load.** Fails CLOSED |
  | This file | Lightroom NEWER than we tested | **Loads and warns.** Fails OPEN |

  **The asymmetry is correct.** Older cannot work -- the APIs are absent. Newer
  probably works and is merely unproven, so refusing would strand Terry on release
  day for a problem that usually does not exist.
]]

local LrApplication = import("LrApplication")
local LrColor = import("LrColor")
local LrTasks = import("LrTasks")

local HostVersion = {}

--[[ **The integer somebody TESTED against.** Bump it after testing on a new
     Lightroom major, never before. See the header. ]]
HostVersion.TESTED_AGAINST_MAJOR = 15

--[[ Literal UTF-8 rather than escapes. **Lua 5.1 has no `\u{}`** -- that is a 5.3
     escape and a syntax error here -- and spike 0.9 tried decimal byte escapes,
     which something in the toolchain read as OCTAL and rendered as garbage.

     **THE WORDS CARRY THE MEANING AND THE GLYPH IS DECORATION.** If LrView
     renders these as boxes the badge still reads correctly, which is the only
     reason it is safe to use one at all. ]]
local TICK = "✅"
local WARN = "⚠"

--[[ Pure, so it can be self-tested without Lightroom. Takes the host major and
     returns everything the UI needs. ]]
function HostVersion.classify(hostMajor)
	local tested = HostVersion.TESTED_AGAINST_MAJOR

	if type(hostMajor) ~= "number" then
		return {
			supported = false,
			badge = WARN,
			colorName = "yellow",
			summary = "Lightroom version unknown " .. WARN,
			detail = "The plug-in could not read the Lightroom version, so it cannot "
				.. "say whether this release was tested. Treating it as untested.",
		}
	end

	if hostMajor == tested then
		return {
			supported = true,
			badge = TICK,
			colorName = "green",
			summary = "supported " .. TICK,
			detail = string.format("Tested against Lightroom Classic %d.", tested),
		}
	end

	local direction = hostMajor > tested and "newer than" or "older than"
	return {
		supported = false,
		badge = WARN,
		colorName = "yellow",
		summary = "major version unsupported " .. WARN,
		detail = string.format(
			"This is Lightroom Classic %d, %s the %d this plug-in was tested "
				.. "against. It will probably still work. Re-test on %d and bump "
				.. "TESTED_AGAINST_MAJOR in HostVersion.lua once it does.",
			hostMajor,
			direction,
			tested,
			hostMajor
		),
	}
end

--[[ `LrColor` takes named colors -- confirmed in the SDK reference, which lists
     "yellow" and "green" among them. Kept out of `classify` so that function
     stays pure and testable. ]]
function HostVersion.color(classification)
	return LrColor(classification.colorName)
end

--[[ **MUST be called inside an `LrTasks` task.** `LrTasks.pcall` is used rather
     than bare `pcall` because Lua 5.1 cannot yield across a bare one, and
     assuming an SDK call does not yield is how spike 0.1 died. ]]
function HostVersion.hostMajor()
	local ok, versions = LrTasks.pcall(function()
		return LrApplication.versionTable()
	end)
	if not ok or type(versions) ~= "table" then
		return nil
	end
	return tonumber(versions.major)
end

--[[ The whole line a person reads, e.g.
     "Lightroom Classic 15.5.0  (supported ✅)" ]]
function HostVersion.describe()
	local ok, versions = LrTasks.pcall(function()
		return LrApplication.versionTable()
	end)

	local major = (ok and type(versions) == "table") and tonumber(versions.major)
		or nil
	local classification = HostVersion.classify(major)

	local versionText = "Lightroom Classic (version unavailable)"
	if ok and type(versions) == "table" then
		versionText = string.format(
			"Lightroom Classic %s.%s.%s",
			tostring(versions.major),
			tostring(versions.minor),
			tostring(versions.revision)
		)
		--[[ **`build_version` is a STRING and only exists from 8.3.0.** Before that
		     it was a 6- or 7-digit number, and at 8.3.0 it became a date as
		     YYYYMMDDHHmm. Anything treating it as a number is wrong twice over, so
		     it is concatenated and never compared. ]]
		if versions.build_version ~= nil then
			versionText = versionText .. " build " .. tostring(versions.build_version)
		end
	end

	classification.versionText = versionText
	classification.line = versionText .. "  (" .. classification.summary .. ")"
	return classification
end

--[[ **Proves the classifier can say BOTH answers before it is believed.** A badge
     that is always green is indistinguishable from a plug-in that is always
     supported, and only one of those is a fact. Same guard `EntropyProbe.lua`
     puts on its UUID validator and `build-diagram.py` on its collision detector. ]]
function HostVersion.selfTest()
	local tested = HostVersion.TESTED_AGAINST_MAJOR
	local cases = {
		{ tested, true, "the tested major is supported" },
		{ tested + 1, false, "a newer major is not" },
		{ tested - 1, false, "an older major is not" },
		{ nil, false, "an unreadable version is not" },
		{ "15", false, "a STRING major is not a number and MUST NOT pass" },
	}

	local failures = {}
	for _, case in ipairs(cases) do
		local got = HostVersion.classify(case[1]).supported
		if got ~= case[2] then
			failures[#failures + 1] = string.format(
				"%s -- got %s, want %s",
				case[3],
				tostring(got),
				tostring(case[2])
			)
		end
	end

	if #failures == 0 then
		return true, string.format("Self-test: %d/%d passed", #cases, #cases)
	end
	return false, "SELF-TEST FAILED:\n  " .. table.concat(failures, "\n  ")
end

return HostVersion
