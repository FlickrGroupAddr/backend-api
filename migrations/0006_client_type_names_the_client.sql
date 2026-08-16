-- `plugin` becomes `lrc15_plugin`: a client type MUST name the client.
--
-- **Terry, 2026-08-16: *"let's not assume there will never be another plugin that we need
-- to treat differently."*** He is right, and the cost of being wrong is asymmetric. A
-- generic `plugin` is fine right up until a second one exists, and at that moment every
-- live token in the table is ambiguous -- there is no way to tell which client a row
-- belongs to, so the two cannot be given different lifetimes, different reach, or
-- different revocation, which is the entire reason this column exists.
--
-- **Renaming later would be worse than renaming now.** Today the value appears in zero
-- production rows: the device flow that mints it is being written in this same session and
-- has never been deployed, so `mintSession(..., "plugin")` has only ever run in a test.
-- **This is the last moment the change is free.**
--
-- **THE VERSION IS IN THE NAME AND THAT IS A DECISION, not an accident.** `lrc15_plugin`
-- says LrC 15's plug-in specifically. A future LrC 16 plug-in with the SAME policy --
-- 90-day life, same allow-list -- SHOULD keep minting `lrc15_plugin` rather than inventing
-- `lrc16_plugin`, because this column keys POLICY and not provenance. Splitting it per
-- Lightroom major would fragment the table for no behavioral difference. **A new value
-- MUST be introduced only when a client needs different treatment**, which is what the
-- rename buys the ability to express.
--
-- ## SQLite cannot alter a CHECK, so this is the twelve-step rebuild
--
-- There is no `ALTER TABLE ... DROP CONSTRAINT`. `migrations/0002` and `0003` both perform
-- this same dance for other reasons, so the cost is visible in this repository rather than
-- theoretical.
--
-- **`STRICT` is restated, and so is every CHECK, index and foreign key.** A rebuild that
-- forgets one silently ships a weaker table than the one it replaced -- and nothing would
-- fail, because the missing constraint only matters on the row that violates it. That is
-- the same failure mode ADR-22 exists to close.

-- Foreign keys are enforced in D1, so the CASCADE from `users` has to be stood back up
-- rather than assumed. Deferring the check for the length of the swap keeps the rebuild
-- atomic instead of ordering-sensitive.
PRAGMA defer_foreign_keys = ON;

CREATE TABLE sessions_rebuilt (
  id_hash     TEXT    PRIMARY KEY NOT NULL,
  nsid        TEXT    NOT NULL REFERENCES users (nsid) ON DELETE CASCADE,
  created_at  INTEGER NOT NULL,
  expires_at  INTEGER NOT NULL,
  client_type TEXT    NOT NULL DEFAULT 'browser'
                      CHECK (client_type IN ('browser', 'lrc15_plugin')),
  CHECK (expires_at > created_at)
) STRICT;

-- **The conversion runs even though it is expected to match zero rows.** Asserting that
-- production has no `plugin` rows and acting on the assertion are different things, and
-- the second one costs nothing. A row that did exist would otherwise fail the new CHECK
-- mid-migration, which is a bad way to discover the assumption was wrong.
INSERT INTO sessions_rebuilt (id_hash, nsid, created_at, expires_at, client_type)
SELECT id_hash,
       nsid,
       created_at,
       expires_at,
       CASE client_type WHEN 'plugin' THEN 'lrc15_plugin' ELSE client_type END
FROM sessions;

DROP TABLE sessions;

ALTER TABLE sessions_rebuilt RENAME TO sessions;

-- Dropping the table dropped its indexes with it. All three are recreated, with the same
-- names and the same reasoning recorded in 0004 and 0005.
CREATE INDEX idx_sessions_nsid ON sessions (nsid);
CREATE INDEX idx_sessions_expires ON sessions (expires_at);
CREATE INDEX idx_sessions_nsid_client_type ON sessions (nsid, client_type);
