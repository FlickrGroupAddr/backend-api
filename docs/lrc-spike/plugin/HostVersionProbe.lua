--[[
  Shows which Lightroom this is, and whether the plug-in was tested against it.
  ADR-25.

  **A nudge to future Terry**, in his words: *"recompile per LR major version,
  test, then upgrade."* Major versions are yearly, so this asks for one re-test a
  year and nothing in between.

  READ-ONLY. No network, no catalog, no writes. It reads one SDK value and does
  arithmetic on it.

  **The self-test runs FIRST and its result is shown**, because a badge that is
  always green is indistinguishable from a plug-in that is always supported.
]]

local LrColor = import("LrColor")
local LrDialogs = import("LrDialogs")
local LrTasks = import("LrTasks")
local LrView = import("LrView")

local HostVersion = require("HostVersion")

local function run()
	local passed, selfTestMessage = HostVersion.selfTest()
	local host = HostVersion.describe()

	local f = LrView.osFactory()

	--[[ Adobe's own samples pair `text_color` with `static_text` -- see
	     `helloworld.lrdevplugin/RadioButtons.lua` and `flickr.lrdevplugin/FlickrAPI.lua`.
	     Copied rather than invented, because an unknown LrView attribute fails the
	     WHOLE dialog rather than rendering plain. ]]
	local contents = f:column({
		spacing = f:control_spacing(),

		--[[ **`<system/bold>` is documented** -- `LrView control view properties`
		     names it. `docs/LRC-CLIENT-NOTES.md` recorded it as deliberately NOT
		     used, because at the time the SDK was not on this machine and an
		     unknown LrView attribute fails the WHOLE dialog rather than rendering
		     plain. The reference is on hand now, which is exactly the condition
		     that note set for using it. ]]
		f:static_text({
			title = host.versionText,
			font = "<system/bold>",
		}),

		--[[ **THE GOOD NEWS IS PLAIN AND THE WARNING IS A ROAD SIGN.**

		     Terry, on the first render: *"Green text doesn't work."* Then:
		     *"black text on high-contrast alert yellow, similar to US road signs
		     that are warnings."*

		     Supported takes the platform default color -- a badge that shouts on
		     success has nothing left for the case that matters. Unsupported gets a
		     filled panel, because black on #FFCC00 is the highest-contrast warning
		     pairing in common use and it survives a bad display.

		     **`scrolled_view` is the ONLY view here that can hold a fill**, and it
		     is usable only because `horizontal_scroller` and `vertical_scroller` are
		     documented Booleans. Left at their default of true this would be a
		     yellow panel wearing two grayed-out scrollbars on Windows. ]]
		host.supported
				and f:static_text({
					title = "(" .. host.summary .. ")",
				})
			or f:scrolled_view({
				background_color = HostVersion.fillColor(),
				horizontal_scroller = false,
				vertical_scroller = false,
				width = 520,
				height = HostVersion.BANNER_HEIGHT,

				f:static_text({
					title = host.summary,
					text_color = LrColor(0, 0, 0),
					font = "<system/bold>",
				}),
			}),

		f:separator({ fill_horizontal = 1 }),

		--[[ **`wraps` is an EDIT FIELD property and MUST NOT be used here.** It is
		     documented under `LrView edit view properties`; `LrView text
		     properties` -- the page `static_text` draws from -- lists only
		     `height_in_lines`, `width_in_chars` and `width_in_digits`, and says
		     outright: *"If height_in_lines is set to -1, and width or
		     width_in_digits or width_in_chars is specified, text wraps."*

		     So -1 IS the wrap instruction. I wrote `wraps = true` first, which
		     would have failed the entire dialog rather than being ignored. ]]
		f:static_text({
			title = host.detail,
			height_in_lines = -1,
			width_in_chars = 60,
		}),

		f:separator({ fill_horizontal = 1 }),

		--[[ **Shown whether it passed or failed.** A self-test whose result is
		     hidden on success is a self-test nobody can confirm ran. ]]
		f:static_text({
			title = selfTestMessage,
			text_color = passed and LrColor("gray") or LrColor("red"),
		}),

		f:static_text({
			title = string.format(
				"TESTED_AGAINST_MAJOR = %d, in HostVersion.lua",
				HostVersion.TESTED_AGAINST_MAJOR
			),
			text_color = LrColor("gray"),
		}),

		--[[ **A warning nobody can see until the day it fires is a warning nobody
		     has reviewed.** On a supported major the banner above never renders, so
		     its design would go unexamined for a year and then appear for the first
		     time on the morning Terry least wants a surprise.

		     Shown ONLY when the real badge is the plain one, and labeled, so it can
		     never be mistaken for the live state. Same argument as the toolchain
		     banner: the loud shape has to be earned, and it has to have been LOOKED
		     at before it is earned. ]]
		host.supported and f:static_text({
			title = "Preview -- what an untested major will look like:",
			text_color = LrColor("gray"),
		}) or f:spacer({ height = 1 }),

		host.supported
				and f:scrolled_view({
					background_color = HostVersion.fillColor(),
					horizontal_scroller = false,
					vertical_scroller = false,
					width = 520,
					height = HostVersion.BANNER_HEIGHT,

					f:static_text({
						title = HostVersion.classify(
							HostVersion.TESTED_AGAINST_MAJOR + 1
						).summary,
						text_color = LrColor(0, 0, 0),
						font = "<system/bold>",
					}),
				})
			or f:spacer({ height = 1 }),
	})

	LrDialogs.presentModalDialog({
		title = "FGA: Lightroom version",
		contents = contents,
		actionVerb = "Close",
		cancelVerb = "< exclude >",
	})
end

LrTasks.startAsyncTask(function()
	--[[ Three outcomes, not two. A probe whose own failure reads as a finding is
	     how spike 0.1 nearly killed the publish-service design. ]]
	local ok, err = LrTasks.pcall(run)
	if not ok then
		LrDialogs.message(
			"FGA version probe INCONCLUSIVE -- the probe itself failed",
			tostring(err),
			"critical"
		)
	end
end)
