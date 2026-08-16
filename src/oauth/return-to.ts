/**
 * Where the login sends the user afterwards. ADR-11.
 *
 * **A `returnTo` is an open redirect waiting to happen, and this is the whole file.**
 * Accept an arbitrary one and `flickrgroupaddr.com/oauth/login?returnTo=https://evil.com`
 * lands a freshly authenticated user on somebody else's site, session cookie already
 * set. It is the same family as ADR-11's rule against reflecting `Origin`: **never send
 * a user somewhere an attacker chose.**
 *
 * TWO CHECKS, AND THE SECOND IS NOT REDUNDANT.
 *
 * The origin check alone is sound against escaping the site. It is done by RESOLVING the
 * candidate against our own origin and comparing what comes out, rather than by pattern
 * matching, because every hand-written path validator has a bypass:
 *
 *   `//evil.com`      protocol-relative -- resolves to https://evil.com
 *   `https://evil.com` absolute -- resolves to itself
 *   `/\evil.com`      WHATWG normalizes `\` to `/` in a special scheme, so this is `//`
 *   `/%2f%2fevil.com` percent-encoded, decoded by the parser
 *
 * **`new URL(candidate, base).origin` collapses all four to a comparison a reader can
 * verify.** A regex that tried would be a puzzle nobody could review.
 *
 * The ALLOW-LIST is then a second, independent bound, and it is here because this
 * project takes ADR-17's line that no list is unbounded. It also makes adding a
 * destination a deliberate act: a future `/link` page has to be named here, which is one
 * more place somebody has to think about where a login can deposit a user.
 */

/** Every path a completed login may return to. **Adding one is a decision.** */
const ALLOWED_RETURN_PATHS: ReadonlySet<string> = new Set(["/", "/link"]);

/**
 * The path and query to return to, or `null` when the caller supplied nothing usable.
 *
 * **Returns a PATH, never a URL.** The caller composes it against `UI_ORIGIN`, so no
 * value from this function can carry an origin even if the checks below were wrong.
 * Defense in depth by return type.
 *
 * **`null` means "use the default", never an error.** A bad `returnTo` is either an
 * attack or a stale link, and in both cases depositing the person on the app root is the
 * kind thing to do. A 400 would punish the victim for the attacker's query string.
 */
export function safeReturnPath(
	candidate: string | null | undefined,
	uiOrigin: string,
): string | null {
	if (candidate === null || candidate === undefined || candidate === "") {
		return null;
	}

	let resolved: URL;
	let base: URL;
	try {
		base = new URL(uiOrigin);
		resolved = new URL(candidate, uiOrigin);
	} catch {
		return null;
	}

	if (resolved.origin !== base.origin) return null;
	if (!ALLOWED_RETURN_PATHS.has(resolved.pathname)) return null;

	return `${resolved.pathname}${resolved.search}`;
}
