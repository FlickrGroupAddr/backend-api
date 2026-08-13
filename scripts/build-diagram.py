"""Generate the FGA architecture .drawio with embedded vector logos.

Run from anywhere:  python scripts/build-diagram.py

The .drawio under docs/architecture/ is a GENERATED artifact. Edit this file, not
the XML -- a hand edit to the output is lost the next time this runs.

draw.io embeds images as `image=data:image/svg+xml,<base64>` -- note it omits the
usual `;base64` marker and puts the payload straight after the comma. Base64 uses
only [A-Za-z0-9+/=], so it is safe unescaped inside an XML attribute.

Generated rather than hand-written because the Cloudflare payload alone is over
3,000 characters of base64, and hand-transcribing that is a good way to ship a
silently corrupt image.

Logos come from Wikimedia Commons and live in docs/architecture/logos/ so the
build has no network dependency:
  cloudflare-mark.svg  File:Cloudflare Logo.svg
  flickr-mark.svg      File:Flickr logo - SuperTinyIcons.svg
Both are company trademarks used here nominatively, to identify the services this
system actually depends on.
"""

import base64
import pathlib

# Dates are versions on this project -- there is no v1/v2 numbering. The
# filename and the title block MUST carry the same date, so both come from this
# one constant. Bump it when the diagram's content changes, and git mv the
# existing file to match before running.
DATE = "2026-08-13"

ROOT = pathlib.Path(__file__).resolve().parent.parent
SVG = ROOT / "docs" / "architecture" / "logos"
OUT = ROOT / "docs" / "architecture" / f"FlickrGroupAddr-Architecture-{DATE}.drawio"


def embed(name: str) -> str:
    raw = (SVG / name).read_bytes()
    return "data:image/svg+xml," + base64.b64encode(raw).decode("ascii")


CF = embed("cloudflare-mark.svg")
FLICKR = embed("flickr-mark.svg")

