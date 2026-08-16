--[[
  The group picker, version three: TWO LISTS OF CHECKBOXES and two arrows.

  Terry's design, after `simple_list` defeated four attempts at click-to-move:

    "checkboxes for both lists ... check things on left side and click add
     arrow to move right. can check on left and click remove arrow to pull
     left"

  and, when offered a single combined list instead:

    "two lists with checkboxes feels right"
    "I like filtering only impacting left"

  ## Why checkboxes fix what `simple_list` could not

  `simple_list` keeps a POSITIONAL selection through an `items` rebind, and it
  will not fire for a row it already considers selected. After a move, the row
  that slid into the vacated slot was highlighted and DEAD. Four fixes failed:
  `value = {}`, `value = ""`, the reference's own `value_equal` hook, and
  buttons that ignored the selection entirely.

  **A checkbox is a bound boolean.** Toggling it always changes the value, so it
  always fires. There is no "already selected" state for the widget to swallow.
  The whole class of bug disappears rather than being worked around.

  ## The constraint that shapes this file

  **LrView builds its view tree ONCE.** Bindings change values, never structure,
  so rows cannot be added or removed after `presentModalDialog` is called. So
  every group gets a row in BOTH panes up front, and `visible` decides which are
  on screen. `API Reference/modules/LrView view properties.html`: *"True to show
  the view, if the parent view is also visible, or false to hide the view and
  its children."*

  That is 744 views for 372 groups. **Build time is the risk and it is
  unmeasured**, so this dialog times its own construction and says so.

  THE DIALOG IS A STAGING AREA. Nothing reaches Flickr until Save.

  NO NETWORK, NO CATALOG WRITES.
]]

local LrDialogs = import("LrDialogs")
local LrView = import("LrView")
local LrBinding = import("LrBinding")
local LrFunctionContext = import("LrFunctionContext")
local LrTasks = import("LrTasks")
local LrDate = import("LrDate")

local GROUP_COUNT = 372
local ALREADY_IN_COUNT = 8

--[[ U+25CF as raw UTF-8 bytes. `\u{...}` is Lua 5.3 and Lightroom runs 5.1. ]]
local MARK_AT_FLICKR = "\226\151\143 "
local MARK_QUEUED = "+ "

local WORDS = {
	"Canada", "Landscapes", "Black and White", "Long Exposure", "Wildlife",
	"Alberta", "Sunrise", "Macro", "Street", "Architecture", "Portraits",
	"Night", "Autumn", "Coastal", "Mountains", "Birds", "Minimalism",
	"Fine Art", "Travel", "Winter", "Reflections", "Urban Decay",
}

