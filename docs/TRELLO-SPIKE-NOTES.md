# Spike: can Trello be the work log?

**RFC 2119 keywords, and the capitals are load-bearing.** MUST and MUST NOT are absolute. SHOULD is
a strong default a good argument may overrule. MAY is optional.

**Terry, 2026-08-18.** He pays for Trello, likes it, and is open to it becoming the single source of
truth for `docs/WORK-LOG.md`. He set the investigation order himself: a Claude skill or MCP server
first, then a Python SDK published by Trello, then a community Python library, then a public REST or
GraphQL API. **This file records the survey either way**, because *"there wasn't one"* needs
evidence.

**Spiked 2026-08-18. Nothing was installed and nothing was connected.**

---

## The survey, in his order

| Tier | He asked for | Found |
|---|---|---|
| 1 | A Claude skill or MCP server | **`atlassian/trello-mcp-server`, OFFICIAL, and an official `trello-use` skill in the same repo** |
| 2 | A Python SDK published by Trello | **NONE.** Atlassian publishes no Trello Python library |
| 3 | A community Python library | `py-trello` 0.20.1, and it is **two years stale** |
| 4 | A public REST or GraphQL API | **REST yes, documented and live. GraphQL exists and is NOT public** |

### Tier 1 — there IS an official one, and both of us missed it

**Terry googled and found only third-party servers. He was wrong, in the good direction.**

`github.com/atlassian/trello-mcp-server` — *"Official remote MCP server for Trello."* Apache-2.0,
created 2026-06-10, last pushed 2026-08-12, repository touched 2026-08-17. **Nine weeks old**, which
is why a search turns up the third-party ones first and why it is absent from the Claude plugin
catalog on this machine.

| | |
|---|---|
| Endpoint | `https://mcp.trello.com/v1`, a REMOTE server. Nothing runs locally |
| Auth | OAuth 2.0, and access is **scoped to the one workspace approved on the consent screen** |
| Claude listing | `https://claude.ai/directory/connectors/trello` |
| Agent skill | `trello-use`, in the same repository. `npx skills install atlassian/trello-mcp-server` |
| Covers | Boards, lists, cards, checklists, search, attachments, comments, members, Inbox, Planner |

**It cannot permanently delete anything.** The README is explicit: the assistant can archive cards
and lists and nothing more. **That is the single best property it has for this use**, because the
work log is append-only by design and Trello would enforce that rather than trust it.

**The `trello-use` skill exists because the tools are easy to call wrongly** — its stated job is the
ARI id format, UTC date handling, Inbox versus board tools, and ordered creation. **Load it before
the first call rather than after the first malformed id**, which is the same rule this repository
already applies to Cloudflare's skills.

**Atlassian's OTHER MCP server does not cover Trello.** `atlassian/atlassian-mcp-server` is Jira,
Confluence, Jira Service Management, Bitbucket and Compass. **Trello appears zero times in its
README**, checked rather than assumed.

### Tier 2 — Atlassian publishes no Trello Python library

**`atlassian-python-api` is the near miss, and it is not one.** It is community-maintained by the
`atlassian-api` org, not by `atlassian`, it is very much alive at 5.0.3 pushed 2026-08-18, and a
code search for `trello` in its path returns **0 results**. It is Jira, Confluence, Bitbucket,
Insight and X-Ray.

**The name is one character from being an official SDK for the wrong products**, which is exactly
the trap `integrate-before-innovate` records. Check the org, not the name.

### Tier 3 — the community library is stale

| Package | Version | Last release | Repository |
|---|---|---|---|
| `py-trello` | 0.20.1 | **2024-06-11** | `sarumont/py-trello`, 956 stars, 65 open issues |
| `trello` | 0.9.7.3 | 2021-05-10 | `tghw/trello-py` |
| `trello-python` | 0.1.0 | 2023-05-15 | none declared |
| `pytrello` | 0.1.6 | 2018-05-06 | `dohlee/python-trello` |
| `trolly` | 0.2.2 | 2015-11-09 | `plish/Trolly` |

**`py-trello` is the only live candidate and it has not shipped in over two years.** It is not
abandoned-looking so much as finished-looking, which is a different risk: the API it wraps keeps
moving and the wrapper does not.

### Tier 4 — REST is public. GraphQL is NOT

**REST is real, documented and answered live.** Base `https://api.trello.com/1/`. An unauthenticated
`GET /1/members/me` returns `400` with the body `invalid token`, which proves the service is up and
the auth model is what the docs say: **an API key plus a token**, delegated so an application never
handles a password. Over-limit requests get `429`.

**A GraphQL endpoint EXISTS at `https://api.trello.com/graphql`, and it MUST NOT be built on.** It
is an Apollo Server and it is undocumented. Two clean probes carrying a valid `query` were both
refused with *"GraphQL operations must contain a non-empty `query` or a `persistedQuery`
extension"* — behavior consistent with **persisted queries only**, which is how a first-party web
client talks to its own backend. **An internal transport is not an API**, and it can change without
notice or a deprecation window.

