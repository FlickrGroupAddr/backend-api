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

Artwork comes from Wikimedia Commons and lives in docs/architecture/logos/ so the
build has no network dependency:
  cloudflare-mark.svg  File:Cloudflare Logo.svg
  flickr-mark-tight.svg  File:Flickr logo - SuperTinyIcons.svg, cropped to the
                         two dots. The 512x512 original is ~60% invisible white
                         padding, which renders as an uncloseable gap above the
                         title no matter what spacingTop says. See that file.
  users.svg            File:Font Awesome 5 solid users.svg

The first two are company trademarks used nominatively, to identify the services
this system actually depends on. users.svg is Font Awesome Free 5.2.0 by
@fontawesome, icons licensed CC BY 4.0 (https://fontawesome.com/license); the
attribution comment travels inside the SVG itself.
"""

import base64
import itertools
import math
import pathlib
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable

from diagram_sheets import AUTHORED, SHEETS, Sheet, sheet_path

# Dates are versions on this project -- there is no v1/v2 numbering. The
# filename and the title block MUST carry the same date, so both come from this
# one constant. Bump it when the diagram's content changes, and git mv the
# existing files to match before running.
#
# **The date records when the CONTENT changed, and all three sheets carry the
# same content.** They therefore carry the same date. Adding a sheet, or changing
# a page size, is not a content change and MUST NOT bump this.
DATE = "2026-08-17"

ROOT = pathlib.Path(__file__).resolve().parent.parent
SVG = ROOT / "docs" / "architecture" / "logos"
OUT = sheet_path(ROOT, DATE, AUTHORED)


def embed(name: str) -> str:
    raw = (SVG / name).read_bytes()
    return "data:image/svg+xml," + base64.b64encode(raw).decode("ascii")


CF = embed("cloudflare-mark.svg")
FLICKR = embed("flickr-mark-tight.svg")

# **A workstation, not a crowd of people.** The old glyph was FontAwesome's
# "users", which answers WHO rather than WHAT. Terry, 2026-08-15: the tile is the
# browser, and two little people read as "users of the system" when the diagram
# means "the browser client, one of exactly two first-class clients". Its
# neighbor on the canvas is a piece of software; this one should be too.
WORKSTATION = embed("workstation.svg")

# Adobe's Lightroom Classic "LrC" mark, hand-drawn as paths. Terry asked for it
# 2026-08-16, to put the Lightroom card on the same footing as the Cloudflare and
# Flickr cards, which both carry their marks. **Classic's icon, not Lightroom
# CC's** -- see that file's own comment for why the distinction matters here.
LRC_MARK = embed("lightroom-classic-mark.svg")

# ---------------------------------------------------------------------------
# THREE SHEETS, ONE DRAWING. The sheets themselves are in `diagram_sheets.py`.
#
# **The content is authored for tabloid, 11x17, and it fits that sheet exactly.**
# The other two sheets carry the SAME drawing, moved -- never resized. Each one
# gets a rigid translation so the ink sits centered on it, and legal additionally
# gets a `pageScale`, which is draw.io's own mechanism for "print this drawing
# smaller than one drawing unit per hundredth of an inch".
#
# **A TRANSLATION IS SAFE AND A RESCALE IS NOT, and that is the whole design.**
# Moving every coordinate by one delta changes no distance, so every font size,
# every hand-set box height, `CHAR_W`, the badge band and every threshold in the
# check suite below survive it meaning exactly what they meant. Multiplying every
# coordinate would leave all of them silently wrong -- see the paragraph on
# rescaling further down, which has stood here since 2026-08-14.
#
# **8.5x14 CANNOT SHOW THIS DRAWING AT A READABLE SIZE, and the arithmetic is
# not close.** Legal landscape has 7.9 in of printable height against tabloid's
# 10.4, so the content lands at ~76% and the 10.1 pt body type becomes ~7.7 pt.
# **Terry measured 7.9 pt himself and called that print an eyechart.** A perfect
# reflow to legal's aspect would buy about 3% -- the sheet holds 62% of tabloid's
# printable AREA, so the ceiling is sqrt(0.62) = 78.8%, still under his floor.
# The build prints the resulting point size for every sheet on every run, so this
# is a number on screen rather than a claim in a comment.
#
# PAGE SIZE, the tabloid reasoning this block was originally written for:
#
# **drawio uses 100 units per inch**, so tabloid landscape is 1700 x 1100 and
# US Letter landscape is 1100 x 850.
#
# **Terry printed this on Letter landscape and called it "a fuckin unusable
# eyechart", which the arithmetic agreed with.** The content was 1770 x 1303 units
# then, so fitting it to Letter scaled to 65%. Fitting the same content to tabloid
# scaled to 84%, on a sheet 1.55x larger in each direction -- roughly DOUBLE the
# physical text size. **Those numbers are HISTORY. The content is 1640 x 1030
# today** and the current figures are below.
#
# **DPI DOES NOT APPLY TO A PDF, and the distinction is worth one paragraph.** A
# PDF stores shapes as coordinates and text as glyphs, so it re-renders sharp at
# whatever resolution the viewer or printer asks for. There is no "300 DPI PDF" to
# choose -- a 300 DPI printer draws it at 300, a 1200 DPI one at 1200, and zooming
# in on screen keeps sharpening. **DPI is a raster setting**, and it matters only
# for a PNG or JPG export.
#
# **What decides a PDF is the PAGE SIZE**, which is why `Sheet.width` and
# `Sheet.height` are in hundredths of an inch and not in dots.

# **THE CONTENT FITS THIS PAGE 1:1, as of 2026-08-16, and it never did before.**
#
#   Printable area  1640 x 1040   (1700 x 1100, less 30 per side)
#   Content         1640 x 1030   x 30 to 1670, y 16.35 to 1046.35
#   Scale           100.0%        width binds exactly, height has 10 to spare
#
# **The content is CENTERED horizontally and is not centered vertically.** x 30
# to 1670 leaves 30 on each side, which is exactly MARGIN.
#
# **The TOP is measured in ink, not in boxes.** The canvas moved -3.65 in y on
# 2026-08-16 so the title's cap top lands on y=30 -- see `label_ink_y()` below and
# the check that asserts it. The box therefore starts at 16.35, which looks like
# a margin violation and is not. The BOTTOM is unsettled: Terry is stretching the
# content down the page rather than centering it.
#
# **The horizontal landed in two moves on 2026-08-16**, both from Terry looking at
# a render. First +20 in x, which closed a 5-against-45 split at the old 0.25in
# margin. Then, for the 0.30in target, the right column gave up 10 of width and
# the whole canvas moved +5 -- 16.5in of content became 16.4in, and 25/25 became
# 30/30. **The vertical is mid-change**: he is stretching the canvas down the
# page rather than centering it.
#
# **So export WITHOUT "Fit to Page".** That option is now the wrong choice -- it
# would shrink a drawing that already fits. This reverses the instruction that
# stood here from 2026-08-14 to 2026-08-16, when the content was 1770 x 1303 and
# ran 4% over in width and 18% over in height.
#
# **Three separate changes closed that gap**, and none of them was a rescale:
# the step badges came off (badge `n7` used to hang to y=1327, 227 units below the
# page), the Cloudflare frame lost 140 units of height, and the right column
# narrowed from 350 to 330 on 2026-08-16 -- the last 20 units of width. It gave up
# another 10 the same evening, to 320, to buy the 0.30in margin.
#
# **Scaling every coordinate to chase a page was always the wrong fix**, and it
# still is. It changes no physical text size -- it moves the shrink out of the
# export dialog and into the file -- while silently invalidating every absolute
# threshold here: the badge band, `CHAR_W`, every hand-set box height. None of
# them would fail. They would stop meaning anything.
#
# **THE MARGIN NOW BINDS, which is the cost of fitting exactly.** At 1640 of 1640
# there is zero slack in width, so a driver cannot absorb an overflow by scaling a
# percent or two. Anything that widens the canvas breaks the 1:1 fit immediately.
# The page-fit block prints the figures on every build.

# **The Auth Data Flow panel's row size, and it is ONE number rather than 64.**
# Terry tunes this by eye against the render, so it was 64 identical literals on a
# single line -- the shape `measuring-tools-need-a-render` warns about, where a
# checker's configuration is duplicated and one copy silently stops matching.
#
# **It is FRACTIONAL on purpose.** `char_w` interpolates between its calibrated
# integer sizes, so a tenth of a unit is measurable and the panel can be filled
# much closer than a whole-point step allows.
JOURNEY_ROW_PX = 12.2

TEMPLATE = f"""<mxfile host="app.diagrams.net" agent="Claude Code" version="24.0.0">
  <diagram id="fga-architecture" name="FlickrGroupAddr Architecture">
    <mxGraphModel dx="1422" dy="900" grid="0" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{AUTHORED.width}" pageHeight="{AUTHORED.height}" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />

        <mxCell id="title" value="FlickrGroupAddr Architecture" style="text;html=1;align=left;verticalAlign=middle;fontSize=28;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="30" y="16.35" width="700" height="48" as="geometry" />
        </mxCell>
        <mxCell id="date" value="{DATE}" style="text;html=1;align=center;verticalAlign=middle;fontSize=20;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="30" y="52.35" width="399" height="36" as="geometry" />
        </mxCell>

        <mxCell id="cfframe" value="" style="rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#1A1A1A;strokeWidth=2;" vertex="1" parent="1">
          <mxGeometry x="231.5" y="106.35" width="814" height="917.15" as="geometry" />
        </mxCell>
        <mxCell id="cflogo" value="" style="shape=image;html=1;imageAspect=1;aspect=fixed;image={CF}" vertex="1" parent="1">
          <mxGeometry x="261.5" y="136.35" width="205.827" height="68" as="geometry" />
        </mxCell>
        <mxCell id="netb" value="Lowest-Latency Cloudflare Edge PoP (Anycast Routing)" style="rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#F6821F;dashed=1;strokeWidth=2;verticalAlign=top;fontColor=#F6821F;fontStyle=1;fontSize=15;spacingTop=6;" vertex="1" parent="1">
          <mxGeometry x="261.5" y="232.55" width="542.6" height="762.75" as="geometry" />
        </mxCell>

        <mxCell id="lrcapp" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#546E7A;strokeWidth=3;arcSize=6;" vertex="1" parent="1">
          <mxGeometry x="31.5" y="106.35" width="180" height="380" as="geometry" />
        </mxCell>
        <mxCell id="lrcmark" value="" style="shape=image;html=1;imageAspect=1;aspect=fixed;image={LRC_MARK}" vertex="1" parent="1">
          <mxGeometry x="83.1" y="122.35" width="76.8" height="74.88" as="geometry" />
        </mxCell>
        <mxCell id="lrc" value="&lt;b&gt;FGA&lt;br&gt;LrC Plugin&lt;/b&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#546E7A;strokeColor=none;fontColor=#FFFFFF;fontSize=14;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="56.5" y="352.55" width="130" height="120" as="geometry" />
        </mxCell>
        <mxCell id="lrcat" value="&lt;b&gt;Catalog&lt;/b&gt;&lt;br&gt;&lt;i&gt;Flickr photo IDs&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#607D8B;strokeColor=none;fontColor=#FFFFFF;fontSize=14;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="56.5" y="229.75" width="130" height="60" as="geometry" />
        </mxCell>
        <mxCell id="users" value="Browser" style="shape=image;html=1;imageAspect=1;aspect=fixed;image={WORKSTATION};fontSize=15;fontStyle=1;labelPosition=center;align=right;verticalLabelPosition=bottom;verticalAlign=top;spacingTop=-6;spacingRight=0;" vertex="1" parent="1">
          <mxGeometry x="30" y="540.7" width="183" height="146.399"  as="geometry" />
        </mxCell>

        <mxCell id="dns" value="&lt;b&gt;FGA DNS&lt;/b&gt;&lt;br&gt;&lt;i&gt;Cloudflare DNS&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F6821F;strokeColor=none;fontColor=#FFFFFF;fontSize=14;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="289.7" y="476.625" width="158" height="60" as="geometry" />
        </mxCell>
        <mxCell id="secrets" value="&lt;b&gt;App Secrets Store&lt;/b&gt;&lt;br&gt;&lt;i&gt;Worker Secrets&lt;br&gt;FGA Flickr API credentials&lt;br&gt;Token key (encryption)&lt;br&gt;Session key (signing)&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#6B7280;strokeColor=none;fontColor=#FFFFFF;fontSize=14;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="475.9" y="710.9" width="300" height="111" as="geometry" />
        </mxCell>
        <mxCell id="cron" value="&lt;b&gt;Nightly Event&lt;/b&gt;&lt;br&gt;&lt;i&gt;Workers Cron Trigger&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FBAD41;strokeColor=none;fontColor=#3A2200;fontSize=14;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="289.7" y="710.9" width="158" height="111" as="geometry" />
        </mxCell>

        <mxCell id="devicedo_b2" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#2E7D32;strokeColor=#FFFFFF;strokeWidth=2;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="848.3" y="272.55" width="169" height="142.8" as="geometry" />
        </mxCell>
        <mxCell id="devicedo_b1" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#2E7D32;strokeColor=#FFFFFF;strokeWidth=2;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="840.3" y="280.55" width="169" height="142.8" as="geometry" />
        </mxCell>
        <mxCell id="devicedo" value="&lt;b&gt;Device Link User Code&lt;/b&gt;&lt;br&gt;&lt;i&gt;One Durable Object&lt;br&gt;per link attempt&lt;br&gt;10 min TTL&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#2E7D32;strokeColor=#FFFFFF;strokeWidth=2;fontColor=#FFFFFF;fontSize=13;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="832.3" y="288.55" width="169" height="142.8" as="geometry" />
        </mxCell>
        <mxCell id="oauthdo_b2" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#6A3D9A;strokeColor=#FFFFFF;strokeWidth=2;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="848.3" y="449.55" width="169" height="142.8" as="geometry" />
        </mxCell>
        <mxCell id="oauthdo_b1" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#6A3D9A;strokeColor=#FFFFFF;strokeWidth=2;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="840.3" y="457.55" width="169" height="142.8" as="geometry" />
        </mxCell>
        <mxCell id="oauthdo" value="&lt;b&gt;Flickr OAuth State&lt;/b&gt;&lt;br&gt;&lt;i&gt;One Durable Object&lt;br&gt;per login attempt&lt;br&gt;~15 min TTL&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#6A3D9A;strokeColor=#FFFFFF;strokeWidth=2;fontColor=#FFFFFF;fontSize=13;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="832.3" y="465.55" width="169" height="142.8" as="geometry" />
        </mxCell>
        <mxCell id="api" value="&lt;b&gt;flickrgroupaddr.com&lt;/b&gt;&lt;div style=&quot;font-size:14px;margin-top:6px&quot;&gt;&lt;i&gt;Single Cloudflare Worker&lt;/i&gt;&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F6821F;strokeColor=none;fontColor=#FFFFFF;fontSize=15;arcSize=12;verticalAlign=top;spacingTop=8;" vertex="1" parent="1">
          <mxGeometry x="475.9" y="288.55" width="300" height="394.15" as="geometry" />
        </mxCell>
        <mxCell id="apidevice" value="&lt;b&gt;/auth/device-link/start&lt;/b&gt; API endpoint" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#B85C0A;strokeColor=#FFFFFF;strokeWidth=1;fontColor=#FFFFFF;fontSize=13;arcSize=14;" vertex="1" parent="1">
          <mxGeometry x="495.9" y="352.55" width="260" height="36" as="geometry" />
        </mxCell>
        <mxCell id="apiplugin" value="&lt;b&gt;/auth/device-link/poll&lt;/b&gt; API endpoint" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#B85C0A;strokeColor=#FFFFFF;strokeWidth=1;fontColor=#FFFFFF;fontSize=13;arcSize=14;" vertex="1" parent="1">
          <mxGeometry x="495.9" y="394.55" width="260" height="36" as="geometry" />
        </mxCell>
        <mxCell id="apinew" value="&lt;b&gt;/auth/device-link/{{approve,deny}}&lt;/b&gt; Endpoint" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#B85C0A;strokeColor=#FFFFFF;strokeWidth=1;fontColor=#FFFFFF;fontSize=12;arcSize=14;" vertex="1" parent="1">
          <mxGeometry x="495.9" y="624.7" width="260" height="36" as="geometry" />
        </mxCell>
        <mxCell id="apioauth" value="&lt;b&gt;/auth/flickr/*&lt;/b&gt; API endpoints" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#B85C0A;strokeColor=#FFFFFF;strokeWidth=1;fontColor=#FFFFFF;fontSize=13;arcSize=14;" vertex="1" parent="1">
          <mxGeometry x="495.9" y="582.7" width="260" height="36" as="geometry" />
        </mxCell>
        <mxCell id="apilink" value="&lt;b&gt;/auth/device-link/enter-user-code&lt;/b&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#B85C0A;strokeColor=#FFFFFF;strokeWidth=1;fontColor=#FFFFFF;fontSize=13;arcSize=14;" vertex="1" parent="1">
          <mxGeometry x="495.9" y="540.7" width="260" height="36" as="geometry" />
        </mxCell>
        <mxCell id="apirest" value="&lt;b&gt;/api/v001/*&lt;/b&gt; API endpoints" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#B85C0A;strokeColor=#FFFFFF;strokeWidth=1;fontColor=#FFFFFF;fontSize=13;arcSize=14;" vertex="1" parent="1">
          <mxGeometry x="495.9" y="436.55" width="260" height="36" as="geometry" />
        </mxCell>
        <mxCell id="retry" value="&lt;b&gt;Nightly Retry Logic&lt;/b&gt;&lt;br&gt;&lt;i&gt;Cloudflare Worker&lt;br&gt;Attempt to flush every queue with&lt;br&gt;pending requests. Stop a queue at&lt;br&gt;its first throttle status&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F6821F;strokeColor=none;fontColor=#FFFFFF;fontSize=15;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="475.9" y="850.1" width="300" height="117" as="geometry" />
        </mxCell>

        <mxCell id="d1" value="&lt;b&gt;SQL Database&lt;/b&gt;&lt;br&gt;&lt;i&gt;Cloudflare D1&lt;br&gt;Users &#183; requests &#183; tokens&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#00A3E0;strokeColor=none;fontColor=#FFFFFF;fontSize=14;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="832.3" y="710.9" width="169" height="111" as="geometry" />
        </mxCell>

        <mxCell id="flickr" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#FF0084;strokeWidth=3;arcSize=6;" vertex="1" parent="1">
          <mxGeometry x="1065.5" y="418.75" width="236" height="604.75" as="geometry" />
        </mxCell>
        <mxCell id="flickrtitle" value="Flickr" style="text;html=1;align=center;verticalAlign=middle;fontSize=20;fontStyle=1;fontColor=#1A1A1A;" vertex="1" parent="1">
          <mxGeometry x="1090.5" y="534.75" width="186" height="32" as="geometry" />
        </mxCell>
        <mxCell id="flickrapi" value="&lt;b&gt;Flickr API&lt;/b&gt;&lt;div style=&quot;font-size:14px&quot;&gt;&lt;i&gt;OAuth 1.0a&lt;/i&gt;&lt;/div&gt;&lt;div style=&quot;font-size:15px;border-bottom:2px solid #FFFFFF;display:inline-block;padding-bottom:3px;margin-top:48px&quot;&gt;&lt;b&gt;OAuth Endpoints&lt;/b&gt;&lt;/div&gt;&lt;div style=&quot;font-size:14px;line-height:22px;margin-top:7px&quot;&gt;/oauth/request_token&lt;/div&gt;&lt;div style=&quot;font-size:14px;line-height:22px&quot;&gt;/oauth/authorize&lt;/div&gt;&lt;div style=&quot;font-size:14px;line-height:22px&quot;&gt;/oauth/access_token&lt;/div&gt;&lt;div style=&quot;font-size:15px;border-bottom:2px solid #FFFFFF;display:inline-block;padding-bottom:3px;margin-top:48px&quot;&gt;&lt;b&gt;API Functions&lt;/b&gt;&lt;/div&gt;&lt;div style=&quot;font-size:14px;line-height:22px;margin-top:7px&quot;&gt;groups.pools.getGroups&lt;/div&gt;&lt;div style=&quot;font-size:14px;line-height:22px&quot;&gt;photos.getAllContexts&lt;/div&gt;&lt;div style=&quot;font-size:14px;line-height:22px&quot;&gt;groups.pools.add&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FF0084;strokeColor=none;fontColor=#FFFFFF;fontSize=20;arcSize=8;verticalAlign=top;spacingTop=16;" vertex="1" parent="1">
          <mxGeometry x="1090.5" y="616.75" width="186" height="378.55" as="geometry" />
        </mxCell>
        <mxCell id="flickrlogo" value="" style="shape=image;html=1;imageAspect=1;aspect=fixed;image={FLICKR}" vertex="1" parent="1">
          <mxGeometry x="1090.5" y="443.75" width="186" height="88.05" as="geometry" />
        </mxCell>
                <mxCell id="justification" value="&lt;b&gt;Project Justification&lt;/b&gt;&lt;div style=&quot;margin-left:26px;font-size:13px&quot;&gt;Flickr caps how many photos a member may add to a group each day. Doing it by hand means coming back every day for weeks. FGA queues each request and keeps retrying until it lands.&lt;/div&gt;" style="rounded=0;whiteSpace=wrap;html=1;align=left;verticalAlign=top;fillColor=#FFFFFF;strokeColor=#B0B0B0;fontSize=14;spacingLeft=10;spacingTop=8;spacingRight=8;" vertex="1" parent="1">
          <mxGeometry x="1065.5" y="106.35" width="236" height="147.5" as="geometry" />
        </mxCell>

        <mxCell id="key" value="&lt;b&gt;Legend&lt;/b&gt;&lt;div style=&quot;margin-left:26px;font-size:13px&quot;&gt;&lt;span style=&quot;display:inline-block;width:39px;margin-right:10px;border-bottom:2px solid #1A1A1A;vertical-align:middle&quot;&gt;&lt;/span&gt;Request / response&lt;/div&gt;&lt;div style=&quot;margin-left:26px;font-size:13px&quot;&gt;&lt;span style=&quot;display:inline-block;width:39px;margin-right:10px;border-bottom:2px dotted #1A1A1A;vertical-align:middle&quot;&gt;&lt;/span&gt;Scheduled trigger&lt;/div&gt;&lt;div style=&quot;margin-left:26px;font-size:12px;margin-top:13px&quot;&gt;Why it is built this way:&lt;/div&gt;&lt;div style=&quot;margin-left:26px;font-size:12px&quot;&gt;docs/architecture/DECISIONS.md&lt;/div&gt;" style="rounded=0;whiteSpace=wrap;html=1;align=left;verticalAlign=top;fillColor=#FFFFFF;strokeColor=#B0B0B0;fontSize=14;spacingLeft=10;spacingTop=8;" vertex="1" parent="1">
          <mxGeometry x="1065.5" y="276.3" width="236" height="120" as="geometry" />
        </mxCell>

        <mxCell id="journey" value="&lt;div style=&quot;font-size:16px;border-bottom:2px solid #1A1A1A;display:inline-block;padding-bottom:3px&quot;&gt;&lt;b&gt;Auth Data Flow&lt;/b&gt;&lt;/div&gt;&lt;table cellpadding=&quot;0&quot; cellspacing=&quot;0&quot; style=&quot;margin-top:7px;border-collapse:collapse&quot;&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:right;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;1&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;User clicks &lt;b&gt;Authorize with FGA&lt;/b&gt; button in LrC Plugin&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:right;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;2&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Plugin resolves DNS for fga.com&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:right;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;3&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Plugin HTTPS POST to /auth/device-link/start&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:right;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;4&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Server creates Durable Object identified by &lt;b&gt;User Code&lt;/b&gt;&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:right;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;5&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Server responds w/ &lt;b&gt;User Code&lt;/b&gt; and &lt;b&gt;Device Code&lt;/b&gt;&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:right;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;6&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;LrC Plugin displays &lt;b&gt;User Code&lt;/b&gt; on screen and launches browser w/ URL: /auth/device-link/enter-user-code&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:right;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;7&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Browser resolves DNS for fga.com&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:right;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;8&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Browser HTTPS GET: /auth/device-link/enter-user-code&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:right;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;9&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;/auth/device-link/enter-user-code returns HTTP redirect to /auth/flickr/login, due to absence of &lt;b&gt;FGA Session ID&lt;/b&gt; cookie in request headers&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;10&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Browser redirected, HTTPS GET: /auth/flickr/login&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;11&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Server reads Flickr API creds from Worker Secrets&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;12&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Server makes signed call to Flickr /oauth/request_token&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;13&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Flickr responds w/ &lt;b&gt;Request Token&lt;/b&gt;, &lt;b&gt;Request Secret&lt;/b&gt;&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;14&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Server creates Durable Object identified by &lt;b&gt;Request Token&lt;/b&gt;, holding &lt;b&gt;Request Secret&lt;/b&gt; and return path&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;15&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;/auth/flickr/login returns HTTP redirect to Flickr API /oauth/authorize, carrying &lt;b&gt;Request Token&lt;/b&gt;&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;16&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Browser redirected, HTTPS GET: Flickr API /oauth/authorize, carrying &lt;b&gt;Request Token&lt;/b&gt; in oauth_token URL query parameter&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;17&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;User grants FGA &lt;b&gt;write&lt;/b&gt; access on their entire Flickr account, w/ manual click in their browser&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;18&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Flickr API returns HTTP redirect to /auth/flickr/callback, carrying &lt;b&gt;Request Token&lt;/b&gt; and &lt;b&gt;Verifier&lt;/b&gt;&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;19&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Browser redirected, HTTPS GET: /auth/flickr/callback, carrying &lt;b&gt;Request Token&lt;/b&gt; and &lt;b&gt;Verifier&lt;/b&gt; in oauth_token and oauth_verifier URL query parameters&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;20&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Server reads and deletes Durable Object, recovering &lt;b&gt;Request Secret&lt;/b&gt; and return path&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;21&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Server calls Flickr /oauth/access_token, signed w/ &lt;b&gt;Request Secret&lt;/b&gt;, carrying &lt;b&gt;Verifier&lt;/b&gt;&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;22&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Flickr responds w/ &lt;b&gt;Access Token&lt;/b&gt;, &lt;b&gt;Access Secret&lt;/b&gt;, NSID and username&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;23&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Server encrypts &lt;b&gt;Access Token&lt;/b&gt; and &lt;b&gt;Access Secret&lt;/b&gt; under &lt;b&gt;Token Key&lt;/b&gt;, writes user row to D1&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;24&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Server creates &lt;b&gt;FGA Session ID&lt;/b&gt; and writes its &lt;span style=&quot;white-space:nowrap&quot;&gt;SHA2-256&lt;/span&gt; hash to D1&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;25&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;/auth/flickr/callback returns HTTP redirect to /auth/device-link/enter-user-code, setting host-only &lt;b&gt;FGA Session ID&lt;/b&gt; cookie for fga.com&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;26&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Browser redirected w/ &lt;b&gt;FGA Session ID&lt;/b&gt; cookie, HTTPS GET: &lt;span style=&quot;white-space:nowrap&quot;&gt;/auth/device-link/enter-user-code&lt;/span&gt;&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;27&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;User reads &lt;b&gt;User Code&lt;/b&gt; from LrC Plugin and submits via browser form; browser HTTPS POST to &lt;span style=&quot;white-space:nowrap&quot;&gt;/auth/device-link/approve&lt;/span&gt;&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;28&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Server marks Durable Object approved, attaching user&#39;s Flickr NSID&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;29&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Plugin polls /auth/device-link/poll w/ &lt;b&gt;Device Code&lt;/b&gt;, repeating since step 6&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;30&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Polling read returns &lt;b&gt;FGA Session ID&lt;/b&gt;&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;31&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Plugin saves session ID in LrC secure credential store&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:16px;text-align:left;padding-right:10px;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;&lt;b&gt;32&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:{JOURNEY_ROW_PX}px&quot;&gt;Plugin performs FGA app operations against /api/v001/*&lt;/td&gt;&lt;/tr&gt;&lt;/table&gt;" style="rounded=0;whiteSpace=wrap;html=1;align=left;verticalAlign=top;fillColor=#FFFFFF;strokeColor=#003087;strokeWidth=2;fontSize=15;spacingLeft=12;spacingTop=8;spacingRight=10;" vertex="1" parent="1">
          <mxGeometry x="1321.5" y="106.35" width="347.5" height="917.15" as="geometry" />
        </mxCell>

        <mxCell id="e26" value="" style="rounded=0;html=1;endArrow=block;endFill=1;startArrow=block;startFill=1;endSize=3;startSize=3;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.630217;exitDx=0;exitDy=0;entryX=0;entryY=0.500000;entryDx=0;entryDy=0;" edge="1" parent="1" source="api" target="oauthdo">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e1" value="" style="rounded=0;html=1;endArrow=block;endFill=1;startArrow=block;startFill=1;endSize=3;startSize=3;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=0.970711;exitY=0.036612;exitDx=0;exitDy=0;exitPerimeter=0;entryX=0;entryY=0.75;entryDx=0;entryDy=0;entryPerimeter=0;" edge="1" parent="1" source="users" target="dns">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e24" value="" style="rounded=0;html=1;endArrow=block;endFill=1;startArrow=block;startFill=1;endSize=3;startSize=3;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.500000;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" edge="1" parent="1" source="lrc" target="apiplugin">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e13" value="" style="rounded=0;html=1;endArrow=block;endFill=1;startArrow=block;startFill=1;endSize=3;startSize=3;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.850000;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" edge="1" parent="1" source="lrc" target="apirest">
          <mxGeometry x="0.55" relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e23" value="" style="rounded=0;html=1;endArrow=block;endFill=1;startArrow=block;startFill=1;endSize=3;startSize=3;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.696722;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" edge="1" parent="1" source="users" target="apinew">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e22" value="" style="rounded=0;html=1;endArrow=block;endFill=1;startArrow=block;startFill=1;endSize=3;startSize=3;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.409836;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" edge="1" parent="1" source="users" target="apioauth">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e25" value="" style="rounded=0;html=1;endArrow=block;endFill=1;startArrow=block;startFill=1;endSize=3;startSize=3;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.122950;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" edge="1" parent="1" source="users" target="apilink">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e21" value="" style="rounded=0;html=1;endArrow=block;endFill=1;startArrow=block;startFill=1;endSize=3;startSize=3;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=0.967554;exitY=0.964850;exitDx=0;exitDy=0;exitPerimeter=0;entryX=0;entryY=0.25;entryDx=0;entryDy=0;entryPerimeter=0;" edge="1" parent="1" source="lrc" target="dns">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e18" value="" style="rounded=0;html=1;endArrow=block;endFill=1;startArrow=block;startFill=1;endSize=3;startSize=3;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.150000;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" edge="1" parent="1" source="lrc" target="apidevice">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e20" value="" style="rounded=0;html=1;endArrow=block;endFill=1;startArrow=block;startFill=1;endSize=3;startSize=3;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;exitX=0.5;exitY=0;exitDx=0;exitDy=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;" edge="1" parent="1" source="lrc" target="lrcat">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e19" value="" style="rounded=0;html=1;endArrow=block;endFill=1;endSize=3;startSize=3;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" edge="1" parent="1" source="lrc" target="users">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e3" value="" style="rounded=0;html=1;endArrow=block;endFill=1;startArrow=block;startFill=1;endSize=3;startSize=3;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.208043;exitDx=0;exitDy=0;entryX=0;entryY=0.574230;entryDx=0;entryDy=0;" edge="1" parent="1" source="api" target="devicedo">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e4" value="" style="rounded=0;html=1;endArrow=block;endFill=1;startArrow=block;startFill=1;endSize=3;startSize=3;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;exitX=0.5;exitY=0;exitDx=0;exitDy=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;" edge="1" parent="1" source="secrets" target="api">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e5" value="" style="rounded=0;html=1;endArrow=block;endFill=1;startArrow=block;startFill=1;endSize=3;startSize=3;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" edge="1" parent="1" source="secrets" target="retry">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e6" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;endSize=3;startSize=3;strokeWidth=2;dashed=1;dashPattern=1 4;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" edge="1" parent="1" source="cron" target="retry">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e14" value="" style="rounded=0;html=1;endArrow=block;endFill=1;startArrow=block;startFill=1;endSize=3;startSize=3;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;exitX=0.973207;exitY=0.959612;exitDx=0;exitDy=0;exitPerimeter=0;entryX=0.017598;entryY=0.044423;entryDx=0;entryDy=0;entryPerimeter=0;" edge="1" parent="1" source="api" target="d1">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e15" value="" style="rounded=0;html=1;endArrow=block;endFill=1;startArrow=block;startFill=1;endSize=3;startSize=3;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;exitX=0.990437;exitY=0.047316;exitDx=0;exitDy=0;exitPerimeter=0;entryX=0.016101;entryY=0.952685;entryDx=0;entryDy=0;entryPerimeter=0;" edge="1" parent="1" source="retry" target="d1">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e9" value="" style="rounded=0;html=1;endArrow=block;endFill=1;startArrow=block;startFill=1;endSize=3;startSize=3;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.891666;exitDx=0;exitDy=0;entryX=0;entryY=0.061419;entryDx=0;entryDy=0;" edge="1" parent="1" source="api" target="flickrapi">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e10" value="" style="rounded=0;html=1;endArrow=block;endFill=1;startArrow=block;startFill=1;endSize=3;startSize=3;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.770968;entryDx=0;entryDy=0;" edge="1" parent="1" source="retry" target="flickrapi">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e11" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;startArrow=block;startFill=1;endSize=3;startSize=3;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=0.5;exitY=0.984615;exitDx=0;exitDy=0;exitPerimeter=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;" edge="1" parent="1" source="users" target="flickrapi">
          <mxGeometry relative="1" as="geometry">
            <Array as="points">
              <mxPoint x="121.5" y="1053.5" />
              <mxPoint x="1183.5" y="1053.5" />
            </Array>
          </mxGeometry>
        </mxCell>


        <mxCell id="n1" value="1" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="64.5" y="360.55" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n2" value="2" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=2.5;fontColor=#FFFFFF;fontSize=11;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="236" y="471.7573" width="21" height="21" as="geometry" />
        </mxCell>
        <mxCell id="n6" value="6" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="109.5" y="497" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n4" value="4" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="840.3" y="296.55" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n3" value="3" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="321.7" y="358.55" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n5" value="5" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="391.7" y="358.55" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n7" value="7" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=2.5;fontColor=#FFFFFF;fontSize=11;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="236" y="523.9887" width="21" height="21" as="geometry" />
        </mxCell>
        <mxCell id="n8" value="8" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="286.7" y="546.7" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n9" value="9" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="356.7" y="546.7" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n10" value="10" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="275.7" y="588.7" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n11" value="11" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=2.5;fontColor=#FFFFFF;fontSize=11;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="639.4" y="686.3" width="21" height="21" as="geometry" />
        </mxCell>
        <mxCell id="n12" value="12" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="817.8" y="628" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n13" value="13" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="875.8" y="628" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n14" value="14" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="840.3" y="473.55" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n15" value="15" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="329.7" y="588.7" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n16" value="16" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=15;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="534.9" y="1038.5" width="30" height="30"  as="geometry" />
        </mxCell>
        <mxCell id="n17" value="17" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=15;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="610.9" y="1038.5" width="30" height="30" as="geometry" />
        </mxCell>
        <mxCell id="n18" value="18" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=15;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="686.9" y="1038.5" width="30" height="30" as="geometry" />
        </mxCell>
        <mxCell id="n19" value="19" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="383.7" y="588.7" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n20" value="20" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="969.3" y="473.55" width="24" height="24"  as="geometry" />
        </mxCell>
        <mxCell id="n21" value="21" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="933.8" y="628" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n22" value="22" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="991.8" y="628" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n23" value="23" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=2.5;fontColor=#FFFFFF;fontSize=11;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="778.535" y="671.687" width="21" height="21" as="geometry" />
        </mxCell>
        <mxCell id="n24" value="24" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=2.5;fontColor=#FFFFFF;fontSize=11;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="803.601" y="689.925" width="21" height="21" as="geometry" />
        </mxCell>
        <mxCell id="n25" value="25" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="437.7" y="588.7" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n26" value="26" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="426.7" y="546.7" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n27" value="27" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="356.7" y="630.7" width="24" height="24"  as="geometry" />
        </mxCell>
        <mxCell id="n28" value="28" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="969.3" y="296.55" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n29" value="29" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="321.7" y="400.55" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n31" value="31" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="154.5" y="360.55" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n32" value="32" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="356.7" y="442.55" width="24" height="24" as="geometry" />
        </mxCell>
        <mxCell id="n30" value="30" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=12;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="391.7" y="400.55" width="24" height="24" as="geometry" />
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
"""

# **TEMPLATE is an f-string, so `{CF}`, `{FLICKR}`, `{WORKSTATION}` and `{DATE}`
# are already substituted by the time it is a value.** The `.replace()` chain that
# used to live here was doing nothing, and it hid a dangling `{USERS}` reference
# until the variable was deleted -- at which point the f-string failed loudly,
# which is the better failure.
#
# **This writes the AUTHORED sheet only.** The other two are written at the very
# end of this file, because each one needs the ink extents to center itself on
# its page, and those extents are measured by the page-fit block in the check
# suite. Deriving them here would mean a second implementation of the ink
# measurement, and the two would drift.
OUT.write_text(TEMPLATE, encoding="utf-8")
print(f"Wrote {OUT}")
print(f"  cloudflare payload : {len(CF)} chars")
print(f"  flickr payload     : {len(FLICKR)} chars")
print(f"  total file         : {OUT.stat().st_size} bytes")

# ===========================================================================
# CHECKS_ENABLED IS A PERMANENT LEVER. IT MUST NOT BE REMOVED.
#
# **Standing order, Terry, 2026-08-16, verbatim: "Note that I plan to flip that
# toggle often, so leave standing orders to never remove it. That's a lever I
# pull often."** RFC 2119 sense -- MUST NOT is absolute.
#
# **A future session MUST NOT delete this flag as cleanup**, MUST NOT fold it
# into a command-line argument nobody remembers, and MUST NOT "simplify" it away
# once the checks are green again. Finding it set to True is NOT evidence that it
# has stopped being needed -- True is its resting state, and the whole point is
# that Terry moves it.
#
# **Why he needs it.** The build otherwise REFUSES to write a diagram that fails
# any check. That is the right default and it is wrong during a design pass: an
# assertion pinned to a layout being redrawn fires on every intermediate state,
# and a check that fires on every run is a check nobody reads.
#
# **That is the WHOLE reason, and it is about signal rather than speed.** This
# block used to claim the suite "costs a full iteration of wall-clock time per
# edit". **Measured 2026-08-17: this script runs in 0.197 s, median of seven,
# and 0.070 s of that is starting Python and importing ElementTree.** The checks
# are worth roughly 0.13 s. **The speed argument was never true, so it is deleted
# rather than softened** -- a lever defended on a claim a stopwatch refutes is a
# lever somebody removes the first time they time it. The signal argument alone
# is sufficient and does not weaken.
#
# **The shape is fixed: ONE flag, never commented-out blocks, and a banner on
# EVERY build.** The banner is load-bearing. The last time the suite went off,
# two documents still said so eight hours later, and nothing on screen disagreed.
#
# **Turning it back on is NOT flipping this flag.** A suite switched back on
# after a redesign asserts the design that no longer exists. Re-read the suite
# against the new layout and rewrite what has stopped being true.
# ===========================================================================

CHECKS_ENABLED = True

if not CHECKS_ENABLED:
    # **The other sheets are DELETED rather than left behind, and that is
    # deliberate.** Each one is placed from ink extents the page-fit check
    # measures, so with the suite off there is nothing to place them from. A
    # stale sheet holding yesterday's content is indistinguishable from a current
    # one; a missing sheet is not. The next full build writes them again.
    _dropped = [p for s in SHEETS if s != AUTHORED
                for p in [sheet_path(ROOT, DATE, s)] if p.exists()]
    for _p in _dropped:
        _p.unlink()
    print()
    print("  " + "=" * 68)
    print("  CHECKS ARE OFF. This diagram was written WITHOUT being validated.")
    print("  Set CHECKS_ENABLED = True and rewrite the suite before trusting it.")
    print(f"  Only the {AUTHORED.slug} sheet was written.")
    for _p in _dropped:
        print(f"  Deleted stale sheet {_p.name}")
    print("  " + "=" * 68)
    raise SystemExit(0)

# ===========================================================================
# THE CHECKS. Re-armed 2026-08-16, rewritten rather than switched back on.
#
# **They were off for one working day** while Terry overhauled the canvas, and
# switching the old set back on would have been useless: nearly every assertion
# named a coordinate the overhaul moved. **So this suite asserts RELATIONSHIPS.**
#
# `docs/architecture/DIAGRAM-NOTES.md` carries the map these are written from --
# semantic pins, load-bearing level runs, shared edges, and the gap rhythm.
# **A number appears below only where the number itself is the rule.**
#
# Every check prints as it goes, so the run is the list.
# ===========================================================================

root = ET.parse(OUT).getroot()
cells = root.findall(".//mxCell")
by_id = {c.get("id"): c for c in cells}

def cell_id(el: ET.Element) -> str:
    """A cell's id. Every cell in THIS document has one, and a missing one is a
    malformed artifact rather than a case to handle."""
    value = el.get("id")
    if value is None:
        raise SystemExit(f"A <{el.tag}> carries no id; the diagram is malformed.")
    return value


def attr_f(el: ET.Element, name: str, default: float | None = None) -> float:
    """One attribute as a float.

    **`Element.get` returns `str | None`, and 22 call sites fed it straight to
    `float()`.** Every one was guarded by an `is not None` test somewhere nearby,
    which is exactly the shape a reader trusts and a type checker cannot follow.
    This makes the contract explicit: absent means malformed unless a default
    says otherwise.
    """
    raw = el.get(name)
    if raw is None:
        if default is None:
            raise SystemExit(f"<{el.tag}> has no {name!r}; the diagram is malformed.")
        return default
    return float(raw)


boxes: dict[str, tuple[float, float, float, float]] = {}
edges: list[ET.Element] = []
waypoints: list[tuple[float, float]] = []
for c in cells:
    g = c.find("mxGeometry")
    if g is None:
        continue
    if c.get("vertex") == "1" and g.get("x") is not None:
        boxes[cell_id(c)] = (
            attr_f(g, "x", 0.0), attr_f(g, "y", 0.0),
            attr_f(g, "width", 0.0), attr_f(g, "height", 0.0),
        )
    elif c.get("edge") == "1":
        edges.append(c)
    waypoints.extend(
        (attr_f(pt, "x"), attr_f(pt, "y"))
        for pt in g.findall(".//mxPoint")
        if pt.get("x") is not None and pt.get("y") is not None
    )

edge_by_id = {e.get("id"): e for e in edges}
problems = 0
EPS = 0.5


def matched(pattern: str, text: str, what: str) -> re.Match[str]:
    """A regex match that MUST succeed, or the artifact is malformed.

    **`re.search` returns `Match | None`, and five call sites reached straight
    for `.group()`.** Each one is genuinely guaranteed by a style string this
    file wrote itself -- which is why nobody guarded them, and why a failure
    would surface as `NoneType has no attribute group` a hundred lines from the
    cause. Naming what was expected turns that into one readable line.
    """
    hit = re.search(pattern, text)
    if hit is None:
        raise SystemExit(f"Expected {what} in: {text[:80]!r}")
    return hit


def note(line: str) -> None:
    print(f"  {line}")


def check(label: str, ok: bool, detail: str = "") -> None:
    """One assertion, one printed line, and the count is the return value."""
    global problems
    if not ok:
        problems += 1
    print(f"    {'ok  ' if ok else 'FAIL'} {label}{('  ' + detail) if detail else ''}")


def left(cid: str) -> float:   return boxes[cid][0]
def top(cid: str) -> float:    return boxes[cid][1]
def width(cid: str) -> float:  return boxes[cid][2]
def height(cid: str) -> float: return boxes[cid][3]
def right(cid: str) -> float:  return boxes[cid][0] + boxes[cid][2]
def bottom(cid: str) -> float: return boxes[cid][1] + boxes[cid][3]
def cx(cid: str) -> float:     return boxes[cid][0] + boxes[cid][2] / 2.0
def cy(cid: str) -> float:     return boxes[cid][1] + boxes[cid][3] / 2.0


# ---------------------------------------------------------------------------
# WHERE AN EDGE ACTUALLY ATTACHES, which is not where its fractions say.
#
# **`exitPerimeter` defaults to 1, and then the fraction is only a DIRECTION.**
# draw.io casts a ray from the shape's center through the point and returns
# where it crosses the bounding RECTANGLE -- `mxRectanglePerimeter`, which knows
# nothing about `arcSize` and nothing about artwork inside a `shape=image` tile.
#
# **Reproducing that here is what makes every geometric check below honest.**
# The old suite used the raw fraction, so it was measuring points draw.io does
# not draw. See DIAGRAM-NOTES, "exitPerimeter=0 is REQUIRED".
# ---------------------------------------------------------------------------


def perimeter_point(bounds: tuple[float, float, float, float], pt: tuple[float, float]) -> tuple[float, float]:
    x, y, w, h = bounds
    ox, oy = x + w / 2.0, y + h / 2.0
    dx, dy = pt[0] - ox, pt[1] - oy
    if dx == 0.0 and dy == 0.0:
        return ox, oy
    if dx == 0.0:
        return ox, oy + (h / 2.0) * (1 if dy > 0 else -1)
    if dy == 0.0:
        return ox + (w / 2.0) * (1 if dx > 0 else -1), oy
    t = min((w / 2.0) / abs(dx), (h / 2.0) / abs(dy))
    return ox + dx * t, oy + dy * t


def endpoint(cid: str, style: str, prefix: str) -> tuple[float, float]:
    bounds = boxes[cid]
    x, y, w, h = bounds
    fx = re.search(rf"(?<!\w){prefix}X=([\d.]+)", style)
    fy = re.search(rf"(?<!\w){prefix}Y=([\d.]+)", style)
    literal = re.search(rf"{prefix}Perimeter=0", style) is not None
    if fx and fy:
        pt = (x + float(fx.group(1)) * w, y + float(fy.group(1)) * h)
        return pt if literal else perimeter_point(bounds, pt)
    return perimeter_point(bounds, (x + w / 2.0, y + h / 2.0))


# **Prove the perimeter model before trusting it**, the same way the collision
# detector below earns its silence. A 100x100 box, a point beyond the top-right
# corner: the ray leaves through the corner exactly.
_pb = (0.0, 0.0, 100.0, 100.0)
_ppt = perimeter_point(_pb, (200.0, 200.0))
if abs(_ppt[0] - 100.0) > 1e-9 or abs(_ppt[1] - 100.0) > 1e-9:
    raise SystemExit(f"SELF-TEST FAILED: perimeter_point corner -> {_ppt}")
_ppt = perimeter_point(_pb, (50.0, -10.0))
if abs(_ppt[0] - 50.0) > 1e-9 or abs(_ppt[1] - 0.0) > 1e-9:
    raise SystemExit(f"SELF-TEST FAILED: perimeter_point straight up -> {_ppt}")

def waypoints_of(e: ET.Element) -> list[tuple[float, float]]:
    """The bend points draw.io routes an edge through, in document order.

    They live in `<Array as="points">` inside the edge's own `<mxGeometry>`.
    An edge with no Array is a straight line and returns an empty list.
    """
    g = e.find("mxGeometry")
    if g is None:
        return []
    return [(attr_f(p, "x"), attr_f(p, "y"))
            for p in g.findall("./Array[@as='points']/mxPoint")]


segments: dict[str, tuple] = {}
# **THE FULL DRAWN PATH, not the chord between its ends.** A routed edge bends
# through its waypoints, and measuring anything against the straight line from
# first point to last describes a line draw.io never draws.
#
# **That hole was real and it hid three correctly placed badges.** `n16`, `n17`
# and `n18` sit dead on `e11`'s horizontal leg at y=1068.5 -- offset 0.00 against
# the path -- while the chord model reported them 205, 227 and 248 units off. A
# check cannot report "the badge is nowhere near its line" about a badge centered
# on it, so the model was wrong rather than the canvas.
paths: dict[str, list[tuple[float, float]]] = {}
for e in edges:
    style = e.get("style") or ""
    src, tgt = e.get("source"), e.get("target")
    if src not in boxes or tgt not in boxes:
        continue          # a floating edge, parked on an explicit sourcePoint
    _p, _q = endpoint(src, style, "exit"), endpoint(tgt, style, "entry")
    segments[cell_id(e)] = (
        src, tgt, _p, _q,
        "orthogonalEdgeStyle" in style,
    )
    paths[cell_id(e)] = [_p, *waypoints_of(e), _q]


def point_to_segment(pt: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(pt[0] - ax, pt[1] - ay)
    t = max(0.0, min(1.0, ((pt[0] - ax) * dx + (pt[1] - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(pt[0] - (ax + t * dx), pt[1] - (ay + t * dy))


def point_to_path(pt: tuple[float, float], path: list[tuple[float, float]]) -> float:
    """Distance to the nearest leg of a polyline."""
    return min(point_to_segment(pt, a, b) for a, b in itertools.pairwise(path))


def path_length(path: list[tuple[float, float]]) -> float:
    return sum(math.dist(a, b) for a, b in itertools.pairwise(path))

# **Prove `point_to_path` can measure a BEND before trusting a zero from it.** A
# straight-line-only implementation returns the chord distance and would report
# 150 here; the L-route's own corner is 50 from the probe point. Validated in both
# directions, because a distance function that always answers 0 passes every
# "the badge is on its line" check ever written.
_lroute = [(0.0, 0.0), (0.0, 200.0), (300.0, 200.0)]
if abs(point_to_path((150.0, 200.0), _lroute)) > 1e-9:
    raise SystemExit("SELF-TEST FAILED: point_to_path missed a point ON the bend leg")
if abs(point_to_path((50.0, 150.0), _lroute) - 50.0) > 1e-9:
    raise SystemExit("SELF-TEST FAILED: point_to_path off-path distance")
if abs(path_length(_lroute) - 500.0) > 1e-9:
    raise SystemExit("SELF-TEST FAILED: path_length")

print()
note("Attachment model:")
check("perimeter_point self-test", True, "2/2")
check("point_to_path self-test", True, "3/3")
check("edges resolved", len(segments) > 0, f"{len(segments)} of {len(edges)}")
_floating = [cell_id(e) for e in edges if cell_id(e) not in segments]
if _floating:
    note(f"    floating (parked on a sourcePoint): {', '.join(_floating)}")



# ---------------------------------------------------------------------------
# Straight edges MUST NOT cut through a box they are not attached to.
#
# Prettier than orthogonal routes, and exactly the defect a human sees instantly
# and a generator never does.
# ---------------------------------------------------------------------------

# Frames, labels, and containers whose own children are legitimate targets.
NOT_OBSTACLES = {
    "cfframe", "netb", "cflogo", "title", "date",
    # The Worker is a CONTAINER of five route tiles. An edge aimed at any of them
    # must cross `api` to arrive, so treating the parent as an obstacle reports a
    # collision for every one of its own children.
    "api",
    "flickrlogo", "flickr", "flickrtitle",
    # Same reasoning: the Lightroom card holds the tiles edges terminate on.
    "lrcapp",
    # Cascade cards behind each Durable Object tile: decoration, and the edge
    # legitimately terminates on the tile stacked in front of them. Both stacks.
    "oauthdo_b1", "oauthdo_b2", "devicedo_b1", "devicedo_b2",
}
# DERIVED, not listed. A hardcoded badge set silently stops covering the badges
# added after it was written, and every new badge then reads as a box its own
# arrow collides with.
NOT_OBSTACLES |= {
    c.get("id") for c in cells if re.fullmatch(r"n\d+", c.get("id") or "")
}


def seg_hits_rect(a: tuple[float, float], b: tuple[float, float], rect: tuple[float, float, float, float], pad: float = 6.0) -> bool:
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
                return False
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


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
    if seg_hits_rect(_a, _b, _box, pad=0.0) != _want:
        raise SystemExit(f"SELF-TEST FAILED: {_name}")

print()
note("Straight edges cross nothing they do not touch:")
check("collision detector self-test", True, f"{len(_cases)}/{len(_cases)}")
_hits = []
for eid, (src, tgt, p, q, routed) in segments.items():
    if routed:
        continue          # waypoints are not modeled here
    for bid, rect in boxes.items():
        if bid in (src, tgt) or bid in NOT_OBSTACLES:
            continue
        if seg_hits_rect(p, q, rect):
            _hits.append(f"{eid} ({src}->{tgt}) crosses {bid}")
for h in _hits:
    note(f"    {h}")
check("no crossings", not _hits, f"{len(segments)} straight edges checked")


# ---------------------------------------------------------------------------
# LEVEL AND PLUMB RUNS. A two-unit drift reads as a mistake, not a change.
#
# **Stated as "this edge is level", never as "this edge is at y=388".** The
# absolute line moved four times on 2026-08-16 and the requirement never did.
# ---------------------------------------------------------------------------

MUST_BE_LEVEL = {
    "e18": "plug-in -> /auth/device-link/start",
    "e24": "plug-in -> /auth/device-link/poll",
    "e13": "plug-in -> /api/v001/*",
    "e23": "browser -> /auth/device-link/approve",
    "e22": "browser -> /auth/flickr/*",
    # **`e3` was retargeted to `devicedo` on 2026-08-17 and this label was not.**
    # It read "OAuth Durable Object" while the arrow pointed at the Device Link one,
    # so the suite described the wrong object in its own output.
    "e3":  "Worker -> Device Link Durable Object",
    "e9":  "Worker -> Flickr API",
    "e10": "Nightly Retry -> Flickr API",
}
MUST_BE_PLUMB = {
    "e4":  "App Secrets Store -> Worker",
    "e5":  "App Secrets Store -> Nightly Retry",
    "e19": "plug-in -> browser",
    "e20": "plug-in -> Catalog",
}
# Edges that must be level WITH EACH OTHER, because they read as one line.
LEVEL_TOGETHER = [
    (("e18", "e3"), "the device-link handshake crosses the canvas as ONE run"),
]

print()
note("Level and plumb runs:")
for eid, why in MUST_BE_LEVEL.items():
    if eid not in segments:
        check(f"{eid} present", False, why)
        continue
    _, _, p, q, _ = segments[eid]
    check(f"{eid:4} level", abs(p[1] - q[1]) < EPS, f"y {p[1]:.1f} -> {q[1]:.1f}   {why}")
for eid, why in MUST_BE_PLUMB.items():
    if eid not in segments:
        check(f"{eid} present", False, why)
        continue
    _, _, p, q, _ = segments[eid]
    check(f"{eid:4} plumb", abs(p[0] - q[0]) < EPS, f"x {p[0]:.1f} -> {q[0]:.1f}   {why}")
for (a, b), why in LEVEL_TOGETHER:
    if a in segments and b in segments:
        ya, yb = segments[a][2][1], segments[b][2][1]
        check(f"{a} and {b} share a line", abs(ya - yb) < EPS, f"{ya:.1f} vs {yb:.1f}   {why}")


# ---------------------------------------------------------------------------
# SHARED EDGES. Break one and the eye sees raggedness before it sees why.
# ---------------------------------------------------------------------------

SHARE_TOP    = [(["cfframe", "lrcapp"], "the two outer cards start together")]
SHARE_BOTTOM = [
    (["cfframe", "flickr"], "the two OUTER boxes share a baseline"),
    (["netb", "flickrapi"], "the two INNER boxes share a baseline"),
]
SHARE_LEFT   = [(["cflogo", "netb"], "the mark and the PoP box share a left edge")]
SHARE_COLUMN = [   # left edge AND width
    (["flickr", "justification"], "the right column is flush"),
    (["flickrlogo", "flickrtitle", "flickrapi"], "the Flickr card's contents"),
    (["dns", "cron"], "the PoP's left column"),
    (["devicedo", "oauthdo", "d1"], "the single-location column"),
    (["apidevice", "apiplugin", "apirest", "apinew", "apioauth", "apilink"],
     "the Worker's route stack"),
]
# **THE REQUIREMENT IS THE AXIS, AND IT NEVER WAS THE WIDTH.** This used to demand
# a shared width as well, which held only while all three tiles happened to be 130
# wide. The browser glyph grew to 183 on 2026-08-17 and the check failed while the
# thing it exists to protect -- `e19` and `e20` hanging plumb down one spine at
# x=121.5 -- was never disturbed.
#
# **A tile is free to be any width as long as its center stays on the spine**, so
# asserting the width was asserting a coincidence of the old layout.
SHARE_AXIS = [
    (["lrcat", "lrc", "users"], "the Lightroom spine keeps e19 and e20 plumb"),
]

print()
note("Shared edges:")
for ids, why in SHARE_TOP:
    vals = [top(i) for i in ids]
    check("top    " + "/".join(ids), max(vals) - min(vals) < EPS, f"{vals[0]:.1f}   {why}")
for ids, why in SHARE_BOTTOM:
    vals = [bottom(i) for i in ids]
    check("bottom " + "/".join(ids), max(vals) - min(vals) < EPS, f"{vals[0]:.1f}   {why}")
for ids, why in SHARE_LEFT:
    vals = [left(i) for i in ids]
    check("left   " + "/".join(ids), max(vals) - min(vals) < EPS, f"{vals[0]:.1f}   {why}")
for ids, why in SHARE_COLUMN:
    ls, ws = [left(i) for i in ids], [width(i) for i in ids]
    check("column " + "/".join(ids),
          max(ls) - min(ls) < EPS and max(ws) - min(ws) < EPS,
          f"x {ls[0]:.1f} w {ws[0]:.1f}   {why}")
for ids, why in SHARE_AXIS:
    axes = [cx(i) for i in ids]
    check("axis   " + "/".join(ids), max(axes) - min(axes) < EPS,
          f"axis {axes[0]:.1f}   widths {', '.join(f'{width(i):.0f}' for i in ids)}   {why}")


# ---------------------------------------------------------------------------
# THE ROUTE STACK'S RHYTHM, and the gap that carries meaning.
#
# Five route tiles in two groups. **The gap between the groups is not spacing --
# it separates what the PLUG-IN calls from what the BROWSER calls**, and the DNS
# tile sits in it.
# ---------------------------------------------------------------------------

PLUGIN_ROUTES  = ["apidevice", "apiplugin", "apirest"]
BROWSER_ROUTES = ["apinew", "apioauth", "apilink"]

print()
note("The Worker's route stack:")
_pitches = []
for group, label in ((PLUGIN_ROUTES, "plug-in"), (BROWSER_ROUTES, "browser")):
    ordered = sorted(group, key=top)
    steps = [top(b) - top(a) for a, b in itertools.pairwise(ordered)]
    _pitches += steps
    check(f"{label:8} group evenly pitched",
          max(steps) - min(steps) < EPS if steps else True,
          f"{', '.join(f'{s:.0f}' for s in steps)}")
check("both groups share one pitch",
      max(_pitches) - min(_pitches) < EPS, f"{_pitches[0]:.0f}")
_gap = min(top(b) for b in BROWSER_ROUTES) - max(bottom(p) for p in PLUGIN_ROUTES)
check("the two groups are separated", _gap > max(_pitches),
      f"{_gap:.1f} between them, against a {_pitches[0]:.0f} pitch inside")
# **DNS's CENTER, not its whole box.** The tile is 60 tall and the separation is
# 46, so demanding containment would be unsatisfiable -- and the claim being made
# is that DNS reads as sitting between the two groups, not that it fits between
# them. An unsatisfiable assertion is worse than none: it fails forever and
# teaches everyone to ignore the output.
_band = (max(bottom(p) for p in PLUGIN_ROUTES), min(top(b) for b in BROWSER_ROUTES))
check("DNS reads as sitting in that separation",
      _band[0] <= cy("dns") <= _band[1],
      f"dns center {cy('dns'):.1f} in {_band[0]:.0f}-{_band[1]:.0f}")


# ---------------------------------------------------------------------------
# THE EDGE PoP'S GAP RHYTHM. Five gaps, one number.
#
# Solved jointly on 2026-08-16 after Terry spotted the dashed edge sitting
# 30.333 from the tile inside it and 25 from the tile outside. **Every number
# here is derived from the others; only their EQUALITY is the rule.**
# ---------------------------------------------------------------------------

print()
note("The Edge PoP's five gaps agree:")
_gaps = {
    "PoP left -> left column":      left("dns") - left("netb"),
    "left column -> Worker column": left("api") - right("dns"),
    "Worker column -> PoP right":   right("netb") - right("api"),
    "PoP right -> Durable Object":  left("oauthdo") - right("netb"),
    "cascade -> Cloudflare frame":  right("cfframe") - right("oauthdo_b2"),
}
for label, g in _gaps.items():
    note(f"    {label:30} {g:6.2f}")
_vals = list(_gaps.values())
check("all five equal", max(_vals) - min(_vals) < EPS, f"spread {max(_vals) - min(_vals):.2f}")


# ---------------------------------------------------------------------------
# WHICH SIDE OF THE DASHED LINE A TILE SITS ON IS A CLAIM, NOT LAYOUT.
#
# A Worker runs at the nearest anycast PoP. A Durable Object and a D1 primary
# each live in exactly one location. Drag a box across that boundary and the
# drawing starts asserting something false.
# ---------------------------------------------------------------------------

IN_EDGE_POP = {
    "dns": True, "cron": True, "api": True, "secrets": True, "retry": True,
    "oauthdo": False, "oauthdo_b1": False, "oauthdo_b2": False,
    # **The SECOND Durable Object stack, and it was missing from this table.** The
    # Device Link object and its two cascade cards were added on 2026-08-17 and this
    # check never learned about them, so the one claim it exists to protect -- a
    # Durable Object lives in exactly ONE location, outside the anycast PoP -- went
    # unmade for the newer of the two stacks.
    "devicedo": False, "devicedo_b1": False, "devicedo_b2": False,
    "d1": False,
}


def contains(outer: str, inner: str) -> bool:
    ox, oy, ow, oh = boxes[outer]
    ix, iy, iw, ih = boxes[inner]
    return ix >= ox and ix + iw <= ox + ow and iy >= oy and iy + ih <= oy + oh


print()
note("Edge-PoP containment:")
for tile, expected in IN_EDGE_POP.items():
    if tile not in boxes:
        check(f"{tile} present", False)
        continue
    inside = contains("netb", tile)
    where = "inside the PoP" if expected else "outside the PoP (single-location)"
    check(f"{tile:11} {where}", inside == expected and contains("cfframe", tile))


# ---------------------------------------------------------------------------
# THE MIDDLE ROW. One height, and centered in its channel.
# ---------------------------------------------------------------------------

MIDDLE_ROW = ["cron", "secrets", "d1"]

print()
note("The middle row:")
_tops, _heights = [top(i) for i in MIDDLE_ROW], [height(i) for i in MIDDLE_ROW]
check("one row", max(_tops) - min(_tops) < EPS and max(_heights) - min(_heights) < EPS,
      f"y {_tops[0]:.1f} h {_heights[0]:.1f}")
_above = min(_tops) - bottom("api")
_below = top("retry") - max(bottom(i) for i in MIDDLE_ROW)
check("centered between the two Workers", abs(_above - _below) < EPS,
      f"{_above:.1f} above, {_below:.1f} below")


# ---------------------------------------------------------------------------
# STEP BADGES. On their line where the run affords it, beside it where it does
# not -- and the threshold is DERIVED from coverage rather than chosen.
# ---------------------------------------------------------------------------

BADGE_ON_LINE = {
    "n2":  "e21", "n3":  "e18", "n5":  "e18", "n6":  "e19", "n7":  "e1",
    "n8":  "e25", "n9":  "e25", "n10": "e22", "n12": "e9",  "n13": "e9",
    "n15": "e22", "n16": "e11", "n17": "e11", "n18": "e11", "n19": "e22",
    # **n21 to n25 were on the canvas and in NO placement table**, so five badges
    # were drawn and never checked. Found 2026-08-17 by counting the tables against
    # the badges the artifact actually holds; every one measures 0.00 from its edge,
    # so they were correct all along and simply unguarded. The coverage check below
    # is what stops the next five.
    "n21": "e9",  "n22": "e9",  "n23": "e14", "n24": "e14", "n25": "e22",
    "n26": "e25", "n27": "e23", "n29": "e24", "n30": "e24", "n32": "e13",
}
# Empty for now. Kept because the beside placement is still the right answer for a
# short run that a badge would otherwise swallow, and BESIDE_MIN/MAX carry its band.
BADGE_BESIDE  = {"n11": "e4"}
# **A THIRD placement, and it is not a fudge.** Step 1 is a click INSIDE the
# plug-in -- it crosses no boundary, so there is no arrow to number and no gap to
# sit beside. A badge tucked into the tile's own corner is the only honest place
# for it. Declared here so the overlap check exempts exactly this pair and keeps
# reporting every other badge that lands on a tile.
BADGE_ON_TILE = {"n1": "lrc", "n4": "devicedo", "n14": "oauthdo", "n20": "oauthdo", "n28": "devicedo", "n31": "lrc"}
BESIDE_MIN, BESIDE_MAX = 10.0, 26.0     # center-to-line, for a 24-unit badge
COVERAGE_CEILING = 0.55


print()
note("Step badges:")

# **EVERY badge MUST be claimed by exactly one placement table.** The three tables
# are hand-written, and a hand-written membership list stops covering new members
# the moment one is added -- silently, because the loops below simply never look at
# a badge nobody listed.
#
# **That is not hypothetical here: `n21` through `n25` were drawn on the canvas and
# appeared in none of the three.** Five badges, unchecked, while every other
# assertion printed `ok`. This derives the roster from the artifact and compares it
# to the tables, so the failure is a named badge rather than a silence.
_placed = {**BADGE_ON_LINE, **BADGE_BESIDE, **BADGE_ON_TILE}
_all_badges = {cell_id(c) for c in cells if re.fullmatch(r"n\d+", c.get("id") or "")}
_unplaced = sorted(_all_badges - set(_placed), key=lambda n: int(n[1:]))
_phantom = sorted(set(_placed) - _all_badges, key=lambda n: int(n[1:]))
_double = sorted(
    {b for b in BADGE_ON_LINE if b in BADGE_BESIDE or b in BADGE_ON_TILE}
    | {b for b in BADGE_BESIDE if b in BADGE_ON_TILE}, key=lambda n: int(n[1:]))
for _b in _unplaced:
    note(f"    {_b} is on the canvas and in no placement table")
for _b in _phantom:
    note(f"    {_b} is in a placement table and not on the canvas")
for _b in _double:
    note(f"    {_b} is claimed by two placement tables")
check("every badge has exactly one placement rule", not (_unplaced or _phantom or _double),
      f"{len(_all_badges)} badges: {len(BADGE_ON_LINE)} on a line, "
      f"{len(BADGE_BESIDE)} beside, {len(BADGE_ON_TILE)} on a tile")

# **A badge check is only as honest as the path it measures against**, so the
# edges the badges sit on MUST be ones this model draws exactly. Two shapes are:
# a straight edge, and an edge routed through explicit waypoints whose every leg
# is level or plumb. `e11` is the second kind and carries three badges.
#
# **The shape that is NOT exact is an `orthogonalEdgeStyle` edge with NO waypoints.**
# draw.io computes the right-angled route itself, so the file holds two points and
# the canvas shows an L -- `e6` is exactly that. Measuring a badge against its chord
# would report a confident distance to a line no reader can see.
#
# It costs nothing today because no badge sits on `e6`. **Stated here rather than
# globally so it fails the moment a badge is placed somewhere the model cannot
# follow**, which is the only time the difference matters.
_unmodeled = []
for _b, _eid in {**BADGE_ON_LINE, **BADGE_BESIDE}.items():
    if _eid not in segments or not segments[_eid][4]:
        continue                      # absent, or straight and therefore exact
    if len(paths[_eid]) == 2:
        _unmodeled.append(f"{_b} sits on {_eid}, which draw.io auto-routes (no waypoints)")
    elif any(abs(a[0] - b[0]) > EPS and abs(a[1] - b[1]) > EPS
             for a, b in itertools.pairwise(paths[_eid])):
        _unmodeled.append(f"{_b} sits on {_eid}, which has a leg that is neither level nor plumb")
for _u in _unmodeled:
    note(f"    {_u}")
check("every badge's edge is exactly modeled", not _unmodeled,
      f"{len(BADGE_ON_LINE) + len(BADGE_BESIDE)} badges on edges")

for badge, eid in BADGE_ON_LINE.items():
    if badge not in boxes or eid not in segments:
        check(f"{badge} on {eid}", False, "missing")
        continue
    path = paths[eid]
    d = point_to_path((cx(badge), cy(badge)), path)
    run = path_length(path)
    cover = width(badge) / run
    check(f"{badge:3} centered ON {eid}", d < EPS, f"offset {d:.2f}")
    check(f"{badge:3} run affords it", cover <= COVERAGE_CEILING,
          f"covers {cover * 100:.0f}% of {run:.0f}")
for badge, eid in BADGE_BESIDE.items():
    if badge not in boxes or eid not in segments:
        check(f"{badge} beside {eid}", False, "missing")
        continue
    _, _, p, q, _ = segments[eid]
    d = point_to_path((cx(badge), cy(badge)), paths[eid])
    along = min(p[1], q[1]) <= cy(badge) <= max(p[1], q[1]) or \
            min(p[0], q[0]) <= cx(badge) <= max(p[0], q[0])
    check(f"{badge:3} beside {eid}", BESIDE_MIN <= d <= BESIDE_MAX and along,
          f"offset {d:.1f}, band {BESIDE_MIN:.0f}-{BESIDE_MAX:.0f}")

BADGES = sorted((cell_id(c) for c in cells if re.fullmatch(r"n\d+", c.get("id") or "")),
                key=lambda n: int(n[1:]))
# **CONTAINERS are excluded, for the same reason they are not obstacles.** A
# badge legitimately sits INSIDE the Lightroom card, beside the arrow it numbers,
# and inside the Worker if one ever labels a route tile's own edge. Listing a
# container here reports an overlap for every badge doing its job correctly.
TILES = ["dns", "secrets", "cron", "oauthdo", "api", "retry", "d1", "users",
         "lrcat", "lrc", "flickrapi", "journey", "key", "justification", "devicedo",
         "apidevice", "apiplugin", "apirest", "apinew", "apioauth", "apilink"]


def overlaps(a: str, b: str) -> bool:
    ax, ay, aw, ah = boxes[a]
    bx, by, bw, bh = boxes[b]
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


_clashes = [(n, t) for n in BADGES for t in TILES
            if t in boxes and overlaps(n, t) and BADGE_ON_TILE.get(n) != t]
for n, t in _clashes:
    note(f"    {n} OVERLAPS {t}")
check("badges clear of every tile", not _clashes, f"{len(BADGES)} badges")
_pairs = [(a, b) for i, a in enumerate(BADGES) for b in BADGES[i + 1:] if overlaps(a, b)]
for a, b in _pairs:
    note(f"    {a} OVERLAPS {b}")
check("badges clear of each other", not _pairs)


# ---------------------------------------------------------------------------
# The badges are a distinct visual language and MUST NOT be confusable with any
# tile. **The white ring is what separates them from the black arrows** -- navy
# against #1A1A1A is 1.47:1 -- so this guards the fill against the TILES only.
#
# **THE WHITE RING IS LOAD-BEARING AND MUST NOT BE REMOVED**, and this threshold
# is only defensible because it exists. Terry spotted it on the canvas, 2026-08-17:
# "man that white border around badges saves 14. The contrast would be tough
# without that white border." He is right, and the numbers say so.
#
#     lrc      #546E7A   105   badge 1 sits ON it
#     oauthdo  #6A3D9A   108   badge 14 sits ON it
#
# **Both clear MIN_COLOR_DISTANCE by under 20, and both carry a badge directly on
# the fill.** The purple case is the worse one: 106 of its 108 is the red channel
# alone, and blue-against-purple is where human color discrimination is weakest.
#
# **So this check does NOT stand on its own.** It measures fill against fill, and
# what actually makes a badge readable on a tile is the ring between them. Drop
# the ring as tidy-up and every number here still passes while three badges become
# unreadable -- the check would report a canvas it can no longer describe.
#
# BADGE_ON_TILE is only a viable placement category for the same reason.
# ---------------------------------------------------------------------------

BADGE_FILL = "#003087"
MIN_COLOR_DISTANCE = 90.0
# The Lightroom mark's ground sits 83 from the badge navy, under the threshold.
# Recorded rather than silently excused: they never appear near each other, and
# the mark is artwork rather than a tile a badge could be mistaken for.
COLOR_EXEMPT = {"lrcmark": "artwork, not a tile; 83 from the badge fill"}


def rgb(hexcolor: str) -> tuple[int, ...]:
    h = hexcolor.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


print()
note("Badge color distinct from every tile fill:")
_badge_rgb = rgb(BADGE_FILL)
for tile in ["dns", "secrets", "cron", "api", "retry", "oauthdo", "devicedo", "d1", "lrc",
             "lrcat", "apidevice", "apiplugin", "apirest", "apinew", "apioauth",
             "apilink"]:
    style = by_id[tile].get("style") or ""
    m = re.search(r"fillColor=(#[0-9A-Fa-f]{6})", style)
    if not m:
        continue
    dist = math.dist(_badge_rgb, rgb(m.group(1)))
    check(f"{tile:11} {m.group(1)}", dist >= MIN_COLOR_DISTANCE, f"distance {dist:.0f}")


# ---------------------------------------------------------------------------
# Boxed text sized by hand is how you get a box that crowds its last line or
# trails 50px of dead space.
#
# **CHANGING EITHER TABLE BELOW INVALIDATES EVERY HAND-SET BOX HEIGHT.** The
# heights are literals chosen against whatever these said at the time, and the
# slack check only catches boxes that are too SMALL -- so a corrected constant
# silently leaves every box sized under the old one wrong, and nothing fails.
# ---------------------------------------------------------------------------

ADVANCE_100 = {
    ' ': 27.783, '!': 27.783, '"': 35.498, '#': 55.615, '$': 55.615, '%': 88.916, '&':
    66.699, "'": 19.092, '(': 33.301, ')': 33.301, '*': 38.916, '+': 58.398, ',':
    27.783, '-': 33.301, '.': 27.783, '/': 27.783, '0': 55.615, '1': 55.615, '2':
    55.615, '3': 55.615, '4': 55.615, '5': 55.615, '6': 55.615, '7': 55.615, '8':
    55.615, '9': 55.615, ':': 27.783, ';': 27.783, '<': 58.398, '=': 58.398, '>':
    58.398, '?': 55.615, '@': 101.514, 'A': 66.699, 'B': 66.699, 'C': 72.217, 'D':
    72.217, 'E': 66.699, 'F': 61.084, 'G': 77.783, 'H': 72.217, 'I': 27.783, 'J': 50,
    'K': 66.699, 'L': 55.615, 'M': 83.301, 'N': 72.217, 'O': 77.783, 'P': 66.699, 'Q':
    77.783, 'R': 72.217, 'S': 66.699, 'T': 61.084, 'U': 72.217, 'V': 66.699, 'W':
    94.385, 'X': 66.699, 'Y': 66.699, 'Z': 61.084, '[': 27.783, '\\': 27.783, ']':
    27.783, '^': 46.924, '_': 55.615, '`': 33.301, 'a': 55.615, 'b': 55.615, 'c': 50,
    'd': 55.615, 'e': 55.615, 'f': 27.783, 'g': 55.615, 'h': 55.615, 'i': 22.217, 'j':
    22.217, 'k': 50, 'l': 22.217, 'm': 83.301, 'n': 55.615, 'o': 55.615, 'p': 55.615,
    'q': 55.615, 'r': 33.301, 's': 50, 't': 27.783, 'u': 55.615, 'v': 50, 'w': 72.217,
    'x': 50, 'y': 50, 'z': 50, '{': 33.398, '|': 25.977, '}': 33.398, '~': 58.398,
}
# Anything outside the table -- an em dash, a middle dot, a non-ASCII glyph -- takes
# the digit width. Every one of them on this canvas sits in a label short enough that
# the fallback cannot decide a wrap.
FALLBACK_ADVANCE = 55.615


# Bold Arial, same measurement, same run. **Bold is not a uniform scale factor** --
# `o` widens 55.615 -> 61.084 while `0` does not move at all -- so it needs its own
# table rather than a multiplier.
ADVANCE_100_BOLD = {
    ' ': 27.783, '!': 33.301, '"': 47.412, '#': 55.615, '$': 55.615, '%': 88.916, '&':
    72.217, "'": 23.779, '(': 33.301, ')': 33.301, '*': 38.916, '+': 58.398, ',':
    27.783, '-': 33.301, '.': 27.783, '/': 27.783, '0': 55.615, '1': 55.615, '2':
    55.615, '3': 55.615, '4': 55.615, '5': 55.615, '6': 55.615, '7': 55.615, '8':
    55.615, '9': 55.615, ':': 33.301, ';': 33.301, '<': 58.398, '=': 58.398, '>':
    58.398, '?': 61.084, '@': 97.51, 'A': 72.217, 'B': 72.217, 'C': 72.217, 'D': 72.217,
    'E': 66.699, 'F': 61.084, 'G': 77.783, 'H': 72.217, 'I': 27.783, 'J': 55.615, 'K':
    72.217, 'L': 61.084, 'M': 83.301, 'N': 72.217, 'O': 77.783, 'P': 66.699, 'Q':
    77.783, 'R': 72.217, 'S': 66.699, 'T': 61.084, 'U': 72.217, 'V': 66.699, 'W':
    94.385, 'X': 66.699, 'Y': 66.699, 'Z': 61.084, '[': 33.301, '\\': 27.783, ']':
    33.301, '^': 58.398, '_': 55.615, '`': 33.301, 'a': 55.615, 'b': 61.084, 'c':
    55.615, 'd': 61.084, 'e': 55.615, 'f': 33.301, 'g': 61.084, 'h': 61.084, 'i':
    27.783, 'j': 27.783, 'k': 55.615, 'l': 27.783, 'm': 88.916, 'n': 61.084, 'o':
    61.084, 'p': 61.084, 'q': 61.084, 'r': 38.916, 's': 55.615, 't': 33.301, 'u':
    61.084, 'v': 55.615, 'w': 77.783, 'x': 55.615, 'y': 55.615, 'z': 50, '{': 38.916,
    '|': 27.979, '}': 38.916, '~': 58.398,
}


def advance(ch: str, bold: bool = False) -> float:
    """One character's advance width at 100px."""
    table = ADVANCE_100_BOLD if bold else ADVANCE_100
    return table.get(ch, FALLBACK_ADVANCE)


def text_w(s: str, size: float, bold: bool = False) -> float:
    """Rendered width of a string, from REAL Arial advance widths.

    **This replaced an average-character-width table, and the average was the last
    big lie in this estimator.** `CHAR_W` charged about 0.508 em for every character,
    so a word of narrow letters -- `list`, `title`, `illicit` -- measured far wider
    than it draws. On the Auth Data Flow panel that invented three whole lines and
    the build refused a panel the render fits comfortably.

    **Advance widths scale linearly with font size**, so one table at 100px covers
    every size including the fractional ones.
    """
    return sum(advance(ch, bold) for ch in s) * size / 100.0


# **Arial's `line-height: normal`, MEASURED rather than assumed.** This was 1.2 for
# months, which is the CSS spec's rough guidance and not what any browser does with
# Arial: (ascent 1854 + descent 434 + lineGap 67) / 2048 unitsPerEm = 1.1499.
# Measured in headless Chrome 2026-08-17 at exactly 1.15.
#
# **The 0.05 looks negligible and is worth 3.5 lines on the Auth Data Flow panel.**
# Across its 62 lines at 12.3px it invented 38 units of height, so the build kept
# refusing row sizes the render had room for. Terry found it by looking at the white
# space under step 32, after this estimator had already been corrected three times.
LINE_HEIGHT = 1.15


def line_h(size: float) -> float:
    """1.2x the font size, matching the browser's line-height:normal.

    **NOT rounded, and the rounding was a real defect once sizes went fractional.**
    An integer line height was harmless while every size was an integer. At
    `font-size:12.2px` the true line box is 14.64 and `round()` charged 15 -- 0.36
    per line, which is 21 units across the Auth Data Flow panel's 59 lines, all of
    it invented.
    """
    return size * LINE_HEIGHT
SLACK_MIN, SLACK_MAX = 12.0, 45.0


def text_lines(raw: str) -> list[str]:
    """One entry per rendered line, each still carrying its own style tag.

    A div is a block element, so its OPENING tag ends the previous line just as
    surely as its closing tag does. Splitting on </div> alone glues a heading
    onto the item below it -- which is how two tiles were measured a full line
    short while reporting a comfortable fit.
    """
    s = re.sub(r"</div>|</tr>|</table>", "", raw)
    s = re.sub(r"<br\s*/?>", "\x00", s)
    s = re.sub(r"(<div[^>]*>|<tr[^>]*>)", "\x00\\1", s)
    parts = s.split("\x00")
    if parts and not re.sub(r"<[^>]*>", "", parts[0]).strip():
        parts.pop(0)
    return parts


def styled_chars(chunk: str) -> list[tuple[str, bool]]:
    """Every visible character of a chunk, paired with whether it renders BOLD.

    **Bold was the last unmodeled term, and it is worth about 50 units here.**
    The Auth Data Flow rows are dense with `<b>` -- `Request Token`, `FGA Session
    ID`, every step number -- and bold Arial is wider glyph for glyph: `o` goes
    from 55.615 to 61.084 per 100px. Measuring the stripped text as regular
    under-counted the panel by roughly three lines.

    **Only `<b>` is tracked**, because that is the only weight this canvas uses. A
    `font-weight:bold` inside a `style` attribute would need span matching and
    would be silently missed -- so it is refused loudly rather than ignored.
    """
    if re.search(r"font-weight:\s*(bold|[6-9]00)", chunk):
        raise SystemExit(
            "text_height models <b> only, and this chunk sets font-weight in CSS: "
            f"{chunk[:80]!r}")
    out: list[tuple[str, bool]] = []
    depth, i = 0, 0
    while i < len(chunk):
        if chunk[i] == "<":
            j = chunk.find(">", i)
            if j == -1:
                break
            tag = chunk[i + 1:j].strip().lower()
            if re.fullmatch(r"b|strong", tag):
                depth += 1
            elif re.fullmatch(r"/b|/strong", tag):
                depth = max(0, depth - 1)
            i = j + 1
            continue
        out.append((chunk[i], depth > 0))
        i += 1
    return out


def wrapped_lines(chars: list[tuple[str, bool]], size: float, usable: float) -> int:
    """Greedy word wrap, the way a browser actually breaks a line.

    Dividing total width by column width assumes text can break anywhere, and it
    cannot. One long unbreakable token ends its line early and wastes the rest.
    Undercounting lines is the dangerous direction, because a box then reports
    slack it does not have.
    """
    words: list[list[tuple[str, bool]]] = []
    current: list[tuple[str, bool]] = []
    for ch, is_bold in chars:
        if ch.isspace():
            if current:
                words.append(current)
                current = []
        else:
            current.append((ch, is_bold))
    if current:
        words.append(current)

    space = text_w(" ", size)
    line_w, lines = 0.0, 1
    for word in words:
        w = sum(advance(ch, is_bold) for ch, is_bold in word) * size / 100.0
        if line_w and line_w + space + w > usable:
            lines += 1
            line_w = w
        else:
            line_w += (space if line_w else 0.0) + w
    return lines


def spacing_of(cid: str) -> tuple[float, float, float]:
    """The tile's own left, right and top insets, READ rather than assumed.

    **draw.io applies a global `spacing` to all four sides and then adds the
    directional ones**, and its default `spacing` is 2. This used to be hardcoded
    at `pad_left=10, pad_right=8` for every tile, which modeled the Auth Data Flow
    panel's text column 6 units wider than it renders -- worth four whole lines
    across 32 rows, every one of them in the direction that reports slack the panel
    does not have.
    """
    style = by_id[cid].get("style") or ""

    def s(name: str, default: float) -> float:
        m = re.search(rf"(?<![\w-]){name}=([\d.]+)", style)
        return float(m.group(1)) if m else default

    base = s("spacing", 2.0)
    return base + s("spacingLeft", 0.0), base + s("spacingRight", 0.0), base + s("spacingTop", 0.0)


def text_height(cid: str) -> float:
    raw = by_id[cid].get("value") or ""
    chunks = text_lines(raw)
    if len(chunks) < 2:
        raise SystemExit(f"Text estimator found no line breaks in '{cid}' -- it would measure blind.")
    pad_left, pad_right, pad_top = spacing_of(cid)
    usable = width(cid) - pad_left - pad_right
    size, total = 12, pad_top
    for chunk in chunks:
        # **Spacing on a nested `<span>` does NOT raise the line box**, so it is
        # stripped before these are counted. The Legend draws its two rule samples
        # as empty inline-block spans carrying `border-bottom`, and charging those
        # 2px per row grew the tile by 4 units of pure modeling artifact -- enough
        # to overrun a column budget that is fixed to the unit.
        #
        # **A block-level tag's spacing is still counted**, which is what the journey
        # header's own `border-bottom` and the table's `margin-top` rely on.
        outside_spans = re.sub(r"<span[^>]*>", "", chunk)
        for prop in ("margin-top", "padding-bottom", "border-bottom"):
            m_css = re.search(rf"{prop}:\s*(\d+)px", outside_spans)
            if m_css:
                total += int(m_css.group(1))
        m = re.search(r"font-size:([\d.]+)px", chunk)
        if m:
            size = float(m.group(1))
        # **A FIXED-WIDTH TABLE CELL IS ITS OWN COLUMN, so its text MUST NOT join
        # the text beside it.** `text_lines` splits on `<tr>` and leaves `</td>`
        # alone, so a two-column row arrives as one chunk and the tags strip to
        # "1DNS query..." -- the row number glued to the first word. The 22px cell
        # was then ALSO subtracted as an indent, counting the number twice.
        #
        # **Measured 2026-08-16 against the render**: narrowing `journey` from 330
        # to 320 changed where 26 lines broke and did not change how many there
        # were, while this estimator reported two extra. It nearly bought the panel
        # 25 units of height it did not need.
        #
        # **AND THE CELL IT DROPS STILL TAKES ITS WIDTH OUT OF THE ROW.** Stripping
        # it without charging for it measured every journey row against the FULL
        # panel width, so the estimator modeled a column 26 units wider than the one
        # the browser lays out -- `width:16px` plus `padding-right:10px`.
        #
        # **That error is invisible and it points the dangerous way.** It under-counts
        # lines, so the panel reports slack it does not have: at `font-size:12.5px` it
        # claimed 23 units spare while the render put steps 31 and 32 outside the box.
        # Measured 2026-08-17 by looking at the picture, which is the only instrument
        # that can see this.
        m_cell = re.search(r"<td[^>]*?width:\s*(\d+)px[^>]*?>", chunk)
        cell_indent = 0
        if m_cell:
            cell_indent = int(m_cell.group(1))
            m_pad = re.search(r"padding-right:\s*(\d+)px", m_cell.group(0))
            if m_pad:
                cell_indent += int(m_pad.group(1))
        chunk = re.sub(r"<td[^>]*width:\s*\d+px[^>]*>.*?</td>", "", chunk)
        text = re.sub(r"<[^>]*>", "", chunk).replace("&nbsp;", " ").strip()
        if not text:
            total += line_h(size)
            continue
        m_ind = re.search(r"margin-left:\s*(\d+)px|width:\s*(\d+)px", chunk)
        indent = cell_indent + (int(next(g for g in m_ind.groups() if g)) if m_ind else 0)
        total += wrapped_lines(styled_chars(chunk), size, usable - indent) * line_h(size)
    return total


# ---------------------------------------------------------------------------
# HOW ACCURATE THIS ESTIMATOR ACTUALLY IS, measured 2026-08-17 rather than hoped.
#
# **It was rebuilt from the ground up that day and it is worth stating the error
# bar, because the old one was out by 110 units and nothing said so.** Four terms
# were wrong at once: an average character width instead of real advances, bold
# ignored, `pad_left`/`pad_right` hardcoded instead of read, and a line height
# rounded to an integer.
#
#     panel           estimator     Chrome     delta
#     journey            896         894        +2
#     justification      128         131        -3
#     key                 94          97        -3
#
# **Within about 3 units on a 900-unit panel. The remaining disagreement is the
# LINE HEIGHT, and it is not resolvable from here.** Arial's `line-height: normal`
# measures exactly 1.15 in Chrome, mxGraph's own `mxConstants.LINE_HEIGHT` is 1.2,
# and the rendered canvas sits between them. **So the last unit belongs to the eye.**
# Terry bracketed the Auth Data Flow row size by looking at three renders: 12.1
# left white space, 12.3 pushed step 32 outside the border, 12.2 is right.
#
# **DO NOT re-tune `JOURNEY_ROW_PX` from this estimator alone.** It is close enough
# to refuse a box that is genuinely too small and too coarse to pick the last tenth.
# ---------------------------------------------------------------------------

print()
note("Boxed text fits its tile:")
_slacks = {}
for cid in ["justification", "key", "journey"]:
    need, have = text_height(cid), height(cid)
    slack = have - need
    _slacks[cid] = slack
    check(f"{cid:14} slack {slack:>5.0f}", SLACK_MIN <= slack <= SLACK_MAX,
          f"box {have:.0f} text ~{need:.0f}")
# Reported, not asserted. These are read side by side, so the eye compares their
# bottom gaps and an outlier looks like a mistake even when each is legal.
note(f"    spread across the three: {max(_slacks.values()) - min(_slacks.values()):.0f}px")


# ---------------------------------------------------------------------------
# The User Journey is a two-column table -- number, then text -- because that is
# the only construction where a wrapped line starts at the same x as the first.
# A rewrite once produced three-cell rows rendering as "11DNS query", and every
# check passed: they all read the flattened text and none looked at the shape.
# ---------------------------------------------------------------------------

_rows = re.findall(r"<tr[^>]*>(.*?)</tr>", by_id["journey"].get("value") or "")
_wrong = [i for i, r in enumerate(_rows, 1) if r.count("<td") != 2]
print()
note("User Journey:")
check("rows are number-plus-text pairs", not _wrong,
      f"{len(_rows)} rows" + (f", WRONG in {_wrong}" if _wrong else ""))
# **ASSERTED AGAIN, because the mismatch it was downgraded for is over.** This was
# reduced to a note while the canvas was scoped to the Lightroom journey and the
# panel still described the browser-first ordering. The panel was rewritten to 32
# plug-in-first steps and the canvas carries 32 badges, so the two agree -- and the
# note went on printing "KNOWN mismatch" over two equal numbers.
#
# **A step and its badge are one decision.** A row with no badge names a hop the
# drawing does not show, and a badge with no row is an arrow nobody explained.
check("every journey row has a badge", len(BADGES) == len(_rows),
      f"{len(BADGES)} badges against {len(_rows)} rows")


# ---------------------------------------------------------------------------
# LOGOS. A squashed mark is a subtle, permanent embarrassment: the only cue is
# that it looks faintly wrong and nobody can say why.
# ---------------------------------------------------------------------------

LOGO_ART = {
    "flickrlogo": "flickr-mark-tight.svg",
    "cflogo": "cloudflare-mark.svg",
    "lrcmark": "lightroom-classic-mark.svg",
}

print()
note("Logos:")
for cid, art in LOGO_ART.items():
    vb = (SVG / art).read_text(encoding="utf-8")
    vw, vh = (float(v) for v in
              matched(r'viewBox="\S+ \S+ (\S+) (\S+)"', vb, "a viewBox").groups())
    skew = abs((width(cid) / height(cid)) - (vw / vh)) / (vw / vh)
    check(f"{cid:11} undistorted", skew <= 0.01,
          f"{width(cid):.0f}x{height(cid):.0f}  {skew * 100:.2f}% off its viewBox")

# The Cloudflare mark is inset equally from the frame's left and top. Unequal
# margins on a corner element read as a mistake, and the eye catches it long
# before it can name it -- so this is an equality, not a band.
check("Cloudflare mark inset equally",
      abs((left("cflogo") - left("cfframe")) - (top("cflogo") - top("cfframe"))) < EPS,
      f"left {left('cflogo') - left('cfframe'):.0f}, top {top('cflogo') - top('cfframe'):.0f}")

# The Flickr mark's three whitespaces match, and it shares its column's inset.
_fl = {"left": left("flickrlogo") - left("flickr"),
       "right": right("flickr") - right("flickrlogo"),
       "top": top("flickrlogo") - top("flickr")}
check("Flickr mark's three margins agree",
      max(_fl.values()) - min(_fl.values()) < EPS,
      ", ".join(f"{k} {v:.0f}" for k, v in _fl.items()))

# **The title MUST sit nearer the mark than the tile below it.** That is the
# whole point of locking it: whichever element it is nearest is the one a reader
# groups it with. **No absolute band** -- the old `LOGO_GAP_MIN/MAX = 6, 8` was
# measured box-to-box, which is one of three terms, and it would have PASSED the
# version Terry rejected and FAILED the one he liked. See DIAGRAM-NOTES.
_to_mark = top("flickrtitle") - bottom("flickrlogo")
_to_tile = top("flickrapi") - bottom("flickrtitle")
check("Flickr title groups upward", _to_mark < _to_tile,
      f"{_to_mark:.1f} to the mark, {_to_tile:.1f} to the tile")


# ---------------------------------------------------------------------------
# The Flickr API tile lists the method names FGA calls, and a name that wraps
# mid-name reads as a typo rather than as a long line. Width is the only thing
# worth asserting here; the height is set by the arrows that must reach it.
# ---------------------------------------------------------------------------

print()
note("Flickr API tile:")
_usable = width("flickrapi") - 18.0
_size, _wide = 20, []
for chunk in text_lines(by_id["flickrapi"].get("value") or ""):
    m = re.search(r"font-size:(\d+)px", chunk)
    if m:
        _size = int(m.group(1))
    t = re.sub(r"<[^>]*>", "", chunk).strip()
    if t and text_w(t, _size) > _usable:
        _wide.append(t)
for t in _wide:
    note(f"    {t!r} too wide")
check(f"every line fits {_usable:.0f}px", not _wide)


# ---------------------------------------------------------------------------
# "Master key" rode an arrow for two commits after the design stopped having
# one. A label naming a secret the tile does not hold describes an older design,
# and it reads as authoritative right up until someone acts on it.
# ---------------------------------------------------------------------------

_entries = [re.sub(r"<[^>]*>", "", s).strip()
            for s in re.split(r"<br\s*/?>", by_id["secrets"].get("value") or "")]
_entries = [e for e in _entries if e]
if len(_entries) < 2:
    raise SystemExit("Worker Secrets tile parsed to fewer than 2 entries -- the check is blind.")
print()
note(f"Worker Secrets arrows name only what the tile holds ({len(_entries) - 1} entries):")
for c in edges:
    if "secrets" not in (c.get("source"), c.get("target")):
        continue
    label = (c.get("value") or "").strip()
    if not label:
        check(f"{c.get('id'):4} unlabeled", True, "reads as 'this Worker reads secrets'")
        continue
    check(f"{c.get('id'):4} {label!r}",
          any(label.lower() in e.lower() for e in _entries))


# ---------------------------------------------------------------------------
# Two line styles remain, and the legend has a row per style written against
# these exact edges. Making one solid does not merely change a line -- it
# orphans a legend entry that then explains nothing.
#
# **A broken style also needs a VISIBLE RUN.** `e6` spent months as a 10-unit
# stub where the arrowhead consumed the whole line, so the legend's dotted row
# pointed at something no reader could tell from solid.
# ---------------------------------------------------------------------------

LINE_STYLE = {"e6": ("dotted", "Nightly Event -> Nightly Retry, a scheduled trigger")}
MIN_VISIBLE_BROKEN_RUN = 60.0

print()
note("Line styles the legend describes:")
for eid, (want, why) in LINE_STYLE.items():
    style = edge_by_id[eid].get("style") or ""
    # draw.io draws dotted as a dashed line with a short dash pattern, so the two
    # broken styles differ only by dashPattern -- "dashed=1" alone passes either.
    got = "dotted" if "dashPattern=" in style else "dashed" if "dashed=1" in style else "solid"
    check(f"{eid:4} is {want}", got == want, f"{got}   {why}")
    if eid in segments:
        _, _, p, q, routed = segments[eid]
        run = math.hypot(q[0] - p[0], q[1] - p[1])
        check(f"{eid:4} run is visible",
              routed or run >= MIN_VISIBLE_BROKEN_RUN,
              "routed, measured by eye" if routed else f"{run:.0f}px")


# ---------------------------------------------------------------------------
# "DO" is banned. Terry is a long-time DigitalOcean customer and the
# abbreviation collides with that in his head at exactly the moment he is
# skimming. Write "Durable Object" every time, however verbose it feels.
# ---------------------------------------------------------------------------

print()
_banned = re.findall(
    r"\bDOs?\b",
    re.sub(r"image=data:image/svg\+xml,[A-Za-z0-9+/=]+", "", OUT.read_text(encoding="utf-8")),
)
note("Naming rules:")
check("no 'DO' abbreviation on the canvas", not _banned,
      f"found {len(_banned)}" if _banned else "")


# ---------------------------------------------------------------------------
# Every line a human reads starts with a capital. A label set that capitalizes
# eleven lines and not the twelfth reads as unfinished, and the eye stops on the
# odd one out exactly when someone is trying to skim.
#
# Two legitimate exceptions, listed explicitly rather than pattern-matched,
# because a clever regex here would silently excuse a real lapse.
# ---------------------------------------------------------------------------

LOWERCASE_OPENERS = {
    "flickrgroupaddr.com": "domain",
    # **Case is not ours to correct in a URL path**, and capitalizing one would
    # print a route that does not exist.
    "/": "URL path prefix",
    "docs/architecture/DECISIONS.md": "path",
    # The Flickr API tile lists the surface FGA calls: method and endpoint names.
    "/oauth/request_token": "OAuth endpoint",
    "/oauth/authorize": "OAuth endpoint",
    "/oauth/access_token": "OAuth endpoint",
    "groups.pools.getGroups": "API method",
    "groups.pools.add": "API method",
    "photos.getAllContexts": "API method",
    # **A measurement opens with its number**, which the standing order calls out
    # explicitly: a digit is the right first character and forcing a capital onto
    # one is the mechanical pass this rule warns about.
    "~15 min TTL": "a measurement, so the digit opens the line",
    "10 min TTL": "a measurement, so the digit opens the line",
}
LOWERCASE_CONTINUATIONS = {
    "per login attempt": "continuation of 'One Durable Object'",
    "per link attempt": "continuation of 'One Durable Object'",
    "pending requests. Stop a queue at": "continuation of 'Attempt to flush every queue with'",
    "its first throttle status": "continuation of the same sentence",
}

_bad_case = []
for c in cells:
    for chunk in re.split(r"<br\s*/?>|</div>", c.get("value") or ""):
        line = re.sub(r"<[^>]*>", "", chunk).replace("&nbsp;", " ").strip()
        if not line or line in LOWERCASE_CONTINUATIONS:
            continue
        if any(line.startswith(tok) for tok in LOWERCASE_OPENERS):
            continue
        first = next((ch for ch in line if ch.isalpha()), None)
        if first and first.islower():
            _bad_case.append((c.get("id"), line[:50]))
for cid, line in _bad_case:
    note(f"    {cid}: {line!r}")
check("every label line starts with a capital", not _bad_case,
      f"{len(_bad_case)} lowercase" if _bad_case else "")


# ---------------------------------------------------------------------------
# THE PAGE, MEASURED IN INK RATHER THAN IN BOXES.
#
# **A geometry is not what the reader sees, and this block is the only place that
# difference is load-bearing.** Three corrections separate the two:
#
#   a stroke straddles its path, so half of `strokeWidth` paints OUTSIDE the box
#   a text box is taller than its letters -- 13.65 for the title alone
#   a routed edge lives in `<mxPoint>`, not in the `<mxGeometry>` of any tile
#
# **All three were wrong here at some point, and each was invisible.** The
# waypoint miss under-reported the height by 45. The box-versus-ink gap put the
# reported top margin at 16.35 while the ink sat on 30. And a stroke has never
# been counted at all until now.
#
# **MARGIN is 30, for a print at a FedEx Office 11x17 color laser.** 0.25in
# clears the 4-5mm unprintable border those engines carry, but not 6mm plus the
# ~1mm of image-placement drift a sheet-fed engine is allowed. 0.30in absorbs
# both and costs 0.1in of a 17in sheet.
#
# **THIS BLOCK FAILS THE BUILD.** The content fits exactly, so there is no slack
# for a driver to absorb an overflow by scaling a percent or two.
# ---------------------------------------------------------------------------

MARGIN = AUTHORED.margin
CAP_HEIGHT, ASCENDER, DESCENDER = 0.716, 0.905, 0.212


def stroke_half(style: str) -> float:
    """How far the ink sits OUTSIDE the geometry, because a stroke is centered.

    An image or a bare text label paints no border at all, so the geometry IS
    the extent. Every tile here names its `strokeColor` explicitly, so an absent
    one means a shape that does not draw a border rather than a defaulted width.
    """
    if "strokeColor=none" in style or "strokeColor=" not in style:
        return 0.0
    m = re.search(r"strokeWidth=([\d.]+)", style)
    return (float(m.group(1)) if m else 1.0) / 2.0


def label_ink_y(cid: str, style: str) -> tuple[float, float]:
    """Cap top and descender bottom of a single-line label, in absolute units.

    **The chain, for `title` at fontSize 28 in a 48-tall box, verticalAlign=middle:**

        line box top   (48 - 28*1.2) / 2                      =  7.200
        ascent top     + half-leading, (33.6 - 1.117*28) / 2  =  1.162
        baseline       + ascender, 0.905 * 28                 = 25.340
        CAP TOP        - cap height, 0.716 * 28               = 13.654 below the box

    **The ratios are Arial's, and Helvetica maps to Arial on this box.** Verified
    two ways on 2026-08-16: Chrome's canvas `TextMetrics` agreed, and the render
    put the title-to-date glyph gap at ~32.8 against this model's 32.96. Chrome
    ROUNDS `TextMetrics` to integers as a fingerprinting mitigation, so reading
    them back gives 13.5 rather than 13.654 -- layout uses the real values, and
    the render measurement is what settles it.
    """
    px = float(matched(r"fontSize=(\d+)", style, "a fontSize").group(1))
    if "verticalAlign=middle" not in style:
        raise SystemExit(f"label_ink_y({cid!r}) models verticalAlign=middle only.")
    line_h = px * 1.2
    half_lead = (line_h - (ASCENDER + DESCENDER) * px) / 2
    baseline = top(cid) + (height(cid) - line_h) / 2 + half_lead + ASCENDER * px
    return baseline - CAP_HEIGHT * px, baseline + DESCENDER * px


# Every extreme carries the id that owns it, because "the drawing is 2 too tall"
# is not actionable and "`lrcapp`'s 3-wide border is" is.
_ink_x, _ink_y = [], []
for _c in cells:
    _cid, _st = _c.get("id"), _c.get("style") or ""
    if _c.get("vertex") != "1" or _cid not in boxes:
        continue
    if _st.startswith("text;"):
        _t, _b = label_ink_y(_cid, _st)
        _ink_y += [(_t, _cid), (_b, _cid)]
        # **X is taken from the BOX for a label, deliberately.** Measuring glyph
        # width needs the text estimator, which this file distrusts. Both labels
        # sit ~940 clear of the right margin, so the box cannot raise a false
        # failure -- if one ever moves outward, measure it instead of trusting this.
        _ink_x += [(left(_cid), _cid), (right(_cid), _cid)]
        continue
    _s = stroke_half(_st)
    _ink_x += [(left(_cid) - _s, _cid), (right(_cid) + _s, _cid)]
    _ink_y += [(top(_cid) - _s, _cid), (bottom(_cid) + _s, _cid)]

for _e in edges:
    _eid, _st = _e.get("id"), _e.get("style") or ""
    _s = stroke_half(_st) or (float(matched(r"strokeWidth=([\d.]+)", _st,
                                            "a strokeWidth").group(1)) / 2
                              if "strokeWidth=" in _st else 0.5)
    _pts = []
    if _eid in segments:
        _pts += [segments[_eid][2], segments[_eid][3]]
    _g = _e.find("mxGeometry")
    if _g is not None:
        _pts += [(attr_f(_p, "x"), attr_f(_p, "y"))
                 for _p in _g.findall(".//mxPoint")
                 if _p.get("x") is not None and _p.get("y") is not None]
    for _x, _y in _pts:
        _ink_x += [(_x - _s, _eid), (_x + _s, _eid)]
        _ink_y += [(_y - _s, _eid), (_y + _s, _eid)]

_x0, _x0id = min(_ink_x)
_x1, _x1id = max(_ink_x)
_y0, _y0id = min(_ink_y)
_y1, _y1id = max(_ink_y)
_pw, _ph = AUTHORED.width - 2 * MARGIN, AUTHORED.height - 2 * MARGIN
CONTENT_W, CONTENT_H = _x1 - _x0, _y1 - _y0

print()
note(f"Page fit, {AUTHORED.slug} with 0.30in margins, measured in INK:")
note(f"    ink x {_x0:.2f} ({_x0id}) to {_x1:.2f} ({_x1id})   width  {CONTENT_W:.2f}")
note(f"    ink y {_y0:.2f} ({_y0id}) to {_y1:.2f} ({_y1id})   height {CONTENT_H:.2f}")
note(f"    printable {_pw:.0f} x {_ph:.0f}")
check("fits 1:1", _pw + EPS >= CONTENT_W and _ph + EPS >= CONTENT_H,
      f"{min(_pw / CONTENT_W, _ph / CONTENT_H) * 100:.1f}%")

for _side, _m, _who in (("left  ", _x0, _x0id), ("right ", AUTHORED.width - _x1, _x1id),
                        ("top   ", _y0, _y0id), ("bottom", AUTHORED.height - _y1, _y1id)):
    check(f"{_side} ink margin >= {MARGIN:.0f}", _m >= MARGIN - EPS, f"{_m:.2f}   set by {_who}")
check("left and right ink margins equal", abs(_x0 - (AUTHORED.width - _x1)) <= EPS,
      f"{_x0:.2f} / {AUTHORED.width - _x1:.2f}")

# **The title is the one element positioned to the margin by hand**, so it gets
# its own assertion rather than relying on it happening to be the topmost thing.
_t_ink, _ = label_ink_y("title", by_id["title"].get("style") or "")
note(f"    title box top {top('title'):.2f}, cap top {_t_ink:.2f}   ink sits {_t_ink - top('title'):.2f} lower")
check("title cap top sits ON the top margin", abs(_t_ink - MARGIN) <= EPS,
      f"{_t_ink:.2f} against {MARGIN:.0f}")
check("the title IS the topmost ink", _y0id == "title", f"topmost is {_y0id}")
note("    export WITHOUT 'Fit to Page' -- it would shrink a drawing that already fits")


# ---------------------------------------------------------------------------
# THE OTHER SHEETS. The same drawing, MOVED -- never resized.
#
# **This runs last because it needs the ink extents the block above measured.**
# Deriving them here would be a second implementation of the ink measurement, and
# two implementations of one measurement drift.
#
# **Each sheet gets one rigid translation and, where the drawing does not fit at
# 1:1, a `pageScale`.** draw.io's page in drawing units is `pageWidth * pageScale`
# by `pageHeight * pageScale`, so a pageScale above 1 is exactly "print this
# drawing smaller than one unit per hundredth of an inch". It keeps the content
# on ONE page in the editor instead of spilling across a 2x2 grid of them.
#
# **THE PAGESCALE FIGURE IS ASSERTED HERE AND HAS NOT BEEN CHECKED AGAINST A REAL
# PRINT.** The mapping of `pageWidth`/`pageHeight` to a paper size is documented
# and certain; how draw.io's export dialog treats `pageScale` is not, and this
# build cannot see a printer. **The print scale is on screen every run** -- if a
# dialog asks, that is the number to type.
#
# **A rigid move is checked, not assumed.** Every absolute point in the written
# sheet MUST differ from the authored one by exactly the same delta, so a
# translation that mangled an edge waypoint or missed a tile fails here rather
# than in a print shop.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# THE COLUMNS, derived from the artifact rather than declared.
#
# **A wider sheet gets its extra width spread evenly between the columns.**
# Terry, 2026-08-17: "evenly space out the columns across the additional x-space
# to use as much of the printable area as we can." Each column keeps its own
# internal geometry exactly; only the gaps between them grow.
#
# **THIS RAISES COVERAGE AND NOT TYPE SIZE, and the distinction is the whole
# arithmetic.** Height binds on both new sheets, so the print scale is
# `printable_height / content_height` and adding width cannot touch it. Legal
# goes from 92.97% of the paper to 100% and stays at 7.7 pt. **Only taking
# HEIGHT out raises the type**, which is a redesign rather than a reflow.
#
# **Text labels are excluded from the derivation, and that is not a detail.**
# The title box runs x 30 to 730 and the date box to 523, so both straddle the
# Lightroom spine and the Cloudflare frame. Counting them merges the first gap
# away -- measured 2026-08-17, the first derivation found three columns.
#
# **STEP BADGES ARE EXCLUDED FOR THE SAME REASON, and they are worse.** A badge on
# a cross-column arrow rides the arrow rather than a column, so on a widened sheet
# it legitimately lands in the gap BETWEEN two columns. Counted as content it then
# invents a column that no tile belongs to -- 16x9 derived five -- or bridges a real
# gap and reports it as having grown by the wrong amount. **A badge is an annotation
# on an edge, never a member of a column.**
# ---------------------------------------------------------------------------

# Any positive threshold works, because a column's own tiles overlap: `cfframe`
# spans its whole column, so the Edge PoP's 28.2-unit internal gaps are already
# covered. The value only has to be smaller than the narrowest real gap.
COLUMN_GAP_MIN = 8.0

# **Four, and the build FAILS if that changes.** A layout edit that splits or
# merges a column changes how the slack is distributed, and it MUST NOT do so
# silently. If this number ever fires, read the printed spans before editing it.
EXPECTED_COLUMNS = 4

def column_spans(tree: ET.Element) -> list[tuple[float, float]]:
    """The vertical bands a drawing occupies, left to right, merged.

    **This runs against the WRITTEN sheets too**, which is what makes the reflow
    checkable rather than merely recomputed. Re-deriving the columns from the
    artifact and comparing widths and gaps is an independent measurement; an
    assertion that replays the writer's own arithmetic proves nothing.
    """
    spans = sorted(
        (attr_f(g, "x"), attr_f(g, "x") + attr_f(g, "width"))
        for c in tree.iter("mxCell")
        for g in [c.find("mxGeometry")]
        if c.get("vertex") == "1" and g is not None and g.get("x") is not None
        and not (c.get("style") or "").startswith("text;")
        and not re.fullmatch(r"n\d+", c.get("id") or ""))
    merged = [list(spans[0])]
    for a, b in spans[1:]:
        if a > merged[-1][1] + COLUMN_GAP_MIN:
            merged.append([a, b])
        else:
            merged[-1][1] = max(merged[-1][1], b)
    return [(m[0], m[1]) for m in merged]


COLUMNS = column_spans(ET.fromstring(TEMPLATE))
GAPS = [COLUMNS[_i + 1][0] - COLUMNS[_i][1] for _i in range(len(COLUMNS) - 1)]

print()
note("Columns, derived from the artifact:")
for _i, (_a, _b) in enumerate(COLUMNS):
    note(f"    col {_i}  {_a:8.2f} -> {_b:8.2f}   width {_b - _a:7.2f}")
    if _i < len(GAPS):
        note(f"    gap   {' ' * 20}{GAPS[_i]:7.2f}")
check(f"{EXPECTED_COLUMNS} columns", len(COLUMNS) == EXPECTED_COLUMNS,
      f"{len(COLUMNS)} found, {len(GAPS)} gaps")


def column_of(x: float) -> int:
    """Which column a coordinate belongs to.

    **The title and its date anchor to the page MARGIN, left of any tile**, so
    they fall outside the first column's span. Clamping puts them in the column
    that never moves, which is what "anchored to the margin" means.
    """
    for i, (a, b) in enumerate(COLUMNS):
        if a - EPS <= x <= b + EPS:
            return i
    if x < COLUMNS[0][0]:
        return 0
    if x > COLUMNS[-1][1]:
        return len(COLUMNS) - 1
    raise SystemExit(f"x={x:.2f} sits in a gap between columns; the reflow cannot place it.")


# **A badge on a cross-column arrow follows the ARROW, not a column.** `n3` and
# `n10` sit on runs from the Browser into the Worker, so widening that gap makes
# their line longer. Shifting them by the mean of the two endpoints' deltas keeps
# each badge at the same fraction along its own arrow. Shifting by its own
# column's delta would leave it on the line and visibly drifted toward one end.
BADGE_EDGE = {**BADGE_ON_LINE, **BADGE_BESIDE}

# **The body size is READ off the canvas, never remembered.** It is the most
# common `fontSize` among the tiles, and 100 drawing units are 1 inch, so a size
# converts to points by 0.72. DIAGRAM-NOTES.md records the calibration: 7.9 pt
# was an eyechart, 12.2 pt was comically huge, and 10.1 pt is the center.
_font_sizes = [int(_m.group(1)) for _c in cells if _c.get("vertex") == "1"
               for _m in [re.search(r"fontSize=(\d+)", _c.get("style") or "")] if _m]
BODY_UNITS = max(set(_font_sizes), key=_font_sizes.count)
BODY_PT = BODY_UNITS * 0.72
EYECHART_PT = 7.9


def fmt(v: float) -> str:
    """A coordinate as short text, so a moved sheet reads like the authored one."""
    return f"{v:.4f}".rstrip("0").rstrip(".") or "0"


def absolute_points(tree: ET.Element) -> list[ET.Element]:
    """Every element in the document whose x and y name an absolute canvas position.

    **`relative="1"` means the number is a FRACTION, and it MUST NOT be moved.**
    `e13` carries `x="0.55"`, which is how far along its own edge the label sits.
    Adding 71.5 to that would put the label three-quarters of a canvas away.
    **This is the same trap as `exitX`/`exitY`** -- draw.io writes fractions and
    absolute units in identically named attributes, and both land close enough to
    read as imprecision rather than as a bug. The first version of this function
    raised on `e13` instead of skipping it, which is how the case was found.

    **A label offset is the other pair that MUST NOT move.** `<mxPoint as="offset">`
    is measured from its own edge. There are none today, and skipping it keeps
    that true when one arrives.

    **A geometry this function cannot classify raises instead of being moved.**
    """
    out = []
    for g in tree.iter("mxGeometry"):
        has = (g.get("x") is not None, g.get("y") is not None)
        if g.get("relative") == "1":
            continue
        if all(has):
            out.append(g)
        elif any(has):
            raise SystemExit("mxGeometry carries only one of x/y; translation is unsafe.")
    for p in tree.iter("mxPoint"):
        if p.get("as") == "offset":
            continue
        if p.get("x") is None or p.get("y") is None:
            raise SystemExit(f"mxPoint as={p.get('as')!r} has no x/y; translation is unsafe.")
        out.append(p)
    return out


def moved_sheet(xml: str, sheet: Sheet, page_scale: float,
                shift: Callable[[str | None, float], float], dy: float) -> str:
    """Write one sheet. `shift` maps a cell id and an x to that point's dx.

    **Y takes one global delta and X does not**, because the reflow is purely
    horizontal: the columns keep every internal distance and only the gaps grow.
    """
    tree = ET.fromstring(xml)
    model = tree.find(".//mxGraphModel")
    if model is None:
        raise SystemExit("The rendered template has no <mxGraphModel>.")
    model.set("pageWidth", fmt(sheet.width))
    model.set("pageHeight", fmt(sheet.height))
    model.set("pageScale", fmt(page_scale))
    owner = {}
    for cell in tree.iter("mxCell"):
        g = cell.find("mxGeometry")
        if g is not None:
            owner[id(g)] = cell.get("id")
        for pt in g.iter("mxPoint") if g is not None else ():
            owner[id(pt)] = cell.get("id")
    for el in absolute_points(tree):
        x = attr_f(el, "x")
        el.set("x", fmt(x + shift(owner.get(id(el)), x)))
        el.set("y", fmt(attr_f(el, "y") + dy))
    return ET.tostring(tree, encoding="unicode") + "\n"


print()
note(f"Sheets. One drawing, {len(SHEETS)} pages, moved but never rescaled:")
_authored_points = absolute_points(ET.fromstring(TEMPLATE))

for _sheet in SHEETS:
    _prw = _sheet.width - 2 * _sheet.margin
    _prh = _sheet.height - 2 * _sheet.margin

    # **Height sets the scale, so it is computed first and width follows.** A
    # horizontal reflow cannot change the height, which is exactly why it cannot
    # change the type size either. `_target_w` is the content width that fills
    # the printable area at that scale.
    _fit_h = min(1.0, _prh / CONTENT_H)
    _target_w = min(_prw / _fit_h, _prw) if _fit_h >= 1.0 else _prw / _fit_h
    # A sheet narrower than the content in proportion is WIDTH-bound. Nothing to
    # spread there -- widening would overflow -- so it falls back to a plain move.
    _extra = max(0.0, _target_w - CONTENT_W)
    _d = _extra / len(GAPS)
    _deltas = [_i * _d for _i in range(len(COLUMNS))]
    _new_w = CONTENT_W + _extra

    _fit = min(_prw / _new_w, _prh / CONTENT_H)
    _pscale = 1.0 if _fit >= 1.0 - 1e-9 else 1.0 / _fit
    _printed = min(1.0, _fit)
    _effw, _effh = _sheet.width * _pscale, _sheet.height * _pscale
    _dx0 = (_effw - _new_w) / 2 - _x0
    _dy = (_effh - CONTENT_H) / 2 - _y0

    # A badge on a cross-column arrow rides the arrow, not a column. See the note
    # beside BADGE_EDGE -- and n14's edge lives inside one column, so it gets 0.
    # **A badge keeps its FRACTION along its own arrow, and the midpoint is only
    # the special case.** The two endpoints belong to different columns and move by
    # different deltas, so the run gets longer and its slope changes. Shifting every
    # badge by the MEAN of the two deltas silently assumes it sits at t=0.5 -- true
    # for most of them here, and false for `n2`, which sits at t=0.60 on `e21` and
    # came off its line by 0.63 on legal and 0.97 on 16x9.
    _badge_dx = {}
    for _b, _eid in BADGE_EDGE.items():
        if _b in boxes and _eid in segments:
            _p, _q = segments[_eid][2], segments[_eid][3]
            _t = 0.5 if abs(_q[0] - _p[0]) < EPS else (cx(_b) - _p[0]) / (_q[0] - _p[0])
            _t = max(0.0, min(1.0, _t))
            _badge_dx[_b] = (_deltas[column_of(_p[0])] * (1 - _t)
                             + _deltas[column_of(_q[0])] * _t)

    def _shift(cid: str | None, x: float, _dx0: float = _dx0,
               _deltas: list[float] = _deltas,
               _badge_dx: dict[str, float] = _badge_dx) -> float:
        return _dx0 + (_badge_dx[cid] if cid in _badge_dx else _deltas[column_of(x)])

    print()
    note(f"  {_sheet.slug:8s} {_sheet.label}")
    if _sheet == AUTHORED:
        check("the authored sheet needs no move", abs(_dx0) <= EPS and abs(_dy) <= EPS
              and _extra <= EPS, f"dx {_dx0:.2f}, dy {_dy:.2f}, spread {_extra:.2f}")
    else:
        _path = sheet_path(ROOT, DATE, _sheet)
        _path.write_text(moved_sheet(TEMPLATE, _sheet, _pscale, _shift, _dy), encoding="utf-8")
        _written = absolute_points(ET.fromstring(_path.read_text(encoding="utf-8")))
        note(f"    wrote {_path.name}")
        note(f"    spread {_extra:.2f} across {len(GAPS)} gaps, {_d:+.2f} each"
             f"   -> {'  '.join(f'{_g + _d:.2f}' for _g in GAPS)}")

        # **The columns are RE-DERIVED from the file just written**, then their
        # widths and gaps are compared to the authored ones. Nothing here replays
        # the writer's arithmetic, so a mis-assigned tile shows up as a column
        # that changed width rather than as an assertion that agrees with itself.
        _got = column_spans(ET.fromstring(_path.read_text(encoding="utf-8")))
        _wid_ok = len(_got) == len(COLUMNS) and all(
            abs((_g[1] - _g[0]) - (_c[1] - _c[0])) <= 1e-3
            for _g, _c in zip(_got, COLUMNS, strict=True))
        check("every column kept its width", _wid_ok,
              f"{len(_got)} columns")
        _got_gaps = [_got[_i + 1][0] - _got[_i][1] for _i in range(len(_got) - 1)]
        check(f"every gap grew by {_d:.2f}",
              len(_got_gaps) == len(GAPS) and all(
                  abs(_n - (_o + _d)) <= 1e-3
                  for _n, _o in zip(_got_gaps, GAPS, strict=True)),
              "  ".join(f"{_g:.2f}" for _g in _got_gaps))
        # Y is untouched by a horizontal reflow, and one uniform delta proves it.
        #
        # **Compare with a TOLERANCE, never by rounding into a set.** The first
        # version did the latter and failed on 8.5x14 alone: its delta is 9.4895,
        # whose 4th decimal is exactly 5, so `round(v, 3)` landed on the tie
        # boundary and float noise sent some points to 9.489 and others to 9.490.
        # The geometry was correct the whole time. 16x9 passed, which made it
        # look like a layout fault rather than an arithmetic one.
        _ys = [attr_f(_q, "y") - attr_f(_p, "y")
               for _p, _q in zip(_authored_points, _written, strict=True)]
        check("nothing moved vertically but the centering",
              all(abs(_v - _dy) <= 1e-3 for _v in _ys),
              f"{len(_written)} points, y all {_dy:+.4f}")

        # **The badges are re-checked against the arrows they now sit on.** The
        # endpoints move with their own tiles, so the shifted run is exact --
        # tiles never resize here and the exit/entry fractions never change.
        for _b, _eid in BADGE_EDGE.items():
            if _b not in boxes or _eid not in segments:
                continue
            # **The WHOLE path moves, waypoints included**, which is what makes this
            # comparable to the authored measurement above. Reading only the two
            # endpoints would re-introduce the chord model on the moved sheets and
            # report three routed badges as drifting by 200-odd units.
            _sp = [(_x + _dx0 + _deltas[column_of(_x)], _y + _dy) for _x, _y in paths[_eid]]
            _bc = (cx(_b) + _dx0 + _badge_dx[_b], cy(_b) + _dy)
            _off = point_to_path(_bc, _sp)
            _was = point_to_path((cx(_b), cy(_b)), paths[_eid])
            check(f"{_b:3} keeps its offset from {_eid}", abs(_off - _was) <= EPS,
                  f"{_was:.2f} -> {_off:.2f}")

    _vx0, _vx1 = _x0 + _dx0, _x1 + _dx0 + _extra
    _vy0, _vy1 = _y0 + _dy, _y1 + _dy
    check("ink centered on its page",
          abs(_vx0 - (_effw - _vx1)) <= EPS and abs(_vy0 - (_effh - _vy1)) <= EPS,
          f"x {_vx0:.2f}/{_effw - _vx1:.2f}   y {_vy0:.2f}/{_effh - _vy1:.2f}")
    _least = min(_vx0, _effw - _vx1, _vy0, _effh - _vy1) * _printed
    check(f"printed margins >= {_sheet.margin:.0f}", _least >= _sheet.margin - EPS,
          f"{_least:.2f} at the tightest side")
    check("the drawing sits on ONE page", _new_w <= _effw + EPS and _effh + EPS >= CONTENT_H,
          f"page {_effw:.1f} x {_effh:.1f} units, pageScale {_pscale:.4f}")

    # **Not a check, because the verdict is Terry's.** The build states the size
    # and names his own measured floor; it does not refuse to write a sheet he
    # asked for. See the three-sheets block at the top of this file.
    _pt = BODY_PT * _printed
    _verdict = (f" -- BELOW the {EYECHART_PT} pt Terry called an eyechart"
                if _pt < EYECHART_PT else "")
    note(f"    prints at {_printed * 100:.1f}%, body type {_pt:.1f} pt{_verdict}")

    # **How much of the paper the drawing actually covers.** The two figures
    # answer different questions and both are worth having: the scale says how
    # small the type gets, and this says how much sheet went unused.
    #
    # **When one dimension binds exactly, this fraction IS the ratio of the two
    # aspect ratios** -- content 1.5769 against legal's printable 1.6962 gives
    # 92.97%, and the arithmetic below reaches the same number the long way.
    # Widening the content toward a sheet's aspect is the only thing that raises
    # it, and on 8.5x14 that buys 3 points of scale rather than a readable print.
    _used = (_new_w * _printed) * (CONTENT_H * _printed) / (_prw * _prh)
    note(f"    covers {_used * 100:.2f}% of the {_prw:.0f} x {_prh:.0f} printable area"
         f"   (content {_new_w / CONTENT_H:.4f} against sheet {_prw / _prh:.4f})")


# ---------------------------------------------------------------------------

print()
if problems:
    raise SystemExit(f"Diagram check FAILED: {problems} problem(s). Fix the layout before committing.")
print(f"  All checks pass. {len(boxes)} tiles, {len(edges)} edges, {len(BADGES)} badges.")
