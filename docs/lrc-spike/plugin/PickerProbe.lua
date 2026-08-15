--[[
  The group picker, built as a MEASUREMENT INSTRUMENT rather than as a UI.

  Two questions decide how the real picker feels, and `docs/LRC-CLIENT-NOTES.md`
  records both as UNMEASURED:

    1. Does rebinding `simple_list.items` clear or corrupt the current selection?
    2. How does a 372-item `simple_list` look and perform, and does `height`
       accept a large value? The reference states a minimum of 80 and names no
       maximum.

  **The merge selection model is correct either way**, which is why it is the
  design regardless of the answer. What differs is the FEEL: a widget that
  visibly drops its highlighting on every keystroke is unpleasant even when the
  model underneath is right.

  SO THIS ANSWERS THEM BY BEING USED. It fills the list with 372 synthetic
  groups, filters in realtime, and reports what the widget actually did.

  NO NETWORK, NO CATALOG WRITES. The group names are generated here. Nothing
  reaches Flickr or FGA, and nothing touches the catalog -- this measures the
  widget, not the workflow.

  `LrTasks.pcall`, never bare `pcall`. Lightroom runs plug-in code as coroutines
  and SDK calls yield; Lua 5.1 cannot yield across a `pcall` boundary. Version
  0.1 of the sibling probe died on exactly that and reported it as a finding.
]]

local LrDialogs = import("LrDialogs")
local LrView = import("LrView")
local LrBinding = import("LrBinding")
local LrFunctionContext = import("LrFunctionContext")
local LrTasks = import("LrTasks")

--[[ 372 is the real number: Terry belonged to 372 groups on 2026-08-15, up from
     330 earlier the same day. The count MUST NOT be cached anywhere, and this
     probe uses it only to reproduce the real list length. ]]
local GROUP_COUNT = 372

local WORDS = {
	"Canada", "Landscapes", "Black and White", "Long Exposure", "Wildlife",
	"Alberta", "Sunrise", "Macro", "Street", "Architecture", "Portraits",
	"Night", "Autumn", "Coastal", "Mountains", "Birds", "Minimalism",
	"Fine Art", "Travel", "Winter", "Reflections", "Urban Decay",
}

--[[ Names are deliberately long and repetitive. A picker that looks fine with
     "Group 12" and falls apart with "Canada - Alberta - Lake Louise (moderated,
     already seen)" has not been tested. ]]
local function makeGroups()
	local groups = {}
	for i = 1, GROUP_COUNT do
		local a = WORDS[(i % #WORDS) + 1]
		local b = WORDS[((i * 7) % #WORDS) + 1]
		groups[i] = {
			id = string.format("%d@N%02d", 1000000 + i, i % 30),
			name = string.format("%s %s - pool %03d", a, b, i),
		}
	end
	return groups
end

--[[ **Lowercased ONCE, not per keystroke.** 372 `:lower()` calls on every
     character typed is waste a precomputed shadow list removes. ]]
local function withLowered(groups)
	for _, g in ipairs(groups) do
		g.lowered = g.name:lower()
	end
	return groups
end

--[[ **`plain = true` is REQUIRED.** Lua's `find` defaults to PATTERN matching,
     so a group name or a search term containing `-`, `(`, `)`, `%` or `.` would
     either match wrongly or throw. Group names contain all of those. ]]
local function matches(group, needle)
	if needle == "" then
		return true
	end
	return group.lowered:find(needle, 1, true) ~= nil
end

local function run()
	LrFunctionContext.callWithContext("fgaPicker", function(context)
		local groups = withLowered(makeGroups())
		local factory = LrView.osFactory()
		local props = LrBinding.makePropertyTable(context)

		props.filter = ""
		props.chosen = {}
		props.items = {}
		props.report = ""

		--[[ **The plug-in owns the selection; the widget does not.**

		     When the filter narrows, groups selected but no longer visible MUST
		     stay selected; when it widens they MUST come back. So `value` is an
		     INPUT and never the source of truth, and the update is a merge:

		         selected = (selected MINUS currentlyVisible) UNION value

		     This is correct whether or not rebinding `items` clears `value`,
		     which is the point -- the model does not depend on the answer. ]]
		local selected = {}
		local visibleIds = {}

		local function selectedCount()
			local n = 0
			for _ in pairs(selected) do
				n = n + 1
			end
			return n
		end

		local function rebuild()
			local items = {}
			local nowVisible = {}
			local needle = (props.filter or ""):lower()

			for _, g in ipairs(groups) do
				if matches(g, needle) then
					items[#items + 1] = { title = g.name, value = g.id }
					nowVisible[g.id] = true
				end
			end

			visibleIds = nowVisible
			props.items = items

			-- Re-present the surviving selection to the widget.
			local stillShown = {}
			for id in pairs(selected) do
				if nowVisible[id] then
					stillShown[#stillShown + 1] = id
				end
			end
			props.chosen = stillShown

			props.report = string.format(
				"showing %d of %d  ·  selected %d",
				#items,
				#groups,
				selectedCount()
			)
		end

		--[[ MERGE, not replace. Everything visible is re-derived from `value`;
		     everything filtered out is left exactly as it was. ]]
		props:addObserver("chosen", function()
			for id in pairs(visibleIds) do
				selected[id] = nil
			end
			for _, id in ipairs(props.chosen or {}) do
				selected[id] = true
			end
			props.report = string.format(
				"showing %d of %d  ·  selected %d",
				#(props.items or {}),
				#groups,
				selectedCount()
			)
		end)

		--[[ **`immediate = true` is what makes filtering realtime.** Without it
		     the binding updates only on commit -- Enter or moving focus away --
		     so a user types `canada`, watches nothing happen, and concludes the
		     box is broken. It fails as a NO-OP rather than an error. ]]
		props:addObserver("filter", function()
			rebuild()
		end)

		rebuild()

		local contents = factory:column({
			bind_to_object = props,
			spacing = factory:control_spacing(),

			factory:static_text({
				title = "Type to filter. Selection MUST survive filtering.",
			}),

			factory:edit_field({
				value = LrView.bind("filter"),
				immediate = true,
				width_in_chars = 40,
				placeholder_string = "filter groups",
			}),

			factory:simple_list({
				items = LrView.bind("items"),
				value = LrView.bind("chosen"),
				allows_multiple_selection = true,
				-- The reference gives a minimum of 80 and names no maximum.
				-- Whether a tall list behaves is one of the two open questions.
				height = 420,
				width = 520,
			}),

			factory:static_text({
				title = LrView.bind("report"),
				fill_horizontal = 1,
			}),
		})

		local button = LrDialogs.presentModalDialog({
			title = string.format("FGA picker probe -- %d groups", GROUP_COUNT),
			contents = contents,
			actionVerb = "Report",
		})

		if button == "ok" then
			local names = {}
			for _, g in ipairs(groups) do
				if selected[g.id] then
					names[#names + 1] = g.name
				end
			end
			table.sort(names)

			local shown = {}
			for i = 1, math.min(#names, 12) do
				shown[i] = "  " .. names[i]
			end
			if #names > 12 then
				shown[#shown + 1] = string.format("  ... and %d more", #names - 12)
			end

			LrDialogs.message(
				string.format("Selected %d of %d", #names, #groups),
				(#names > 0) and table.concat(shown, "\n") or "Nothing selected.",
				"info"
			)
		end
	end)
end

LrTasks.startAsyncTask(function()
	local ok, err = LrTasks.pcall(run)
	if not ok then
		LrDialogs.message("FGA picker probe FAILED", tostring(err), "critical")
	end
end)
