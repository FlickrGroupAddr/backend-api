"""Build a self-contained viewer.diagrams.net URL that carries the diagram itself.

Run from anywhere:  python scripts/preview-diagram.py

**This exists to delete git from the review loop.** The documented loop was
build -> commit -> push -> read the commit hash -> point viewer.diagrams.net at a
raw.githubusercontent.com URL pinned to that hash. That is four network round
trips and a CDN, and it costs tens of seconds per iteration. draw.io's `#R`
fragment carries the diagram XML in the URL itself, so the viewer fetches
nothing and the loop becomes build -> navigate.

**The `#U` form is still the RIGHT one for anything Terry keeps.** A `#R` URL is
enormous, it is unreadable, and it is a snapshot rather than a pointer -- it does
not track the repository. Use `#U` pinned to a commit hash for a link that lives
longer than the next edit.

Two details that matter:

  * `#R` takes the raw XML, percent-encoded. draw.io reads the fragment client
    side, so the payload never leaves the browser and no CORS rule applies.
  * The payload is deflated first when that is shorter. draw.io accepts a
    fragment that is not raw XML by inflating it -- the same encoding it uses
    inside a compressed `<diagram>` node -- and the SVG logos in this file
    compress by roughly 4x.
"""

import base64
import pathlib
import urllib.parse
import zlib

from diagram_sheets import arch_dir, authored_diagram

ROOT = pathlib.Path(__file__).resolve().parent.parent
ARCH = arch_dir(ROOT)

VIEWER = "https://viewer.diagrams.net/?lightbox=1&nav=1#R"


def newest_diagram() -> pathlib.Path:
    """The AUTHORED sheet of the newest date -- the tabloid one.

    A `#R` URL carries the drawing itself, so this picks which drawing. The other
    sheets hold the same picture moved onto another page, and previewing one of
    those answers a question nobody asked.
    """
    return authored_diagram(ROOT)


def compress(xml: str) -> str:
    """draw.io's own encoding: percent-encode, raw deflate, then base64.

    This is what draw.io writes inside a compressed `<diagram>` node, and its
    reader accepts the same bytes in a `#R` fragment.
    """
    packed = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
    body = packed.compress(urllib.parse.quote(xml, safe="~()*!.'").encode("ascii"))
    body += packed.flush()
    return base64.b64encode(body).decode("ascii")


def preview_url(path: pathlib.Path) -> str:
    xml = path.read_text(encoding="utf-8")
    # draw.io reads a `#R` fragment as raw XML when it starts with `<`, and
    # inflates it otherwise. Take whichever is shorter and say which won.
    raw = urllib.parse.quote(xml, safe="")
    small = urllib.parse.quote(compress(xml), safe="")
    body = raw if len(raw) <= len(small) else small
    which = "raw" if body is raw else "deflated"
    print(f"  source     : {path.name}  ({len(xml)} chars of XML)")
    print(f"  raw        : {len(raw)} chars")
    print(f"  deflated   : {len(small)} chars")
    print(f"  chose      : {which}")
    return VIEWER + body


if __name__ == "__main__":
    target = newest_diagram()
    url = preview_url(target)
    out = ROOT / ".preview-url.txt"
    out.write_text(url, encoding="utf-8")
    print(f"  wrote      : {out}  ({len(url)} chars)")
    print()
    print(url)
