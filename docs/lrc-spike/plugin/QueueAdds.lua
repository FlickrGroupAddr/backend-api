--[[
  ADR-20's promise, as the two calls a client actually makes: WARN, then COMMIT.

  UI-free, like `FgaApi.lua` and `PhotoIds.lua`. It decides what to ask and what to
  send; a probe or a dialog decides what to show.

  ## The rule this file exists to keep

  **The warning MUST arrive before the commitment, from every client.** Before
  `preflight` existed, a picker learned about warnings by submitting: forty groups
  meant forty POSTs, each returning `409 needs_acknowledgement`, each one a decision
  the user had already made blind. The warning arrived AFTER the commitment, which
  is backwards for a rule whose whole point is informed consent.

  **`acknowledgedModeration` is a LIST, never a flag, and that is ADR-20 in the
  wire format.** A blanket boolean would let one click acknowledge warnings the
  person never saw. This file will only ever put a group id in that list if the
  caller passed it in explicitly, and `askedFor` below is how a caller proves it.

  ## THIS IS ADVISORY AND IS NOT A SECURITY CONTROL

  `POST /requests/batch` re-checks everything itself. A caller that skipped
  preflight gets the same protection and a caller that forges a preflight result
  gains nothing. **So nothing here is defending the server** -- it is keeping a
  promise to the person, and a client CAN quietly skip it while nothing errors.
  That is exactly why it is written down rather than assumed.

  ## Chunking, because both endpoints cap at 200

  `preflight` and `requests/batch` both take at most 200 group ids. Terry's own
  account is in the low hundreds of groups and other accounts are larger, so a
  caller asking about everything would silently 400. This splits the list, calls in
  order, and merges -- **and it MUST stop at the first failure rather than pressing
  on**, because a half-submitted batch that reports success is the worst outcome
  available here.
]]

local FgaApi = require("FgaApi")

local QueueAdds = {}

--[[ The server's cap, from `z.array(...).max(200)` on both `preflight` and
     `batchSubmission` in `src/routes/api.ts`. Stated once here so a future bump
     is a one-line change rather than a hunt. ]]
QueueAdds.CHUNK = 200

