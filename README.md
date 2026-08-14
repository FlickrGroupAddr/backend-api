# FlickrGroupAddr

**Flickr limits how many photos you may add to a group each day.** Adding a batch by hand means
coming back every day for weeks.

**FGA queues each request and keeps trying until it lands.**

## Status, verified 2026-08-14

| | |
|---|---|
| API | <https://fga-backend-api.terryott.workers.dev> |
| Health | `/health` answers `{"status":"ok"}` |
| Auth | Every `/v001/*` route answers `401` without a session cookie |
| Nightly sweep | Cron `15 0 * * *` |
| Frontend | None yet |
| Domain | `flickrgroupaddr.com` is not owned yet |

## Read this before anything else

**Group moderators are unpaid volunteers.** A moderated group does not reject an add. It puts the
photo in a queue for a person to review.

**So where an outcome could mean a person already declined, FGA stops.** It never retries into a
human. That rule outranks every other decision in this project.

It is ADR-08. See [docs/architecture/DECISIONS.md](docs/architecture/DECISIONS.md).

## Where to go

| You want to | Read |
|---|---|
| Run it, or rebuild it | [docs/SETUP.md](docs/SETUP.md) |
| Change the code | [docs/architecture/DECISIONS.md](docs/architecture/DECISIONS.md) |
| Call the Flickr API | [docs/FLICKR.md](docs/FLICKR.md) |
| See the shape of it | [the architecture diagram](docs/architecture/) |

## The gate

```
npm run check
```

Typecheck, lint, and 178 tests. **It MUST be clean before a commit.**

## What it is built on

Cloudflare Workers, D1, and one Durable Object. TypeScript. Three runtime dependencies, each with
no dependencies of its own: `hono`, `jose`, `zod`.
