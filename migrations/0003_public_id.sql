-- Gives every request an opaque public identifier. ADR-16.
--
-- **WHY A SECOND COLUMN AND NOT A NEW PRIMARY KEY.** `requests.id` is not merely an
-- identifier, it is ADR-03's FIFO ORDERING KEY -- `queueHeads` runs `SELECT MIN(q.id)`.
-- Every UUID form ties somewhere, and in SQLite a text key also costs the rowid:
-- `INTEGER PRIMARY KEY` IS the rowid, so it would turn a direct seek into an index
-- lookup plus a row fetch.
--
-- **WHY v4 AND NOT v7.** This column exists to be unguessable. A UUIDv7 spends its first
-- 48 bits on a plaintext millisecond timestamp -- 74 random bits against v4's 122 -- and
-- republishes its own creation time to anyone holding it. v7 is the better default for a
-- primary key, where time-ordering buys index locality. That is not this column's job.

CREATE TABLE requests_rebuilt (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,

  -- NOT NULL and UNIQUE are both load-bearing: a null would silently become an
  -- unaddressable request, and a duplicate would let one user's withdraw reach another's
  -- row before the nsid check ever ran.
  public_id       TEXT    NOT NULL UNIQUE,

  nsid            TEXT    NOT NULL REFERENCES users (nsid) ON DELETE CASCADE,
  photo_id        TEXT    NOT NULL,
  group_id        TEXT    NOT NULL,

  state           TEXT    NOT NULL DEFAULT 'pending'
                          CHECK (state IN ('pending', 'resolved')),

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

-- Backfill only. The Worker mints new ones with `crypto.randomUUID()`, a CSPRNG v4.
-- **SQLite's `random()` MUST NOT be used for new values** -- it is a PRNG. The layout
-- below pins the version nibble to 4 and the variant to one of 8/9/a/b, so these are
-- indistinguishable from the Worker's.
INSERT INTO requests_rebuilt
  (id, public_id, nsid, photo_id, group_id, state, outcome, flickr_code,
   attempts, created_at, last_attempt_at, resolved_at)
SELECT
   id,
   lower(
     hex(randomblob(4)) || '-' ||
     hex(randomblob(2)) || '-4' ||
     substr(hex(randomblob(2)), 2) || '-' ||
     substr('89ab', 1 + (abs(random()) % 4), 1) ||
     substr(hex(randomblob(2)), 2) || '-' ||
     hex(randomblob(6))
   ),
   nsid, photo_id, group_id, state, outcome, flickr_code,
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