TEMPLATE = """<mxfile host="app.diagrams.net" agent="Claude Code" version="24.0.0">
  <diagram id="fga-architecture" name="FlickrGroupAddr Architecture">
    <mxGraphModel dx="1422" dy="900" grid="0" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1900" pageHeight="1260" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />

        <mxCell id="title" value="FlickrGroupAddr Architecture" style="text;html=1;align=left;verticalAlign=middle;fontSize=24;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="50" y="24" width="700" height="34" as="geometry" />
        </mxCell>
        <mxCell id="date" value="{DATE}" style="text;html=1;align=left;verticalAlign=middle;fontSize=15;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="50" y="62" width="300" height="24" as="geometry" />
        </mxCell>

        <mxCell id="cfframe" value="" style="rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#1A1A1A;strokeWidth=2;" vertex="1" parent="1">
          <mxGeometry x="220" y="150" width="1300" height="950" as="geometry" />
        </mxCell>
        <mxCell id="cflogo" value="" style="shape=image;html=1;imageAspect=1;aspect=fixed;image={CF}" vertex="1" parent="1">
          <mxGeometry x="238" y="166" width="182" height="60" as="geometry" />
        </mxCell>
        <mxCell id="netb" value="Cloudflare global network &#8212; anycast, no regions to choose" style="rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#F6821F;dashed=1;strokeWidth=2;verticalAlign=top;fontColor=#F6821F;fontStyle=1;fontSize=13;spacingTop=6;" vertex="1" parent="1">
          <mxGeometry x="260" y="250" width="1240" height="820" as="geometry" />
        </mxCell>

        <mxCell id="users" value="Users" style="shape=actor;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#1A1A1A;strokeWidth=2;fontSize=13;fontStyle=1;verticalLabelPosition=bottom;verticalAlign=top;" vertex="1" parent="1">
          <mxGeometry x="70" y="520" width="90" height="100" as="geometry" />
        </mxCell>

        <mxCell id="pages" value="&lt;b&gt;Cloudflare Pages&lt;/b&gt;&lt;br&gt;&lt;i&gt;JAMstack UI&lt;/i&gt;&lt;br&gt;&lt;i&gt;flickrgroupaddr.com&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F6821F;strokeColor=none;fontColor=#FFFFFF;fontSize=12;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="320" y="520" width="190" height="100" as="geometry" />
        </mxCell>
        <mxCell id="secrets" value="&lt;b&gt;Worker Secrets&lt;/b&gt;&lt;br&gt;&lt;i&gt;consumer key + secret,&lt;br&gt;master encryption key&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#6B7280;strokeColor=none;fontColor=#FFFFFF;fontSize=12;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="640" y="662" width="220" height="100" as="geometry" />
        </mxCell>
        <mxCell id="cron" value="&lt;b&gt;Cron Trigger&lt;/b&gt;&lt;br&gt;&lt;i&gt;nightly&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FBAD41;strokeColor=none;fontColor=#3A2200;fontSize=12;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="320" y="830" width="190" height="100" as="geometry" />
        </mxCell>

        <mxCell id="oauthdo" value="&lt;b&gt;OAuth Dance DO&lt;/b&gt;&lt;br&gt;&lt;i&gt;one Durable Object per oauth_token&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#0051C3;strokeColor=none;fontColor=#FFFFFF;fontSize=13;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="940" y="300" width="230" height="100" as="geometry" />
        </mxCell>
        <mxCell id="api" value="&lt;b&gt;API Worker&lt;/b&gt;&lt;br&gt;&lt;i&gt;backend-api&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F6821F;strokeColor=none;fontColor=#FFFFFF;fontSize=13;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="940" y="520" width="230" height="100" as="geometry" />
        </mxCell>
        <mxCell id="retry" value="&lt;b&gt;Retry Worker&lt;/b&gt;&lt;br&gt;&lt;i&gt;drains due requests&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F6821F;strokeColor=none;fontColor=#FFFFFF;fontSize=13;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="940" y="830" width="230" height="100" as="geometry" />
        </mxCell>

        <mxCell id="d1" value="&lt;b&gt;D1 (SQLite)&lt;/b&gt;&lt;br&gt;&lt;i&gt;users &#183; pending requests&lt;br&gt;per-group counters&lt;br&gt;encrypted Flickr tokens&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#00A3E0;strokeColor=none;fontColor=#FFFFFF;fontSize=12;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="1240" y="670" width="210" height="110" as="geometry" />
        </mxCell>

        <mxCell id="flickr" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#FF0084;strokeWidth=3;arcSize=6;" vertex="1" parent="1">
          <mxGeometry x="1600" y="520" width="200" height="410" as="geometry" />
        </mxCell>
        <mxCell id="flickrlogo" value="" style="shape=image;html=1;imageAspect=1;aspect=fixed;image={FLICKR}" vertex="1" parent="1">
          <mxGeometry x="1655" y="610" width="90" height="90" as="geometry" />
        </mxCell>
        <mxCell id="flickrtext" value="&lt;b&gt;Flickr API&lt;/b&gt;&lt;br&gt;&lt;i&gt;flickr.com&lt;/i&gt;&lt;br&gt;&lt;br&gt;&lt;i&gt;OAuth 1.0a&lt;br&gt;HMAC-SHA1 signed&lt;/i&gt;" style="text;html=1;align=center;verticalAlign=top;fontSize=13;fontColor=#1A1A1A;whiteSpace=wrap;" vertex="1" parent="1">
          <mxGeometry x="1610" y="715" width="180" height="120" as="geometry" />
        </mxCell>
        <mxCell id="aflickr" value="&lt;i&gt;Per-group daily add limits are why this system exists &#8212; a single request may retry for weeks.&lt;/i&gt;" style="text;html=1;align=left;verticalAlign=top;fontSize=11;fontColor=#333333;whiteSpace=wrap;" vertex="1" parent="1">
          <mxGeometry x="1600" y="945" width="240" height="80" as="geometry" />
        </mxCell>

        <mxCell id="key" value="&lt;b&gt;Legend&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:11px&quot;&gt;&#8212;&#8212;&#8212; request / response&lt;br&gt;&#8211; &#8211; &#8211; scheduled&lt;/font&gt;&lt;br&gt;&lt;br&gt;&lt;font style=&quot;font-size:10px&quot;&gt;Why it is built this way:&lt;br&gt;docs/architecture/DECISIONS.md&lt;/font&gt;" style="rounded=0;whiteSpace=wrap;html=1;align=left;verticalAlign=top;fillColor=#FFFFFF;strokeColor=#B0B0B0;fontSize=12;spacingLeft=10;spacingTop=8;" vertex="1" parent="1">
          <mxGeometry x="320" y="965" width="255" height="95" as="geometry" />
        </mxCell>

        <mxCell id="e1" value="HTTPS" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=2;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;" edge="1" parent="1" source="users" target="pages">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e2" value="fetch /api/v001/*&lt;br&gt;session cookie" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=2;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;" edge="1" parent="1" source="pages" target="api">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e3" value="request-token secret" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=2;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;" edge="1" parent="1" source="api" target="oauthdo">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e4" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;strokeWidth=2;strokeColor=#1A1A1A;fontSize=11;" edge="1" parent="1" source="secrets" target="api">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e5" value="master key" style="rounded=0;html=1;endArrow=classic;endFill=1;strokeWidth=2;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;" edge="1" parent="1" source="secrets" target="retry">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e6" value="nightly sweep" style="rounded=0;html=1;endArrow=classic;endFill=1;strokeWidth=2;dashed=1;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;" edge="1" parent="1" source="cron" target="retry">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e7" value="queue &#183; status" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=2;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;" edge="1" parent="1" source="api" target="d1">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e8" value="claim &#183; record" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=2;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;" edge="1" parent="1" source="retry" target="d1">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e9" value="request_token &#183; access_token" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=2;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.41;exitDx=0;exitDy=0;entryX=0;entryY=0.1;entryDx=0;entryDy=0;" edge="1" parent="1" source="api" target="flickr">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e10" value="flickr.groups.pools.add" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=2;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.59;exitDx=0;exitDy=0;entryX=0;entryY=0.9;entryDx=0;entryDy=0;" edge="1" parent="1" source="retry" target="flickr">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e11" value="authorize at flickr.com" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=2;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;" edge="1" parent="1" source="users" target="flickr">
          <mxGeometry relative="1" as="geometry">
            <Array as="points">
              <mxPoint x="115" y="1180" />
              <mxPoint x="1700" y="1180" />
            </Array>
          </mxGeometry>
        </mxCell>

      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
"""

