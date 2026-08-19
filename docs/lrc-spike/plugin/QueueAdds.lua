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

	for _, part in ipairs(chunk(groupIds, QueueAdds.CHUNK)) do
		local reply, failure, _, detail = FgaApi.preflight(photoId, part)
		if reply == nil then
			return nil, failure, detail
		end

		if reply.poolsKnown ~= true then
			poolsKnown = false
		end

		if type(reply.groups) == "table" then
			for _, entry in ipairs(reply.groups) do
				merged[#merged + 1] = entry
			end
		end
	end

	return { poolsKnown = poolsKnown, groups = merged }, nil
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

	for _, entry in ipairs(preflightResult.groups) do
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
		if type(reply.groups) == "table" then
			for _, entry in ipairs(reply.groups) do
				merged[#merged + 1] = entry
			end
		end
	end

	return {
		photoId = photoId,
		poolsKnown = poolsKnown,
		queuedCount = queuedCount,
		groups = merged,
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
