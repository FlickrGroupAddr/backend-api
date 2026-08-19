--[[
  Turns the photos you have selected in Lightroom into Flickr photo IDs.

  This is the join between the two halves of the product. Lightroom knows about
  catalog photos; FGA's API only ever speaks in Flickr photo IDs. Nothing else in
  this plug-in can call `/api/v001/photos/{id}/preflight` until this file answers.

  UI-FREE, like `DeviceLink.lua` and `FgaApi.lua`. Every dialog lives in a probe.

  ## The premise underneath it is CONFIRMED, not assumed

  A third-party plug-in CAN enumerate Adobe's Flickr publish service and read its
  published photos. Measured on Terry's real catalog, 834 published photos, 834
  carrying a Flickr URL and an 8+ digit numeric ID, cross-checked against the
  catalog's own SQLite. `docs/lrc-spike/RESULT-2026-08-15.txt` is the raw evidence
  and `DumpPublishServices.lua` is the probe that produced it.

  ## `getRemoteId()` READS LOCAL RECORDS, which is what makes this cheap

  It returns what Lightroom wrote into the catalog at publish time. **It does not
  call Flickr.** So this needs no Flickr credential, no network, and no upload, and
  a catalog whose Flickr service is expired still carries every ID.

  ## THE SERVICE IS CHECKED, and skipping that check would be a real bug

  `photo:getContainedPublishedCollections()` returns collections from EVERY publish
  service -- SmugMug, Zenfolio, a hard-drive publisher, anything installed. Each of
  those records its own `remoteId` in its own namespace. **Handing a SmugMug ID to
  Flickr would be nonsense that looks exactly like a valid request**, so every
  collection is filtered by `collection:getService():getPluginId()` first.

  ## Two IDs live one call apart and only one of them is right

  | Call | Returns |
  |---|---|
  | `publishedPhoto:getRemoteId()` | **The Flickr PHOTO id. This one.** |
  | `collection:getRemoteId()` | The Flickr photoSET id. Not this one |

  `LrTasks.pcall`, never bare `pcall` -- catalog calls yield, and Lua 5.1 cannot
  yield across a standard `pcall`. That mistake once made a probe report REFUTED
  about a premise that is true.
]]

local LrApplication = import("LrApplication")
local LrTasks = import("LrTasks")

local PhotoIds = {}

--[[ Adobe's own Flickr publish service, as it identifies itself at runtime.
     Measured rather than guessed: `DumpPublishServices.lua` printed exactly this
     from `service:getPluginId()` on 2026-08-15. ]]
PhotoIds.FLICKR_PLUGIN_ID = "com.adobe.lightroom.export.flickr"

--[[ Why a photo produced no Flickr ID. **Named rather than blank**, because
     "never published" and "published somewhere that is not Flickr" need different
     sentences in front of a photographer. ]]
PhotoIds.REASONS = {
	notPublished = "notPublished", -- In no published collection at all
	notFlickr = "notFlickr", -- Published, but not by Adobe's Flickr service
	noRemoteId = "noRemoteId", -- In a Flickr collection with no ID recorded yet
	conflicting = "conflicting", -- Two Flickr collections, two different IDs
}

--- Yield-safe accessor. MUST be `LrTasks.pcall`, never bare `pcall`.
local function call(object, method)
	local ok, value = LrTasks.pcall(function()
		return object[method](object)
	end)
	if not ok then
		return nil
	end
	return value
end

--[[ Builds `localIdentifier -> remoteId` for ONE collection, once.

     **Built per collection rather than per photo, and that is a real difference.**
     `getPublishedPhotos()` on Terry's catalog returns 834 rows. Scanning it once
     per selected photo would be 834 x N comparisons -- fine for one photo, and
     417,000 for a 500-photo selection. Indexing first makes it 834 + N.

     `photo.localIdentifier` is the key. It is a documented `LrPhoto` PROPERTY,
     a number unique within the catalog, and Adobe's own `HttpHandler.lua` sample
     uses it as an identity key. **Comparing `LrPhoto` objects with `==` is the
     tempting alternative and it is not safe** -- the SDK may hand back a
     different wrapper for the same underlying photo. ]]
local function indexCollection(collection)
	local published = call(collection, "getPublishedPhotos")
	if type(published) ~= "table" then
		return nil
	end

	local byLocalId = {}
	for _, publishedPhoto in ipairs(published) do
		local photo = call(publishedPhoto, "getPhoto")
		if photo ~= nil then
			local ok, localId = LrTasks.pcall(function()
				return photo.localIdentifier
			end)
			if ok and localId ~= nil then
				byLocalId[localId] = {
					remoteId = call(publishedPhoto, "getRemoteId"),
					remoteUrl = call(publishedPhoto, "getRemoteUrl"),
				}
			end
		end
	end

	return byLocalId
