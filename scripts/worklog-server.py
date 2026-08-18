"""A live, shared view of `docs/WORK-LOG.md` at one short, constant URL.

Run it and leave it running:  python scripts/worklog-server.py
Then open:                    http://127.0.0.1:8792/

**This exists to give Terry and Claude ONE artifact instead of two views that need
a contract to stay equal.** Terry's call, 2026-08-18, after watching the diagram
preview work: *"if we could get it to auto-refresh on every .md write that claude
makes ... do we have a better system?"* Yes -- and the reason is structural rather
than cosmetic. **The sync contract exists only because there are two views.** A
browser tab reading the same file Claude writes cannot diverge from it.

**It also lifts the panel's size limit.** The harness task panel gives Terry about
five lines, so the log had to be trimmed to fit a window it does not control. This
page shows every open row with its full detail cell, and a `hide landed` toggle
keeps the completed history out of the way without deleting it.

**Terry NEVER edits `docs/WORK-LOG.md`. Claude owns it exclusively.** That is his
own half of the contract and it is what makes a read-only viewer sufficient -- no
form, no POST, no write path, nothing to reconcile.

## What this page deliberately does NOT do

**It does not render the file as markdown.** It parses the two tables through
`worklog.py` -- the same module `worklog-sync-check.py` uses -- and lays them out
as a list. **Rendering the whole document would put the sync contract and the
RFC 2119 preamble in front of Terry**, which is Claude-facing text he has no reason
to read. The tables are the part he wants.

**A parse that finds nothing is reported LOUDLY rather than as an empty list.** An
empty backlog and a broken regex look identical, and one of them is a lie. See the
`#empty` banner below.

## Two staleness edges, both measured 2026-08-18

**A change to `docs/WORK-LOG.md` is live. A change to THIS FILE or to `worklog.py`
needs a RESTART.** The server imports the parser once at startup, so editing the
parser and watching the page is watching the old code. That cost a confusing minute:
the fix was in, the parser returned the new answer at a prompt, and the page kept
showing the old list.

**And the page only re-fetches when the log's mtime CHANGES.** So after a restart it
will happily keep showing what it already had until the file is next written. `touch`
the log, or edit it, to force a repaint.

**Both are the right trade for a review loop** -- polling the content on every tick
would repaint over Terry's scroll position twice a second. They are written down
because each one looks exactly like the server being broken.

## The browser rules this had to satisfy, inherited from `preview-server.py`

  * **Loopback is exempt from mixed-content blocking, and `127.0.0.1` is the
    address that gets the exemption.** This machine's LAN address is a plain
    insecure origin and Chrome blocks it.
  * **Chrome may gate loopback behind a Local Network Access prompt** on a fresh
    profile. The symptom looks exactly like a server that is not running.

**It binds to loopback only.** A work log is not secret, but a server that answers
the LAN is a different thing from one that answers this machine, and `X:` sits on
a network with other hosts on it.
"""

import datetime
import html
import http.server
import json
import re

import worklog

HOST = "127.0.0.1"
# 8791 is the diagram preview. Keeping them apart means both can run at once, which
# is the normal state during a working session.
PORT = 8792

# Same cadence as the diagram preview: far below the time a human takes to switch
# windows, and a stat() against a local server rather than anything on a network.
POLL_MS = 400

