"""A live preview of the architecture diagram at one short, constant URL.

Run it and leave it running:  python scripts/preview-server.py
Then open:                    http://127.0.0.1:8791/

**This exists to delete git AND the copy-paste from the review loop.** The
documented loop was build -> commit -> push -> read the commit hash -> point
viewer.diagrams.net at a raw.githubusercontent.com URL pinned to that hash. That
is four network round trips and a CDN, and GitHub's CDN serves a stale copy of a
branch for minutes -- a cached render looks exactly like a change that did not
work. **The loop is now: run the build, and watch the tab redraw itself.**

**The `#U` fragment does NOT work against loopback, and that was measured.**
draw.io fetched `http://127.0.0.1:8791/...` successfully -- the server logged
`200` -- and still reported `File not found`, so its own `#U` loader rejects the
result rather than the request. `#R` carries the XML in the fragment instead, and
that renders. **The page below therefore builds a `#R` URL for an iframe**, where
its ~10,000 characters cost nothing and nobody has to look at them.

Two browser rules this had to satisfy, both easy to trip:

  * **Chrome gates loopback behind a Local Network Access permission.** The first
    attempt failed with draw.io's `File not found` and the server logged NOTHING,
    because Chrome blocked the fetch before it left the browser. Terry granted the
    permission for `viewer.diagrams.net`. **A fresh browser profile MUST grant it
    again**, and the symptom will look like a server that is not running.
  * **Loopback is exempt from mixed-content blocking.** An `https://` page may not
    normally fetch `http://`, but Chrome treats `127.0.0.1` as a potentially
    trustworthy origin. **Use `127.0.0.1`, never this machine's LAN address** --
    that is a plain insecure origin and Chrome blocks it.

**It binds to loopback only.** The served directory holds nothing secret, but a
server that answers the LAN is a different thing from one that answers this
machine, and `X:` is an SMB share on a network with other hosts on it.
"""

import http.server
import json
import pathlib
import urllib.parse

