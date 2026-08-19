# Traceability matrix

**Generated. Do not edit.** Rebuild with `python scripts/traceability.py`.

Every decision is verified by a test. Every test defends a decision, or says why
it does not. **`--check` fails the build on either gap.**

| Column | Answers |
|---|---|
| Verified by | Does anything actually check this decision? |
| Mutation | Would the test NOTICE the code breaking it? |

**25 decisions · 61 test blocks · 46 mutations**

## Forward: decision to verification

**Method** follows MIL-STD practice. `Test` runs something. `Inspection` is verified
by reading code or config, because there is no runtime behavior to exercise.

| ADR | Decision | Method | Verified by | Mutation |
|---|---|---|---|---|
| **ADR-01** | Fail-polite. This one outranks the rest. | Test | `api.test.ts` withdrawing a request<br>`api.test.ts` ADR-01, the queue view is where fail-polite becomes visible<br>`classify.test.ts` classifyAdd<br>`classify.test.ts` classifyResult<br>`classify.test.ts` outcomeColumn<br>`device.test.ts` ADR-24: polling refuses everything it should<br>`photo-groups.test.ts` ADR-17, the groups a photo is already in<br>`schema.test.ts` ADR-22, STRICT tables refuse a wrong type<br>`sweep.test.ts` queues are independent | yes |
| **ADR-02** | Classify by Flickr's error code. Unknown means terminal. | Test | `admin.test.ts` ADR-19, findings only appear when there is something to do<br>`classify.test.ts` classifyAdd<br>`classify.test.ts` classifyResult<br>`classify.test.ts` outcomeColumn<br>`schema.test.ts` ADR-02, requests: the resolution invariant | yes |
| **ADR-03** | FIFO per (user, group). The queue is never jumped. | Test | `api.test.ts` ADR-03 and ADR-05, queueing a request<br>`batch.test.ts` ADR-03, the batch endpoint does NOT attempt at batch scale<br>`schema.test.ts` ADR-03 and ADR-16, requests: ordering<br>`sweep.test.ts` the queue is never jumped<br>`sweep.test.ts` queues are independent<br>`sweep.test.ts` ADR-04, the permanent record<br>`sweep.test.ts` does nothing on an empty night, and says so | yes |
| **ADR-04** | A pair that reached a moderator is remembered forever | Test | `admin.test.ts` ADR-19, findings only appear when there is something to do<br>`api.test.ts` ADR-04, the moderation warning<br>`batch.test.ts` ADR-20 and ADR-04, the batch endpoint refuses per group, not per batch<br>`preflight.test.ts` ADR-20, the batch preflight<br>`schema.test.ts` ADR-22, STRICT tables refuse a wrong type<br>`schema.test.ts` ADR-04, requests: one outstanding request per pair<br>`schema.test.ts` moderated_pairs<br>`sweep.test.ts` ADR-04, the permanent record | yes |
| **ADR-05** | Adds are idempotent per (photo, group) | Test | `api.test.ts` ADR-03 and ADR-05, queueing a request<br>`preflight.test.ts` ADR-20, the batch preflight | yes |
| **ADR-06** | The work engine is a nightly cron over D1 | Test | `sweep.test.ts` the queue is never jumped<br>`sweep.test.ts` queues are independent<br>`sweep.test.ts` ADR-04, the permanent record<br>`sweep.test.ts` does nothing on an empty night, and says so | — |
| **ADR-07** | The Flickr account is the identity | Test | `oauth.test.ts` buildAuthorizeUrl<br>`schema.test.ts` ADR-22, STRICT tables refuse a wrong type<br>`schema.test.ts` ADR-07 and ADR-09, users<br>`worker.test.ts` ADR-14 and ADR-07, the diagnostic page | — |
| **ADR-08** | OAuth state lives in a Durable Object | Test | `oauth.test.ts` protocolParams<br>`oauth.test.ts` authorizationHeader<br>`oauth.test.ts` buildAuthorizeUrl<br>`oauth.test.ts` parseFormResponse<br>`oauth.test.ts` the login attempt, ADR-08<br>`oauth.test.ts` sends a login to Flickr carrying a request token<br>`oauth.test.ts` ADR-11: returnTo can never leave our origin<br>`oauth.test.ts` ADR-11: the callback returns where the login STARTED | yes |
| **ADR-09** | Tokens are AES-GCM encrypted in D1, under a separate key | Test | `crypto.test.ts` round trip<br>`crypto.test.ts` nonce handling<br>`crypto.test.ts` rejection<br>`schema.test.ts` ADR-07 and ADR-09, users | yes |
| **ADR-10** | The session is an opaque, revocable handle | Test | `api.test.ts` ADR-10, authentication<br>`session.test.ts` mint and verify<br>`session.test.ts` revocation, which ADR-10 could not do<br>`session.test.ts` cookie attributes on a real login<br>`session.test.ts` clears with attributes that match, or the deletion is a no-op | — |
| **ADR-11** | The session cookie is host-only, and `Origin` is never reflected | Test | `device.test.ts` ADR-24: the confirmation page, and what it refuses<br>`oauth.test.ts` ADR-11: returnTo can never leave our origin<br>`oauth.test.ts` ADR-11: the callback returns where the login STARTED<br>`session.test.ts` mint and verify<br>`session.test.ts` revocation, which ADR-10 could not do<br>`session.test.ts` cookie attributes on a real login<br>`session.test.ts` clears with attributes that match, or the deletion is a no-op<br>`worker.test.ts` ADR-11, CORS | yes |
| **ADR-12** | No cache in front of D1 | Test | `admin.test.ts` ADR-19, the admin gate<br>`api.test.ts` ADR-12, nothing behind a session reaches a shared cache<br>`device.test.ts` ADR-24: starting a link needs no credential<br>`photo-groups.test.ts` ADR-17, the groups a photo is already in | yes |
| **ADR-13** | TypeScript, on the current stable toolchain | Inspection | *by inspection* | — |
| **ADR-14** | Integrate when feasible, innovate otherwise | Inspection | `signature.test.ts` percentEncode<br>`signature.test.ts` baseStringUri<br>`signature.test.ts` normalizeParameters<br>`signature.test.ts` signatureBaseString<br>`signature.test.ts` signingKey<br>`signature.test.ts` signHmacSha1<br>`worker.test.ts` ADR-14 and ADR-07, the diagnostic page | yes |
| **ADR-15** | Which store holds what | Inspection | *by inspection* | — |
| **ADR-16** | A request has two identifiers | Test | `schema.test.ts` ADR-03 and ADR-16, requests: ordering | — |
| **ADR-17** | No list is unbounded, whoever owns its size | Test | `api.test.ts` ADR-17, pagination<br>`api.test.ts` ADR-17, a list FGA cannot bound: the Flickr group list<br>`photo-groups.test.ts` ADR-17, the groups a photo is already in<br>`plugin-scope.test.ts` ADR-19, a plug-in token reaches only its allow-list | yes |
| **ADR-18** | One origin, an `/api` prefix, and a Svelte app shell | Test | `worker.test.ts` ADR-18, one origin split by an /api prefix | yes |
| **ADR-19** | The admin surface reports findings, not figures | Test | `admin.test.ts` ADR-19, the admin gate<br>`admin.test.ts` ADR-19, the allowlist fails closed<br>`admin.test.ts` ADR-19, findings only appear when there is something to do<br>`api.test.ts` ADR-10, authentication<br>`plugin-scope.test.ts` ADR-19, a plug-in token reaches only its allow-list | yes |
| **ADR-20** | The warning arrives before the commitment | Test | `batch.test.ts` ADR-03, the batch endpoint does NOT attempt at batch scale<br>`batch.test.ts` ADR-20 and ADR-04, the batch endpoint refuses per group, not per batch<br>`batch.test.ts` the batch endpoint's shape<br>`preflight.test.ts` ADR-20, the batch preflight | yes |
| **ADR-21** | The web sourcemap ships, and reopening this needs an extreme bar | Inspection | *by inspection* | — |
| **ADR-22** | The schema enforces the rules, and every table is `STRICT` | Test | `photo-groups.test.ts` ADR-17, the groups a photo is already in<br>`schema.test.ts` ADR-22, STRICT tables refuse a wrong type | — |
| **ADR-23** | Randomness comes from the Worker, and the undocumented `LrUUID` MUST NOT be used | Inspection | *by inspection* | — |
| **ADR-24** | The Lightroom plug-in gets its credential by device link, and holds no Flickr token | Test | `api.test.ts` ADR-10, authentication<br>`device.test.ts` ADR-24: starting a link needs no credential<br>`device.test.ts` ADR-24: the whole flow, and the token it mints<br>`device.test.ts` ADR-24: polling refuses everything it should<br>`device.test.ts` ADR-24: polling is throttled server-side, not on trust<br>`device.test.ts` ADR-24: the confirmation page, and what it refuses<br>`device.test.ts` ADR-24: approval is browser-only, and that stops escalation | yes |
| **ADR-25** | The plug-in reports whether it was TESTED against this Lightroom major | Inspection | *by inspection* | — |

