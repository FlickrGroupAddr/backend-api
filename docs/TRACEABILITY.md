# Traceability matrix

**Generated. Do not edit.** Rebuild with `python scripts/traceability.py`.

Every decision is verified by a test. Every test defends a decision, or says why
it does not. **`--check` fails the build on either gap.**

| Column | Answers |
|---|---|
| Verified by | Does anything actually check this decision? |
| Mutation | Would the test NOTICE the code breaking it? |

**18 decisions · 41 test blocks · 69 mutations**

## Forward: decision to verification

**Method** follows MIL-STD practice. `Test` runs something. `Inspection` is verified
by reading code or config, because there is no runtime behavior to exercise.

| ADR | Decision | Method | Verified by | Mutation |
|---|---|---|---|---|
| **ADR-01** | Fail-polite. This one outranks the rest. | Test | `api.test.ts` withdrawing a request<br>`api.test.ts` ADR-01, the queue view is where fail-polite becomes visible<br>`classify.test.ts` classifyAdd<br>`classify.test.ts` classifyResult<br>`classify.test.ts` outcomeColumn<br>`sweep.test.ts` queues are independent | yes |
| **ADR-02** | Classify by Flickr's error code. Unknown means terminal. | Test | `classify.test.ts` classifyAdd<br>`classify.test.ts` classifyResult<br>`classify.test.ts` outcomeColumn<br>`schema.test.ts` ADR-02, requests: the resolution invariant | yes |
| **ADR-03** | FIFO per (user, group). The queue is never jumped. | Test | `api.test.ts` ADR-03 and ADR-05, queueing a request<br>`schema.test.ts` ADR-03 and ADR-16, requests: ordering<br>`sweep.test.ts` the queue is never jumped<br>`sweep.test.ts` queues are independent<br>`sweep.test.ts` ADR-04, the permanent record<br>`sweep.test.ts` does nothing on an empty night, and says so | yes |
| **ADR-04** | A pair that reached a moderator is remembered forever | Test | `api.test.ts` ADR-04, the moderation warning<br>`schema.test.ts` ADR-04, requests: one outstanding request per pair<br>`schema.test.ts` moderated_pairs<br>`sweep.test.ts` ADR-04, the permanent record | yes |
| **ADR-05** | Adds are idempotent per (photo, group) | Test | `api.test.ts` ADR-03 and ADR-05, queueing a request | — |
| **ADR-06** | The work engine is a nightly cron over D1 | Test | `sweep.test.ts` the queue is never jumped<br>`sweep.test.ts` queues are independent<br>`sweep.test.ts` ADR-04, the permanent record<br>`sweep.test.ts` does nothing on an empty night, and says so | — |
| **ADR-07** | The Flickr account is the identity | Test | `oauth.test.ts` buildAuthorizeUrl<br>`schema.test.ts` ADR-07 and ADR-09, users<br>`worker.test.ts` answers /health without a session<br>`worker.test.ts` ADR-14 and ADR-07, the diagnostic page | — |
| **ADR-08** | OAuth state lives in a Durable Object | Test | `oauth.test.ts` protocolParams<br>`oauth.test.ts` authorizationHeader<br>`oauth.test.ts` buildAuthorizeUrl<br>`oauth.test.ts` parseFormResponse<br>`oauth.test.ts` the login attempt, ADR-08<br>`oauth.test.ts` sends a login to Flickr carrying a request token | — |
| **ADR-09** | Tokens are AES-GCM encrypted in D1, under a separate key | Test | `crypto.test.ts` round trip<br>`crypto.test.ts` nonce handling<br>`crypto.test.ts` rejection<br>`schema.test.ts` ADR-07 and ADR-09, users | — |
| **ADR-10** | The session is a stateless signed cookie | Test | `api.test.ts` ADR-10, authentication<br>`session.test.ts` mint and verify<br>`session.test.ts` cookie attributes on a real login<br>`session.test.ts` clears with attributes that match, or the deletion is a no-op | — |
| **ADR-11** | The session cookie is host-only, and `Origin` is never reflected | Test | `session.test.ts` mint and verify<br>`session.test.ts` cookie attributes on a real login<br>`session.test.ts` clears with attributes that match, or the deletion is a no-op<br>`worker.test.ts` ADR-11, CORS | — |
| **ADR-12** | No cache in front of D1 | Test | `api.test.ts` ADR-12, nothing behind a session reaches a shared cache | — |
| **ADR-13** | TypeScript, on the current stable toolchain | Inspection | *by inspection* | — |
| **ADR-14** | Integrate when feasible, innovate otherwise | Inspection | `signature.test.ts` percentEncode<br>`signature.test.ts` baseStringUri<br>`signature.test.ts` normalizeParameters<br>`signature.test.ts` signatureBaseString<br>`signature.test.ts` signingKey<br>`signature.test.ts` signHmacSha1<br>`worker.test.ts` answers /health without a session<br>`worker.test.ts` ADR-14 and ADR-07, the diagnostic page | — |
| **ADR-15** | Which store holds what | Inspection | *by inspection* | — |
| **ADR-16** | A request has two identifiers | Test | `schema.test.ts` ADR-03 and ADR-16, requests: ordering | — |
| **ADR-17** | Every list endpoint is paginated, with a cursor | Test | `api.test.ts` ADR-17, pagination | — |
| **ADR-18** | One origin, an `/api` prefix, and a Svelte app shell | Test | `worker.test.ts` ADR-14 and ADR-07, the diagnostic page<br>`worker.test.ts` ADR-18, one origin split by an /api prefix | yes |

