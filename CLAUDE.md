# FlickrGroupAddr backend-api

**RFC 2119 keywords, and the capitals are load-bearing.** MUST and MUST NOT are absolute; SHOULD
and SHOULD NOT are strong defaults a good argument may overrule; MAY is genuinely optional.

## Naming rules, each fixing a real collision

**Never write "DO". Write "Durable Object" in full, every time.** Diagrams, documents, commit
messages, code comments, conversation. Not `DOs`, not `DO-shaped`, not "DO alarms". Terry is a
long-time DigitalOcean customer and the abbreviation collides with that in his head at exactly the
moment he is skimming rather than reading — which is how a years-old diagram gets read. The
diagram build fails if a standalone `DO` reaches the canvas.

**Architecture decisions are `ADR-nn`, never `D-n`.** Cloudflare's SQLite database is called D1 and
this project refers to it constantly, so a decision numbered D1 beside a database named D1 is the
same class of collision.

**Zero-pad any number that will ever be sorted.** `ADR-07` not `ADR-7`; the REST API is
`/api/v001/*`. Unpadded numbers sort as `1, 10, 2` and cannot be retrofitted cheaply once cited.

**Prefer the unabbreviated form whenever a short form could plausibly mean something else in his
world.** Cloud vendors, storage products, and protocol names are the usual offenders.

## Dates are versions

There is no `v1`/`v2`/`draft`/`final` on this project. **Artifacts are dated, and the filename and
any in-document date MUST come from one source** so they cannot drift. Bumping a date means
renaming the file too — use `git mv` so history follows.

## The architecture diagram is generated

**Edit `scripts/build-diagram.py`, never the `.drawio`.** A hand edit to the XML is lost on the
next build.

```
python scripts/build-diagram.py
```

builds and validates in one step. It runs twelve geometry and consistency assertions — collisions,
arrow levelness, label fit, edge-PoP containment, badge placement, colour distance, text fit,
column alignment, and the `DO` ban — and **refuses to write a diagram that fails any of them**.
Most of those checks exist because a defect got past everything already there, so when one fires it
is usually right.

## ADR-08 outranks every other decision

**Fail-polite: where an outcome could mean a person declined, treat it as terminal** — even when it
could also mean something retryable. FGA submits photos into queues that unpaid volunteer
moderators work through, and retrying into a human is the one failure this project will not ship.
Read `docs/architecture/DECISIONS.md` before resolving any conflict between the other decisions.

## The old FlickrGroupAddr repos are stale reference

The GitHub org holds roughly a decade of abandoned attempts. **Mine them for domain facts** — the
per-group daily add limits, what the API surface had to cover — and **do not inherit their
architecture**. Precedent is the weakest argument available here.

## Where things live

| | |
|---|---|
| `docs/architecture/DECISIONS.md` | The ADRs, and a verified-facts table where every row records how it was established |
| `docs/architecture/*.drawio` | Generated. Do not edit. |
| `scripts/build-diagram.py` | The generator and its assertions |
| `scripts/check-diagram-date.py` | SessionStart hook; reports whether the diagram's date is stale |