## Backward: every test block defends something

| File | Block | Defends |
|---|---|---|
| `admin.test.ts` | ADR-19, the admin gate | ADR-12, ADR-19 |
| `admin.test.ts` | ADR-19, the allowlist fails closed | ADR-19 |
| `admin.test.ts` | ADR-19, findings only appear when there is something to do | ADR-02, ADR-04, ADR-19 |
| `api.test.ts` | ADR-10, authentication | ADR-10, ADR-19, ADR-24 |
| `api.test.ts` | ADR-12, nothing behind a session reaches a shared cache | ADR-12 |
| `api.test.ts` | ADR-03 and ADR-05, queueing a request | ADR-03, ADR-05 |
| `api.test.ts` | ADR-04, the moderation warning | ADR-04 |
| `api.test.ts` | withdrawing a request | ADR-01 |
| `api.test.ts` | ADR-01, the queue view is where fail-polite becomes visible | ADR-01 |
| `api.test.ts` | ADR-17, pagination | ADR-17 |
| `api.test.ts` | ADR-17, a list FGA cannot bound: the Flickr group list | ADR-17 |
| `batch.test.ts` | ADR-03, the batch endpoint does NOT attempt at batch scale | ADR-03, ADR-20 |
| `batch.test.ts` | ADR-20 and ADR-04, the batch endpoint refuses per group, not per batch | ADR-04, ADR-20 |
| `batch.test.ts` | the batch endpoint's shape | ADR-20 |
| `classify.test.ts` | classifyAdd | ADR-01, ADR-02 |
| `classify.test.ts` | classifyResult | ADR-01, ADR-02 |
| `classify.test.ts` | outcomeColumn | ADR-01, ADR-02 |
| `crypto.test.ts` | round trip | ADR-09 |
| `crypto.test.ts` | nonce handling | ADR-09 |
| `crypto.test.ts` | rejection | ADR-09 |
| `device.test.ts` | ADR-24: starting a link needs no credential | ADR-12, ADR-24 |
| `device.test.ts` | ADR-24: the whole flow, and the token it mints | ADR-24 |
| `device.test.ts` | ADR-24: polling refuses everything it should | ADR-01, ADR-24 |
| `device.test.ts` | ADR-24: polling is throttled server-side, not on trust | ADR-24 |
| `device.test.ts` | ADR-24: the confirmation page, and what it refuses | ADR-11, ADR-24 |
| `device.test.ts` | ADR-24: approval is browser-only, and that stops escalation | ADR-24 |
| `oauth.test.ts` | protocolParams | ADR-08 |
| `oauth.test.ts` | authorizationHeader | ADR-08 |
| `oauth.test.ts` | buildAuthorizeUrl | ADR-07, ADR-08 |
| `oauth.test.ts` | parseFormResponse | ADR-08 |
| `oauth.test.ts` | the login attempt, ADR-08 | ADR-08 |
| `oauth.test.ts` | sends a login to Flickr carrying a request token | ADR-08 |
| `oauth.test.ts` | ADR-11: returnTo can never leave our origin | ADR-08, ADR-11 |
| `oauth.test.ts` | ADR-11: the callback returns where the login STARTED | ADR-08, ADR-11 |
| `photo-groups.test.ts` | ADR-17, the groups a photo is already in | ADR-01, ADR-12, ADR-17, ADR-22 |
| `plugin-scope.test.ts` | ADR-19, a plug-in token reaches only its allow-list | ADR-17, ADR-19 |
| `preflight.test.ts` | ADR-20, the batch preflight | ADR-04, ADR-05, ADR-20 |
| `schema.test.ts` | ADR-22, STRICT tables refuse a wrong type | ADR-01, ADR-04, ADR-07, ADR-22 |
| `schema.test.ts` | ADR-03 and ADR-16, requests: ordering | ADR-03, ADR-16 |
| `schema.test.ts` | ADR-02, requests: the resolution invariant | ADR-02 |
| `schema.test.ts` | ADR-04, requests: one outstanding request per pair | ADR-04 |
| `schema.test.ts` | moderated_pairs | ADR-04 |
| `schema.test.ts` | ADR-07 and ADR-09, users | ADR-07, ADR-09 |
| `session.test.ts` | mint and verify | ADR-10, ADR-11 |
| `session.test.ts` | revocation, which ADR-10 could not do | ADR-10, ADR-11 |
| `session.test.ts` | cookie attributes on a real login | ADR-10, ADR-11 |
| `session.test.ts` | clears with attributes that match, or the deletion is a no-op | ADR-10, ADR-11 |
| `signature.test.ts` | percentEncode | ADR-14 |
| `signature.test.ts` | baseStringUri | ADR-14 |
| `signature.test.ts` | normalizeParameters | ADR-14 |
| `signature.test.ts` | signatureBaseString | ADR-14 |
| `signature.test.ts` | signingKey | ADR-14 |
| `signature.test.ts` | signHmacSha1 | ADR-14 |
| `sweep.test.ts` | the queue is never jumped | ADR-03, ADR-06 |
| `sweep.test.ts` | queues are independent | ADR-01, ADR-03, ADR-06 |
| `sweep.test.ts` | ADR-04, the permanent record | ADR-03, ADR-04, ADR-06 |
| `sweep.test.ts` | does nothing on an empty night, and says so | ADR-03, ADR-06 |
| `worker.test.ts` | ADR-11, CORS | ADR-11 |
| `worker.test.ts` | answers /health without a session | *exempt — hygiene, not a decision. A health endpoint answers 200 because* |
| `worker.test.ts` | ADR-14 and ADR-07, the diagnostic page | ADR-07, ADR-14 |
| `worker.test.ts` | ADR-18, one origin split by an /api prefix | ADR-18 |

