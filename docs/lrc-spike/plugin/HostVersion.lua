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
			summary = "Lightroom version unknown " .. WARN,
			detail = "The plug-in could not read the Lightroom version, so it cannot "
				.. "say whether this release was tested. Treating it as untested.",
		}
	end

	if hostMajor == tested then
		return {
			supported = true,
			badge = TICK,
			--[[ **No color, deliberately.** Terry, 2026-08-16, looking at the render:
			     *"Green text doesn't work."* He is right -- green on the dialog's
			     light gray is poor contrast, and LrView offers no background fill on
			     a `static_text` to put white on instead. **So the good news is plain,
			     and only the warning is colored.** That is the better hierarchy
			     anyway: a badge that shouts on success has nothing left for the case
			     that matters. ]]
			summary = "Supported " .. TICK,
			detail = string.format("Tested against Lightroom Classic %d.", tested),
		}
	end

	local direction = hostMajor > tested and "newer than" or "older than"
	return {
		supported = false,
		badge = WARN,
		--[[ **No color here. `classify` stays SEMANTIC and the probe owns
		     presentation.** An earlier version carried an RGB triple and a bold flag
		     through this table, which put a rendering decision inside the function
		     whose self-test is supposed to be about meaning. ]]
		summary = "Major version unsupported " .. WARN,
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

--[[ **US road-sign warning yellow**, which is roughly Pantone 116 / #FFCC00. Black
     on this is the highest-contrast warning pairing in common use, and it is what
     Terry asked for: *"black text on high-contrast alert yellow, similar to US road
     signs that are warnings."*

     **A colored PANEL is possible, and only just.** `background_color` exists on
     exactly three views -- `scrolled_view`, `catalog_photo` and `picture`'s frame --
     and on nothing else. Read from the reference 2026-08-16 by sweeping every
     documented factory method, because "LrView cannot fill a background" was the
     answer until the sweep found the one that can.

     **`scrolled_view` is usable because its scrollbars are optional.**
     `horizontal_scroller` and `vertical_scroller` are documented Booleans that
     default to true. Without them this would be a yellow panel wearing two grayed
     scrollbars on Windows. ]]
HostVersion.WARNING_FILL = { 1.0, 0.80, 0.0 }

--[[ **Dark green, so WHITE text on it clears WCAG AA.** Roughly #006B2E, which is
     about a 6:1 contrast ratio against white.

     **A lighter, prettier green would fail the only job it has.** Terry has already
     rejected green once here -- as TEXT on the light dialog -- and the fix both
     times is the same: the color goes behind the text, and it goes dark enough that
     white sits on it cleanly. ]]
HostVersion.SUPPORTED_FILL = { 0.0, 0.42, 0.18 }

--[[ **The minimum `scrolled_view` height, and it is a floor rather than a choice:**
     *"Will not be allowed to be smaller than 80."* A one-line badge in an 80px
     panel is chunky, which for a warning banner is the point. ]]
HostVersion.BANNER_HEIGHT = 80

--[[ Takes one of the two fill tables above. Kept here rather than in the probe so
     the RGB values and the reasoning for them live together. ]]
function HostVersion.fillColor(rgb)
	return LrColor(rgb[1], rgb[2], rgb[3])
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
