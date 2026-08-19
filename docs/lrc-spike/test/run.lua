--[[
  The plug-in's pure logic, tested off-host. Card #0078.

      luajit docs/lrc-spike/test/run.lua        # via `npm run lua:test`

  It exits non-zero on the first failure count, so the gate can depend on it.

  WHAT IS COVERED, and it is deliberately the arithmetic rather than the dialogs:
  slicing at the server's 200-group cap, merging replies, the ADR-20
  acknowledgement narrowing, ADR-04's `poolsKnown` conjunction, the publish-service
  filter in `PhotoIds`, and every named failure having a sentence.

  WHAT IS NOT COVERED: anything that needs Lightroom. `LrView`, `LrHttp` against a
  real socket, the catalog. **Those are what the probes in `Info.lua` are for**, and
  pretending to cover them here would be the reassuring-but-blind test this
  repository keeps refusing.
]]

local here = arg[0]:match("^(.*)[/\\][^/\\]*$") or "."
package.path = here .. "/?.lua;" .. here .. "/../plugin/?.lua;" .. package.path

local stubs = require("lrc-stubs")
stubs.install()

local failures = 0
local checks = 0

local function check(label, got, want)
	checks = checks + 1
	if got ~= want then
		failures = failures + 1
		print(string.format("  FAIL  %s\n          got  %s\n          want %s",
			label, tostring(got), tostring(want)))
	end
end

local function section(name)
	print("\n" .. name)
end

--[[ **`FgaApi` is replaced BEFORE `QueueAdds` requires it**, so the module under
     test talks to a recorder instead of to `LrHttp`. That is what makes the slicing
     assertions possible without a network. ]]
local fake = { calls = {}, preflightReply = nil, batchReply = nil, failAfter = nil }

function fake.reset()
	fake.calls = {}
	fake.failAfter = nil
end

fake.FAILURES = {
	transport = "transport", notAuthenticated = "notAuthenticated",
	notAllowed = "notAllowed", noFlickr = "noFlickr",
	tooManyGroups = "tooManyGroups", flickrDown = "flickrDown",
	badRequest = "badRequest", unreadable = "unreadable", unexpected = "unexpected",
}

