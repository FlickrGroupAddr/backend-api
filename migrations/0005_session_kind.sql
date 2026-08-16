-- A second kind of credential: the Lightroom plug-in's token.
--
-- **ONE TABLE, ONE MINTING PATH, ONE VERIFICATION PATH.** A separate `device_tokens`
-- table was the obvious alternative and it is the wrong one, because this project has
-- already been bitten by exactly that shape. `CLAUDE.md` on `src/session.ts`: *"The only
-- place that knows the cookie's name or attributes. They were once duplicated, and one
-- copy had silently lost `HttpOnly`."*
--
-- A second table means a second mint, a second verify, and a second place for a security
-- attribute to go quietly missing. **The failure is documented, in this repository, about
-- this exact code.** One column and one comparison is a smaller surface than two tables
-- that must be kept in step.
--
-- **WHAT IS ACTUALLY THE SAME.** Both are opaque bearer handles naming an nsid. Both
-- store only `SHA-256(id)`. Both verify the HMAC before any read. None of that wants
-- reinventing per credential class.
--
-- **WHAT DIFFERS IS POLICY, NOT MECHANISM:**
--
--   * Delivery. The browser gets an `HttpOnly; Secure; SameSite` cookie. The plug-in
--     sends an `Authorization` header, because it has no browser to protect it.
--   * CSRF. Applies to the cookie and NOT to the header, which is never sent
--     automatically by anything.
--   * Lifetime. A browser session can be short because re-login is one click. A plug-in
--     that demands re-login daily is not worth installing.
--   * Reach. A plug-in token MUST NOT be able to revoke other credentials or change
--     account settings, or a stolen laptop can lock the owner out of their own account.
--
-- **DEFAULT 'browser', so every existing row keeps behaving exactly as it did.** A
-- migration that changed the meaning of live sessions would sign everybody out, and
-- worse, would do it for a reason nobody could see in the release notes.

ALTER TABLE sessions ADD COLUMN kind TEXT NOT NULL DEFAULT 'browser'
  CHECK (kind IN ('browser', 'plugin'));

-- **The listing query for the revocation UI**, which is the whole reason a user can ever
-- kill a plug-in token without killing their browser session. Ordered by kind first
-- because that is how the list is grouped on screen.
CREATE INDEX idx_sessions_nsid_kind ON sessions (nsid, kind);
