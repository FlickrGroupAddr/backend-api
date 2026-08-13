-- FlickrGroupAddr initial schema.
--
-- Every table and index below is traceable to a decision in
-- docs/architecture/DECISIONS.md. Where a constraint could have been left to
-- application code, it is in the schema instead: a violated invariant should be
-- a failed write, not a subtle behavior nobody notices.

-- ---------------------------------------------------------------------------
-- users -- ADR-01 (the Flickr account IS the identity) and ADR-03 (tokens are
-- AES-GCM encrypted at rest).
--
-- No email, no display name beyond what Flickr already publishes, no password.
-- The NSID is the whole identity, which is the point of ADR-01.
-- ---------------------------------------------------------------------------
CREATE TABLE users (
  nsid                          TEXT    PRIMARY KEY,

  -- Display only, refreshed at login. Never used as a key: Flickr usernames
  -- change and NSIDs do not.
  flickr_username               TEXT,

  -- ADR-03. AES-GCM ciphertext with the 12-byte IV prepended to each value.
  -- Storing the IV inline rather than in its own column keeps a value and the
  -- nonce that decrypts it impossible to separate by accident.
  access_token_encrypted        BLOB    NOT NULL,
  access_token_secret_encrypted BLOB    NOT NULL,

  -- Which token key encrypted the two values above. ADR-03 notes that rotating
  -- the token key means re-encrypting every stored token; this column is what
  -- makes that an incremental migration rather than one all-or-nothing
  -- transaction. It is the only forward-looking column in this schema and it
  -- costs one integer.
  token_key_version             INTEGER NOT NULL DEFAULT 1,

  -- ADR-07: codes 98 and 99 are auth failures that MUST flag the user to
  -- re-link. Set here, cleared by a successful login.
  needs_relink                  INTEGER NOT NULL DEFAULT 0 CHECK (needs_relink IN (0, 1)),

  created_at                    INTEGER NOT NULL,
  updated_at                    INTEGER NOT NULL
) STRICT;

-- ---------------------------------------------------------------------------
-- requests -- the queues. ADR-10 (FIFO per user and group), ADR-07 (classify by
-- Flickr's numeric code), ADR-05 (idempotent per photo and group).
-- ---------------------------------------------------------------------------
CREATE TABLE requests (
  -- ADR-10 requires attempts in append order. A monotonic id IS that order, and
  -- it is safer than a timestamp, which can tie. AUTOINCREMENT additionally
  -- stops SQLite reusing the rowid of a deleted row, which would silently put a
  -- new request at the head of a queue it should have joined the back of.
  id              INTEGER PRIMARY KEY AUTOINCREMENT,

  nsid            TEXT    NOT NULL REFERENCES users (nsid) ON DELETE CASCADE,
  photo_id        TEXT    NOT NULL,
  group_id        TEXT    NOT NULL,

  -- A request leaves its queue only by resolving. ADR-10.
  state           TEXT    NOT NULL DEFAULT 'pending'
                          CHECK (state IN ('pending', 'resolved')),

  -- How it resolved. Null while pending.
  --   succeeded            -- added to the pool
  --   already_in_pool      -- code 3, or getAllContexts said so. ADR-05 treats
  --                           this as success, not error.
  --   queued_for_moderator -- codes 6 and 7. Terminal by ADR-07, and the reason
  --                           ADR-08 exists. NOT a failure and NOT a success.
  --   failed               -- terminal failure, ADR-07
  outcome         TEXT    CHECK (outcome IN (
                            'succeeded',
                            'already_in_pool',
                            'queued_for_moderator',
                            'failed'
                          )),

  -- ADR-07: every attempt MUST record the numeric code Flickr returned,
  -- including codes this project does not recognize. Recording the raw code is
  -- what makes a future classification change a data question rather than a
  -- forensics exercise.
  flickr_code     INTEGER,

  attempts        INTEGER NOT NULL DEFAULT 0,
  created_at      INTEGER NOT NULL,
  last_attempt_at INTEGER,
  resolved_at     INTEGER,

  -- Pending means undecided; resolved means both fields are filled in. Stated
  -- as a constraint so a half-written resolution cannot be committed.
  CHECK (
    (state = 'pending'  AND outcome IS NULL     AND resolved_at IS NULL) OR
    (state = 'resolved' AND outcome IS NOT NULL AND resolved_at IS NOT NULL)
  )
) STRICT;

-- The queue-head lookup the nightly sweep and the API Worker both run. Partial,
-- because resolved rows accumulate forever and are never the head of anything.
CREATE INDEX idx_requests_queue
  ON requests (nsid, group_id, id)
  WHERE state = 'pending';

-- ADR-05's cheap first-pass idempotency guard: has this pair already succeeded?
CREATE INDEX idx_requests_pair
  ON requests (nsid, photo_id, group_id);

-- At most one outstanding request per pair. ADR-11 deliberately permits
-- RE-submitting a pair that already reached a moderator, but that is a new
-- request after the first resolved -- never two in flight at once. Enforced
-- here so a double-clicked button cannot put the same photo in front of the
-- same volunteer twice.
CREATE UNIQUE INDEX idx_requests_one_pending_per_pair
  ON requests (nsid, photo_id, group_id)
  WHERE state = 'pending';

-- ---------------------------------------------------------------------------
-- moderated_pairs -- ADR-11. Every pair that reached a human's queue, kept
-- permanently.
--
-- Deliberately NOT a foreign key to requests: ADR-11 requires these records to
-- outlive the request row, the queue, and any later cleanup. A cascade here
-- would delete exactly the history the warning depends on.
--
-- Named for what is known -- the request reached a queue -- and not for a
-- rejection, because no rejection signal exists in the Flickr API. See the
-- verified-facts row on moderator decisions being invisible.
-- ---------------------------------------------------------------------------
CREATE TABLE moderated_pairs (
  nsid          TEXT    NOT NULL,
  photo_id      TEXT    NOT NULL,
  group_id      TEXT    NOT NULL,

  -- 6 (added to the pending queue) or 7 (already in it). ADR-11 requires the
  -- code alongside the pair so the interface can tell those apart later without
  -- a schema change -- a code 7 on resubmission means the original is still
  -- undecided and nobody has been pestered.
  flickr_code   INTEGER NOT NULL CHECK (flickr_code IN (6, 7)),

  first_seen_at INTEGER NOT NULL,
  last_seen_at  INTEGER NOT NULL,

  PRIMARY KEY (nsid, photo_id, group_id)
) STRICT;
