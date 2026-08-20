import { describe, expect, it } from "vitest";
import { parse } from "../web/src/lib/router.js";

/**
 * ADR-14 and ADR-18, as the three paths a deep link can carry.
 *
 * **ADR-14 was weighed here and answered "innovate"**, on the grounds that the spec is
 * short and fully exercised. `parse` is that spec, and until 2026-08-19 nothing exercised
 * it at all -- so the carve-out was being claimed rather than met.
 *
 * **ADR-18 is what makes a bad answer here a 404 rather than a wrong screen.**
 * `not_found_handling: "single-page-application"` hands `index.html` to a cold load of
 * `/queue`, and this function reads the path back out. Every deep link in the product
 * goes through this one branch.
 */

describe("parse", () => {
	it.each(["/", "", "//", "///"])(
		"sends %s to the add screen, the app's front door",
		(pathname) => {
			expect(parse(pathname)).toEqual({ name: "add" });
		},
	);

	it.each([
		["/queue", "queue"],
		["/queue/", "queue"],
		["/admin", "admin"],
		["/admin/", "admin"],
	])("resolves %s to the %s screen", (pathname, name) => {
		expect(parse(pathname)).toEqual({ name });
	});

	/**
	 * **`/admin` resolves for everybody, and that is correct.** The route is not a
	 * permission; the server is. Hiding it here would only look like security while the
	 * API did the actual work -- and ADR-19 answers 404 rather than 403 so the surface is
	 * not confirmed either.
	 */
	it("does not pretend to be a permission check", () => {
		expect(parse("/admin").name).toBe("admin");
	});

	it.each([
		"/nope",
		"/queue/extra",
		"/admin/users",
		"/QUEUE",
		"/queue2",
		"/api/v001/me",
	])("reports %s as not found, carrying the path back", (pathname) => {
		expect(parse(pathname)).toEqual({ name: "notFound", path: pathname });
	});

	/**
	 * **The unmatched path is echoed, not summarized.** The screen shows what was asked
	 * for, which is the difference between "no such page" and a shrug -- and a mistyped
	 * deep link is the normal way somebody arrives here.
	 */
	it("keeps the original spelling, including its slashes", () => {
		const route = parse("/Queue/");
		expect(route).toEqual({ name: "notFound", path: "/Queue/" });
	});

	it("never throws, whatever the path", () => {
		for (const pathname of ["", "/", "%", "/%%%", "/a".repeat(500)]) {
			expect(() => parse(pathname)).not.toThrow();
		}
	});
});