---

## SETTLED 2026-08-18, and the recommendation below was OVERTAKEN

**Terry connected the server, then shut it off. Standing order, verbatim: *"do not read OR write
from trello."*** RFC 2119 sense — **MUST NOT is absolute**, and it covers the read tools too.

**The blocker is identity, and it was invisible until the connection existed.** The OAuth grant
**makes Claude the user**. `trelloReadMember` with `action: "get_me"` returned `terrydott`, Terry
Ott, timezone `America/New_York` — his own account, not a bot member.

| What we assumed | What is true |
|---|---|
| A private board is the boundary | Privacy limits which PEOPLE see a board. Claude is authenticated as an owner |
| The grant can be scoped to one board | **Workspace-scoped only.** All 25 boards in `Terry Personal` were reachable |
| Terry's signoff would be provable | A card Claude moves and a card Terry moves are **the same event by the same member** |

**That last row kills the recommendation below on its own terms.** The whole design rested on Terry
alone owning the `ready_for_review` to `completed` edge. Trello cannot tell us apart, so the edge
stops being provable and becomes an honor system — which is exactly the property the design existed
to buy.

**He created the private board FIRST and expected it to be the boundary.** It is not, and nobody
could have read that off the documentation: the README's *"workspace-scoped access"* line describes
the grant, and says nothing about the assistant borrowing the granting user's identity.

**The unfinished thread, if this is ever reopened:** give Claude its OWN free Trello account, then
invite it to one board as a guest rather than a workspace member. That would buy a real boundary and
real attribution at once. **It was NOT verified** — the safety classifier went down before the check
ran, and this file MUST NOT be read as evidence that the feature exists.

**The server stays registered** in `~/.claude.json` under user scope. **Registered is not
permission.** Nothing was created on any board; only reads happened, and those stopped when the
order landed.

**`docs/WORK-LOG.md` remains the single source of truth.**

---

## The recommendation as it stood before that, kept for the reasoning

**It was written before the identity problem surfaced, and its four arguments all still hold.**
They are the reason the fallback is comfortable rather than a consolation prize.

## The recommendation: Trello for SIGNOFF, not for the log

**The file stays the source of truth. Trello carries exactly one transition.**

**Four things break if Trello becomes the log**, and the first one is the one that matters:

- **The log leaves git.** Today a status change rides in the SAME COMMIT as the work that caused
  it — `28d8ef7` moved row 8 to `ready_for_review` alongside the 4K sheet that earned it. **A card
  moved in a web app has no such tie.** Six months later `git log` answers *why did this change* and
  a Trello activity feed does not.
- **The sync contract inverts, and one-way is why the current one is cheap.** Claude owns the file
  exclusively and Terry never edits it, so `worklog-sync-check.py` only has to compare. **A board he
  edits from a phone makes it bidirectional**, and bidirectional means real conflict resolution:
  he moves a card while a write is in flight.
- **`npm run check` cannot reach it.** A gate step would need a stored token and a network round
  trip, so the gate would then fail when Trello is slow. **A gate that cries wolf is a gate nobody
  reads**, which is the failure this repository guards against everywhere else.
- **It does not work on a plane.** `~/.claude/CLAUDE.md` already settles this shape for the build
  chain: offline is not stale. A work log he cannot open at 35,000 feet is worse than a file.

**But the phone is a real gap and the file does not close it.** He watched this session from a
phone and could not touch the list.

**So give Trello the ONE transition he owns.** Terry owns `completed` and nothing else — Claude
takes work to `ready_for_review` and stops. That is a single edge, by a single person, at a
predictable moment.

| | |
|---|---|
| A list named `Needs Terry` | Holds a card per `ready_for_review` row, nothing else |
| He drags one to `Done` | From a phone, at a red light, in one gesture |
| Claude reads it back | Stamps the date, moves the row to `Landed`, archives the card |
| The file | Stays the source of truth for every other state |
| The gate | Never calls Trello, so it cannot fail on Trello |

**The conflict surface is one edge in one direction**, which is what makes this cheap where a full
migration is not. **And Trello's inability to hard-delete matches the log's append-only rule**
rather than fighting it.

**This is a recommendation, not a decision. Terry holds it.**

---

## What a build would need, if he says yes

**Nothing here is built.** Recorded so the next session does not re-derive it.

- **Connect the official MCP server** from the Claude connectors directory, and grant the ONE
  workspace. **Read the `trello-use` skill before the first tool call.**
- **Decide where the token lives** if anything non-interactive ever needs it. **The gate MUST NOT
  need one**, per the recommendation above.
- **`scripts/worklog.py` already parses the tables**, and it is shared by the viewer and the sync
  checker. A publisher is a third consumer of the same parser rather than a second parser.
- **The `Landed` table is where a signoff lands**, and its rows never leave. A date stamp comes from
  Terry's drag, not from when Claude noticed.