--[[ **Copy one reply's answers, INDEX BY INDEX, however many holes it has.**

     **A JSON `null` inside an array decodes to Lua `nil`, and `ipairs` STOPS at the
     first one.** Measured with LuaJIT against the vendored rxi decoder: an array of
     four with a `null` at position 2 reports `#` of 4 and `ipairs` visits exactly ONE
     element. Everything after the hole is invisible.

     **`/requests/batch` can produce that null.** It answers
     `groupIds.map(groupId => byGroup.get(groupId))`, and `Map.get` returns `undefined`
     for a group that reached neither `decided` nor `minted` -- which happens when
     `enqueueMany` writes fewer rows than it was asked for. `JSON.stringify` writes that
     as `null` INSIDE the array.

     **So `count` comes from the list WE SENT, never from the reply.** The server
     answers in the order asked, and asking for the length of a table with holes is
     undefined behavior in Lua -- `#` happened to return 4 in the probe and is not
     promised to.

     **It writes at an EXPLICIT index, and `into[#into + 1]` was the first attempt.**
     Assigning `nil` to a table is a no-op, so that version silently CLOSED the hole and
     shifted every later answer one place left -- destroying the alignment the server
     promises ("answered in the order asked, so a client can zip the reply against its
     own list"). The suite caught it immediately: group `c` arrived where `b` should be.

     **So a missing answer stays a hole.** A caller reads by index and gets `nil` for the
     group that went unanswered, which is the truth. ]]
local function appendAnswers(into, answers, count, base)
	--[[ **A reply with no `groups` at all still advances the base**, leaving that whole
	     slice as holes. Returning early would slide the NEXT slice into its place, which
	     is the same misalignment one level up. ]]
	if type(answers) == "table" then
		for index = 1, count do
			into[base + index] = answers[index]
		end
	end
	return base + count
end

local function chunk(list, size)
	local chunks = {}
	for i = 1, #list, size do
		local part = {}
		for j = i, math.min(i + size - 1, #list) do
			part[#part + 1] = list[j]
		end
		chunks[#chunks + 1] = part
	end
	return chunks
end

--[[ Asks the server about every group, in slices, and merges the answers.

     Returns `{ poolsKnown = boolean, groups = { ... } }, nil` or `nil, failure, detail`.

     **`poolsKnown` is ANDed across slices, deliberately.** It reports whether
     Flickr's `getAllContexts` answered. If any slice could not learn the photo's
     pools, the caller does not know them -- and ADR-04 says absence proves nothing
     while presence proves approval. **ORing it would let one lucky slice present an
     unknown as a clean answer**, which suppresses warnings the server then raises
     at submit time. ]]
function QueueAdds.preflight(photoId, groupIds)
	local merged = {}
	local poolsKnown = true
	local written = 0

	for _, part in ipairs(chunk(groupIds, QueueAdds.CHUNK)) do
		local reply, failure, _, detail = FgaApi.preflight(photoId, part)
		if reply == nil then
			return nil, failure, detail
		end

		if reply.poolsKnown ~= true then
			poolsKnown = false
		end

		--[[ **`written` advances by the size of the SLICE, answered or not.** Reading
		     `#merged` instead would slide every later slice up by however many holes
		     came before it. ]]
		written = appendAnswers(merged, reply.groups, #part, written)
	end

	--[[ **`count` is carried rather than left to `#`.** The length of a table with
	     holes is undefined in Lua, and `bucket` and every caller need to know how far
	     to read. ]]
	return { poolsKnown = poolsKnown, groups = merged, count = written }, nil
end

--[[ Splits a preflight result into the four buckets a dialog needs.

     **`needsAcknowledgement` is the one that MUST be shown before submitting.**
     Each of those groups has already had one of this user's photos reach a
     moderator, which under ADR-04 is remembered forever and under ADR-01 is
     terminal -- so asking again is asking a volunteer to look at the same
     submission twice. ]]
function QueueAdds.bucket(preflightResult)
	local buckets = {
		ready = {},
		needsAcknowledgement = {},
		alreadyInPool = {},
		alreadyQueued = {},
	}

	--[[ **By index over `count`, never `ipairs`.** A hole anywhere in the merged list
	     would make `ipairs` stop there, and the buckets would silently describe only
	     the groups before it -- a picker showing a short list with nothing to say it
	     was short. `count` comes from `preflight` for exactly this. ]]
	--[[ **A plain `if`, NOT `goto continue`.** That was the first shape here and it is
	     Lua 5.2 syntax. Lightroom runs 5.1, which has no `goto` at all -- and LuaJIT
	     accepts it as a 5.2 extension, so `npm run lua:test` would have gone green while
	     the real host refused to load the file. The `.luarc.json` pin caught it, and the
	     real `luac` 5.1 in `npm run lua` would have caught it next. ]]
	for index = 1, preflightResult.count or #preflightResult.groups do
		local entry = preflightResult.groups[index]
		-- A hole means the server answered nothing for that group. Nothing to bucket,
		-- and nothing to invent.
		if entry ~= nil then
			if entry.status == "ready" then
				buckets.ready[#buckets.ready + 1] = entry
			elseif entry.status == "needs_acknowledgement" then
				buckets.needsAcknowledgement[#buckets.needsAcknowledgement + 1] = entry
			elseif entry.status == "already_in_pool" then
				buckets.alreadyInPool[#buckets.alreadyInPool + 1] = entry
			elseif entry.status == "already_queued" then
				buckets.alreadyQueued[#buckets.alreadyQueued + 1] = entry
			end
		end
	end

	return buckets
end

--[[ Submits, in slices, and merges the answers.

     **`askedFor` is the list of group ids whose warning was SHOWN AND ACCEPTED**,
     and it is a separate argument from `groupIds` on purpose. Passing
     `groupIds` for both would acknowledge every warning automatically, which is
     precisely the blanket-flag failure ADR-20 refuses -- and it would be one
     character to write and impossible to see in review.

     **It stops at the first failed slice and REPORTS HOW FAR IT GOT.** A caller
     that only saw "it failed" would not know whether to retry the whole list, and
     retrying an already-submitted slice puts photos in front of a moderator twice.
     ADR-01 is why that matters more here than the usual retry argument. ]]
function QueueAdds.submit(photoId, groupIds, askedFor)
	--[[ **The narrowing happens ONCE, per slice, in the loop below.**

	     An earlier version narrowed twice: first against `groupIds`, then again
	     against each slice. **The first pass was dead code**, because every slice is
	     a subset of `groupIds` and the slices union back to it -- so the second pass
	     already removed everything the first one would have.

	     **Found by mutation, not by reading.** Deleting the first filter's condition
	     left all 53 checks passing, which is what a redundant guard looks like from
	     the outside. Card #0078. ]]
	local acknowledged = type(askedFor) == "table" and askedFor or {}

	local merged = {}
	local queuedCount = 0
	local poolsKnown = true
	local submitted = 0
	local written = 0

	for _, part in ipairs(chunk(groupIds, QueueAdds.CHUNK)) do
		--[[ The acknowledgement list is narrowed to THIS slice. The server dedupes
		     and ignores unknown ids, but sending the whole list every time would
		     make the request describe groups it is not submitting. ]]
		local inPart = {}
		for _, id in ipairs(part) do
			inPart[id] = true
		end
		local partAcks = {}
		for _, id in ipairs(acknowledged) do
			if inPart[id] then
				partAcks[#partAcks + 1] = id
			end
		end

		local reply, failure, _, detail = FgaApi.batch(photoId, part, partAcks)

		if reply == nil then
			return nil, failure, {
				detail = detail,
				submittedGroups = submitted,
				totalGroups = #groupIds,
			}
		end

		submitted = submitted + #part
		queuedCount = queuedCount + (tonumber(reply.queuedCount) or 0)
		if reply.poolsKnown ~= true then
			poolsKnown = false
		end
		--[[ **THIS is the reply that can carry a hole**, and the reason `appendAnswers`
		     exists. See its comment: a `byGroup.get` miss produces a JSON `null` here,
		     `ipairs` would stop at the first one and silently lose every group after
		     it, and `#merged` would slide the next slice into the gap. ]]
		written = appendAnswers(merged, reply.groups, #part, written)
	end

	return {
		photoId = photoId,
		poolsKnown = poolsKnown,
		queuedCount = queuedCount,
		groups = merged,
		-- **How far to read**, since `groups` may carry holes and `#` on a table with
		-- holes is undefined in Lua.
		count = written,
	}, nil
end

--[[ Collects the group ids from a preflight bucket, ready to hand back to
     `submit`. A convenience with one job, kept here so callers do not each write
     their own loop and quietly disagree about which field holds the id. ]]
function QueueAdds.idsOf(entries)
	local ids = {}
	for _, entry in ipairs(entries) do
		if entry.groupId ~= nil then
			ids[#ids + 1] = entry.groupId
		end
	end
	return ids
end

return QueueAdds
