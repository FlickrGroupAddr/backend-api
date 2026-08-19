--[[
  The Lightroom SDK, faked well enough to run the plug-in's PURE logic off-host.

  WHY THIS EXISTS. `QueueAdds.lua` slices lists at 200 and merges replies.
  `PhotoIds.lua` indexes published photos and matches on `localIdentifier`.
  `FgaApi.lua` maps status codes onto named failures. **None of that needs
  Lightroom, and until card #0078 nothing could run any of it** -- the vendored
  SDK ships `luac.exe`, a COMPILER, and no interpreter.

  So `npm run lua` proved the files PARSE. Nothing proved an off-by-one in the
  chunker would be caught.

  WHAT THIS IS NOT. It is not a Lightroom emulator and MUST NOT grow into one.
  It stubs the handful of namespaces the pure modules touch at load time, plus
  `LrTasks.pcall` and `LrDate.currentTime`, and nothing else. **A test that needs
  a real `LrView` is a test that belongs on the host**, and the honest answer
  there is the probes in `Info.lua`.

  RUNTIME: LuaJIT 2.1, which implements Lua 5.1 -- the version Lightroom runs.
  `DEVCOM.Lua` on winget is 5.4 and would have been the wrong language.
]]

local stubs = {}

--[[ **`LrTasks.pcall` behaves exactly like `pcall` here, and that is honest.**
     The real one exists so a call can YIELD inside it, and nothing yields off-host.
     What the plug-in relies on is the pcall CONTRACT -- catch the error, return
     false -- and that is what this provides. ]]
stubs.LrTasks = {
	pcall = function(fn, ...)
		return pcall(fn, ...)
	end,
	sleep = function(_) end,
	startAsyncTask = function(fn)
		fn()
	end,
	yield = function() end,
}

--[[ A monotonic fake clock in SECONDS, matching `LrDate.currentTime()`'s unit.
     Tests that care about elapsed time drive it with `stubs.advance`. ]]
local clock = 0
stubs.LrDate = {
	currentTime = function()
		return clock
	end,
}

function stubs.advance(seconds)
	clock = clock + seconds
end

function stubs.resetClock()
	clock = 0
end

--[[ Recording stubs. A test reads `calls` to assert WHAT was asked for, which is
     most of what matters in a module whose job is slicing and merging. ]]
stubs.LrHttp = { calls = {} }

stubs.LrPasswords = {
	store = function() end,
	retrieve = function()
		return ""
	end,
}

stubs.LrApplication = {
	activeCatalog = function()
		return nil
	end,
}

stubs.LrDialogs = { message = function() end }
stubs.LrPathUtils = {
	child = function(a, b)
		return tostring(a) .. "/" .. tostring(b)
	end,
	getStandardFilePath = function()
		return "."
	end,
}

--[[ **`import` is a GLOBAL in Lightroom**, so it has to be one here. An unknown
     namespace raises rather than returning an empty table: a silent `{}` would let
     a typo'd namespace pass the tests and fail on the host, which is the exact
     class of defect `scripts/lua-imports.py` exists to catch. ]]
function stubs.install()
	_G.import = function(name)
		local ns = stubs[name]
		if ns == nil then
			error("test stub has no namespace " .. tostring(name), 2)
		end
		return ns
	end
end

return stubs
