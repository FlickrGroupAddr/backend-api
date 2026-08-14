import { z } from "zod";

/**
 * Who may see the admin surface.
 *
 * **`ADMIN_NSIDS` is a Worker secret holding a JSON array of NSID strings.** It is a
 * secret rather than a `vars` entry not because an NSID is confidential -- it is on every
 * Flickr profile page -- but because `wrangler.jsonc` is committed to a public repository,
 * and publishing the list of who can see operational data is free reconnaissance.
 *
 * **THIS MUST FAIL CLOSED, and that is the only interesting property here.** A missing,
 * malformed, or empty secret admits NOBODY. The tempting failure is the other way: a
 * config mistake in production silently opening the dashboard to every signed-in user,
 * with no error anywhere because "no allowlist" reads as "no restriction".
 *
 * **Deliberately NOT constant-time.** `crypto.subtle.timingSafeEqual` exists in this
 * runtime and ADR-14 reaches for the platform, but there is nothing to protect: the
 * caller's NSID arrives from their own signature-verified session, so they already know
 * it, and membership in this list is not a value an attacker can grind for. Using a
 * constant-time compare here would be cargo cult, and it would imply a threat model that
 * does not exist.
 */

/** An NSID looks like `12345678@N00`. Validated for shape, never interpreted. */
const nsid = z
	.string()
	.min(3)
	.max(64)
	.regex(/^[0-9]+@N[0-9]{2}$/, "not an NSID");

const allowlist = z.array(nsid).max(64);

export type AdminCheck = {
	readonly admin: boolean;
	/** Set only when the secret itself is broken, so a route can log it. */
	readonly configError: string | null;
};

/**
 * Parses the secret and answers whether this NSID is on it.
 *
 * Returns a reason rather than throwing, because the caller's job is to deny quietly and
 * log loudly, and an exception here would surface as a 500 that looks like a bug in the
 * dashboard rather than a mistake in configuration.
 */
export function checkAdmin(
	callerNsid: string,
	secret: string | undefined,
): AdminCheck {
	if (secret === undefined || secret.trim() === "") {
		return { admin: false, configError: "ADMIN_NSIDS is not set" };
	}

	let parsed: unknown;
	try {
		parsed = JSON.parse(secret);
	} catch {
		return { admin: false, configError: "ADMIN_NSIDS is not valid JSON" };
	}

	const result = allowlist.safeParse(parsed);
	if (!result.success) {
		return {
			admin: false,
			configError: "ADMIN_NSIDS is not an array of NSID strings",
		};
	}

	// An empty array is valid JSON and a valid array, and it means nobody. That is a
	// deliberate way to switch the surface off without deleting the secret.
	return { admin: result.data.includes(callerNsid), configError: null };
}
