# Traceability matrix

**Generated. Do not edit.** Rebuild with `python scripts/traceability.py`.

Every decision is verified by a test. Every test defends a decision, or says why
it does not. **`--check` fails the build on either gap.**

| Column | Answers |
|---|---|
| Verified by | Does anything actually check this decision? |
| Mutation | Would the test NOTICE the code breaking it? |

**17 decisions · 40 test blocks · 67 mutations**

## Forward: decision to verification

**Method** follows MIL-STD practice. `Test` runs something. `Inspection` is verified
by reading code or config, because there is no runtime behavior to exercise.

| ADR | Decision | Method | Verified by | Mutation |
|---|---|---|---|---|
| **ADR-01** | The Flickr account is the identity | Test | `oauth.test.ts` buildAuthorizeUrl<br>`schema.test.ts` ADR-01 and ADR-03, users<br>`worker.test.ts` answers /health without a session<br>`worker.test.ts` ADR-14 and ADR-01, the landing page | — |
| **ADR-02** | OAuth state lives in a Durable Object | Test | `oauth.test.ts` protocolParams<br>`oauth.test.ts` authorizationHeader<br>`oauth.test.ts` buildAuthorizeUrl<br>`oauth.test.ts` parseFormResponse<br>`oauth.test.ts` the login attempt, ADR-02<br>`oauth.test.ts` sends a login to Flickr carrying a request token | — |
| **ADR-03** | Tokens are AES-GCM encrypted in D1, under a separate key | Test | `crypto.test.ts` round trip<br>`crypto.test.ts` nonce handling<br>`crypto.test.ts` rejection<br>`schema.test.ts` ADR-01 and ADR-03, users | — |
| **ADR-04** | The work engine is a nightly cron over D1 | Test | `sweep.test.ts` the queue is never jumped<br>`sweep.test.ts` queues are independent<br>`sweep.test.ts` ADR-11, the permanent record<br>`sweep.test.ts` does nothing on an empty night, and says so | — |
| **ADR-05** | Adds are idempotent per (photo, group) | Test | `api.test.ts` ADR-10 and ADR-05, queueing a request | — |
| **ADR-06** | The session is a stateless signed cookie | Test | `api.test.ts` ADR-06, authentication<br>`session.test.ts` mint and verify<br>`session.test.ts` cookie attributes on a real login<br>`session.test.ts` clears with attributes that match, or the deletion is a no-op | — |
| **ADR-07** | Classify by Flickr's error code. Unknown means terminal. | Test | `classify.test.ts` classifyAdd<br>`classify.test.ts` classifyResult<br>`classify.test.ts` outcomeColumn<br>`schema.test.ts` ADR-07, requests: the resolution invariant | yes |
| **ADR-08** | Fail-polite. This one outranks the rest. | Test | `api.test.ts` withdrawing a request<br>`api.test.ts` ADR-08, the queue view is where fail-polite becomes visible<br>`classify.test.ts` classifyAdd<br>`classify.test.ts` classifyResult<br>`classify.test.ts` outcomeColumn<br>`sweep.test.ts` queues are independent | yes |
| **ADR-09** | No cache in front of D1 | Test | `api.test.ts` ADR-09, nothing behind a session reaches a shared cache | — |
| **ADR-10** | FIFO per (user, group). The queue is never jumped. | Test | `api.test.ts` ADR-10 and ADR-05, queueing a request<br>`schema.test.ts` ADR-10 and ADR-16, requests: ordering<br>`sweep.test.ts` the queue is never jumped<br>`sweep.test.ts` queues are independent<br>`sweep.test.ts` ADR-11, the permanent record<br>`sweep.test.ts` does nothing on an empty night, and says so | yes |
| **ADR-11** | A pair that reached a moderator is remembered forever | Test | `api.test.ts` ADR-11, the moderation warning<br>`schema.test.ts` ADR-11, requests: one outstanding request per pair<br>`schema.test.ts` moderated_pairs<br>`sweep.test.ts` ADR-11, the permanent record | yes |
| **ADR-12** | The UI and API are separate origins, so the cookie is host-only | Test | `session.test.ts` mint and verify<br>`session.test.ts` cookie attributes on a real login<br>`session.test.ts` clears with attributes that match, or the deletion is a no-op<br>`worker.test.ts` ADR-12, CORS | — |
| **ADR-13** | TypeScript, on the current stable toolchain | Inspection | *by inspection* | — |
| **ADR-14** | Integrate when feasible, innovate otherwise | Inspection | `signature.test.ts` percentEncode<br>`signature.test.ts` baseStringUri<br>`signature.test.ts` normalizeParameters<br>`signature.test.ts` signatureBaseString<br>`signature.test.ts` signingKey<br>`signature.test.ts` signHmacSha1<br>`worker.test.ts` answers /health without a session<br>`worker.test.ts` ADR-14 and ADR-01, the landing page | — |
| **ADR-15** | Which store holds what | Inspection | *by inspection* | — |
| **ADR-16** | A request has two identifiers | Test | `schema.test.ts` ADR-10 and ADR-16, requests: ordering | — |
| **ADR-17** | Every list endpoint is paginated, with a cursor | Test | `api.test.ts` ADR-17, pagination | — |