function fake.preflight(photoId, groupIds)
	fake.calls[#fake.calls + 1] = { what = "preflight", photoId = photoId, ids = groupIds }
	if fake.failAfter and #fake.calls > fake.failAfter then
		return nil, "transport", nil, "stubbed failure"
	end
	local groups = {}
	for _, id in ipairs(groupIds) do
		groups[#groups + 1] = { groupId = id, status = "ready" }
	end
	return { poolsKnown = fake.poolsKnown ~= false, groups = groups }, nil
end

function fake.batch(photoId, groupIds, acks)
	fake.calls[#fake.calls + 1] =
		{ what = "batch", photoId = photoId, ids = groupIds, acks = acks }
	if fake.failAfter and #fake.calls > fake.failAfter then
		return nil, "transport", nil, "stubbed failure"
	end
	local groups = {}
	for _, id in ipairs(groupIds) do
		groups[#groups + 1] = { groupId = id, status = "queued" }
	end
	return { photoId = photoId, poolsKnown = true, queuedCount = #groupIds, groups = groups }
end

function fake.explain()
	return "stub"
end

package.loaded["FgaApi"] = fake

local QueueAdds = require("QueueAdds")

local function ids(n, prefix)
	local out = {}
	for i = 1, n do
		out[i] = string.format("%s%03d", prefix or "g", i)
	end
	return out
end

section("QueueAdds.preflight slices at the server's cap")
do
	fake.reset()
	fake.poolsKnown = true
	local result = QueueAdds.preflight("photo1", ids(450))
	check("450 groups -> 3 calls", #fake.calls, 3)
	check("first slice is 200", #fake.calls[1].ids, QueueAdds.CHUNK)
	check("last slice is the remainder", #fake.calls[3].ids, 50)
	check("every group comes back", #result.groups, 450)
	check("order is preserved", result.groups[201].groupId, "g201")

	fake.reset()
	QueueAdds.preflight("photo1", ids(200))
	check("exactly 200 is ONE call", #fake.calls, 1)

	fake.reset()
	QueueAdds.preflight("photo1", ids(201))
	check("201 is two calls", #fake.calls, 2)
end

section("ADR-04: poolsKnown is ANDed across slices, never ORed")
do
	fake.reset()
	fake.poolsKnown = false
	local result = QueueAdds.preflight("photo1", ids(300))
	check("one unknown slice makes the whole answer unknown", result.poolsKnown, false)
	fake.poolsKnown = true
end

section("QueueAdds.preflight reports a failed slice instead of a short list")
do
	fake.reset()
	fake.failAfter = 1
	local result, failure = QueueAdds.preflight("photo1", ids(450))
	check("no result", result, nil)
	check("the failure name is passed through", failure, "transport")
	fake.failAfter = nil
end

section("QueueAdds.bucket sorts every status")
do
	local buckets = QueueAdds.bucket({ groups = {
		{ groupId = "a", status = "ready" },
		{ groupId = "b", status = "needs_acknowledgement" },
		{ groupId = "c", status = "already_in_pool" },
		{ groupId = "d", status = "already_queued" },
		{ groupId = "e", status = "ready" },
	} })
	check("ready", #buckets.ready, 2)
	check("needsAcknowledgement", #buckets.needsAcknowledgement, 1)
	check("alreadyInPool", #buckets.alreadyInPool, 1)
	check("alreadyQueued", #buckets.alreadyQueued, 1)
	check("idsOf reads groupId", QueueAdds.idsOf(buckets.ready)[2], "e")
end

section("ADR-20: acknowledgements are narrowed, never widened")
do
	fake.reset()
	-- Submitting two groups while acknowledging THREE, one of which was dropped.
	QueueAdds.submit("photo1", { "a", "b" }, { "a", "zz", "b" })
	check("one batch call", #fake.calls, 1)
	check("only submitted ids are acknowledged", #fake.calls[1].acks, 2)

	fake.reset()
	-- The dangerous shape: acknowledging a group that is NOT being submitted.
	QueueAdds.submit("photo1", { "a" }, { "b" })
	check("an acknowledgement for a dropped group is discarded",
		#fake.calls[1].acks, 0)

	fake.reset()
	QueueAdds.submit("photo1", { "a", "b" }, nil)
	check("no acknowledgements means none sent", #fake.calls[1].acks, 0)
end

section("ADR-20: a slice's acknowledgements stay inside that slice")
do
	fake.reset()
	local all = ids(300)
	QueueAdds.submit("photo1", all, { "g001", "g250" })
	check("two batch calls", #fake.calls, 2)
	check("first slice carries only its own ack", #fake.calls[1].acks, 1)
	check("and it is the right one", fake.calls[1].acks[1], "g001")
	check("second slice carries only its own ack", #fake.calls[2].acks, 1)
	check("and it is the right one", fake.calls[2].acks[1], "g250")
end

section("ADR-01: a failed submit reports HOW FAR it got")
do
	fake.reset()
	fake.failAfter = 1
	local result, failure, detail = QueueAdds.submit("photo1", ids(450), nil)
	check("no result", result, nil)
	check("failure name", failure, "transport")
	check("200 groups were already submitted", detail.submittedGroups, 200)
	check("out of 450", detail.totalGroups, 450)
	fake.failAfter = nil
end

section("QueueAdds.submit merges counts across slices")
do
	fake.reset()
	local result = QueueAdds.submit("photo1", ids(450), nil)
	check("queuedCount is summed", result.queuedCount, 450)
	check("every group comes back", #result.groups, 450)
end

section("A JSON null in the reply does NOT truncate the merge")
do
	--[[ **The bug this was written for, card #0087.** `/requests/batch` answers
	     `groupIds.map(g => byGroup.get(g))`, and a miss is `undefined`, which
	     `JSON.stringify` writes as `null` INSIDE the array. rxi decodes that to Lua
	     `nil`, and `ipairs` stops at the hole -- measured: an array of four with a null
	     at index 2 lets `ipairs` visit exactly ONE element.

	     Before the fix, everything after the first hole silently vanished. ]]
	fake.reset()
	local holed = fake.batch
	fake.batch = function(photoId, groupIds, acks)
		local reply = holed(photoId, groupIds, acks)
		-- Punch a hole exactly as a `byGroup` miss would.
		reply.groups[2] = nil
		return reply
	end

	local result = QueueAdds.submit("photo1", { "a", "b", "c", "d" }, nil)
	check("every asked-for slot comes back", #result.groups, 4)
	check("the group AFTER the hole survives", result.groups[3].groupId, "c")
	check("and so does the last one", result.groups[4].groupId, "d")
	check("the hole itself stays nil", result.groups[2], nil)

	fake.batch = holed
end

section("PhotoIds filters on the publish SERVICE")
do
	local PhotoIds = require("PhotoIds")

	--[[ Minimal fakes shaped like the SDK objects. `getPhoto` returns the same
	     table so `localIdentifier` matching has something to match. ]]
	local function photo(localId)
		return { localIdentifier = localId }
	end

	local function publishedPhoto(p, remoteId)
		return {
			getPhoto = function() return p end,
			getRemoteId = function() return remoteId end,
			getRemoteUrl = function() return "https://flickr/" .. tostring(remoteId) end,
		}
	end

	local function collection(name, pluginId, published)
		local col
		col = {
			getName = function() return name end,
			getService = function()
				return { getPluginId = function() return pluginId end }
			end,
			getPublishedPhotos = function() return published end,
		}
		return col
	end

	local flickrPhoto = photo(11)
	local smugPhoto = photo(22)
	local bothPhoto = photo(33)

	local flickrCol = collection("Flickr set", PhotoIds.FLICKR_PLUGIN_ID,
		{ publishedPhoto(flickrPhoto, "4271"), publishedPhoto(bothPhoto, "9999") })
	local smugCol = collection("SmugMug set", "com.smugmug.export",
		{ publishedPhoto(smugPhoto, "SMUG-1"), publishedPhoto(bothPhoto, "SMUG-2") })

	flickrPhoto.getContainedPublishedCollections = function() return { flickrCol } end
	smugPhoto.getContainedPublishedCollections = function() return { smugCol } end
	bothPhoto.getContainedPublishedCollections = function() return { smugCol, flickrCol } end

	local rows = PhotoIds.forPhotos({ flickrPhoto, smugPhoto, bothPhoto })

	check("one row per photo, in order", #rows, 3)
	check("the Flickr photo resolves", rows[1].flickrId, "4271")
	check("the SmugMug photo does NOT", rows[2].flickrId, nil)
	check("and says why", rows[2].reason, PhotoIds.REASONS.notFlickr)
	check("a photo in BOTH takes only the Flickr id", rows[3].flickrId, "9999")

	local never = photo(44)
	never.getContainedPublishedCollections = function() return {} end
	local none = PhotoIds.forPhotos({ never })
	check("never published", none[1].reason, PhotoIds.REASONS.notPublished)
end

section("PhotoIds reports a conflict instead of guessing")
do
	local PhotoIds = require("PhotoIds")
	local p = { localIdentifier = 77 }

	local function col(remoteId)
		return {
			getName = function() return "set" end,
			getService = function()
				return { getPluginId = function() return PhotoIds.FLICKR_PLUGIN_ID end }
			end,
			getPublishedPhotos = function()
				return { {
					getPhoto = function() return p end,
					getRemoteId = function() return remoteId end,
					getRemoteUrl = function() return "u" end,
				} }
			end,
		}
	end

	p.getContainedPublishedCollections = function() return { col("111"), col("222") } end
	local rows = PhotoIds.forPhotos({ p })
	check("two Flickr ids is a CONFLICT", rows[1].reason, PhotoIds.REASONS.conflicting)
	check("and no id is returned", rows[1].flickrId, nil)

	p.getContainedPublishedCollections = function() return { col("111"), col("111") } end
	rows = PhotoIds.forPhotos({ p })
	check("the SAME id twice is not a conflict", rows[1].flickrId, "111")
end

section("Every named failure and reason has a sentence")
do
	package.loaded["FgaApi"] = nil
	local FgaApi = require("FgaApi")
	for name, value in pairs(FgaApi.FAILURES) do
		local text = FgaApi.explain(value)
		check("FgaApi.explain(" .. name .. ") is a real sentence",
			type(text) == "string" and #text > 20, true)
	end

	local PhotoIds = require("PhotoIds")
	for name, value in pairs(PhotoIds.REASONS) do
		local text = PhotoIds.explain(value)
		check("PhotoIds.explain(" .. name .. ") is a real sentence",
			type(text) == "string" and #text > 20, true)
	end

	check("an unknown failure still answers",
		type(FgaApi.explain("nonsense")) == "string", true)
end

print(string.format("\n%d check(s), %d failure(s)", checks, failures))
if failures > 0 then
	os.exit(1)
end
print("Plug-in logic holds.")
