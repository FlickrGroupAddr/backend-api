--[[
  Is there an UNDOCUMENTED source of randomness in Lightroom Classic?

  **The documented answer is no, and it was measured on 2026-08-16** by reading
  the vendored SDK reference: no `LrUUID`, no `generateUUID`, no
  `getRandomValues`, and `LrMath` carries exactly three functions -- `bitAnd`,
  `bitOr`, `bitXor`. `LrDigest` hashes and `LrPasswords` stores, so the SDK can
  keep a secret and cannot mint one.

  **Absent from the documentation is not absent from the runtime**, and Terry
  asked the right question: Adobe ships namespaces it does not document. Nothing
  outside Lightroom can answer it. `luac -p` parse-checks this file; only the
  application can execute `import("LrUUID")`.

  READ-ONLY. No network, no catalog access, no writes except one text file on
  the desktop.

  WHAT A PASS WOULD AND WOULD NOT PROVE
  -------------------------------------
  A value can look like a version-4 UUID and still come from a clock-seeded
  `rand()`. **Shape is not provenance.** Six hex digits in the right places cost
  nothing to fake and are exactly what a weak generator produces after masking.

  So this probe reports THREE things separately, and they MUST NOT be collapsed:

    1. Does the namespace exist at all?
    2. Does its output have version-4 SHAPE?
    3. Do 1024 draws collide?

  A clean sweep of all three raises the question to "worth a real statistical
  review". It does not answer it. **Only Adobe can say what feeds the generator**,
  and a design that needs a CSPRNG MUST NOT rest on inference from output.

  A collision, or a version nibble that is not 4, is decisive in the other
  direction -- and that is the outcome this probe is actually built to catch,
  because a negative result here closes the question for good.

  `LrTasks.pcall`, never bare `pcall`. Lightroom runs plug-in code as coroutines
  and SDK calls yield; Lua 5.1 cannot yield across a `pcall` boundary.
]]

local LrDialogs = import("LrDialogs")
local LrTasks = import("LrTasks")
local LrPathUtils = import("LrPathUtils")
local LrDate = import("LrDate")

local DRAWS = 1024

--[[ Namespaces to try. `LrUUID` is Terry's candidate; the rest are the names a
     vendor plausibly uses for the same job. Guessing names is weak evidence, so
     the global sweep below backs it up by ENUMERATING what is really there. ]]
local CANDIDATE_NAMESPACES = {
	"LrUUID", "LrUuid", "LrGUID", "LrGuid",
	"LrRandom", "LrCrypto", "LrSecurity", "LrSecureRandom",
	"LrMath", "LrStringUtils", "LrSystemInfo", "LrDigest",
}

--[[ If a namespace turns up, the function might not be called `generateUUID`.
     Probing a list of names beats assuming one. ]]
local CANDIDATE_FUNCTIONS = {
	"generateUUID", "generateUuid", "generateGUID", "generate",
	"uuid", "newUUID", "createUUID", "new", "random", "randomBytes",
}

--[[ 8-4-4-4-12 hex. Built by concatenation because a 36-character pattern
     literal is unreadable and a miscount in one would silently never match. ]]
local HEX8 = "%x%x%x%x%x%x%x%x"
local HEX4 = "%x%x%x%x"
local HEX12 = "%x%x%x%x%x%x%x%x%x%x%x%x"
local UUID_PATTERN = "^" .. HEX8 .. "%-" .. HEX4 .. "%-" .. HEX4 ..
	"%-" .. HEX4 .. "%-" .. HEX12 .. "$"

--[[ **Prove the validator can FAIL before trusting it to pass.** A pattern with
     a miscounted digit matches nothing, and "no valid UUIDs" would then read as
     a finding about Lightroom rather than a bug in this file. Same guard the
     diagram build puts on its collision detector. ]]