## Backward: every test block defends something

| File | Block | Defends |
|---|---|---|
| `api.test.ts` | ADR-10, authentication | ADR-10 |
| `api.test.ts` | ADR-12, nothing behind a session reaches a shared cache | ADR-12 |
| `api.test.ts` | ADR-03 and ADR-05, queueing a request | ADR-03, ADR-05 |
| `api.test.ts` | ADR-04, the moderation warning | ADR-04 |
| `api.test.ts` | withdrawing a request | ADR-01 |
| `api.test.ts` | ADR-01, the queue view is where fail-polite becomes visible | ADR-01 |
| `api.test.ts` | ADR-17, pagination | ADR-17 |
| `classify.test.ts` | classifyAdd | ADR-01, ADR-02 |
| `classify.test.ts` | classifyResult | ADR-01, ADR-02 |
| `classify.test.ts` | outcomeColumn | ADR-01, ADR-02 |
| `crypto.test.ts` | round trip | ADR-09 |
| `crypto.test.ts` | nonce handling | ADR-09 |
| `crypto.test.ts` | rejection | ADR-09 |
| `oauth.test.ts` | protocolParams | ADR-08 |
| `oauth.test.ts` | authorizationHeader | ADR-08 |
| `oauth.test.ts` | buildAuthorizeUrl | ADR-07, ADR-08 |
| `oauth.test.ts` | parseFormResponse | ADR-08 |
| `oauth.test.ts` | the login attempt, ADR-08 | ADR-08 |
| `oauth.test.ts` | sends a login to Flickr carrying a request token | ADR-08 |
| `schema.test.ts` | ADR-03 and ADR-16, requests: ordering | ADR-03, ADR-16 |
| `schema.test.ts` | ADR-02, requests: the resolution invariant | ADR-02 |
| `schema.test.ts` | ADR-04, requests: one outstanding request per pair | ADR-04 |
| `schema.test.ts` | moderated_pairs | ADR-04 |
| `schema.test.ts` | ADR-07 and ADR-09, users | ADR-07, ADR-09 |
| `session.test.ts` | mint and verify | ADR-10, ADR-11 |
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
| `worker.test.ts` | answers /health without a session | ADR-07, ADR-14 |
| `worker.test.ts` | ADR-14 and ADR-07, the diagnostic page | ADR-07, ADR-14, ADR-18 |
| `worker.test.ts` | ADR-18, one origin split by an /api prefix | ADR-18 |

## Mutations, and the decision each one attacks

