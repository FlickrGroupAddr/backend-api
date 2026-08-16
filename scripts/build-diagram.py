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
import pathlib

# Dates are versions on this project -- there is no v1/v2 numbering. The
# filename and the title block MUST carry the same date, so both come from this
# one constant. Bump it when the diagram's content changes, and git mv the
# existing file to match before running.
DATE = "2026-08-16"

ROOT = pathlib.Path(__file__).resolve().parent.parent
SVG = ROOT / "docs" / "architecture" / "logos"
OUT = ROOT / "docs" / "architecture" / f"FlickrGroupAddr-Architecture-{DATE}.drawio"


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
# PAGE SIZE: tabloid landscape, 11x17 inches.
#
# **drawio uses 100 units per inch**, so tabloid landscape is 1700 x 1100 and
# US Letter landscape is 1100 x 850.
#
# **Terry printed this on Letter landscape and called it "a fuckin unusable
# eyechart", which the arithmetic agreed with.** The content was 1770 x 1303 units
# then, so fitting it to Letter scaled to 65%. Fitting the same content to tabloid
# scaled to 84%, on a sheet 1.55x larger in each direction -- roughly DOUBLE the
# physical text size. **Those numbers are HISTORY. The content is 1650 x 1030
# today** and the current figures are below.
#
# **DPI DOES NOT APPLY TO A PDF, and the distinction is worth one paragraph.** A
# PDF stores shapes as coordinates and text as glyphs, so it re-renders sharp at
# whatever resolution the viewer or printer asks for. There is no "300 DPI PDF" to
# choose -- a 300 DPI printer draws it at 300, a 1200 DPI one at 1200, and zooming
# in on screen keeps sharpening. **DPI is a raster setting**, and it matters only
# for a PNG or JPG export.
#
# **What decides a PDF is the PAGE SIZE**, which is why these constants are in
# hundredths of an inch and not in dots.
PAGE_WIDTH = 1700  # 17 inches
PAGE_HEIGHT = 1100  # 11 inches

# **THE CONTENT FITS THIS PAGE 1:1, as of 2026-08-16, and it never did before.**
#
#   Printable area  1650 x 1050   (1700 x 1100, less 25 per side)
#   Content         1650 x 1030   x 5 to 1655, y 20 to 1050
#   Scale           100.0%        width binds exactly, height has 20 to spare
#
# **So export WITHOUT "Fit to Page".** That option is now the wrong choice -- it
# would shrink a drawing that already fits. This reverses the instruction that
# stood here from 2026-08-14 to 2026-08-16, when the content was 1770 x 1303 and
# ran 4% over in width and 18% over in height.
#
# **Three separate changes closed that gap**, and none of them was a rescale:
# the step badges came off (badge `n7` used to hang to y=1327, 227 units below the
# page), the Cloudflare frame lost 140 units of height, and the right column
# narrowed from 350 to 330 on 2026-08-16 -- the last 20 units of width.
#
# **Scaling every coordinate to chase a page was always the wrong fix**, and it
# still is. It changes no physical text size -- it moves the shrink out of the
# export dialog and into the file -- while silently invalidating every absolute
# threshold here: the badge band, `CHAR_W`, every hand-set box height. None of
# them would fail. They would stop meaning anything.
#
# **THE MARGIN NOW BINDS, which is the cost of fitting exactly.** At 1650 of 1650
# there is zero slack in width, so a driver cannot absorb an overflow by scaling a
# percent or two. Anything that widens the canvas breaks the 1:1 fit immediately.
# `check_page_fit()` prints the figures on every build.