OUT.write_text(
    TEMPLATE.replace("{CF}", CF).replace("{FLICKR}", FLICKR).replace("{DATE}", DATE),
    encoding="utf-8",
)
print(f"Wrote {OUT}")
print(f"  cloudflare payload : {len(CF)} chars")
print(f"  flickr payload     : {len(FLICKR)} chars")
print(f"  total file         : {OUT.stat().st_size} bytes")


# --------------------------------------------------------------------------
# Self-check. Straight edges are prettier than orthogonal ones but they cut
# corners off anything standing between the endpoints, and that is exactly the
# defect a human notices immediately and a generator never does. So the build
# refuses to pass silently: every straight edge is intersected against every
# box it is not attached to.
# --------------------------------------------------------------------------

import math
import re
import xml.etree.ElementTree as ET

# Frames, labels, and the pieces that sit inside the Flickr card on purpose.
NOT_OBSTACLES = {
    "cfframe", "netb", "cflogo", "title", "date", "subtitle",
    "flickrlogo", "flickrtext", "aflickr",
}

root = ET.parse(OUT).getroot()
cells = root.findall(".//mxCell")

boxes, edges = {}, []
for c in cells:
    g = c.find("mxGeometry")
    if c.get("vertex") == "1" and g is not None and g.get("x") is not None:
        boxes[c.get("id")] = tuple(float(g.get(k, 0)) for k in ("x", "y", "width", "height"))
    elif c.get("edge") == "1":
        edges.append(c)


def attach_point(box, style, prefix):
    """Fixed exitX/entryX if the style pins one, otherwise the box centre."""
    x, y, w, h = box
    fx = re.search(rf"{prefix}X=([\d.]+)", style)
    fy = re.search(rf"{prefix}Y=([\d.]+)", style)
    if fx and fy:
        return x + float(fx.group(1)) * w, y + float(fy.group(1)) * h
    return x + w / 2, y + h / 2


def seg_hits_rect(a, b, rect, pad=6.0):
    """True if segment ab passes through rect, grown by pad for near-misses.

    Liang-Barsky. The sign convention is the whole trick and is easy to get
    backwards: the parameter is p = -dx for the left edge and +dx for the right,
    NOT dx for both. An earlier version used dx throughout, which inverted every
    accept/reject and made the function answer False for everything -- a checker
    that reported "no collisions" because it could not see any. Hence the
    self-test below.
    """
    x, y, w, h = rect
    xmin, ymin, xmax, ymax = x - pad, y - pad, x + w + pad, y + h + pad
    dx, dy = b[0] - a[0], b[1] - a[1]

    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a[0] - xmin), (dx, xmax - a[0]),
                 (-dy, a[1] - ymin), (dy, ymax - a[1])):
        if p == 0:
            if q < 0:
                return False          # parallel and outside this slab
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