| Mutation | Attacks |
|---|---|
| fail-polite: retry a photo that reached a moderator | — |
| src/adds/classify.ts | — |
| const RETRYABLE = new Set([5, 105, 106]); | — |
| const RETRYABLE = new Set([5, 6, 105, 106]); | — |
| ADR-02: make an unrecognized code retryable | ADR-02 |
| src/adds/classify.ts | — |
| ADR-01 transport: make an unanswered call retryable | ADR-01 |
| src/adds/classify.ts | — |
| ADR-03: keep walking a queue past a throttle | ADR-03 |
| src/sweep.ts | — |
| \t\t\t\tstoppedOnThrottle++;\n\t\t\t\tbreak; | — |
| \t\t\t\tstoppedOnThrottle++;\n\t\t\t\thead = await nextInQueue(db, head.nsid, head.groupId);\n\t\t\t\tcontinue; | — |
| cookie: drop HttpOnly | — |
| src/session.ts | — |
| \thttpOnly: true, | — |
| \thttpOnly: false, | — |
| cookie: SameSite=None | — |
| src/session.ts | — |
| cookie: drop the __Host- prefix | — |
| src/session.ts | — |
| session: stop pinning the JWS algorithm | — |
| src/session.ts | — |
| CORS: reflect the request Origin | — |
| src/index.ts | — |
| \t\torigin: (origin) => (origin === c.env.UI_ORIGIN ? c.env.UI_ORIGIN : null), | — |
| \t\torigin: (origin) => origin, | — |
| crypto: unbind the NSID from the ciphertext | — |
| src/crypto/tokens.ts | — |
| function aad(nsid: string): Uint8Array {\n\treturn new TextEncoder().encode(nsid); | — |
| crypto: reuse one IV forever | — |
| src/crypto/tokens.ts | — |
| \tconst iv = crypto.getRandomValues(new Uint8Array(IV_BYTES)); | — |
| \tconst iv = new Uint8Array(IV_BYTES); | — |
| withdraw: drop the state='pending' guard | — |
| src/db/requests.ts | — |
|        WHERE public_id = ? AND nsid = ? AND state = 'pending' | — |
|        WHERE public_id = ? AND nsid = ? | — |
| withdraw: let one user withdraw another's request | — |
| src/db/requests.ts | — |
| \t\t.bind(Date.now(), publicId, nsid) | — |
| \t\t.bind(Date.now(), publicId, nsid ? nsid : nsid) | — |
| sweep: stop excluding users flagged needs_relink | — |
| src/db/requests.ts | — |
|          AND u.needs_relink = 0\n | — |
| immediate path: stop recording the attempt | — |
| src/routes/api.ts | — |
| \t\tawait recordAttempt(c.env.DB, id); | — |
| OAuth: use encodeURIComponent without the five-character fix | — |
| src/oauth/signature.ts | — |
| \treturn encodeURIComponent(value).replace(\n\t\t/[!'()*]/g,\n\t\t(char) => `%${char.charCodeAt(0).toString(16).toUpperCase()}`,\n\t); | — |
| \treturn encodeURIComponent(value); | — |
| OAuth: drop the trailing ampersand in the signing key | — |
| src/oauth/signature.ts | — |
| \treturn `${percentEncode(consumerSecret)}&${percentEncode(tokenSecret)}`; | — |
| \treturn tokenSecret\n\t\t? `${percentEncode(consumerSecret)}&${percentEncode(tokenSecret)}`\n\t\t: percentEncode(consumerSecret); | — |
| ADR-04: stop writing the permanent moderated-pair record | ADR-04 |
| src/db/requests.ts | — |
| \tif (reachedAModerator(disposition)) { | — |
| \tif (false as boolean) { | — |
| login attempt: return the secret more than once | — |
| src/oauth/login-attempt.ts | — |
| \t\tawait this.ctx.storage.deleteAll();\n\t\treturn { requestTokenSecret: attempt.requestTokenSecret }; | — |
| \t\treturn { requestTokenSecret: attempt.requestTokenSecret }; | — |
| pagination: cap the limit at nothing | — |
| src/routes/api.ts | — |
| \tlimit: z.coerce.number().int().min(1).max(200).default(50), | — |
| \tlimit: z.coerce.number().int().min(1).default(50), | — |
| ADR-18: claim / in the Worker, shadowing the app shell | ADR-18 |
| src/index.ts | — |