local VALIDATOR_CASES = {
	{ "3f2504e0-4f89-41d3-9a0c-0305e82c3301", true, "textbook v4 shape" },
	{ "3F2504E0-4F89-41D3-9A0C-0305E82C3301", true, "uppercase is still hex" },
	{ "3f2504e0-4f89-11d3-9a0c-0305e82c3301", false, "version nibble is 1, not 4" },
	{ "3f2504e0-4f89-41d3-1a0c-0305e82c3301", false, "variant nibble is 1" },
	{ "3f2504e04f8941d39a0c0305e82c3301", false, "no dashes" },
	{ "3f2504e0-4f89-41d3-9a0c-0305e82c33", false, "too short" },
	{ "zzzzzzzz-4f89-41d3-9a0c-0305e82c3301", false, "not hex" },
}

--[[ Returns ok, reason. Checks SHAPE only, and the name says so. ]]
local function looks_like_v4(value)
	if type(value) ~= "string" then
		return false, "not a string (" .. type(value) .. ")"
	end
	if #value ~= 36 then
		return false, "length " .. #value .. ", expected 36"
	end
	if not value:match(UUID_PATTERN) then
		return false, "does not match 8-4-4-4-12 hex"
	end
	local version = value:sub(15, 15):lower()
	if version ~= "4" then
		return false, "version nibble is '" .. version .. "', expected '4'"
	end
	local variant = value:sub(20, 20):lower()
	if not variant:match("[89ab]") then
		return false, "variant nibble is '" .. variant .. "', expected 8, 9, a or b"
	end
	return true, "version-4 shape"
end