local function makeGroups()
	local groups = {}
	for i = 1, GROUP_COUNT do
		local a = WORDS[(i % #WORDS) + 1]
		local b = WORDS[((i * 7) % #WORDS) + 1]
		groups[i] = {
			id = string.format("%d@N%02d", 1000000 + i, i % 30),
			name = string.format("%s %s - pool %03d", a, b, i),
		}
		groups[i].lowered = groups[i].name:lower()
	end
	table.sort(groups, function(x, y)
		if x.lowered == y.lowered then
			return x.id < y.id
		end
		return x.lowered < y.lowered
	end)
	return groups
end

--[[ **`plain = true` is REQUIRED.** Lua's `find` defaults to PATTERN matching,
     and real group names contain `-`, `(`, `)`, `%` and `.`. ]]
local function matches(group, needle)
	if needle == "" then
		return true
	end
	return group.lowered:find(needle, 1, true) ~= nil
end

local function run()
	LrFunctionContext.callWithContext("fgaCheckboxPicker", function(context)
		local started = LrDate.currentTime()
		local groups = makeGroups()

		--[[ Simulates `GET /api/v001/photos/:photoId/groups`, which FGA proxies
		     because the plug-in deliberately holds no Flickr credentials. ]]
		local atFlickr = {}
		for i = 1, ALREADY_IN_COUNT do
			atFlickr[groups[((i * 43) % GROUP_COUNT) + 1].id] = true
		end

		local selected = {}
		for id in pairs(atFlickr) do
			selected[id] = true
		end

		local factory = LrView.osFactory()
		local props = LrBinding.makePropertyTable(context)

		props.filter = ""
		props.leftStats = ""
		props.rightStats = ""
		props.pending = ""
		props.buildNote = ""

		--[[ Four properties per group. Named rather than nested so a binding key
		     is a plain string, which is what `LrView.bind` wants. ]]
		local function keyLeftVisible(id)
			return "lv_" .. id
		end
		local function keyRightVisible(id)
			return "rv_" .. id
		end
		local function keyLeftChecked(id)
			return "lc_" .. id
		end
		local function keyRightChecked(id)
			return "rc_" .. id
		end

		for _, g in ipairs(groups) do
			props[keyLeftVisible(g.id)] = not selected[g.id]
			props[keyRightVisible(g.id)] = selected[g.id] == true
			props[keyLeftChecked(g.id)] = false
			props[keyRightChecked(g.id)] = false
		end

		local function counts()
			local total, adds, removes = 0, 0, 0
			for id in pairs(selected) do
				total = total + 1
				if not atFlickr[id] then
					adds = adds + 1
				end
			end
			for id in pairs(atFlickr) do
				if not selected[id] then
					removes = removes + 1
				end
			end
			return total, adds, removes
		end

		--[[ **Visibility is recomputed; the view tree never changes.** The filter
		     touches the LEFT pane only -- Terry: *"I like filtering only impacting
		     left"*. A selected group is therefore never hidden, which is the
		     property that the original single-list picker lost. ]]
		local function refresh()
			local needle = (props.filter or ""):lower()
			local shown, hidden = 0, 0

			for _, g in ipairs(groups) do
				local isSelected = selected[g.id] == true
				local showLeft = (not isSelected) and matches(g, needle)

				props[keyLeftVisible(g.id)] = showLeft
				props[keyRightVisible(g.id)] = isSelected

				if isSelected then
					-- Not counted either way: the left pane is the only filtered one.
				elseif showLeft then
					shown = shown + 1
				else
					hidden = hidden + 1
				end
			end

			local total, adds, removes = counts()
			props.leftStats = string.format(
				"Groups displayed: %d   \226\128\162   Groups hidden by filter: %d",
				shown,
				hidden
			)
			props.rightStats =
				string.format("Number of groups currently selected: %d", total)

			if adds == 0 and removes == 0 then
				props.pending = "No changes staged."
			else
				props.pending = string.format(
					"Staged: %d to add, %d to REMOVE from Flickr. Nothing is sent until you click Save.",
					adds,
					removes
				)
			end
		end

		--[[ **The arrows act on every CHECKED row at once**, which is the point of
		     checkboxes over a selection: check five, click once, five move.

		     Each moved row's checkbox is cleared, so the panes never open holding
		     a check the user already spent. ]]
		local function addChecked()
			for _, g in ipairs(groups) do
				if props[keyLeftChecked(g.id)] then
					selected[g.id] = true
					props[keyLeftChecked(g.id)] = false
				end
			end
			refresh()
		end

		local function removeChecked()
			for _, g in ipairs(groups) do
				if props[keyRightChecked(g.id)] then
					selected[g.id] = nil
					props[keyRightChecked(g.id)] = false
				end
			end
			refresh()
		end

		--[[ **`immediate = true` is what makes filtering realtime.** Without it the
		     binding updates only on commit, and it fails as a NO-OP rather than as
		     an error. ]]
		props:addObserver("filter", function()
			refresh()
		end)

		refresh()

		local paneWidth = 320
		local paneHeight = 420

		local leftRows = {}
		local rightRows = {}
		for i, g in ipairs(groups) do
			leftRows[i] = factory:checkbox({
				title = g.name,
				value = LrView.bind(keyLeftChecked(g.id)),
				visible = LrView.bind(keyLeftVisible(g.id)),
				width = paneWidth - 30,
			})
			--[[ The marker carries what color cannot: a row already at Flickr means
			     a REMOVAL if it is unchecked and moved left. ]]
			rightRows[i] = factory:checkbox({
				title = (atFlickr[g.id] and MARK_AT_FLICKR or MARK_QUEUED) .. g.name,
				value = LrView.bind(keyRightChecked(g.id)),
				visible = LrView.bind(keyRightVisible(g.id)),
				width = paneWidth - 30,
			})
		end

		local contents = factory:column({
			bind_to_object = props,
			spacing = factory:control_spacing(),

			factory:static_text({
				title = "Check groups, then use the arrows. The filter searches the left list only.",
			}),

			factory:edit_field({
				value = LrView.bind("filter"),
				immediate = true,
				width_in_chars = 40,
				placeholder_string = "Filter unselected groups",
			}),

			factory:row({
				spacing = factory:control_spacing(),

				factory:column({
					spacing = 4,
					factory:static_text({ title = "Unselected groups" }),
					factory:scrolled_view({
						width = paneWidth,
						height = paneHeight,
						factory:column({ spacing = 2, unpack(leftRows) }),
					}),
					factory:static_text({
						title = LrView.bind("leftStats"),
						width = paneWidth,
					}),
				}),

				factory:column({
					spacing = 10,
					factory:static_text({ title = " " }),
					factory:push_button({
						title = "Add  -->",
						width = 100,
						action = addChecked,
					}),
					factory:push_button({
						title = "<--  Remove",
						width = 100,
						action = removeChecked,
					}),
				}),

				factory:column({
					spacing = 4,
					factory:static_text({ title = "Selected groups" }),
					factory:scrolled_view({
						width = paneWidth,
						height = paneHeight,
						factory:column({ spacing = 2, unpack(rightRows) }),
					}),
					factory:static_text({
						title = LrView.bind("rightStats"),
						width = paneWidth,
					}),
				}),
			}),

			factory:static_text({
				title = MARK_AT_FLICKR
					.. "Already in this group at Flickr   \226\128\162   "
					.. MARK_QUEUED
					.. "Will be added",
			}),

			factory:static_text({
				title = LrView.bind("pending"),
				fill_horizontal = 1,
			}),

			--[[ **744 views is the risk in this design, so the dialog measures
			     itself** rather than leaving "it felt slow" as the only evidence. ]]
			factory:static_text({
				title = LrView.bind("buildNote"),
				fill_horizontal = 1,
			}),
		})

		props.buildNote = string.format(
			"Built %d rows in %.0f ms.",
			#groups * 2,
			(LrDate.currentTime() - started) * 1000
		)

		local button = LrDialogs.presentModalDialog({
			title = string.format("FGA group picker -- %d groups", GROUP_COUNT),
			contents = contents,
			actionVerb = "Save",
		})

		if button ~= "ok" then
			return
		end

		local adds, removes = {}, {}
		for _, g in ipairs(groups) do
			if selected[g.id] and not atFlickr[g.id] then
				adds[#adds + 1] = g.name
			elseif atFlickr[g.id] and not selected[g.id] then
				removes[#removes + 1] = g.name
			end
		end

		local function block(label, names, note)
			if #names == 0 then
				return string.format("%s: none", label)
			end
			local lines = { string.format("%s (%d)%s:", label, #names, note or "") }
			for i = 1, math.min(#names, 10) do
				lines[#lines + 1] = "  " .. names[i]
			end
			if #names > 10 then
				lines[#lines + 1] = string.format("  ... and %d more", #names - 10)
			end
			return table.concat(lines, "\n")
		end

		LrDialogs.message(
			"What the real client would send",
			block("Add", adds, " -- one batch call")
				.. "\n\n"
				.. block("Remove", removes, " -- each throws away a moderator approval"),
			"info"
		)
	end)
end

LrTasks.startAsyncTask(function()
	local ok, err = LrTasks.pcall(run)
	if not ok then
		LrDialogs.message("FGA checkbox picker FAILED", tostring(err), "critical")
	end
end)
