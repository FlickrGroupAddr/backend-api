--[[
  Does `checkbox.title` accept a binding? The picker's whole design rests on it.

  READ-ONLY. No network, no catalog, no Flickr. It builds one dialog out of
  generated strings and asks you what you saw.

  ## Why this question blocks the picker

  `docs/LRC-CLIENT-NOTES.md` records the defect: `visible = false` hides a view but
  KEEPS ITS SPACE, so a filtered pane fills with white gaps. The design that fixes
  it is a FIXED WINDOW of about 25 rows plus paging -- build 25 checkboxes once,
  then repoint their titles at whichever slice of the filtered list is on screen.

  **That design is impossible unless a checkbox's `title` can be bound.** If it can
  only be set at build time, 25 slots can never show 372 different labels, and the
  picker needs rethinking rather than tuning.

  ## What the archive says, and why it is not enough

  **Adobe's own samples bind `value` thirteen times out of thirteen and bind
  `title` zero times.** Measured 2026-08-19 across every `.lua` in the vendored
  SDK: FlickrExportServiceProvider, FlickrPublishSupport, FtpUploadExportDialog,
  ShowCustomDialog and RemoteControlSettings. Every one is
  `checkbox { title = "literal", value = bind "key" }`.

  **They DO bind other non-value properties**, though -- the Flickr sample carries
  `enabled = LrBinding.keyEquals( 'privacy', 'private' )` on a checkbox. So the
  control is not limited to binding `value` alone.

  **Absence from the samples is not absence from the runtime**, which is this
  project's own lesson from `LrUUID` and from `luac`. Only the application can
  answer it, so this probe exists rather than a paragraph of reasoning.

  ## What a PASS and a FAIL look like

  The dialog shows 5 rows and a Next button. Pressing Next moves the window down
  the generated list.

    PASS  the labels change when you press Next
    FAIL  the labels stay on Row 01 .. Row 05 while the count at the top moves

  **A FAIL is the informative outcome**, and it means the slot design dies and the
  picker gets rethought. Say which one you saw.
]]

local LrDialogs = import("LrDialogs")
local LrView = import("LrView")
local LrBinding = import("LrBinding")
local LrFunctionContext = import("LrFunctionContext")
local LrTasks = import("LrTasks")

--[[ Small on purpose. The question is whether a bound title RENDERS AND UPDATES,
     and 5 rows answers that exactly as well as 25 while keeping the dialog
     readable on a laptop. Build cost is already measured elsewhere: 744 views in
     9-12 ms on Terry's machine. ]]
local SLOTS = 5

local TOTAL = 40

--[[ Stand-ins for group names. Deliberately NOT fetched -- a network call here
     would put two unproven things in one experiment. ]]
local function makeItems()
	local items = {}
	for i = 1, TOTAL do
		items[i] = string.format("Row %02d -- a group name of realistic length", i)
	end
	return items
end

local function run()
	LrFunctionContext.callWithContext("fga-bind-title", function(context)
		local factory = LrView.osFactory()
		local props = LrBinding.makePropertyTable(context)

		local items = makeItems()
		props.offset = 0

		--[[ **One property per SLOT, never one per item.** That is the whole design:
		     the number of bound keys is fixed at 5 and the 40 items flow through
		     them. If this works, 372 groups flow through 25 the same way. ]]
		local function repaint()
			for slot = 1, SLOTS do
				local index = props.offset + slot
				props["title" .. slot] = items[index] or ""
				props["shown" .. slot] = items[index] ~= nil
			end
			props.caption = string.format(
				"Showing %d-%d of %d",
				props.offset + 1,
				math.min(props.offset + SLOTS, TOTAL),
				TOTAL
			)
		end

		repaint()

		local rows = {}
		for slot = 1, SLOTS do
			rows[#rows + 1] = factory:checkbox({
				--[[ **THE ASSERTION.** Everything else in this file is scaffolding
				     around this one line. ]]
				title = LrView.bind("title" .. slot),
				value = LrView.bind("checked" .. slot),
				width = 420,
			})
		end

		local contents = factory:column({
			spacing = 6,
			bind_to_object = props,

			factory:static_text({
				title = LrView.bind("caption"),
				width = 420,
			}),

			factory:separator({ fill_horizontal = 1 }),

			factory:column({ spacing = 4, unpack(rows) }),

			factory:separator({ fill_horizontal = 1 }),

			factory:row({
				spacing = 10,
				factory:push_button({
					title = "<-- Back",
					action = function()
						props.offset = math.max(0, props.offset - SLOTS)
						repaint()
					end,
				}),
				factory:push_button({
					title = "Next -->",
					action = function()
						if props.offset + SLOTS < TOTAL then
							props.offset = props.offset + SLOTS
							repaint()
						end
					end,
				}),
			}),

			factory:static_text({
				title = "PASS: the row labels change when you press Next."
					.. "\nFAIL: the labels stay put while the count above moves.",
				width = 420,
				height_in_lines = 2,
			}),
		})

		LrDialogs.presentModalDialog({
			title = "FGA: can a checkbox title be bound?",
			contents = contents,
			actionVerb = "The labels CHANGED (pass)",
			cancelVerb = "The labels STAYED (fail)",
		})
	end)
end

LrTasks.startAsyncTask(function()
	local ok, err = LrTasks.pcall(run)
	if not ok then
		--[[ **An error here is itself an answer, and a good one.** If binding a
		     title is rejected outright, the SDK says so when the view is built, and
		     that is the FAIL case arriving loudly rather than as a blank label. ]]
		LrDialogs.message(
			"FGA bind-title probe FAILED to build the dialog",
			"This is a RESULT, not a crash to work around. A checkbox title that"
				.. " cannot be bound kills the slot-based picker design.\n\nDetail:\n"
				.. tostring(err),
			"critical"
		)
	end
end)