local function self_test()
	local failures = {}
	for _, case in ipairs(VALIDATOR_CASES) do
		local got = looks_like_v4(case[1])
		if got ~= case[2] then
			failures[#failures + 1] = string.format(
				"        %s -- got %s, want %s", case[3], tostring(got), tostring(case[2])
			)
		end
	end
	if #failures == 0 then
		return string.format("Validator self-test: %d/%d passed",
			#VALIDATOR_CASES, #VALIDATOR_CASES)
	end
	return "Validator self-test FAILED -- every result below is meaningless\n" ..
		table.concat(failures, "\n")
end

--[[ Lightroom namespaces are not always plain tables, so `pairs` can throw.
     A failed enumeration is reported rather than swallowed -- it is a different
     answer from "the namespace is empty". ]]
local function describe_namespace(ns)
	local lines = { string.format("        Lua type: %s", type(ns)) }

	local ok, keys = LrTasks.pcall(function()
		local found = {}
		for key, value in pairs(ns) do
			found[#found + 1] = string.format("%s (%s)", tostring(key), type(value))
		end
		table.sort(found)
		return found
	end)

	if ok and keys and #keys > 0 then
		lines[#lines + 1] = string.format("        Keys (%d): %s", #keys, table.concat(keys, ", "))
	elseif ok then
		lines[#lines + 1] = "        Keys: none enumerable (pairs returned nothing)"
	else
		lines[#lines + 1] = "        Keys: pairs() threw -- userdata with a metatable, most likely"
	end

	--[[ Index-probing works where enumeration does not, which is the usual shape
	     for an SDK namespace backed by C. ]]
	local reachable = {}
	for _, name in ipairs(CANDIDATE_FUNCTIONS) do
		local got_ok, member = LrTasks.pcall(function() return ns[name] end)
		if got_ok and member ~= nil then
			reachable[#reachable + 1] = string.format("%s (%s)", name, type(member))
		end
	end
	if #reachable > 0 then
		lines[#lines + 1] = "        Reachable by name: " .. table.concat(reachable, ", ")
	else
		lines[#lines + 1] = "        Reachable by name: none of the candidate function names"
	end

	return table.concat(lines, "\n"), reachable
end

--[[ Draw many values and report the two things that are decisive rather than
     suggestive: a duplicate, and a version nibble that is not 4. ]]
local function stress(fn)
	local seen, duplicates, bad_shape = {}, 0, nil
	local first, last
	local started = LrDate.currentTime()

	for i = 1, DRAWS do
		local ok, value = LrTasks.pcall(fn)
		if not ok then
			return string.format("        Draw %d threw: %s", i, tostring(value))
		end
		if i == 1 then first = value end
		last = value

		local shaped, reason = looks_like_v4(value)
		if not shaped and bad_shape == nil then
			bad_shape = string.format("draw %d: %s (%s)", i, tostring(value), reason)
		end
		if seen[value] then
			duplicates = duplicates + 1
		end
		seen[value] = true
	end

	local elapsed = (LrDate.currentTime() - started) * 1000
	local lines = {
		string.format("        Drew %d values in %.1f ms", DRAWS, elapsed),
		string.format("        First: %s", tostring(first)),
		string.format("        Last : %s", tostring(last)),
		string.format("        Duplicates: %d  %s", duplicates,
			duplicates == 0 and "(none -- as required)" or "*** COLLISION, DECISIVE FAILURE ***"),
	}
	if bad_shape then
		lines[#lines + 1] = "        Shape: FAILED -- " .. bad_shape
	else
		lines[#lines + 1] = string.format("        Shape: all %d carry version-4 shape", DRAWS)
	end
	return table.concat(lines, "\n")
end

--[[ What `math.random` really is here. The concern is not its period, it is its
     SEED: if two Lightroom instances start in the same second and seed from the
     clock, they produce the same sequence. This demonstrates that rather than
     asserting it. ]]
local function math_random_report()
	local lines = {}

	math.randomseed(12345)
	local a = { math.random(), math.random(), math.random() }
	math.randomseed(12345)
	local b = { math.random(), math.random(), math.random() }

	local identical = a[1] == b[1] and a[2] == b[2] and a[3] == b[3]
	lines[#lines + 1] = string.format(
		"        Same seed, same sequence: %s%s",
		tostring(identical),
		identical and "  -- so the only secret is the SEED" or "  -- unexpected, investigate")

	--[[ **THE FIRST VERSION OF THIS MEASURED NOTHING, and the way it failed is the
	     reason it is written up rather than quietly replaced.**

	     It drew `math.random(0, 2147483647)` and reported the largest of 4096.
	     The answer was 0, which looked like a devastating finding about
	     Lightroom's generator and was a bug in this file. Lua 5.1 reads both
	     bounds with `luaL_checkint`, so the span `up - low + 1` is 2^31 -- which
	     overflows a signed 32-bit int to negative. Every draw came back negative,
	     and `v > biggest` never fired against an initial 0.

	     **A probe that reports a number it did not measure is worse than one that
	     crashes**, because the number gets believed. Same rule the three-verdict
	     wrapper at the bottom of this file exists to enforce, violated one level
	     down inside a helper.

	     Counting COLLISIONS measures the state space directly and cannot overflow,
	     and it is the same instrument the UUID stress uses -- so the two results
	     are comparable rather than merely adjacent. ]]
	local DRAWS_RANDOM = 4096
	local seen, duplicates = {}, 0
	math.randomseed(os.time())
	for _ = 1, DRAWS_RANDOM do
		local v = math.random()
		if seen[v] then duplicates = duplicates + 1 end
		seen[v] = true
	end
	--[[ Expected collisions among k draws from N values is about k^2/2N. At
	     k=4096 that is 8.4e6, so a 15-bit rand() (N=32768) would produce roughly
	     256 of them and a 32-bit one roughly 2. Zero says the space is wide;
	     it says NOTHING about whether it is predictable. ]]
	lines[#lines + 1] = string.format(
		"        Collisions in %d raw math.random() draws: %d", DRAWS_RANDOM, duplicates)
	lines[#lines + 1] =
		"        (~256 would indicate a 15-bit rand(); ~2 a 32-bit one)"
	lines[#lines + 1] = string.format(
		"        Clock seed material available: os.time()=%d", os.time())

	return table.concat(lines, "\n")
end

local function run()
	local report = {
		"FGA entropy probe -- is there an undocumented randomness source?",
		string.format("Run at: %s", os.date("%Y-%m-%d %H:%M:%S")),
		"",
		self_test(),
		"",
		"NAMESPACE SWEEP",
		"---------------",
	}

	local winners = {}

	for _, name in ipairs(CANDIDATE_NAMESPACES) do
		--[[ ADR-23 Rule 3 forbids importing an undocumented namespace. This probe
		     MEASURES them instead of depending on them: the call is wrapped in
		     LrTasks.pcall, so an absent namespace is a REPORTED OUTCOME rather than a
		     crash, and no plug-in behavior rests on the result. ADR-23 names this file
		     as the one place that MUST keep doing it. ]]
		local ok, ns = LrTasks.pcall(function() return import(name) end)   -- SDK-UNDOCUMENTED-EXEMPT: measures namespaces rather than depending on them, guarded by LrTasks.pcall
		if ok and ns ~= nil then
			report[#report + 1] = string.format("    %s: PRESENT", name)
			local described, reachable = describe_namespace(ns)
			report[#report + 1] = described
			for _, fname in ipairs(CANDIDATE_FUNCTIONS) do
				local got_ok, member = LrTasks.pcall(function() return ns[fname] end)
				if got_ok and type(member) == "function" then
					winners[#winners + 1] = { name .. "." .. fname, member }
				end
			end
			local _ = reachable
		else
			report[#report + 1] = string.format("    %s: absent (%s)", name,
				tostring(ns):gsub("%s+", " "):sub(1, 90))
		end
	end

	--[[ Guessing names finds only what you thought of. Sweeping `_G` finds what
	     is actually loaded, which is the stronger instrument and the reason a
	     blank namespace sweep above is not the end of the answer. ]]
	report[#report + 1] = ""
	report[#report + 1] = "GLOBALS BEGINNING WITH 'Lr'"
	report[#report + 1] = "---------------------------"
	local globals = {}
	local swept = LrTasks.pcall(function()
		for key, value in pairs(_G) do
			if type(key) == "string" and key:sub(1, 2) == "Lr" then
				globals[#globals + 1] = string.format("%s (%s)", key, type(value))
			end
		end
		table.sort(globals)
	end)
	if swept and #globals > 0 then
		report[#report + 1] = "    " .. table.concat(globals, ", ")
	elseif swept then
		report[#report + 1] = "    None. Namespaces arrive through import() rather than as globals."
	else
		report[#report + 1] = "    Sweep of _G threw."
	end

	report[#report + 1] = ""
	report[#report + 1] = "GENERATOR STRESS"
	report[#report + 1] = "----------------"
	if #winners == 0 then
		report[#report + 1] = "    No candidate generator function was reachable. Nothing to stress."
	else
		for _, winner in ipairs(winners) do
			report[#report + 1] = string.format("    %s", winner[1])
			report[#report + 1] = stress(winner[2])
		end
	end

	report[#report + 1] = ""
	report[#report + 1] = "math.random, FOR COMPARISON"
	report[#report + 1] = "---------------------------"
	report[#report + 1] = math_random_report()

	report[#report + 1] = ""
	report[#report + 1] = "HOW TO READ THIS"
	report[#report + 1] = "----------------"
	report[#report + 1] = "    A namespace that is absent closes the question."
	report[#report + 1] = "    A collision in the stress run closes it the other way, decisively."
	report[#report + 1] = "    Version-4 SHAPE proves the format and says NOTHING about the source."
	report[#report + 1] = "    A weak generator masked into UUID layout passes every check above."

	local text = table.concat(report, "\n")

	--[[ Guarded, and the guard is the point. The measurement is the sweep; the
	     file is a convenience, and a read-only desktop MUST NOT throw away the
	     answer. ]]
	local out = LrPathUtils.child(LrPathUtils.getStandardFilePath("desktop"), "fga-entropy.txt")
	local wrote = LrTasks.pcall(function()
		local handle = assert(io.open(out, "w"))
		handle:write(text)
		handle:close()
	end)
	if not wrote then
		out = "(could not write the file -- the report above is the result)"
	end

	LrDialogs.message("FGA entropy probe", text .. "\n\nWritten to:\n" .. out, "info")
end

LrTasks.startAsyncTask(function()
	--[[ Three outcomes, not two. A probe whose own failure reads as a finding is
	     how spike 0.1 nearly killed the publish-service design by reporting
	     REFUTED when it had actually broken. ]]
	local ok, err = LrTasks.pcall(run)
	if not ok then
		LrDialogs.message("FGA entropy probe INCONCLUSIVE -- the probe itself failed",
			tostring(err), "critical")
	end
end)