## Mutations, and the decision each one attacks

| Mutation | Attacks |
|---|---|
| ADR-01: retry a photo that reached a moderator | ADR-01 |
| ADR-02: make an unrecognized code retryable | ADR-02 |
| ADR-01 transport: make an unanswered call retryable | ADR-01 |
| ADR-03: keep walking a queue past a throttle | ADR-03 |
| ADR-11: drop HttpOnly from the session cookie | ADR-11 |
| ADR-11: set SameSite=None on the session cookie | ADR-11 |
| ADR-11: drop the __Host- cookie prefix | ADR-11 |
| sessions: store the raw id instead of its hash | — |
| ADR-19: let a plug-in token reach any route, not just its allow-list | ADR-19 |
| sessions: skip the HMAC gate and go straight to the database | — |
| sessions: honor an expired handle | — |
| sessions: make logout clear the cookie without revoking the row | — |
| ADR-03: let the batch attempt immediately even when many groups were asked for | ADR-03 |
| ADR-04: queue a batch group that already reached a moderator | ADR-04 |
| ADR-05: queue a batch group whose photo is already in the pool | ADR-05 |
| ADR-11: reflect the request Origin in CORS | ADR-11 |
| ADR-09: unbind the NSID from the ciphertext | ADR-09 |
| ADR-09: reuse one IV forever | ADR-09 |
| ADR-01: drop the state='pending' guard from withdraw | ADR-01 |
| withdraw: let one user withdraw another's request | — |
| sweep: stop excluding users flagged needs_relink | — |
| ADR-19: stop recording the attempt on the immediate path | ADR-19 |
| ADR-14: use encodeURIComponent without the five-character fix | ADR-14 |
| ADR-14: drop the trailing ampersand in the signing key | ADR-14 |
| ADR-04: stop writing the permanent moderated-pair record | ADR-04 |
| ADR-08: return the login secret more than once | ADR-08 |
| ADR-17: cap the pagination limit at nothing | ADR-17 |
| ADR-17: return only the first page of the Flickr group list | ADR-17 |
| ADR-17: soften the ceiling into a truncated list instead of a refusal | ADR-17 |
| ADR-17: report an unknown pool lookup as an empty group list | ADR-17 |
| ADR-18: claim / in the Worker, shadowing the app shell | ADR-18 |
| ADR-19: make a missing allowlist fail OPEN | ADR-19 |
| ADR-19: answer 403 instead of 404, confirming the surface exists | ADR-19 |
| ADR-20: let preflight read another account's moderation history | ADR-20 |
| ADR-20: warn about a photo that is already in the pool | ADR-20 |
| ADR-11: let returnTo escape our origin | ADR-11 |
| ADR-11: accept any path as a login destination | ADR-11 |
| ADR-11: send every login back to the app root | ADR-11 |
| ADR-24: let a plug-in token approve a device link | ADR-24 |
| ADR-24: collect a token without proving you started the flow | ADR-24 |
| ADR-24: let an approved link be collected more than once | ADR-24 |
| ADR-24: mint the plug-in token with a browser lifetime | ADR-24 |
| ADR-24: stop throttling the poll server-side | ADR-24 |
| ADR-24: let an approval override a denial | ADR-24 |
| ADR-12: let a credential-bearing device reply be cached | ADR-12 |
| ADR-24: let a throttled poll push the window forward | ADR-24 |
