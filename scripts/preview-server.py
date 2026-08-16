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

ROOT = pathlib.Path(__file__).resolve().parent.parent
ARCH = ROOT / "docs" / "architecture"

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
</style>
</head>
<body>
  <div id="bar">
    <div id="dot"></div>
    <span id="name">Loading...</span>
    <span id="stamp"></span>
    <span id="count"></span>
  </div>
  <iframe id="frame"></iframe>
<script>
// Reload the iframe only when the file actually changed. Reloading on a timer
// would restart the render every tick and make the page unreadable.
const VIEWER = 'https://viewer.diagrams.net/?lightbox=1&nav=1#R';
let seen = null, builds = 0;

async function tick() {
  try {
    const meta = await (await fetch('/mtime', {cache: 'no-store'})).json();
    if (meta.mtime !== seen) {
      const xml = await (await fetch('/diagram', {cache: 'no-store'})).text();
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
    """The dated .drawio with the latest date in its name.

    Dates are versions on this project, so the newest name is the current file.
    Sorting the names works because the dates are zero-padded ISO.
    """
    found = sorted(ARCH.glob("FlickrGroupAddr-Architecture-*.drawio"))
    if not found:
        raise SystemExit(f"No diagram found under {ARCH}")
    return found[-1]


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

    def do_GET(self):
        import datetime

        if self.path.startswith("/mtime"):
            target = newest_diagram()
            stat = target.stat()
            stamp = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%H:%M:%S")
            body = json.dumps({
                "mtime": stat.st_mtime,
                "name": target.name,
                "stamp": stamp,
            }).encode("utf-8")
            self._send(body, "application/json")
        elif self.path.startswith("/diagram"):
            self._send(newest_diagram().read_bytes(), "application/xml")
        elif self.path in ("/", "/index.html"):
            page = PAGE.replace("%POLL%", str(POLL_MS))
            self._send(page.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self.send_error(404)

    def log_message(self, fmt, *args):
        # The poll runs twice a second, so logging every request would bury the
        # one line that matters. Only a real diagram fetch gets printed.
        if "/diagram" in (args[0] if args else ""):
            print(f"  Served {newest_diagram().name}", flush=True)


if __name__ == "__main__":
    print(f"Serving {ARCH}")
    print(f"  file    : {newest_diagram().name}")
    print(f"  preview : http://{HOST}:{PORT}/")
    print(f"  polling : every {POLL_MS} ms, reloads only when the file changes")
    print(f"Listening on {HOST}:{PORT}. Press Ctrl+C to stop.", flush=True)
    http.server.ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