# Prove the detector can detect before trusting it to report clean. A checker
# that has never caught anything is indistinguishable from one that cannot.
_box = (100.0, 100.0, 100.0, 100.0)
_cases = [
    ("horizontal straight through", (0.0, 150.0), (300.0, 150.0), True),
    ("diagonal through corner",     (0.0, 0.0),   (300.0, 300.0), True),
    ("passes clearly above",        (0.0, 50.0),  (300.0, 50.0),  False),
    ("passes clearly below",        (0.0, 400.0), (300.0, 400.0), False),
    ("stops short of the box",      (0.0, 150.0), (50.0, 150.0),  False),
    ("starts after the box",        (250.0, 150.0), (400.0, 150.0), False),
]
for _name, _a, _b, _want in _cases:
    _got = seg_hits_rect(_a, _b, _box, pad=0.0)
    if _got != _want:
        raise SystemExit(f"SELF-TEST FAILED: {_name} -> got {_got}, want {_want}")
print(f"  collision detector self-test : {len(_cases)}/{len(_cases)} passed")


problems = 0
segments = {}
for e in edges:
    style = e.get("style") or ""
    if "orthogonalEdgeStyle" in style:
        continue  # routed deliberately; waypoints are not modelled here
    src, tgt = e.get("source"), e.get("target")
    if src not in boxes or tgt not in boxes:
        continue
    p = attach_point(boxes[src], style, "exit")
    q = attach_point(boxes[tgt], style, "entry")
    segments[e.get("id")] = (src, tgt, p, q)
    for bid, rect in boxes.items():
        if bid in (src, tgt) or bid in NOT_OBSTACLES:
            continue
        if seg_hits_rect(p, q, rect):
            print(f"  COLLISION: edge {e.get('id')} ({src} -> {tgt}) crosses '{bid}'")
            problems += 1

print(f"  straight edges checked : {len(segments)}")
print(f"  collisions             : {problems if problems else 'none'}")

# Edges that are meant to read as dead level. Attachment fractions are chosen so
# both ends land on the same y; a later box move silently breaks that, and a
# nearly-horizontal arrow looks like a mistake rather than a decision.
MUST_BE_HORIZONTAL = {
    "e1": "users -> pages",
    "e2": "pages -> api",
    "e6": "cron -> retry",
    "e9": "api -> flickr",
    "e10": "retry -> flickr",
}
for eid, label in MUST_BE_HORIZONTAL.items():
    if eid not in segments:
        raise SystemExit(f"Expected straight edge {eid} ({label}) not found.")
    _, _, p, q = segments[eid]
    drop = abs(p[1] - q[1])
    status = "level" if drop < 0.001 else f"OFF BY {drop:.2f}px"
    print(f"  {eid:4} {label:18} y={p[1]:.0f} -> {q[1]:.0f}  {status}")
    if drop >= 0.001:
        problems += 1


# A label wider than the arrow it sits on hides that arrow: the white label
# background masks the line, and on a short segment the text covers all of it.
# Measured against the VISIBLE segment -- the part between the two box edges --
# not the centre-to-centre distance, which is what makes short hops deceptive.
def visible_span(a, b, box):
    """Walk from a toward b until leaving box; returns where the line emerges."""
    x, y, w, h = box
    lo, hi = 0.0, 1.0
    for _ in range(60):
        m = (lo + hi) / 2
        px, py = a[0] + (b[0] - a[0]) * m, a[1] + (b[1] - a[1]) * m
        if x <= px <= x + w and y <= py <= y + h:
            lo = m
        else:
            hi = m
    return a[0] + (b[0] - a[0]) * lo, a[1] + (b[1] - a[1]) * lo


CHAR_PX = 6.0  # approx width per character at the 11px label font
edge_by_id = {e.get("id"): e for e in edges}
print("  label fit (widest line vs visible arrow):")
for eid, (src, tgt, p, q) in segments.items():
    style = edge_by_id[eid].get("style") or ""
    a = p if "exitX=" in style else visible_span(p, q, boxes[src])
    b = q if "entryX=" in style else visible_span(q, p, boxes[tgt])
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    raw = edge_by_id[eid].get("value") or ""
    if not raw:
        continue
    widest = max(len(line) for line in re.split(r"&lt;br&gt;|<br>", raw))
    est = widest * CHAR_PX
    verdict = "ok" if est <= length else "TOO WIDE"
    print(f"    {eid:4} arrow {length:>5.0f}px  label ~{est:>4.0f}px  {verdict}")
    if est > length:
        problems += 1

if problems:
    raise SystemExit("Diagram geometry check failed -- fix the layout before committing.")
