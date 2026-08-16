--[[
  The group picker, version two: TWO LISTS, and a row hops between them.

  Terry replaced the single filtered list after driving version one. He typed
  "canada", watched four selections vanish from view, and named the defect: a
  list that shows what you have chosen cannot hide what you have chosen. The
  merge model underneath was correct and the screen was wrong, which is the
  worst combination -- a user cannot see a correct model.

  HIS DESIGN, in his words:

    "Left side is alphabetical (case insensitive) sorting of groups with the
     filtering applied titled 'Unselected groups'. Right side is 'selected
     groups'. As we click rows on either side, the group moves to the other
     side."

  And the part that turns it from a picker into a membership editor:

    "I may use the plugin to add/remove groups from pics that already have been
     added to some groups. In that case the groups the pic is ALREADY in should
     be pre-populated on the list to the right."

  SO THE RIGHT LIST IS MEMBERSHIP, NOT A SHOPPING BASKET. It opens holding what
  Flickr already reports for this photo, and what the user adds during the
  session. Those two are different kinds of row and MUST be told apart.

  THE DIALOG IS A STAGING AREA. Nothing reaches Flickr until the user commits.
  That is what makes clicking free, and it is the answer to the ADR-01 worry:
  removing a group a moderator approved would throw that approval away, and a
  stray click MUST NOT be able to do it. Here a stray click costs one more
  click, because the removal is not real until the dialog closes on OK.

  NO NETWORK, NO CATALOG WRITES. Group names and the "already in" set are
  generated here. This measures the widget and the interaction, not the
  workflow.

  `LrTasks.pcall`, never bare `pcall`. Lightroom runs plug-in code as coroutines
  and SDK calls yield; Lua 5.1 cannot yield across a `pcall` boundary.
]]

local LrDialogs = import("LrDialogs")
local LrView = import("LrView")
local LrBinding = import("LrBinding")
local LrFunctionContext = import("LrFunctionContext")
local LrTasks = import("LrTasks")

--[[ 372 is the real number: Terry belonged to 372 groups on 2026-08-15. The
     count MUST NOT be cached anywhere; this probe uses it only to reproduce a
     realistic list length. ]]
local GROUP_COUNT = 372

--[[ How many groups the photo is already in when the dialog opens. In the real
     client this comes from `flickr.photos.getAllContexts`, which FGA already
     calls -- so pre-population needs no new endpoint. ]]
local ALREADY_IN_COUNT = 8

--[[ `simple_list` takes plain strings and gives NO per-row styling -- no color,
     no font, no icon. Verified against the SDK reference on 2026-08-15. So the
     distinction has to live inside the string itself. ]]
-- U+25CF BLACK CIRCLE written as raw UTF-8 BYTES. The `\u{...}` form is Lua 5.3
-- and Lightroom runs 5.1, where it is a SYNTAX ERROR rather than a bad glyph --
-- so the whole file would fail to load, not just render the mark wrong.
local MARK_AT_FLICKR = "\226\151\143 "
local MARK_QUEUED = "+ "

--[[ **`value` is an ARRAY, and the SDK reference says so plainly:** *"The current
     control value; an array of the values corresponding to each selected list
     item, if any."* Two earlier attempts wrote a bare string and an empty table
     and neither cleared the highlight -- the string because it is the wrong TYPE
     and the widget ignored it, the table because nothing told the widget how to
     match it.

     **`value_equal` is the documented hook that decides which row is selected:**
     *"A function called to compare the control value to the value of each item in
     turn... If no item returns true, no item is selected in the list."*

     So a sentinel that matches no item, plus a comparison that refuses it, is the
     mechanism the reference describes rather than a trick. ]]
local NO_SELECTION = "__fga_no_selection__"


local WORDS = {
	"Canada", "Landscapes", "Black and White", "Long Exposure", "Wildlife",
	"Alberta", "Sunrise", "Macro", "Street", "Architecture", "Portraits",
	"Night", "Autumn", "Coastal", "Mountains", "Birds", "Minimalism",
	"Fine Art", "Travel", "Winter", "Reflections", "Urban Decay",
}

