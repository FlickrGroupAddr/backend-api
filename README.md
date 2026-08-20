# FlickrGroupAddr

**Flickr limits how many photos you may add to a group each day.** Adding a batch by hand means
coming back every day for weeks.

**FGA queues each request and keeps trying until it lands.**

## Status, verified 2026-08-16

| | |
|---|---|
| Site and API | <https://flickrgroupaddr.com> — one origin serves both. See ADR-18 |
| Health | `/health` answers `{"status":"ok"}` |
| Auth | **Every `/api/v001/*` route answers `401` without a session. No exceptions** — re-read against the routes 2026-08-19 |
| Device link | `POST /auth/device-link/{start,poll,approve,deny}`, plus `GET /auth/device-link/enter-user-code`. **Built 2026-08-16, not yet deployed.** See ADR-24 |
| Nightly sweep | Cron `15 0 * * *` |
| Frontend | Svelte, served by the same Worker. See ADR-18 |
| Admin | `/admin`, gated by the `ADMIN_NSIDS` allowlist. Reports findings, not figures. See ADR-19 |
| Domain | `flickrgroupaddr.com`, registered 2026-08-14, nameservers on Cloudflare |

**THE DEVICE-LINK ROUTES ARE NOT EXCEPTIONS. They live on a different prefix entirely**, and this
table said otherwise until 2026-08-19 — it still named `POST /api/v001/device/{...}`, which the
2026-08-18 move to `/auth/device-link/*` had deleted. **A stale path in the AUTH row is the worst
place in this document to be wrong**, because it describes the shape of the protected surface.

**Two of the four are deliberately unauthenticated, and that is a property of those routes rather
than a hole in the `/api/v001/*` rule.** At `start` nobody has authorized anything, so there is no
session to require — obtaining one is the point. `poll` is authenticated by its `deviceCode`
instead. **`approve` and `deny` require a BROWSER session**, which is what stops a stolen plug-in
token minting a fresh one.

## Read this before anything else

**Group moderators are unpaid volunteers.** A moderated group does not reject an add. It puts the
photo in a queue for a person to review.

**So where an outcome could mean a person already declined, FGA stops.** It never retries into a
human. That rule outranks every other decision in this project.

It is ADR-01. See [docs/architecture/DECISIONS.md](docs/architecture/DECISIONS.md).

## Where to go

| You want to | Read |
|---|---|
| **Catch up fast after time away** | **[docs/ORIENTATION.md](docs/ORIENTATION.md) — start here. It says what to skip** |
| Run it, or rebuild it | [docs/SETUP.md](docs/SETUP.md) |
| Change the code | [docs/architecture/DECISIONS.md](docs/architecture/DECISIONS.md) |
| Check every decision is tested | [docs/TRACEABILITY.md](docs/TRACEABILITY.md) — generated |
| Call the Flickr API | [docs/FLICKR.md](docs/FLICKR.md) |
| See where the Lightroom client got to | [docs/LRC-CLIENT-NOTES.md](docs/LRC-CLIENT-NOTES.md) — investigation notes. **The decisions are ADR-23, ADR-24 and ADR-25** |
| See the spike that proved it possible | [docs/lrc-spike/](docs/lrc-spike/) — the plug-in, the raw result, and the catalog probe |
| Understand the crypto blast radius | [docs/architecture/KEY-ROTATION-NOTES.md](docs/architecture/KEY-ROTATION-NOTES.md) — decided, **not yet built** |
| See the shape of it | [the architecture diagram](docs/architecture/) |

## The gate

```
npm run check
```

Typecheck, lint, the Svelte compiler check, the US English and house-vocabulary checks, a real
`luac 5.1` parse of every plug-in file, the ADR-23 SDK import gate, the Vitest suite, the
traceability gate, and the web build. **It MUST be clean before a commit.**

**No test count appears here, and its absence is the fix.** This line carried one for days, it was
wrong, and the sentence directly under it already said to quote the runner instead.
`scripts/stale-counts.py` now refuses a live count in any tracked document.

## What it is built on

Cloudflare Workers, D1, and **two Durable Objects** — one per OAuth login attempt (ADR-08), one per
device link attempt (ADR-24). TypeScript. Three runtime dependencies, each with no dependencies of
its own: `hono`, `jose`, `zod`.

The UI is Svelte, prebuilt by Vite into `web/dist` and served as static assets by the same Worker,
on one origin. **Measured 2026-08-14 from a wiped `web/dist`: 42.3 kB of JavaScript gzipped, plus
3.0 kB of CSS.**

A throwaway chunked build weighs the parts: `zod` 18.1 kB, Svelte's runtime 14.7 kB, and 10.6 kB for
all three screens. **Those do not add up to 42.3 kB, because one chunk compresses better than
three** — the shipped bundle is the single number above.
