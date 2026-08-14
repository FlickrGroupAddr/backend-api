-- Initial schema.
--
-- Where a constraint could have been left to application code, it is here instead: a
-- violated invariant should be a failed write, not a subtle behavior nobody notices.

-- users -- ADR-07 (the Flickr account IS the identity) and ADR-09 (tokens encrypted).
-- No email, no password, no contact detail. The NSID is the whole identity.
CREATE TABLE users (
  nsid                          TEXT    PRIMARY KEY,

  -- Display only, refreshed at login. Never a key: usernames change, NSIDs do not.
  flickr_username               TEXT,

  -- ADR-09. AES-GCM, with the 12-byte IV prepended to each value so a value and the
  -- nonce that decrypts it cannot be separated by accident.
  access_token_encrypted        BLOB    NOT NULL,
  access_token_secret_encrypted BLOB    NOT NULL,

  -- Which key encrypted the two above. Rotating the token key means re-encrypting every
  -- stored token; this column makes that an incremental migration rather than one
  -- all-or-nothing transaction. The only forward-looking column here, and it costs an int.
  token_key_version             INTEGER NOT NULL DEFAULT 1,

  -- ADR-02: set on code 98 or 99, cleared by a successful login.
  needs_relink                  INTEGER NOT NULL DEFAULT 0 CHECK (needs_relink IN (0, 1)),

  created_at                    INTEGER NOT NULL,
  updated_at                    INTEGER NOT NULL
) STRICT;

-- requests -- the queues. ADR-03, ADR-02, ADR-05.
CREATE TABLE requests (
  -- **The monotonic id IS the queue order.** Safer than a timestamp, which can tie.
  -- AUTOINCREMENT additionally stops SQLite reusing a deleted row's id, which would
  -- silently put a new request at the head of a queue it should have joined the back of.
  id              INTEGER PRIMARY KEY AUTOINCREMENT,

  nsid            TEXT    NOT NULL REFERENCES users (nsid) ON DELETE CASCADE,
  photo_id        TEXT    NOT NULL,
  group_id        TEXT    NOT NULL,

  -- A request leaves its queue only by resolving. ADR-03.
  state           TEXT    NOT NULL DEFAULT 'pending'
                          CHECK (state IN ('pending', 'resolved')),

  --   succeeded            -- added to the pool
  --   already_in_pool      -- code 3. ADR-05 treats this as success, not error
  --   queued_for_moderator -- codes 6 and 7. NOT a failure and NOT a success
  --   failed               -- terminal failure, ADR-02
  outcome         TEXT    CHECK (outcome IN (
                            'succeeded',
                            'already_in_pool',
                            'queued_for_moderator',
                            'failed'
                          )),

  -- ADR-02 records the RAW code, including ones this project does not recognize. That is
  -- what makes a future classification change a data question rather than forensics.
  flickr_code     INTEGER,

  attempts        INTEGER NOT NULL DEFAULT 0,
  created_at      INTEGER NOT NULL,
  last_attempt_at INTEGER,
  resolved_at     INTEGER,

  -- Pending means undecided; resolved means both fields are filled in. As a constraint,
  -- a half-written resolution cannot be committed.
  CHECK (
    (state = 'pending'  AND outcome IS NULL     AND resolved_at IS NULL) OR
    (state = 'resolved' AND outcome IS NOT NULL AND resolved_at IS NOT NULL)
  )
) STRICT;

-- Partial, because resolved rows accumulate forever and are never the head of anything.
CREATE INDEX idx_requests_queue
  ON requests (nsid, group_id, id)
  WHERE state = 'pending';

-- ADR-05's cheap guard, which looks at RESOLVED rows and so cannot use the partial below.
CREATE INDEX idx_requests_pair
  ON requests (nsid, photo_id, group_id);

-- At most one outstanding request per pair. ADR-04 permits RE-submitting a pair that
-- reached a moderator, but only after the first resolved -- never two in flight. Enforced
-- here so a double-clicked button cannot put one photo in front of one volunteer twice.
CREATE UNIQUE INDEX idx_requests_one_pending_per_pair
  ON requests (nsid, photo_id, group_id)
  WHERE state = 'pending';

-- moderated_pairs -- ADR-04. Every pair that reached a human's queue, kept permanently.
--
-- **Deliberately NOT a foreign key to requests.** These records must outlive the request
-- row, the queue, and any later cleanup; a cascade would delete exactly the history the
-- warning depends on.
--
-- Named for what is KNOWN -- the request reached a queue -- and not for a rejection,
-- because the Flickr API reports no such signal. See docs/FLICKR.md.
CREATE TABLE moderated_pairs (
  nsid          TEXT    NOT NULL,
  photo_id      TEXT    NOT NULL,
  group_id      TEXT    NOT NULL,

  -- 6 or 7. Kept alongside the pair so the interface can tell them apart later without a
  -- schema change: a code 7 on resubmission means the original is still undecided.
  flickr_code   INTEGER NOT NULL CHECK (flickr_code IN (6, 7)),

  first_seen_at INTEGER NOT NULL,
  last_seen_at  INTEGER NOT NULL,

  PRIMARY KEY (nsid, photo_id, group_id)
) STRICT;