# **Inline markdown only, and that is a deliberate scope.** The detail cell carries
# `code`, **bold** and *italic* and nothing else -- no lists, no headings, no links.
# A markdown library for one table cell would be a dependency for a job this size,
# and rendering block markdown is precisely what this page does not want to do.
INLINE = (
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
    (re.compile(r"\*\*([^*]+)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"\*([^*]+)\*"), r"<em>\1</em>"),
)

STATUS_LABEL = {
    "in_progress": "IN PROGRESS",
    "not_started": "NOT STARTED",
    "blocked": "BLOCKED",
    "completed": "COMPLETED",
}


def inline(text: str) -> str:
    """Escape HTML, then apply the three inline markdown spans.

    **Escaping happens FIRST and that order is the whole safety of it.** The detail
    cells are written by Claude and read by Terry, so this is about a stray `<` in a
    path rendering as text rather than about an attacker -- but getting the order
    backwards would let the markdown output be escaped instead of the content.
    """
    out = html.escape(text)
    for pattern, repl in INLINE:
        out = pattern.sub(repl, out)
    return out


PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>FGA work log</title>
<style>
  :root {
    --bg: #14161A; --panel: #1C1F25; --line: #2C313A;
    --ink: #E8EAED; --dim: #9AA0A6;
    --active: #F6821F; --idle: #6B7280; --blocked: #E5484D; --done: #3FB950;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; min-height: 100%; background: var(--bg);
               color: var(--ink); font-family: system-ui, "Segoe UI", sans-serif; }
  #bar { position: sticky; top: 0; z-index: 2; background: var(--bg);
         border-bottom: 1px solid var(--line);
         display: flex; align-items: center; gap: 14px; padding: 10px 20px;
         font-size: 12px; color: var(--dim); }
  #dot { width: 8px; height: 8px; border-radius: 50%; background: var(--done); flex: none; }
  #dot.stale { background: var(--blocked); }
  #bar .grow { flex: 1; }
  #bar label { cursor: pointer; user-select: none; display: flex; align-items: center; gap: 6px; }
  h1 { font-size: 15px; margin: 0; color: var(--ink); font-weight: 600; }
  /* 1500px on a wide monitor rather than 1100. Terry's window is far wider than
     the measure, and the detail cell is the long text here -- but a line much
     past this stops being scannable, so it is a cap rather than a fill. */
  main { padding: 18px 20px 60px; max-width: 1500px; }
  h2 { font-size: 11px; letter-spacing: .09em; text-transform: uppercase;
       color: var(--dim); margin: 26px 0 10px; font-weight: 600; }
  .item { display: grid; grid-template-columns: 30px 118px 1fr; gap: 14px;
          background: var(--panel); border: 1px solid var(--line);
          border-left: 3px solid var(--idle);
          border-radius: 6px; padding: 12px 14px; margin-bottom: 8px; }
  .item.in_progress { border-left-color: var(--active); }
  .item.blocked { border-left-color: var(--blocked); }
  .item.completed { border-left-color: var(--done); }
  .num { color: var(--dim); font-variant-numeric: tabular-nums; font-size: 13px; }
  .pill { font-size: 10px; letter-spacing: .07em; font-weight: 700;
          color: var(--idle); align-self: start; padding-top: 2px; }
  .in_progress .pill { color: var(--active); }
  .blocked .pill { color: var(--blocked); }
  .completed .pill { color: var(--done); }
  .subject { font-size: 15px; font-weight: 600; margin-bottom: 4px; }
  .detail { font-size: 12.5px; line-height: 1.55; color: var(--dim); }
  .detail strong { color: var(--ink); font-weight: 600; }
  code { font-family: Consolas, "Cascadia Mono", monospace; font-size: 12px;
         background: #262B33; padding: 1px 5px; border-radius: 3px; color: #D9E1EC; }
  #empty { display: none; background: #3A1D1F; border: 1px solid var(--blocked);
           border-radius: 6px; padding: 14px 16px; font-size: 13px; }
  #empty.show { display: block; }
  .hint { color: var(--dim); font-size: 12px; margin-top: 4px; }
</style>
</head>
<body>
  <div id="bar">
    <div id="dot"></div>
    <h1>FGA work log</h1>
    <span id="counts"></span>
    <span class="grow"></span>
    <label><input type="checkbox" id="hide" checked> Hide landed</label>
    <span id="stamp"></span>
    <span id="reloads"></span>
  </div>
  <main>
    <div id="empty">
      <strong>No rows parsed out of docs/WORK-LOG.md.</strong>
      <div class="hint">An empty backlog and a broken parser look identical, so this
      says so rather than showing you a clean page. Check the Open table's shape.</div>
    </div>
    <div id="open"></div>
    <div id="landed-wrap" hidden>
      <h2>Landed</h2>
      <div id="landed"></div>
    </div>
  </main>
<script>
// Reload only when the file actually changed. Re-rendering on a timer would fight
// the scroll position and make a long list unreadable.
let seen = null, reloads = 0;
const hide = document.getElementById('hide');

// The toggle sticks, because Terry keeps it on and should not re-tick it per tab.
hide.checked = localStorage.getItem('fga-hide-landed') !== '0';
hide.addEventListener('change', () => {
  localStorage.setItem('fga-hide-landed', hide.checked ? '1' : '0');
  paint();
});

let data = {open: [], landed: []};

function row(cls, num, pill, subject, detail) {
  const d = document.createElement('div');
  d.className = 'item ' + cls;
  d.innerHTML = '<div class="num">' + num + '</div>'
    + '<div class="pill">' + pill + '</div>'
    + '<div><div class="subject"></div><div class="detail">' + detail + '</div></div>';
  // The subject is plain text and is set as text, so a stray angle bracket in a
  // filename cannot become markup. The detail cell arrives pre-rendered.
  d.querySelector('.subject').textContent = subject;
  return d;
}

function paint() {
  const open = document.getElementById('open');
  open.replaceChildren();
  for (const r of data.open) {
    open.appendChild(row(r.status, r.key, r.label, r.subject, r.detail));
  }
  document.getElementById('empty').classList.toggle('show', data.open.length === 0);

  const wrap = document.getElementById('landed-wrap');
  const showLanded = !hide.checked && data.landed.length > 0;
  wrap.hidden = !showLanded;
  if (showLanded) {
    const el = document.getElementById('landed');
    el.replaceChildren();
    for (const r of data.landed) {
      el.appendChild(row('completed', '', 'LANDED', r.subject, r.date + ' &middot; ' + r.note));
    }
  }

  const active = data.open.filter(r => r.status === 'in_progress').length;
  document.getElementById('counts').textContent =
    data.open.length + ' open, ' + active + ' in progress, ' + data.landed.length + ' landed';
}

async function tick() {
  try {
    const meta = await (await fetch('/mtime', {cache: 'no-store'})).json();
    if (meta.mtime !== seen) {
      data = await (await fetch('/data', {cache: 'no-store'})).json();
      seen = meta.mtime;
      reloads++;
      document.getElementById('stamp').textContent = 'Written ' + meta.stamp;
      document.getElementById('reloads').textContent = 'Reload ' + reloads;
      paint();
    }
    document.getElementById('dot').classList.remove('stale');
  } catch (e) {
    // Say the server is gone rather than leaving a stale list looking current.
    document.getElementById('dot').classList.add('stale');
    document.getElementById('stamp').textContent = 'Server unreachable';
  }
}
tick();
setInterval(tick, %POLL%);
</script>
</body>
</html>
"""


def payload() -> bytes:
    """The two tables as JSON, with the detail cells already rendered."""
    text = worklog.read()
    return json.dumps({
        "open": [{
            "key": r.key,
            "status": r.status,
            "label": STATUS_LABEL.get(r.status, r.status.upper()),
            "subject": r.subject,
            "detail": inline(r.detail),
        } for r in worklog.open_rows(text)],
        "landed": [{
            "date": r.date,
            "subject": r.subject,
            "note": inline(r.note),
        } for r in worklog.landed_rows(text)],
    }).encode("utf-8")


class Handler(http.server.BaseHTTPRequestHandler):
    """Three routes. The page, the parsed data, and one timestamp to poll."""

    def _send(self, body: bytes, ctype: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # A cached copy of the previous write looks exactly like an edit that did
        # not happen, which is the one thing a live view must never show.
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        route = self.path.partition("?")[0]
        if route == "/mtime":
            stat = worklog.LOG.stat()
            # **Terry's LOCAL wall clock**, which is the point of the bar. `tz=None`
            # on astimezone resolves to this machine's zone, and naming it is what
            # tells a reader the choice was deliberate.
            stamp = (datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.UTC)
                     .astimezone()
                     .strftime("%H:%M:%S"))
            self._send(json.dumps({"mtime": stat.st_mtime, "stamp": stamp}).encode("utf-8"),
                       "application/json")
        elif route == "/data":
            self._send(payload(), "application/json")
        elif route in ("/", "/index.html"):
            self._send(PAGE.replace("%POLL%", str(POLL_MS)).encode("utf-8"),
                       "text/html; charset=utf-8")
        else:
            self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002, ARG002
        # **The parameter names are the base class's and MUST NOT be renamed.**
        # `_fmt` satisfies ruff and then pyright refuses the override outright --
        # a parameter name is part of an override's contract because a caller may
        # pass it by keyword. Both lint codes here are forced by a signature this
        # code does not own.
        #
        # The poll runs twice a second, so logging every request would bury
        # anything worth reading. Only a real data fetch prints.
        #
        # **`args[0]` is NOT always a string.** `send_error` routes through
        # `log_error` with `("code %d, message %s", 404, ...)`, an int first, and an
        # unguarded `in` test raises inside the handler and closes the socket with
        # no response. That bit `preview-server.py` on 2026-08-17.
        first = args[0] if args else ""
        if isinstance(first, str) and "/data" in first:
            print(f"  Served {first.split()[1] if ' ' in first else first}", flush=True)


def main() -> None:
    rows = worklog.open_rows()
    print(f"Serving {worklog.LOG}")
    print(f"  open rows : {len(rows)}")
    print(f"  view      : http://{HOST}:{PORT}/")
    print(f"  polling   : every {POLL_MS} ms, repaints only when the file changes")
    if not rows:
        # Silence here would read as an empty backlog. It is far more likely to be
        # a parse failure, and the page says so too.
        print("  WARNING: no rows parsed. The page will say so rather than look empty.")
    print(f"Listening on {HOST}:{PORT}. Press Ctrl+C to stop.", flush=True)
    http.server.ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
