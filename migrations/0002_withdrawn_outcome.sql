-- Adds 'withdrawn' to requests.outcome.
--
-- **Withdrawal is a RESOLUTION, not an erasure**, so it uses the existing state machine
-- rather than widening it. The row MUST survive: "you withdrew this" is part of the
-- account of what FGA did on someone's behalf.
--
-- A full table rebuild because SQLite cannot alter a CHECK constraint. Dropping a table
-- drops its indexes, so the three below are recreated verbatim from 0001.
--
-- **One invisible consequence:** the AUTOINCREMENT sequence is reseeded from the copied
-- rows. 0001 uses AUTOINCREMENT so a deleted row's id cannot be reused and put a new
-- request at the head of a queue. That guarantee holds going forward from the rebuild; it
-- does not extend across it. Production held zero request rows when this ran.

CREATE TABLE requests_rebuilt (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,

  nsid            TEXT    NOT NULL REFERENCES users (nsid) ON DELETE CASCADE,
  photo_id        TEXT    NOT NULL,
  group_id        TEXT    NOT NULL,

  state           TEXT    NOT NULL DEFAULT 'pending'
                          CHECK (state IN ('pending', 'resolved')),

  --   withdrawn -- reachable ONLY from 'pending', which is what makes it honest: a
  --                request that reached a moderator resolved at that moment, so nothing
  --                withdrawable has ever been in front of a person.
  outcome         TEXT    CHECK (outcome IN (
                            'succeeded',
                            'already_in_pool',
                            'queued_for_moderator',
                            'failed',
                            'withdrawn'
                          )),

  flickr_code     INTEGER,

  attempts        INTEGER NOT NULL DEFAULT 0,
  created_at      INTEGER NOT NULL,
  last_attempt_at INTEGER,
  resolved_at     INTEGER,

  CHECK (
    (state = 'pending'  AND outcome IS NULL     AND resolved_at IS NULL) OR
    (state = 'resolved' AND outcome IS NOT NULL AND resolved_at IS NOT NULL)
  )
) STRICT;

INSERT INTO requests_rebuilt
  (id, nsid, photo_id, group_id, state, outcome, flickr_code,
   attempts, created_at, last_attempt_at, resolved_at)
SELECT
   id, nsid, photo_id, group_id, state, outcome, flickr_code,
   attempts, created_at, last_attempt_at, resolved_at
FROM requests;

DROP TABLE requests;

ALTER TABLE requests_rebuilt RENAME TO requests;

CREATE INDEX idx_requests_queue
  ON requests (nsid, group_id, id)
  WHERE state = 'pending';

CREATE INDEX idx_requests_pair
  ON requests (nsid, photo_id, group_id);

CREATE UNIQUE INDEX idx_requests_one_pending_per_pair
  ON requests (nsid, photo_id, group_id)
  WHERE state = 'pending';