## Backward: every test block defends something

| File | Block | Defends |
|---|---|---|
| `api.test.ts` | ADR-06, authentication | ADR-06 |
| `api.test.ts` | ADR-09, nothing behind a session reaches a shared cache | ADR-09 |
| `api.test.ts` | ADR-10 and ADR-05, queueing a request | ADR-05, ADR-10 |
| `api.test.ts` | ADR-11, the moderation warning | ADR-11 |
| `api.test.ts` | withdrawing a request | ADR-08 |
| `api.test.ts` | ADR-08, the queue view is where fail-polite becomes visible | ADR-08 |
| `api.test.ts` | ADR-17, pagination | ADR-17 |
| `classify.test.ts` | classifyAdd | ADR-07, ADR-08 |
| `classify.test.ts` | classifyResult | ADR-07, ADR-08 |
| `classify.test.ts` | outcomeColumn | ADR-07, ADR-08 |
| `crypto.test.ts` | round trip | ADR-03 |
| `crypto.test.ts` | nonce handling | ADR-03 |
| `crypto.test.ts` | rejection | ADR-03 |
| `oauth.test.ts` | protocolParams | ADR-02 |
| `oauth.test.ts` | authorizationHeader | ADR-02 |
| `oauth.test.ts` | buildAuthorizeUrl | ADR-01, ADR-02 |
| `oauth.test.ts` | parseFormResponse | ADR-02 |
| `oauth.test.ts` | the login attempt, ADR-02 | ADR-02 |
| `oauth.test.ts` | sends a login to Flickr carrying a request token | ADR-02 |
| `schema.test.ts` | ADR-10 and ADR-16, requests: ordering | ADR-10, ADR-16 |
| `schema.test.ts` | ADR-07, requests: the resolution invariant | ADR-07 |
| `schema.test.ts` | ADR-11, requests: one outstanding request per pair | ADR-11 |
| `schema.test.ts` | moderated_pairs | ADR-11 |
| `schema.test.ts` | ADR-01 and ADR-03, users | ADR-01, ADR-03 |
| `session.test.ts` | mint and verify | ADR-06, ADR-12 |
| `session.test.ts` | cookie attributes on a real login | ADR-06, ADR-12 |
| `session.test.ts` | clears with attributes that match, or the deletion is a no-op | ADR-06, ADR-12 |
| `signature.test.ts` | percentEncode | ADR-14 |
| `signature.test.ts` | baseStringUri | ADR-14 |
| `signature.test.ts` | normalizeParameters | ADR-14 |
| `signature.test.ts` | signatureBaseString | ADR-14 |
| `signature.test.ts` | signingKey | ADR-14 |
| `signature.test.ts` | signHmacSha1 | ADR-14 |
| `sweep.test.ts` | the queue is never jumped | ADR-04, ADR-10 |
| `sweep.test.ts` | queues are independent | ADR-04, ADR-08, ADR-10 |
| `sweep.test.ts` | ADR-11, the permanent record | ADR-04, ADR-10, ADR-11 |
| `sweep.test.ts` | does nothing on an empty night, and says so | ADR-04, ADR-10 |
| `worker.test.ts` | ADR-12, CORS | ADR-12 |
| `worker.test.ts` | answers /health without a session | ADR-01, ADR-14 |
| `worker.test.ts` | ADR-14 and ADR-01, the landing page | ADR-01, ADR-14 |

## Mutations, and the decision each one attacks

| Mutation | Attacks |
|---|---|
| fail-polite: retry a photo that reached a moderator | — |
| src/adds/classify.ts | — |
| const RETRYABLE = new Set([5, 105, 106]); | — |
| const RETRYABLE = new Set([5, 6, 105, 106]); | — |
| ADR-07: make an unrecognized code retryable | ADR-07 |
| src/adds/classify.ts | — |
| ADR-08 transport: make an unanswered call retryable | ADR-08 |
| src/adds/classify.ts | — |
| ADR-10: keep walking a queue past a throttle | ADR-10 |
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
| ADR-11: stop writing the permanent moderated-pair record | ADR-11 |
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