from diagram_sheets import (
    CANONICAL,
    SHEETS,
    arch_dir,
    canonical_diagram,
    found_sheets,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
ARCH = arch_dir(ROOT)

HOST = "127.0.0.1"
PORT = 8791

# How often the page asks whether the file changed. 400 ms is far below the time
# a human takes to switch windows, so a rebuild looks instant, and the request is
# a stat() against a local server rather than anything on the network.
POLL_MS = 400

PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>FGA architecture preview</title>
<style>
  html, body { margin: 0; height: 100%; background: #1A1A1A; font-family: system-ui, sans-serif; }
  #bar { height: 26px; display: flex; align-items: center; gap: 16px;
         padding: 0 12px; color: #E8E8E8; font-size: 12px; }
  #dot { width: 8px; height: 8px; border-radius: 50%; background: #4CAF50; }
  #dot.stale { background: #F6821F; }
  #frame { width: 100%; height: calc(100% - 26px); border: 0; background: #FFFFFF; }
  #sheets a { color: #9AA0A6; text-decoration: none; margin-right: 10px; }
  #sheets a.on { color: #F6821F; font-weight: 700; }
</style>
</head>
<body>
  <div id="bar">
    <div id="dot"></div>
    <span id="sheets">%SHEETS%</span>
    <span id="name">Loading...</span>
    <span id="stamp"></span>
    <span id="count"></span>
  </div>
  <iframe id="frame"></iframe>
<script>
// Reload the iframe only when the file actually changed. Reloading on a timer
// would restart the render every tick and make the page unreadable.
const VIEWER = 'https://viewer.diagrams.net/?lightbox=1&nav=1#R';
// Which sheet this tab is watching. The drawing is the same on all of them, so
// this is here to prove a new sheet RENDERS, not to review the picture again.
const SHEET = new URLSearchParams(location.search).get('sheet') || '';
const Q = SHEET ? '?sheet=' + encodeURIComponent(SHEET) : '';
let seen = null, builds = 0;

for (const a of document.querySelectorAll('#sheets a')) {
  if (a.dataset.slug === (SHEET || '%CANONICAL%')) { a.classList.add('on'); }
}

async function tick() {
  try {
    const meta = await (await fetch('/mtime' + Q, {cache: 'no-store'})).json();
    if (meta.mtime !== seen) {
      const xml = await (await fetch('/diagram' + Q, {cache: 'no-store'})).text();
      // A `#R` fragment carries the whole diagram, so the viewer fetches nothing
      // and no CDN sits between the build and the picture.
      document.getElementById('frame').src = VIEWER + encodeURIComponent(xml);
      seen = meta.mtime;
      builds++;
      document.getElementById('name').textContent = meta.name;
      document.getElementById('stamp').textContent = 'Built ' + meta.stamp;
      document.getElementById('count').textContent = 'Reload ' + builds;
    }
    document.getElementById('dot').classList.remove('stale');
  } catch (e) {
    // The server is down or the permission was revoked. Say so in the bar
    // rather than silently showing a diagram that stopped tracking the file.
    document.getElementById('dot').classList.add('stale');
    document.getElementById('name').textContent = 'Preview server unreachable';
  }
}
tick();
setInterval(tick, %POLL%);
</script>
</body>
</html>
"""


def newest_diagram() -> pathlib.Path:
    """The CANONICAL sheet of the newest date -- legal since 2026-08-19.

    **This used to be `sorted(glob)[-1]`, and that broke the day the filenames
    grew a sheet suffix.** ASCII sorted the suffixes into an order nobody intended,
    so the preview silently showed a different sheet: the same drawing, translated,
    with a page scale on it. **That is not a prediction -- the running server was
    caught doing it on 2026-08-17**, and the picture looked almost right, which is
    the worst kind of wrong for a review loop. `diagram_sheets` is the one place
    that decision now lives.

    **THE DEFAULT MOVED FROM THE CANVAS TO LEGAL, and that is the point of the
    card rather than a side effect.** Terry judges the drawing here, and he prints
    legal. **Reviewing an unscaled canvas is what let 7.7 pt type pass for months**
    -- the defect that made the first print an eyechart is only visible at the size
    it will be read. The canvas is still one tab away for a 1:1 look.
    """
    return canonical_diagram(ROOT)


def sheet_diagram(slug: str) -> pathlib.Path:
    """The named sheet of the newest date, or the canonical one when unnamed.

    **The unnamed case is what `http://127.0.0.1:8791/` opens**, so it answers the
    question Terry asks most: what does the diagram look like. The named cases exist
    to answer a narrower one -- does a newly written sheet parse and render at all.
    **Every one of them carries the same drawing.**
    """
    if not slug:
        return canonical_diagram(ROOT)
    newest = max(date for date, _, _ in found_sheets(ROOT))
    for date, found, path in found_sheets(ROOT):
        if date == newest and found == slug:
            return path
    raise KeyError(slug)


class Handler(http.server.BaseHTTPRequestHandler):
    """Three routes. The page, the diagram, and one timestamp to poll."""

    def _send(self, body: bytes, ctype: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # The whole point is that a reload shows the build that just ran. A cached
        # copy of the previous build looks exactly like an edit that did not work.
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(body)

    def _requested(self) -> pathlib.Path:
        query = self.path.partition("?")[2]
        slug = urllib.parse.parse_qs(query).get("sheet", [""])[0]
        return sheet_diagram(slug)

    def do_GET(self) -> None:
        import datetime

        route = self.path.partition("?")[0]
        try:
            if route == "/mtime":
                target = self._requested()
                stat = target.stat()
                # **Terry's LOCAL wall clock, which is the point of the bar.**
                # `tz=None` on `astimezone` resolves to this machine's zone, and
                # naming it is what tells a reader the choice was deliberate.
                stamp = (datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.UTC)
                         .astimezone()
                         .strftime("%H:%M:%S"))
                body = json.dumps({
                    "mtime": stat.st_mtime,
                    "name": target.name,
                    "stamp": stamp,
                }).encode("utf-8")
                self._send(body, "application/json")
            elif route == "/diagram":
                self._send(self._requested().read_bytes(), "application/xml")
            elif route in ("/", "/index.html"):
                links = " ".join(
                    f'<a href="/?sheet={s.slug}" data-slug="{s.slug}">{s.slug}</a>'
                    for s in SHEETS
                )
                page = (PAGE.replace("%POLL%", str(POLL_MS))
                            .replace("%SHEETS%", links)
                            .replace("%CANONICAL%", CANONICAL.slug))
                self._send(page.encode("utf-8"), "text/html; charset=utf-8")
            else:
                self.send_error(404)
        except KeyError as exc:
            # A slug the build does not write. Say which, rather than falling back
            # to the authored sheet and showing a picture nobody asked for.
            self.send_error(404, f"No sheet named {exc.args[0]}")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002, ARG002
        # **A leading underscore is the right way to silence an unused argument --
        # EXCEPT on an override, and this is the exception.** Renaming it to
        # `_fmt` satisfied ruff and then pyright refused the whole method:
        # `Method "log_message" overrides class "BaseHTTPRequestHandler" in an
        # incompatible manner`. **A parameter name is part of an override's
        # contract**, because a caller may pass it by keyword.
        #
        # So the base class wins over both lint rules. `A002` fires because
        # `format` shadows a builtin, and `ARG002` because nothing reads it --
        # **both are forced by a signature this code does not own.**
        # The poll runs twice a second, so logging every request would bury the
        # one line that matters. Only a real diagram fetch gets printed.
        #
        # **`args[0]` is NOT always a string, and assuming it was crashed the
        # connection.** `send_error` routes through `log_error`, which calls this
        # with `("code %d, message %s", 404, "...")` -- an int first. The `in`
        # test then raised TypeError inside the handler, so a mistyped URL closed
        # the socket with no response at all. Found 2026-08-17 by asking for a
        # sheet slug that does not exist; it had been reachable by any 404.
        first = args[0] if args else ""
        if isinstance(first, str) and "/diagram" in first:
            print(f"  Served {first.split()[1] if ' ' in first else first}", flush=True)


if __name__ == "__main__":
    print(f"Serving {ARCH}")
    print(f"  file    : {newest_diagram().name}")
    print(f"  preview : http://{HOST}:{PORT}/")
    print(f"  polling : every {POLL_MS} ms, reloads only when the file changes")
    print(f"Listening on {HOST}:{PORT}. Press Ctrl+C to stop.", flush=True)
    http.server.ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