end

--[[ Resolves a list of `LrPhoto` to Flickr IDs.

     Returns an array in the SAME ORDER as the input, one entry per photo:

       { photo, localId, flickrId, flickrUrl, collectionName }   on success
       { photo, localId, flickrId = nil, reason = <REASONS.*> }  otherwise

     **Order is preserved and nothing is dropped**, so a caller can report on every
     photo the person selected rather than silently shortening the list. A photo
     that produced no ID is the interesting case, not a rounding error.

     MUST be called inside an `LrTasks` async task. ]]
function PhotoIds.forPhotos(photos)
	local results = {}
	--[[ One index per collection, shared across every photo in this call. Two
	     selected photos in the same Flickr photoset therefore cost one scan. ]]
	local indexes = {}

	for _, photo in ipairs(photos) do
		local okId, localId = LrTasks.pcall(function()
			return photo.localIdentifier
		end)
		if not okId then
			localId = nil
		end

		local collections = call(photo, "getContainedPublishedCollections")

		local found = nil
		local reason = PhotoIds.REASONS.notPublished
		local conflicted = false

		if type(collections) == "table" and #collections > 0 then
			--[[ Published somewhere. Whether it is FLICKR is the next question, and
			     assuming it is would be the bug this whole block exists to avoid. ]]
			reason = PhotoIds.REASONS.notFlickr

			for _, collection in ipairs(collections) do
				local service = call(collection, "getService")
				local pluginId = service and call(service, "getPluginId") or nil

				if pluginId == PhotoIds.FLICKR_PLUGIN_ID then
					reason = PhotoIds.REASONS.noRemoteId

					if indexes[collection] == nil then
						indexes[collection] = indexCollection(collection) or false
					end

					local index = indexes[collection]
					local entry = index and localId ~= nil and index[localId] or nil

					if entry ~= nil and entry.remoteId ~= nil then
						if found == nil then
							found = {
								flickrId = tostring(entry.remoteId),
								flickrUrl = entry.remoteUrl,
								collectionName = call(collection, "getName"),
							}
						elseif found.flickrId ~= tostring(entry.remoteId) then
							--[[ **Reported, never resolved by guessing.** Two Flickr
							     collections carrying different IDs for one photo means
							     it was published to two accounts, and picking one at
							     random would queue somebody's photo into a stranger's
							     groups. ADR-01's instinct: an ambiguous outcome is not
							     a small outcome. ]]
							conflicted = true
						end
					end
				end
			end
		end

		if conflicted then
			results[#results + 1] = {
				photo = photo,
				localId = localId,
				flickrId = nil,
				reason = PhotoIds.REASONS.conflicting,
			}
		elseif found ~= nil then
			results[#results + 1] = {
				photo = photo,
				localId = localId,
				flickrId = found.flickrId,
				flickrUrl = found.flickrUrl,
				collectionName = found.collectionName,
			}
		else
			results[#results + 1] = {
				photo = photo,
				localId = localId,
				flickrId = nil,
				reason = reason,
			}
		end
	end

	return results
end

--[[ The selection, as Lightroom defines it.

     **`getTargetPhotos()`, not `getTargetPhoto()`.** The SDK describes the plural
     as "the photos that would be affected by any photo-processing command", which
     is exactly what a person means by "the ones I have selected" -- including the
     filmstrip case where nothing is explicitly selected and the active photo is
     the target. ]]
function PhotoIds.forSelection()
	local catalog = LrApplication.activeCatalog()
	local photos = call(catalog, "getTargetPhotos")
	if type(photos) ~= "table" then
		return {}
	end
	return PhotoIds.forPhotos(photos)
end

--[[ One sentence per reason, so a probe or a dialog never invents one. Each names
     what the PERSON can do about it. ]]
function PhotoIds.explain(reason)
	local R = PhotoIds.REASONS

	if reason == R.notPublished then
		return "This photo has not been published anywhere yet."
			.. " Publish it to Flickr first, then come back."
	elseif reason == R.notFlickr then
		return "This photo is published, but not through Adobe's Flickr service."
			.. " FlickrGroupAddr can only queue photos that are already on Flickr."
	elseif reason == R.noRemoteId then
		return "This photo is in a Flickr collection, but Lightroom has not recorded"
			.. " a Flickr ID for it yet. Publish the collection, then come back."
	elseif reason == R.conflicting then
		return "This photo carries two different Flickr IDs, which happens when it"
			.. " was published to two Flickr accounts. FlickrGroupAddr will not guess"
			.. " which one you meant."
	end

	return "No Flickr ID could be found for this photo."
end

return PhotoIds
