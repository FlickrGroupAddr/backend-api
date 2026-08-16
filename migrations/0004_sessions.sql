-- Sessions become opaque, revocable handles. Replaces ADR-10's stateless JWS.
--
-- **WHAT THE COOKIE STOPS CARRYING.** The old value was a JWS: signed, and fully
-- readable by anyone holding it. `sub` was the user's Flickr NSID in plaintext. The
-- new value is `<id>.<hmac>` where `id` is 256 random bits and carries nothing.
--
-- **THE ADVERSARY IS NOT THE USER.** They already know their own NSID; hiding it from
-- them would be theater. This defends against whatever ends up holding the cookie jar
-- -- an infostealer reading the browser's cookie database off disk, a synced profile, a
-- backup. `HttpOnly` does nothing there: it stops JavaScript, not a native process
-- opening the store directly, which is what commodity infostealers do first.
--
-- **The asymmetry that settles it: a session is revocable and an NSID is not.** A thief
-- now gets a bearer token that dies at logout, at expiry, or whenever the server says
-- so. Before, they also got a permanent identifier tying the loot to a real Flickr
-- account, and nobody can rotate their NSID.
--
-- **WHY THE HASH AND NOT THE ID.** Storing raw ids would make a D1 leak hand over
-- directly usable bearer tokens for every live session. Same reasoning as never storing
-- a password. The server hashes what the browser sends and looks that up.
--
-- **NO `session_key_id` COLUMN, DELIBERATELY.** Rotating `SESSION_KEY` already
-- invalidates every live cookie, because the HMAC is verified under the current key and
-- an old signature fails the cheap gate before D1 is read. A column naming the signing
-- key only earns its place alongside a KEYRING that accepts more than one -- and
-- `users.token_key_version` is this project's standing warning about adding it early:
-- it has existed since migration 0001 and nothing has ever read it.

CREATE TABLE sessions (
  -- base64url of SHA2-256(id). The id itself is never stored, anywhere.
  id_hash    TEXT    PRIMARY KEY NOT NULL,

  -- ON DELETE CASCADE so removing a user removes their ability to authenticate,
  -- rather than leaving live handles pointing at a row that is gone.
  nsid       TEXT    NOT NULL REFERENCES users (nsid) ON DELETE CASCADE,

  -- Epoch milliseconds. ADR: epoch for arithmetic, ISO-8601 only for identifiers.
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,

  -- A session that expired before it was created is a bug in the minting path, and a
  -- constraint is the only place that can never be forgotten to check.
  CHECK (expires_at > created_at)
) STRICT;

-- Revoking every session a user holds -- the "sign me out everywhere" operation, and
-- the sweep's cleanup path after a user row is deleted.
CREATE INDEX idx_sessions_nsid ON sessions (nsid);

-- Deleting expired rows without scanning the table. Verification does NOT rely on this
-- index: it checks `expires_at` on the row it already fetched by primary key, so an
-- unswept table stays correct and merely grows.
CREATE INDEX idx_sessions_expires ON sessions (expires_at);