TEMPLATE = f"""<mxfile host="app.diagrams.net" agent="Claude Code" version="24.0.0">
  <diagram id="fga-architecture" name="FlickrGroupAddr Architecture">
    <mxGraphModel dx="1422" dy="900" grid="0" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{PAGE_WIDTH}" pageHeight="{PAGE_HEIGHT}" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />

        <mxCell id="title" value="FlickrGroupAddr Architecture" style="text;html=1;align=left;verticalAlign=middle;fontSize=28;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="5" y="20" width="700" height="48" as="geometry" />
        </mxCell>
        <mxCell id="date" value="{DATE}" style="text;html=1;align=center;verticalAlign=middle;fontSize=20;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="5" y="56" width="493" height="36" as="geometry" />
        </mxCell>

        <mxCell id="cfframe" value="" style="rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#1A1A1A;strokeWidth=2;" vertex="1" parent="1">
          <mxGeometry x="215" y="110" width="814" height="895" as="geometry" />
        </mxCell>
        <mxCell id="cflogo" value="" style="shape=image;html=1;imageAspect=1;aspect=fixed;image={CF}" vertex="1" parent="1">
          <mxGeometry x="245" y="140" width="242.149" height="80" as="geometry" />
        </mxCell>
        <mxCell id="netb" value="Lowest-Latency Cloudflare Edge PoP (Anycast Routing)" style="rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#F6821F;dashed=1;strokeWidth=2;verticalAlign=top;fontColor=#F6821F;fontStyle=1;fontSize=15;spacingTop=6;" vertex="1" parent="1">
          <mxGeometry x="245" y="250" width="542.6" height="715" as="geometry" />
        </mxCell>

        <mxCell id="lrcapp" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#546E7A;strokeWidth=3;arcSize=6;" vertex="1" parent="1">
          <mxGeometry x="5" y="110" width="180" height="399" as="geometry" />
        </mxCell>
        <mxCell id="lrcmark" value="" style="shape=image;html=1;imageAspect=1;aspect=fixed;image={LRC_MARK}" vertex="1" parent="1">
          <mxGeometry x="63" y="126" width="64" height="62.4" as="geometry" />
        </mxCell>
        <mxCell id="lrc" value="&lt;b&gt;FGA&lt;br&gt;LrC Plugin&lt;/b&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#546E7A;strokeColor=none;fontColor=#FFFFFF;fontSize=14;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="30" y="370" width="130" height="120" as="geometry" />
        </mxCell>
        <mxCell id="lrcat" value="&lt;b&gt;Catalog&lt;/b&gt;&lt;br&gt;&lt;i&gt;Flickr photo IDs&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#607D8B;strokeColor=none;fontColor=#FFFFFF;fontSize=14;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="30" y="218.4" width="130" height="60" as="geometry" />
        </mxCell>
        <mxCell id="users" value="Browser" style="shape=image;html=1;imageAspect=1;aspect=fixed;image={WORKSTATION};fontSize=15;fontStyle=1;labelPosition=center;align=right;verticalLabelPosition=bottom;verticalAlign=top;spacingTop=-6;spacingRight=0;" vertex="1" parent="1">
          <mxGeometry x="30" y="532" width="130" height="104" as="geometry" />
        </mxCell>

        <mxCell id="dns" value="&lt;b&gt;FGA DNS&lt;/b&gt;&lt;br&gt;&lt;i&gt;Cloudflare DNS&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F6821F;strokeColor=none;fontColor=#FFFFFF;fontSize=14;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="273.2" y="483" width="158" height="60" as="geometry" />
        </mxCell>
        <mxCell id="secrets" value="&lt;b&gt;App Secrets Store&lt;/b&gt;&lt;br&gt;&lt;i&gt;Worker Secrets&lt;br&gt;FGA Flickr API credentials&lt;br&gt;Token key (encryption)&lt;br&gt;Session key (signing)&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#6B7280;strokeColor=none;fontColor=#FFFFFF;fontSize=14;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="459.4" y="672.4" width="300" height="111" as="geometry" />
        </mxCell>
        <mxCell id="cron" value="&lt;b&gt;Nightly Event&lt;/b&gt;&lt;br&gt;&lt;i&gt;Workers Cron Trigger&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FBAD41;strokeColor=none;fontColor=#3A2200;fontSize=14;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="273.2" y="672.4" width="158" height="111" as="geometry" />
        </mxCell>

        <mxCell id="oauthdo_b2" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#6A3D9A;strokeColor=#FFFFFF;strokeWidth=2;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="831.8" y="290" width="169" height="155" as="geometry" />
        </mxCell>
        <mxCell id="oauthdo_b1" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#6A3D9A;strokeColor=#FFFFFF;strokeWidth=2;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="823.8" y="298" width="169" height="155" as="geometry" />
        </mxCell>
        <mxCell id="oauthdo" value="&lt;b&gt;OAuth Request Token&lt;/b&gt;&lt;br&gt;&lt;i&gt;One Durable Object&lt;br&gt;per login attempt&lt;br&gt;Self-deletes after ~15 min&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#6A3D9A;strokeColor=#FFFFFF;strokeWidth=2;fontColor=#FFFFFF;fontSize=13;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="815.8" y="306" width="169" height="155" as="geometry" />
        </mxCell>
        <mxCell id="api" value="&lt;b&gt;flickrgroupaddr.com&lt;/b&gt;&lt;div style=&quot;font-size:14px;margin-top:6px&quot;&gt;&lt;i&gt;Single Cloudflare Worker&lt;/i&gt;&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F6821F;strokeColor=none;fontColor=#FFFFFF;fontSize=15;arcSize=12;verticalAlign=top;spacingTop=8;" vertex="1" parent="1">
          <mxGeometry x="459.4" y="306" width="300" height="330" as="geometry" />
        </mxCell>
        <mxCell id="apidevice" value="&lt;b&gt;/auth/device-link/start&lt;/b&gt; API endpoint" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#B85C0A;strokeColor=#FFFFFF;strokeWidth=1;fontColor=#FFFFFF;fontSize=13;arcSize=14;" vertex="1" parent="1">
          <mxGeometry x="479.4" y="370" width="260" height="36" as="geometry" />
        </mxCell>
        <mxCell id="apiplugin" value="&lt;b&gt;/auth/device-link/poll&lt;/b&gt; API endpoint" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#B85C0A;strokeColor=#FFFFFF;strokeWidth=1;fontColor=#FFFFFF;fontSize=13;arcSize=14;" vertex="1" parent="1">
          <mxGeometry x="479.4" y="412" width="260" height="36" as="geometry" />
        </mxCell>
        <mxCell id="apinew" value="&lt;b&gt;/auth/device-link/approve&lt;/b&gt; API endpoint" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#B85C0A;strokeColor=#FFFFFF;strokeWidth=1;fontColor=#FFFFFF;fontSize=13;arcSize=14;" vertex="1" parent="1">
          <mxGeometry x="479.4" y="536" width="260" height="36" as="geometry" />
        </mxCell>
        <mxCell id="apioauth" value="&lt;b&gt;/auth/flickr/*&lt;/b&gt; API endpoints" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#B85C0A;strokeColor=#FFFFFF;strokeWidth=1;fontColor=#FFFFFF;fontSize=13;arcSize=14;" vertex="1" parent="1">
          <mxGeometry x="479.4" y="578" width="260" height="36" as="geometry" />
        </mxCell>
        <mxCell id="apirest" value="&lt;b&gt;/api/v001/*&lt;/b&gt; API endpoints" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#B85C0A;strokeColor=#FFFFFF;strokeWidth=1;fontColor=#FFFFFF;fontSize=13;arcSize=14;" vertex="1" parent="1">
          <mxGeometry x="479.4" y="454" width="260" height="36" as="geometry" />
        </mxCell>
        <mxCell id="retry" value="&lt;b&gt;Nightly Retry Logic&lt;/b&gt;&lt;br&gt;&lt;i&gt;Cloudflare Worker&lt;br&gt;Attempt to flush every queue with&lt;br&gt;pending requests. Stop a queue at&lt;br&gt;its first throttle status&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F6821F;strokeColor=none;fontColor=#FFFFFF;fontSize=15;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="459.4" y="819.8" width="300" height="117" as="geometry" />
        </mxCell>

        <mxCell id="d1" value="&lt;b&gt;SQL Database&lt;/b&gt;&lt;br&gt;&lt;i&gt;Cloudflare D1&lt;br&gt;Users &#183; requests &#183; tokens&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#00A3E0;strokeColor=none;fontColor=#FFFFFF;fontSize=14;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="815.8" y="672.4" width="169" height="111" as="geometry" />
        </mxCell>

        <mxCell id="flickr" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#FF0084;strokeWidth=3;arcSize=6;" vertex="1" parent="1">
          <mxGeometry x="1059" y="306" width="236" height="699" as="geometry" />
        </mxCell>
        <mxCell id="flickrtitle" value="Flickr" style="text;html=1;align=center;verticalAlign=middle;fontSize=20;fontStyle=1;fontColor=#1A1A1A;" vertex="1" parent="1">
          <mxGeometry x="1084" y="422" width="186" height="32" as="geometry" />
        </mxCell>
        <mxCell id="flickrapi" value="&lt;b&gt;Flickr API&lt;/b&gt;&lt;div style=&quot;font-size:14px&quot;&gt;&lt;i&gt;OAuth 1.0a&lt;/i&gt;&lt;/div&gt;&lt;div style=&quot;font-size:15px;border-bottom:2px solid #FFFFFF;display:inline-block;padding-bottom:3px;margin-top:72px&quot;&gt;&lt;b&gt;OAuth Endpoints&lt;/b&gt;&lt;/div&gt;&lt;div style=&quot;font-size:14px;line-height:22px;margin-top:7px&quot;&gt;oauth/request_token&lt;/div&gt;&lt;div style=&quot;font-size:14px;line-height:22px&quot;&gt;oauth/authorize&lt;/div&gt;&lt;div style=&quot;font-size:14px;line-height:22px&quot;&gt;oauth/access_token&lt;/div&gt;&lt;div style=&quot;font-size:15px;border-bottom:2px solid #FFFFFF;display:inline-block;padding-bottom:3px;margin-top:72px&quot;&gt;&lt;b&gt;API Functions&lt;/b&gt;&lt;/div&gt;&lt;div style=&quot;font-size:14px;line-height:22px;margin-top:7px&quot;&gt;groups.pools.getGroups&lt;/div&gt;&lt;div style=&quot;font-size:14px;line-height:22px&quot;&gt;photos.getAllContexts&lt;/div&gt;&lt;div style=&quot;font-size:14px;line-height:22px&quot;&gt;groups.pools.add&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FF0084;strokeColor=none;fontColor=#FFFFFF;fontSize=20;arcSize=8;verticalAlign=top;spacingTop=16;" vertex="1" parent="1">
          <mxGeometry x="1084" y="491" width="186" height="474" as="geometry" />
        </mxCell>
        <mxCell id="flickrlogo" value="" style="shape=image;html=1;imageAspect=1;aspect=fixed;image={FLICKR}" vertex="1" parent="1">
          <mxGeometry x="1084" y="331" width="186" height="88.05" as="geometry" />
        </mxCell>
                <mxCell id="justification" value="&lt;b&gt;Project Justification&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:13px&quot;&gt;Flickr caps how many photos a member may add to a group each day. Doing it by hand means coming back every day for weeks. FGA queues each request and keeps retrying until it lands.&lt;/font&gt;" style="rounded=0;whiteSpace=wrap;html=1;align=left;verticalAlign=top;fillColor=#FFFFFF;strokeColor=#B0B0B0;fontSize=14;spacingLeft=10;spacingTop=8;spacingRight=8;" vertex="1" parent="1">
          <mxGeometry x="1059" y="110" width="236" height="130" as="geometry" />
        </mxCell>

        <mxCell id="key" value="&lt;b&gt;Legend&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:13px&quot;&gt;&#8212;&#8212;&#8212; Request / response&lt;br&gt;&#183; &#183; &#183; &#183; Scheduled trigger&lt;/font&gt;&lt;br&gt;&lt;br&gt;&lt;font style=&quot;font-size:12px&quot;&gt;Why it is built this way:&lt;br&gt;docs/architecture/DECISIONS.md&lt;/font&gt;" style="rounded=0;whiteSpace=wrap;html=1;align=left;verticalAlign=top;fillColor=#FFFFFF;strokeColor=#B0B0B0;fontSize=14;spacingLeft=10;spacingTop=8;" vertex="1" parent="1">
          <mxGeometry x="1325" y="800" width="330" height="126" as="geometry" />
        </mxCell>

        <mxCell id="journey" value="&lt;div style=&quot;font-size:14px;border-bottom:2px solid #1A1A1A;display:inline-block;padding-bottom:3px&quot;&gt;&lt;b&gt;User Journey&lt;/b&gt;&lt;/div&gt;&lt;table cellpadding=&quot;0&quot; cellspacing=&quot;0&quot; style=&quot;margin-top:7px;border-collapse:collapse&quot;&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;1&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;DNS query, resolved at the nearest PoP&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;2&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Static assets served by the same Worker&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;3&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Begin login &#8212; the browser calls the API Worker&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;4&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Worker reads the FGA Flickr API credentials from Worker Secrets&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;5&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Worker signs with them and asks Flickr for a request token&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;6&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Worker stashes the token secret in the OAuth Durable Object&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;7&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;User authorizes FGA&#39;s write access @ Flickr &#8212; HTTP response has HTTP redirect to API OAuth callback&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;8&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Browser follows HTTP redirect instructed by Flickr to OAuth callback, carrying a verifier&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;9&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Worker reads the token secret back out and trades the verifier for the long-lived access token &#8212; the return legs of 5 and 6&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;10&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;REST API endpoints: flickrgroupaddr.com/api/v001/* &#8212; authenticated calls carrying a session cookie&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;11&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Worker calls Flickr as the user &#8212; lists groups, checks pools, adds when clear&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;12&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Lightroom plug-in opens the browser to link itself. It never calls Flickr&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;13&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Lightroom plug-in polls for its token, then queues a batch in one call&lt;/td&gt;&lt;/tr&gt;&lt;/table&gt;" style="rounded=0;whiteSpace=wrap;html=1;align=left;verticalAlign=top;fillColor=#FFFFFF;strokeColor=#003087;strokeWidth=2;fontSize=15;spacingLeft=12;spacingTop=8;spacingRight=10;" vertex="1" parent="1">
          <mxGeometry x="1325" y="110" width="330" height="488" as="geometry" />
        </mxCell>

        <mxCell id="e1" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=0.970692;exitY=0.036635;exitDx=0;exitDy=0;exitPerimeter=0;entryX=0;entryY=0.75;entryDx=0;entryDy=0;entryPerimeter=0;" edge="1" parent="1" source="users" target="dns">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e24" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" edge="1" parent="1" source="lrc" target="apiplugin">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e13" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.85;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" edge="1" parent="1" source="lrc" target="apirest">
          <mxGeometry x="0.55" relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e23" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.211538;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" edge="1" parent="1" source="users" target="apinew">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e22" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.615385;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" edge="1" parent="1" source="users" target="apioauth">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e21" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=0.967554;exitY=0.964850;exitDx=0;exitDy=0;exitPerimeter=0;entryX=0;entryY=0.25;entryDx=0;entryDy=0;entryPerimeter=0;" edge="1" parent="1" source="lrc" target="dns">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e18" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.15;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" edge="1" parent="1" source="lrc" target="apidevice">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e20" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;exitX=0.5;exitY=0;exitDx=0;exitDy=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;" edge="1" parent="1" source="lrc" target="lrcat">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e19" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" edge="1" parent="1" source="lrc" target="users">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e3" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.248485;exitDx=0;exitDy=0;entryX=0;entryY=0.529032;entryDx=0;entryDy=0;" edge="1" parent="1" source="api" target="oauthdo">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e4" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;exitX=0.5;exitY=0;exitDx=0;exitDy=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;" edge="1" parent="1" source="secrets" target="api">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e5" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" edge="1" parent="1" source="secrets" target="retry">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e6" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=classic;endFill=1;strokeWidth=2;dashed=1;dashPattern=1 4;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" edge="1" parent="1" source="cron" target="retry">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e14" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;exitX=0.973207;exitY=0.959612;exitDx=0;exitDy=0;exitPerimeter=0;entryX=0.017598;entryY=0.044423;entryDx=0;entryDy=0;entryPerimeter=0;" edge="1" parent="1" source="api" target="d1">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e15" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;exitX=0.990437;exitY=0.047316;exitDx=0;exitDy=0;exitPerimeter=0;entryX=0.016101;entryY=0.952685;entryDx=0;entryDy=0;entryPerimeter=0;" edge="1" parent="1" source="retry" target="d1">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e9" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.696970;exitDx=0;exitDy=0;entryX=0;entryY=0.094937;entryDx=0;entryDy=0;" edge="1" parent="1" source="api" target="flickrapi">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e10" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.817089;entryDx=0;entryDy=0;" edge="1" parent="1" source="retry" target="flickrapi">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e11" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=0.5;exitY=0.984615;exitDx=0;exitDy=0;exitPerimeter=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;" edge="1" parent="1" source="users" target="flickrapi">
          <mxGeometry relative="1" as="geometry">
            <Array as="points">
              <mxPoint x="95" y="1050" />
              <mxPoint x="1177" y="1050" />
            </Array>
          </mxGeometry>
        </mxCell>

        <mxCell id="n3" value="3" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=17;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="170.5" y="537" width="34" height="34" as="geometry" />
        </mxCell>
        <mxCell id="n10" value="10" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=17;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="170.5" y="579" width="34" height="34" as="geometry" />
        </mxCell>
        <mxCell id="n14" value="14" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=17;fontStyle=1;verticalAlign=middle;" vertex="1" parent="1">
          <mxGeometry x="98" y="307.2" width="34" height="34" as="geometry" />
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
OUT.write_text(TEMPLATE, encoding="utf-8")
print(f"Wrote {OUT}")
print(f"  cloudflare payload : {len(CF)} chars")
print(f"  flickr payload     : {len(FLICKR)} chars")
print(f"  total file         : {OUT.stat().st_size} bytes")

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

import math
import re
import xml.etree.ElementTree as ET

root = ET.parse(OUT).getroot()
cells = root.findall(".//mxCell")
by_id = {c.get("id"): c for c in cells}

boxes: dict[str, tuple[float, float, float, float]] = {}
edges: list[ET.Element] = []
waypoints: list[tuple[float, float]] = []
for c in cells:
    g = c.find("mxGeometry")
    if g is None:
        continue
    if c.get("vertex") == "1" and g.get("x") is not None:
        boxes[c.get("id")] = tuple(
            float(g.get(k, 0)) for k in ("x", "y", "width", "height")
        )
    elif c.get("edge") == "1":
        edges.append(c)
    for pt in g.findall(".//mxPoint"):
        if pt.get("x") is not None and pt.get("y") is not None:
            waypoints.append((float(pt.get("x")), float(pt.get("y"))))

edge_by_id = {e.get("id"): e for e in edges}
problems = 0
EPS = 0.5


def note(line: str) -> None:
    print(f"  {line}")


def check(label: str, ok: bool, detail: str = "") -> None:
    """One assertion, one printed line, and the count is the return value."""
    global problems
    if not ok:
        problems += 1
    print(f"    {'ok  ' if ok else 'FAIL'} {label}{('  ' + detail) if detail else ''}")


def left(cid):   return boxes[cid][0]
def top(cid):    return boxes[cid][1]
def width(cid):  return boxes[cid][2]
def height(cid): return boxes[cid][3]
def right(cid):  return boxes[cid][0] + boxes[cid][2]
def bottom(cid): return boxes[cid][1] + boxes[cid][3]
def cx(cid):     return boxes[cid][0] + boxes[cid][2] / 2.0
def cy(cid):     return boxes[cid][1] + boxes[cid][3] / 2.0


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


def perimeter_point(bounds, pt):
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


def endpoint(cid, style, prefix):
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

segments: dict[str, tuple] = {}
for e in edges:
    style = e.get("style") or ""
    src, tgt = e.get("source"), e.get("target")
    if src not in boxes or tgt not in boxes:
        continue          # a floating edge, parked on an explicit sourcePoint
    segments[e.get("id")] = (
        src, tgt, endpoint(src, style, "exit"), endpoint(tgt, style, "entry"),
        "orthogonalEdgeStyle" in style,
    )

print()
note("Attachment model:")
check("perimeter_point self-test", True, "2/2")
check("edges resolved", len(segments) > 0, f"{len(segments)} of {len(edges)}")
_floating = [e.get("id") for e in edges if e.get("id") not in segments]
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
    # Cascade cards behind the OAuth tile: decoration, and the edge legitimately
    # terminates on the tile stacked in front of them.
    "oauthdo_b1", "oauthdo_b2",
}
# DERIVED, not listed. A hardcoded badge set silently stops covering the badges
# added after it was written, and every new badge then reads as a box its own
# arrow collides with.
NOT_OBSTACLES |= {
    c.get("id") for c in cells if re.fullmatch(r"n\d+", c.get("id") or "")
}


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
    "e3":  "Worker -> OAuth Durable Object",
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
    (["oauthdo", "d1"], "the single-location column"),
    (["apidevice", "apiplugin", "apirest", "apinew", "apioauth"], "the Worker's route stack"),
]
SHARE_WIDTH_AND_AXIS = [
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
for ids, why in SHARE_WIDTH_AND_AXIS:
    ws, axes = [width(i) for i in ids], [cx(i) for i in ids]
    check("axis   " + "/".join(ids),
          max(ws) - min(ws) < EPS and max(axes) - min(axes) < EPS,
          f"w {ws[0]:.1f} axis {axes[0]:.1f}   {why}")


# ---------------------------------------------------------------------------
# THE ROUTE STACK'S RHYTHM, and the gap that carries meaning.
#
# Five route tiles in two groups. **The gap between the groups is not spacing --
# it separates what the PLUG-IN calls from what the BROWSER calls**, and the DNS
# tile sits in it.
# ---------------------------------------------------------------------------

PLUGIN_ROUTES  = ["apidevice", "apiplugin", "apirest"]
BROWSER_ROUTES = ["apinew", "apioauth"]

print()
note("The Worker's route stack:")
_pitches = []
for group, label in ((PLUGIN_ROUTES, "plug-in"), (BROWSER_ROUTES, "browser")):
    ordered = sorted(group, key=top)
    steps = [top(b) - top(a) for a, b in zip(ordered, ordered[1:])]
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
    "d1": False,
}


def contains(outer, inner):
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

BADGE_ON_LINE = {"n3": "e23", "n10": "e22"}
BADGE_BESIDE  = {"n14": "e20"}
BESIDE_MIN, BESIDE_MAX = 14.0, 30.0     # center-to-line, for a 34-unit badge
COVERAGE_CEILING = 0.55


def point_to_segment(pt, a, b):
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(pt[0] - ax, pt[1] - ay)
    t = max(0.0, min(1.0, ((pt[0] - ax) * dx + (pt[1] - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(pt[0] - (ax + t * dx), pt[1] - (ay + t * dy))


print()
note("Step badges:")
for badge, eid in BADGE_ON_LINE.items():
    if badge not in boxes or eid not in segments:
        check(f"{badge} on {eid}", False, "missing")
        continue
    _, _, p, q, _ = segments[eid]
    d = point_to_segment((cx(badge), cy(badge)), p, q)
    run = math.hypot(q[0] - p[0], q[1] - p[1])
    cover = width(badge) / run
    check(f"{badge:3} centered ON {eid}", d < EPS, f"offset {d:.2f}")
    check(f"{badge:3} run affords it", cover <= COVERAGE_CEILING,
          f"covers {cover * 100:.0f}% of {run:.0f}")
for badge, eid in BADGE_BESIDE.items():
    if badge not in boxes or eid not in segments:
        check(f"{badge} beside {eid}", False, "missing")
        continue
    _, _, p, q, _ = segments[eid]
    d = point_to_segment((cx(badge), cy(badge)), p, q)
    along = min(p[1], q[1]) <= cy(badge) <= max(p[1], q[1]) or \
            min(p[0], q[0]) <= cx(badge) <= max(p[0], q[0])
    check(f"{badge:3} beside {eid}", BESIDE_MIN <= d <= BESIDE_MAX and along,
          f"offset {d:.1f}, band {BESIDE_MIN:.0f}-{BESIDE_MAX:.0f}")

BADGES = sorted((c.get("id") for c in cells if re.fullmatch(r"n\d+", c.get("id") or "")),
                key=lambda n: int(n[1:]))
# **CONTAINERS are excluded, for the same reason they are not obstacles.** A
# badge legitimately sits INSIDE the Lightroom card, beside the arrow it numbers,
# and inside the Worker if one ever labels a route tile's own edge. Listing a
# container here reports an overlap for every badge doing its job correctly.
TILES = ["dns", "secrets", "cron", "oauthdo", "api", "retry", "d1", "users",
         "lrcat", "lrc", "flickrapi", "journey", "key", "justification",
         "apidevice", "apiplugin", "apirest", "apinew", "apioauth"]


def overlaps(a, b):
    ax, ay, aw, ah = boxes[a]
    bx, by, bw, bh = boxes[b]
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


_clashes = [(n, t) for n in BADGES for t in TILES if t in boxes and overlaps(n, t)]
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
# ---------------------------------------------------------------------------

BADGE_FILL = "#003087"
MIN_COLOR_DISTANCE = 90.0
# The Lightroom mark's ground sits 83 from the badge navy, under the threshold.
# Recorded rather than silently excused: they never appear near each other, and
# the mark is artwork rather than a tile a badge could be mistaken for.
COLOR_EXEMPT = {"lrcmark": "artwork, not a tile; 83 from the badge fill"}


def rgb(hexcolor):
    h = hexcolor.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


print()
note("Badge color distinct from every tile fill:")
_badge_rgb = rgb(BADGE_FILL)
for tile in ["dns", "secrets", "cron", "api", "retry", "oauthdo", "d1", "lrc",
             "lrcat", "apidevice", "apiplugin", "apirest", "apinew", "apioauth"]:
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

CHAR_W = {40: 20.4, 28: 14.3, 26: 13.3, 20: 11.0, 19: 9.7, 18: 9.2,
          17: 8.7, 16: 8.2, 15: 7.6, 14: 7.1, 13: 6.6, 12: 6.1, 11: 5.6, 10: 5.1}
# 1.2x the font size, which is what a browser renders for line-height:normal.
# The earlier hand-written table drifted between 1.29x and 1.42x, making every
# estimate high -- a box with 90px of visible dead space reported a comfortable
# 30px of slack and passed.
LINE_H = {size: round(size * 1.2) for size in CHAR_W}
# A space is 0.28em against roughly 0.51em for the mixed-case average above.
# Charging a full character per gap compounded into a whole phantom line.
SPACE_W = {size: size * 0.28 for size in CHAR_W}
SLACK_MIN, SLACK_MAX = 12.0, 45.0


def text_lines(raw):
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


def wrapped_lines(text, char_w, usable, space_w):
    """Greedy word wrap, the way a browser actually breaks a line.

    Dividing total width by column width assumes text can break anywhere, and it
    cannot. One long unbreakable token ends its line early and wastes the rest.
    Undercounting lines is the dangerous direction, because a box then reports
    slack it does not have.
    """
    line_w, lines = 0.0, 1
    for word in text.split():
        w = len(word) * char_w
        if line_w and line_w + space_w + w > usable:
            lines += 1
            line_w = w
        else:
            line_w += (space_w if line_w else 0.0) + w
    return lines


def text_height(cid, pad_left=10.0, pad_right=8.0):
    raw = by_id[cid].get("value") or ""
    chunks = text_lines(raw)
    if len(chunks) < 2:
        raise SystemExit(f"Text estimator found no line breaks in '{cid}' -- it would measure blind.")
    usable = width(cid) - pad_left - pad_right
    size, total = 12, 8.0
    for chunk in chunks:
        for prop in ("margin-top", "padding-bottom", "border-bottom"):
            m_css = re.search(rf"{prop}:\s*(\d+)px", chunk)
            if m_css:
                total += int(m_css.group(1))
        m = re.search(r"font-size:(\d+)px", chunk)
        if m:
            size = int(m.group(1))
        text = re.sub(r"<[^>]*>", "", chunk).replace("&nbsp;", " ").strip()
        if not text:
            total += LINE_H[size]
            continue
        m_ind = re.search(r"margin-left:\s*(\d+)px|width:\s*(\d+)px", chunk)
        indent = int(next(g for g in m_ind.groups() if g)) if m_ind else 0
        total += wrapped_lines(text, CHAR_W[size], usable - indent, SPACE_W[size]) * LINE_H[size]
    return total


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
# **NOT asserted against the badge count.** The canvas is scoped to the Lightroom
# journey while the panel still describes the browser-first ordering, so the two
# disagree ON PURPOSE and it is recorded in DIAGRAM-NOTES. Restore the equality
# when the panel is rewritten.
note(f"    {len(BADGES)} badges on the canvas against {len(_rows)} journey rows"
     f" -- KNOWN mismatch, see DIAGRAM-NOTES")


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
    vw, vh = (float(v) for v in re.search(r'viewBox="\S+ \S+ (\S+) (\S+)"', vb).groups())
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
    if t and len(t) * CHAR_W[_size] > _usable:
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
    "oauth/request_token": "OAuth endpoint",
    "oauth/authorize": "OAuth endpoint",
    "oauth/access_token": "OAuth endpoint",
    "groups.pools.getGroups": "API method",
    "groups.pools.add": "API method",
    "photos.getAllContexts": "API method",
}
LOWERCASE_CONTINUATIONS = {
    "per login attempt": "continuation of 'One Durable Object'",
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
# THE PAGE. It fits 11x17 at 100% as of 2026-08-16, and it never did before.
#
# **This now FAILS the build**, where the old version only reported. The content
# was known to exceed the page then, so a failing check would have been scenery
# within a day. It fits exactly now -- 1650 of 1650 -- so there is ZERO slack and
# anything that widens the canvas breaks the 1:1 fit immediately.
#
# **Waypoints are included, and their absence was a real bug.** The old regex
# matched `<mxGeometry>` while a routed run is a pair of `<mxPoint>`, so it
# measured to the lowest TILE and under-reported the height by 45.
# ---------------------------------------------------------------------------

MARGIN = 25.0

print()
note("Page fit, 11x17 with quarter-inch margins:")
_xs = [v for cid in boxes for v in (left(cid), right(cid))] + [p[0] for p in waypoints]
_ys = [v for cid in boxes for v in (top(cid), bottom(cid))] + [p[1] for p in waypoints]
_cw, _ch = max(_xs) - min(_xs), max(_ys) - min(_ys)
_pw, _ph = PAGE_WIDTH - 2 * MARGIN, PAGE_HEIGHT - 2 * MARGIN
note(f"    content   {_cw:.0f} x {_ch:.0f}   bounds x {min(_xs):.0f}-{max(_xs):.0f}, y {min(_ys):.0f}-{max(_ys):.0f}")
note(f"    printable {_pw:.0f} x {_ph:.0f}")
check("fits 1:1", _cw <= _pw and _ch <= _ph,
      f"{min(_pw / _cw, _ph / _ch) * 100:.1f}%")
note("    export WITHOUT 'Fit to Page' -- it would shrink a drawing that already fits")


# ---------------------------------------------------------------------------

print()
if problems:
    raise SystemExit(f"Diagram check FAILED: {problems} problem(s). Fix the layout before committing.")
print(f"  All checks pass. {len(boxes)} tiles, {len(edges)} edges, {len(BADGES)} badges.")
