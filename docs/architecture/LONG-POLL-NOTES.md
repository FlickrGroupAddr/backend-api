# The device-link poll becomes a HELD request

**RFC 2119 keywords. MUST and MUST NOT are absolute. SHOULD is a strong default a good argument may
overrule. MAY is optional.**

## Status: DECIDED, NOT BUILT

**Terry decided the direction on 2026-08-17. None of it exists.** `DeviceLinkAttempt.poll` still
answers immediately.

**This is deliberately not an ADR yet**, for the reason `KEY-ROTATION-NOTES.md` already records: an
ADR MUST be verified by a test or declare inspection, and claiming inspection for behavior nobody
wrote is the forced link `scripts/traceability.py` exists to prevent.

**When the code lands this becomes ADR-26 and this file goes away.** Everything below the rule is
written to paste into `DECISIONS.md` unchanged. ADR-24 carries a pointer here until then.

---

## ADR-26 — The plug-in's device poll is a HELD request, not a poll loop

**Verification: Test.** `device.test.ts` proves a held poll wakes on approval, wakes on denial,
returns `pending` at its own deadline, and refuses to park a wrong `deviceCode`. A mutation proves
the suite would notice the hold being removed.

**`poll` MUST hold the request open until the outcome is known or the hold deadline expires.** It
MUST NOT return `pending` the instant it finds no decision. The plug-in stops asking every five
seconds and instead asks once, then waits.

**The protocol does not change, and that is the point.** `pending` remains a real answer, `pollAfter`
still ships in every reply, and a client that ignores all of this and loops on a timer stays correct.
**This is a latency and request-count optimization the client need not understand.**

### What it costs today

A person walks to a browser, reads the `userCode`, and clicks. That takes 10 to 60 seconds.

| | Poll loop | Held request |
|---|---|---|
| Requests for a 40-second approval | About 8 | **2** |
| Delay between the click and the plug-in noticing | Up to 5 seconds | **Milliseconds** |
| Requests if the user walks away for the full 10-minute TTL | About 120 | **24** |

**The delay row matters more than the request row.** Under ADR-24 the token is minted at collection,
so the five-second gap sits between the person clicking Approve and Lightroom saying anything at all.
**That silence is the whole perceived cost of the feature.**

### Cloudflare holds a request for free, and that is why this is cheap

**`developers.cloudflare.com/workers/platform/limits/`, read 2026-08-17:**

> "There is no hard limit on duration for HTTP-triggered Workers. As long as the client remains
> connected, the Worker can continue processing, making subrequests, and streaming a response body."

> "Waiting on network requests (such as `fetch()` calls, KV reads, or database queries) does **not**
> count toward CPU time."

**CPU time is the metered resource and a parked request spends none of it.** Wall-clock duration is
unbounded while the client stays connected.

### The mechanism

`DeviceLinkAttempt` is addressed by `userCode`, so `poll`, `approve` and `deny` already land in the
same instance. That is what makes this a few lines rather than a subsystem.

- `poll` registers a resolver in an **in-memory** list and races it against a timer.
- `approve` and `deny` resolve every waiter, **after** their storage write.
- The timer resolves to `pending`.

**The waiter list MUST NOT be persisted, and that is not an oversight.** A waiter is a live HTTP
request. If the Durable Object is evicted, the request it belonged to is already gone, so a restored
waiter would resolve nothing. **An in-flight request keeps the object in memory**, which is exactly
the lifetime a waiter needs.

### The rules that carry it

**The hold deadline MUST NOT use `ctx.storage.setAlarm`.** A Durable Object has **one** alarm, and
that slot holds ADR-24's ten-minute `ABANDONED_AFTER_MS` expiry. Arming a second one silently
cancels the first, and an abandoned link would then sit in storage forever with nothing scheduled to
remove it. **Nothing errors, nothing warns, and the only symptom is data that never leaves.** Use a
plain timer raced against the approval promise.

**The `deviceCode` check MUST still come before the hold.** A wrong code MUST return `expired`
immediately and MUST NOT register a waiter. Reversed, anybody who read a `userCode` off a screen
could park requests against the object without ever proving they started the flow. **This is the
same ordering rule ADR-24 already states for throttling, pointed at a new resource.**

**Concurrent waiters MUST be capped.** Only the holder of `deviceCode` can reach this point, so the
cap defends against a buggy plug-in rather than an attacker. Refuse past the cap with `slow_down`.

**`HOLD_MS` MUST stay below the client's `LrHttp` timeout.** The server holds 25 seconds; the plug-in
passes 60. A client that gives up before the server answers turns a working hold into a retry storm,
and the plug-in cannot tell the two apart.

**Throttling survives unchanged.** ADR-24's 2-second floor never fires against an honest held
client, because a 25-second hold clears it by an order of magnitude.

**ADR-12's `no-store` still applies.** A held reply still carries a bearer credential in its body.

### This makes ADR-01 faster, which is the part worth keeping

**`deny` wakes every waiter immediately.** A person who declines gets "you declined" on the
Lightroom screen at once, rather than up to five seconds later.

**ADR-01 requires that a refusal MUST NOT look like a failure.** A refusal the user waits for reads
as a hang, and a user who thinks FGA hung tries again — which is the behavior ADR-01 exists to
prevent. **Speed is part of the promise here, not a nicety.**

### Considered and rejected

**Terry asked directly whether Lua or the Lightroom SDK offers a push socket. It does not, and both
ends refuse independently.**

| Option | Verdict |
|---|---|
| **`LrSocket`** | **Localhost only.** Adobe's own reference: *"Opens a socket connection **(on localhost)** for either reading or writing operations."* SDK 6.0 |
| A WebSocket hand-rolled over `LrSocket` | **Impossible, and unsafe if it were not.** The controller exposes only `send`, `reconnect`, `close` and `type` — no TLS. RFC 6455 would need an HTTP Upgrade, a `SHA1-160` accept key and client-side masking, all written in Lua, over plaintext carrying `deviceCode` |
| Pointing `LrSocket` at the Worker | **Cloudflare has no raw-TCP inbound listener.** Workers accept HTTP and WebSocket. The `address` parameter is not even in Adobe's documented parameter table — `remote_control_socket.lrdevplugin/start.lua` passes it, the reference does not list it |
| Server-Sent Events over `LrHttp` | **`LrHttp.get` and `LrHttp.post` return the complete body as a string.** There is no incremental read. `postMultipart`'s `callbackFn` reports **upload** progress as `0..1`, and a function `postBody` supplies **outbound** chunks — both are send-side only |
| A helper process via `LrTasks.execute` or `LrShell` | **A signed per-platform binary, an antivirus fight and a second update channel, to save ten HTTP requests** |

**Reopening any row needs a change at Adobe, not a change of mind.** The blocker is that the SDK
ships no TLS-capable socket, which no amount of Lua fixes.

### Two accepted costs, and one measurement owed

**A held request keeps the Durable Object billable on wall clock.** Roughly 25 seconds of active
duration per link, against about 8 brief invocations today. **At one link per laptop this is noise**,
and it is named here so nobody rediscovers it as a surprise.

**An intermediary MAY cut a connection it reads as idle.** The client cannot distinguish that from a
hold that expired, and it MUST NOT try — both are handled by polling again.

**`LrHttp`'s `timeout` is documented as *"the length of time to wait during each phase of the
connection"*, and "each phase" is ambiguous.** `HOLD_MS` MUST NOT be raised above 25 seconds until
somebody measures a real held request against real Lightroom Classic. **Adobe's own wording is the
reason this is a measurement rather than an assumption.**