--[[ Names are deliberately long and repetitive. A picker that looks fine with
     "Group 12" and falls apart with a real pool name has not been tested. ]]
local function makeGroups()
	local groups = {}
	for i = 1, GROUP_COUNT do
		local a = WORDS[(i % #WORDS) + 1]
		local b = WORDS[((i * 7) % #WORDS) + 1]
		groups[i] = {
			id = string.format("%d@N%02d", 1000000 + i, i % 30),
			name = string.format("%s %s - pool %03d", a, b, i),
		}
		-- **Lowercased ONCE.** 372 `:lower()` calls per keystroke is waste a
		-- precomputed shadow field removes.
		groups[i].lowered = groups[i].name:lower()
	end
	return groups
end

--[[ **`plain = true` is REQUIRED.** Lua's `find` defaults to PATTERN matching,
     so a name or a search term containing `-`, `(`, `)`, `%` or `.` would match
     wrongly or throw. Real group names contain all of those. ]]
local function matches(group, needle)
	if needle == "" then
		return true
	end
	return group.lowered:find(needle, 1, true) ~= nil
end

--[[ Case-insensitive ascending, on both sides. Terry asked for it explicitly,
     and it is what makes a moved row land where the eye expects. ]]
local function byName(x, y)
	if x.lowered == y.lowered then
		return x.id < y.id
	end
	return x.lowered < y.lowered
end

local function run()
	LrFunctionContext.callWithContext("fgaTransferPicker", function(context)
		local groups = makeGroups()
		local byId = {}
		for _, g in ipairs(groups) do
			byId[g.id] = g
		end

		--[[ Simulates `flickr.photos.getAllContexts`. Spread across the list so
		     the right pane is not a contiguous alphabetical block. ]]
		local atFlickr = {}
		for i = 1, ALREADY_IN_COUNT do
			atFlickr[groups[((i * 43) % GROUP_COUNT) + 1].id] = true
		end

		-- The photo's membership as the dialog currently proposes it.
		local selected = {}
		for id in pairs(atFlickr) do
			selected[id] = true
		end

		local factory = LrView.osFactory()
		local props = LrBinding.makePropertyTable(context)

		props.filter = ""
		props.leftItems = {}
		props.rightItems = {}
		props.leftStats = ""
		props.rightStats = ""
		props.pending = ""
		props.canAdd = false
		props.canRemove = false

		--[[ **A move rebinds both lists, which clears `value`, which fires the
		     observer again.** Without a guard that second firing is read as a
		     click on nothing. The flag is the whole defense and it MUST wrap
		     every rebuild. ]]
		--[[ **The plug-in owns the selection, not the widget.** Set by the
		     observers, consumed by the buttons, cleared on every move -- so a
		     second press without a fresh pick does nothing. ]]
		local pickedLeft = nil
		local pickedRight = nil



		local function counts()
			local sel, adds, removes = 0, 0, 0
			for id in pairs(selected) do
				sel = sel + 1
				if not atFlickr[id] then
					adds = adds + 1
				end
			end
			for id in pairs(atFlickr) do
				if not selected[id] then
					removes = removes + 1
				end
			end
			return sel, adds, removes
		end

		local function rebuild()
			local needle = (props.filter or ""):lower()
			local left, right, hidden = {}, {}, 0

			for _, g in ipairs(groups) do
				if selected[g.id] then
					right[#right + 1] = g
				elseif matches(g, needle) then
					left[#left + 1] = g
				else
					hidden = hidden + 1
				end
			end

			table.sort(left, byName)
			table.sort(right, byName)

			local leftItems = {}
			for i, g in ipairs(left) do
				leftItems[i] = { title = g.name, value = g.id }
			end

			--[[ The marker carries what color cannot. A row the photo is already
			     in at Flickr means a REMOVAL if the user moves it left; a row
			     added this session means only un-picking it. ]]
			local rightItems = {}
			for i, g in ipairs(right) do
				local mark = atFlickr[g.id] and MARK_AT_FLICKR or MARK_QUEUED
				rightItems[i] = { title = mark .. g.name, value = g.id }
			end

			props.leftItems = leftItems
			props.rightItems = rightItems

			--[[ **`nil`, NOT `{}` -- and this was a real bug, found by Terry on the
			     first click.**

			     With `allows_multiple_selection = true` the value is an array and
			     `{}` clears it; `PickerProbe.lua` relies on exactly that. With
			     single selection the value is a SCALAR, so assigning a table is a
			     nonsense value the widget ignores -- it kept its own selection,
			     positionally.

			     The visible symptom was cosmetic and the real one was not. After a
			     move, the row that slid into the vacated slot stayed highlighted,
			     and the widget believed it was already selected. **Clicking it
			     changed nothing, so no observer fired and the row went dead.** The
			     user had to click a different row first.

			     Same scalar-versus-table ambiguity this file already guards on the
			     READ side in `onlyPick`. Guarding one direction and not the other
			     is what let it through.

			     **`NO_SELECTION` rather than `nil`, and the difference matters.**
			     Assigning nil to a Lua table DELETES the key, which a binding may
			     read as "nothing changed" and skip -- leaving the widget's own
			     selection untouched all over again. An empty string is
			     unambiguously a value CHANGE, it is a scalar, and no group id can
			     ever equal it. `onlyPick` treats it as no selection. ]]

			--[[ **The filter applies to the LEFT list only**, so `hidden` counts
			     only unselected groups. A selected group is never hidden, which
			     is the entire point of the redesign. ]]
			props.leftStats = string.format(
				"Groups displayed: %d   ·   Groups hidden by filter: %d",
				#leftItems,
				hidden
			)

			local sel, adds, removes = counts()
			props.rightStats = string.format("Number of groups currently selected: %d", sel)
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

		--[[ Single-row hopping, which Terry chose after testing shift-click and
		     ctrl-click both working: "single row hopping at a time is more
		     intuitive." A later session MUST NOT reintroduce multi-select as an
		     improvement -- it was removed on purpose. ]]
		--[[ **`value` may be a TABLE or a bare id, and the SDK reference does not
		     settle which.** `allows_multiple_selection = true` clearly yields an
		     array; with it false, `simple_list` may hand back the selected value
		     itself. Indexing a string with `[1]` returns nil, so the naive version
		     would run `selected[nil] = true` and die on the FIRST click.

		     Reading both shapes costs four lines and removes the guess. `#` on a
		     string returns its length, so the empty test has to come after the type
		     check rather than before it. ]]
		local function onlyPick(value)
			if value == nil or value == NO_SELECTION then
				return nil
			end
			if type(value) ~= "table" then
				return value
			end
			-- An empty table is the multi-select shape of "nothing selected".
			local first = value[1]
			if first == NO_SELECTION then
				return nil
			end
			return first
		end

		--[[ **The observers RECORD; the buttons MOVE.** Click-to-move was Terry's
		     design and it cannot be made to work.

		     `simple_list` keeps a POSITIONAL selection that survives an `items`
		     rebind, and the list a row DEPARTS from keeps it -- observed every
		     time. Clicking a row the widget already considers selected produces no
		     change, no observer call, and a dead row.

		     Three fixes shipped to Terry's Lightroom and all three failed the same
		     way: `value = {}` in 0.6, `value = ""` in 0.7, and the reference's own
		     `value_equal` hook in 0.8. **A button click always fires**, so a button
		     does not care what the widget believes. Two clicks per group is a real
		     cost against what he asked for, and a control that cannot go dead is
		     worth it. ]]
		--[[ Each move clears only OUR record of the pick, never the widget's. The
		     widget may keep whatever highlight it likes; the button reads these
		     variables, so it can never act on a stale row. ]]
		local function addSelected()
			if pickedLeft == nil then
				return
			end
			selected[pickedLeft] = true
			pickedLeft = nil
			props.canAdd = false
			rebuild()
		end

		local function removeSelected()
			if pickedRight == nil then
				return
			end
			selected[pickedRight] = nil
			pickedRight = nil
			props.canRemove = false
			rebuild()
		end

		props:addObserver("leftValue", function()
			pickedLeft = onlyPick(props.leftValue)
			props.canAdd = pickedLeft ~= nil
		end)

		props:addObserver("rightValue", function()
			pickedRight = onlyPick(props.rightValue)
			props.canRemove = pickedRight ~= nil
		end)

		props:addObserver("filter", function()
			rebuild()
		end)

		rebuild()

		--[[ **No `font` attribute anywhere in this dialog, deliberately.**
		     `font = "<system/bold>"` is almost certainly valid LrView -- and
		     "almost certainly" is recall. There is no SDK on this machine to check
		     against, and an unknown attribute fails the WHOLE dialog rather than
		     rendering plain, which would cost a full load-and-test cycle to learn
		     something cosmetic. The headings read as headings from their position.
		     Add bold once the reference is on hand. ]]
		local listHeight = 420
		local listWidth = 330

		local contents = factory:column({
			bind_to_object = props,
			spacing = factory:control_spacing(),

			factory:static_text({
				title = "Select a group, then use the arrow buttons. The filter searches the left list only.",
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
					factory:simple_list({
						items = LrView.bind("leftItems"),
						value = LrView.bind("leftValue"),
						allows_multiple_selection = false,
						height = listHeight,
						width = listWidth,
					}),
					factory:static_text({
						title = LrView.bind("leftStats"),
						width = listWidth,
					}),
				}),

				--[[ Between the lists, so the direction of travel is obvious from
				     position as well as from the arrow. Disabled until a row is
				     picked, which removes the one case a press could do nothing. ]]
				factory:column({
					spacing = 10,
					factory:static_text({ title = " " }),
					factory:push_button({
						title = "Add  -->",
						width = 100,
						enabled = LrView.bind("canAdd"),
						action = addSelected,
					}),
					factory:push_button({
						title = "<--  Remove",
						width = 100,
						enabled = LrView.bind("canRemove"),
						action = removeSelected,
					}),
				}),

				factory:column({
					spacing = 4,
					factory:static_text({ title = "Selected groups" }),
					factory:simple_list({
						items = LrView.bind("rightItems"),
						value = LrView.bind("rightValue"),
						allows_multiple_selection = false,
						height = listHeight,
						width = listWidth,
					}),
					factory:static_text({
						title = LrView.bind("rightStats"),
						width = listWidth,
					}),
				}),
			}),

			factory:static_text({
				title = MARK_AT_FLICKR .. "Already in this group at Flickr   ·   "
					.. MARK_QUEUED .. "Will be added",
			}),

			factory:static_text({
				title = LrView.bind("pending"),
				fill_horizontal = 1,
			}),
		})

		local button = LrDialogs.presentModalDialog({
			title = string.format("FGA group picker -- %d groups", GROUP_COUNT),
			contents = contents,
			actionVerb = "Save",
		})

		if button ~= "ok" then
			return
		end

		--[[ The report is the whole point of a probe: it states what the real
		     client would send, split by KIND, because the two kinds have very
		     different consequences. ]]
		local adds, removes = {}, {}
		for id in pairs(selected) do
			if not atFlickr[id] then
				adds[#adds + 1] = byId[id].name
			end
		end
		for id in pairs(atFlickr) do
			if not selected[id] then
				removes[#removes + 1] = byId[id].name
			end
		end
		table.sort(adds)
		table.sort(removes)

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
		LrDialogs.message("FGA transfer picker FAILED", tostring(err), "critical")
	end
end)
