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

# ---------------------------------------------------------------------------
# PAGE SIZE: tabloid landscape, 11x17 inches.
#
# **drawio uses 100 units per inch**, so tabloid landscape is 1700 x 1100 and
# US Letter landscape is 1100 x 850.
#
# **Terry printed this on Letter landscape and called it "a fuckin unusable
# eyechart", which the arithmetic agrees with.** Measured content is 1770 x 1303
# units, so fitting it to Letter scales to 65%. Fitting the same content to
# tabloid scales to 84%, on a sheet 1.55x larger in each direction -- roughly
# DOUBLE the physical text size.
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

# **THE CONTENT DOES NOT FIT THIS PAGE, and that is stated rather than hidden.**
# Measured content is 1770 x 1303 against 1700 x 1100 -- 4% over in width, 18%
# over in height. `check_page_fit()` prints the overflow on every build.
#
# **So export with "Fit to Page" checked.** That yields a genuine 11x17 PDF
# carrying the whole drawing at about 84%. Exporting without it tiles the drawing
# across four sheets.
#
# **A 1:1 fit needs the canvas relaid out, and that is deferred deliberately.**
# Height is the binding constraint: the Cloudflare frame is 1080 units tall on its
# own, badge `n7` hangs to y=1327 beneath it, and every assertion in this file
# keys off those positions. **Scaling every coordinate and font by 0.84 would
# change no physical text size** -- it moves the same 84% out of the export dialog
# and into the file -- so it buys tidiness rather than legibility.

TEMPLATE = f"""<mxfile host="app.diagrams.net" agent="Claude Code" version="24.0.0">
  <diagram id="fga-architecture" name="FlickrGroupAddr Architecture">
    <mxGraphModel dx="1422" dy="900" grid="0" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{PAGE_WIDTH}" pageHeight="{PAGE_HEIGHT}" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />

        <mxCell id="title" value="FlickrGroupAddr Architecture" style="text;html=1;align=left;verticalAlign=middle;fontSize=28;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="30" y="20" width="700" height="48" as="geometry" />
        </mxCell>
        <mxCell id="date" value="{DATE}" style="text;html=1;align=center;verticalAlign=middle;fontSize=20;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="30" y="56" width="493" height="36" as="geometry" />
        </mxCell>

        <mxCell id="cfframe" value="" style="rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#1A1A1A;strokeWidth=2;" vertex="1" parent="1">
          <mxGeometry x="215" y="110" width="780" height="895" as="geometry" />
        </mxCell>
        <mxCell id="cflogo" value="" style="shape=image;html=1;imageAspect=1;aspect=fixed;image={CF}" vertex="1" parent="1">
          <mxGeometry x="245" y="140" width="242.149" height="80" as="geometry" />
        </mxCell>
        <mxCell id="netb" value="Lowest-Latency Cloudflare Edge PoP (Anycast Routing)" style="rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#F6821F;dashed=1;strokeWidth=2;verticalAlign=top;fontColor=#F6821F;fontStyle=1;fontSize=15;spacingTop=6;" vertex="1" parent="1">
          <mxGeometry x="245" y="250" width="515" height="715" as="geometry" />
        </mxCell>

        <mxCell id="lrcapp" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#546E7A;strokeWidth=3;arcSize=6;" vertex="1" parent="1">
          <mxGeometry x="5" y="110" width="180" height="320" as="geometry" />
        </mxCell>
        <mxCell id="lrctitle" value="Lightroom Classic" style="text;html=1;align=center;verticalAlign=middle;fontSize=16;fontStyle=1;fontColor=#1A1A1A;" vertex="1" parent="1">
          <mxGeometry x="21" y="126" width="148" height="24" as="geometry" />
        </mxCell>
        <mxCell id="lrc" value="&lt;b&gt;FGA plug-in&lt;/b&gt;&lt;br&gt;&lt;i&gt;Lua&lt;br&gt;All we add&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#546E7A;strokeColor=none;fontColor=#FFFFFF;fontSize=14;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="30" y="306" width="130" height="105" as="geometry" />
        </mxCell>
        <mxCell id="lrcat" value="&lt;b&gt;Catalog&lt;/b&gt;&lt;br&gt;&lt;i&gt;Flickr photo IDs&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#607D8B;strokeColor=none;fontColor=#FFFFFF;fontSize=14;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="30" y="180" width="130" height="60" as="geometry" />
        </mxCell>
        <mxCell id="users" value="Browser" style="shape=image;html=1;imageAspect=1;aspect=fixed;image={WORKSTATION};fontSize=15;fontStyle=1;labelPosition=center;align=right;verticalLabelPosition=bottom;verticalAlign=top;spacingTop=-6;spacingRight=-30;" vertex="1" parent="1">
          <mxGeometry x="30" y="490" width="130" height="104" as="geometry" />
        </mxCell>

        <mxCell id="dns" value="&lt;b&gt;FGA DNS&lt;/b&gt;&lt;br&gt;&lt;i&gt;Cloudflare DNS&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F6821F;strokeColor=none;fontColor=#FFFFFF;fontSize=14;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="275" y="432.5" width="120" height="36" as="geometry" />
        </mxCell>
        <mxCell id="secrets" value="&lt;b&gt;App Secrets Store&lt;/b&gt;&lt;br&gt;&lt;i&gt;Worker Secrets&lt;br&gt;FGA Flickr API credentials&lt;br&gt;Token key (encryption)&lt;br&gt;Session key (signing)&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#6B7280;strokeColor=none;fontColor=#FFFFFF;fontSize=14;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="430" y="610" width="300" height="150" as="geometry" />
        </mxCell>
        <mxCell id="cron" value="&lt;b&gt;Nightly Event Trigger&lt;/b&gt;&lt;br&gt;&lt;i&gt;Workers Cron Trigger&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FBAD41;strokeColor=none;fontColor=#3A2200;fontSize=14;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="250" y="810" width="170" height="100" as="geometry" />
        </mxCell>

        <mxCell id="oauthdo_b2" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#6A3D9A;strokeColor=#FFFFFF;strokeWidth=2;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="801" y="290" width="169" height="155" as="geometry" />
        </mxCell>
        <mxCell id="oauthdo_b1" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#6A3D9A;strokeColor=#FFFFFF;strokeWidth=2;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="793" y="298" width="169" height="155" as="geometry" />
        </mxCell>
        <mxCell id="oauthdo" value="&lt;b&gt;OAuth Request Token&lt;/b&gt;&lt;br&gt;&lt;i&gt;One Durable Object&lt;br&gt;per login attempt&lt;br&gt;Self-deletes after ~15 min&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#6A3D9A;strokeColor=#FFFFFF;strokeWidth=2;fontColor=#FFFFFF;fontSize=13;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="785" y="306" width="169" height="155" as="geometry" />
        </mxCell>
        <mxCell id="api" value="&lt;b&gt;flickrgroupaddr.com&lt;/b&gt;&lt;div style=&quot;font-size:14px;margin-top:6px&quot;&gt;&lt;i&gt;Single Cloudflare Worker&lt;/i&gt;&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F6821F;strokeColor=none;fontColor=#FFFFFF;fontSize=15;arcSize=12;verticalAlign=top;spacingTop=8;" vertex="1" parent="1">
          <mxGeometry x="430" y="306" width="300" height="274" as="geometry" />
        </mxCell>
        <mxCell id="apidevice" value="&lt;b&gt;/device&lt;/b&gt; REST API endpoint" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#B85C0A;strokeColor=#FFFFFF;strokeWidth=1;fontColor=#FFFFFF;fontSize=13;arcSize=14;" vertex="1" parent="1">
          <mxGeometry x="450" y="370" width="260" height="36" as="geometry" />
        </mxCell>
        <mxCell id="apioauth" value="&lt;b&gt;/oauth&lt;/b&gt; REST API endpoint" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#B85C0A;strokeColor=#FFFFFF;strokeWidth=1;fontColor=#FFFFFF;fontSize=13;arcSize=14;" vertex="1" parent="1">
          <mxGeometry x="450" y="494" width="260" height="36" as="geometry" />
        </mxCell>
        <mxCell id="apirest" value="&lt;b&gt;/api&lt;/b&gt; REST API endpoints" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#B85C0A;strokeColor=#FFFFFF;strokeWidth=1;fontColor=#FFFFFF;fontSize=13;arcSize=14;" vertex="1" parent="1">
          <mxGeometry x="450" y="536" width="260" height="36" as="geometry" />
        </mxCell>
        <mxCell id="retry" value="&lt;b&gt;Nightly Retry Logic&lt;/b&gt;&lt;br&gt;&lt;i&gt;Cloudflare Worker&lt;br&gt;Attempt to flush every queue with&lt;br&gt;pending requests. Stop a queue at&lt;br&gt;its first throttle status&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F6821F;strokeColor=none;fontColor=#FFFFFF;fontSize=15;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="430" y="790" width="300" height="140" as="geometry" />
        </mxCell>

        <mxCell id="d1" value="&lt;b&gt;SQL Database&lt;/b&gt;&lt;br&gt;&lt;i&gt;Cloudflare D1&lt;br&gt;Users &#183; requests &#183; tokens&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#00A3E0;strokeColor=none;fontColor=#FFFFFF;fontSize=14;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="785" y="610" width="169" height="130" as="geometry" />
        </mxCell>

        <mxCell id="flickr" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#FF0084;strokeWidth=3;arcSize=6;" vertex="1" parent="1">
          <mxGeometry x="1025" y="306" width="270" height="624" as="geometry" />
        </mxCell>
        <mxCell id="flickrtitle" value="Flickr" style="text;html=1;align=center;verticalAlign=middle;fontSize=20;fontStyle=1;fontColor=#1A1A1A;" vertex="1" parent="1">
          <mxGeometry x="1047" y="443" width="226" height="32" as="geometry" />
        </mxCell>
        <mxCell id="flickrapi" value="&lt;b&gt;Flickr API&lt;/b&gt;&lt;div style=&quot;font-size:14px&quot;&gt;&lt;i&gt;OAuth 1.0a&lt;/i&gt;&lt;/div&gt;&lt;div style=&quot;font-size:15px;border-bottom:2px solid #FFFFFF;display:inline-block;padding-bottom:3px;margin-top:60px&quot;&gt;&lt;b&gt;OAuth Endpoints&lt;/b&gt;&lt;/div&gt;&lt;div style=&quot;font-size:12px;line-height:13px;margin-top:7px&quot;&gt;oauth/request_token&lt;/div&gt;&lt;div style=&quot;font-size:12px;line-height:13px&quot;&gt;oauth/authorize&lt;/div&gt;&lt;div style=&quot;font-size:12px;line-height:13px&quot;&gt;oauth/access_token&lt;/div&gt;&lt;div style=&quot;font-size:15px;border-bottom:2px solid #FFFFFF;display:inline-block;padding-bottom:3px;margin-top:30px&quot;&gt;&lt;b&gt;API Functions&lt;/b&gt;&lt;/div&gt;&lt;div style=&quot;font-size:12px;line-height:13px;margin-top:7px&quot;&gt;groups.pools.getGroups&lt;/div&gt;&lt;div style=&quot;font-size:12px;line-height:13px&quot;&gt;photos.getAllContexts&lt;/div&gt;&lt;div style=&quot;font-size:12px;line-height:13px&quot;&gt;groups.pools.add&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FF0084;strokeColor=none;fontColor=#FFFFFF;fontSize=20;arcSize=8;verticalAlign=top;spacingTop=16;" vertex="1" parent="1">
          <mxGeometry x="1047" y="510" width="226" height="398" as="geometry" />
        </mxCell>
        <mxCell id="flickrlogo" value="" style="shape=image;html=1;imageAspect=1;aspect=fixed;image={FLICKR}" vertex="1" parent="1">
          <mxGeometry x="1047" y="328" width="226" height="107" as="geometry" />
        </mxCell>
                <mxCell id="justification" value="&lt;b&gt;Project Justification&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:13px&quot;&gt;Flickr caps how many photos a member may add to a group each day. Doing it by hand means coming back every day for weeks. FGA queues each request and keeps retrying until it lands.&lt;/font&gt;" style="rounded=0;whiteSpace=wrap;html=1;align=left;verticalAlign=top;fillColor=#FFFFFF;strokeColor=#B0B0B0;fontSize=14;spacingLeft=10;spacingTop=8;spacingRight=8;" vertex="1" parent="1">
          <mxGeometry x="1025" y="110" width="270" height="130" as="geometry" />
        </mxCell>

        <mxCell id="key" value="&lt;b&gt;Legend&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:13px&quot;&gt;&#8212;&#8212;&#8212; Request / response&lt;br&gt;&#183; &#183; &#183; &#183; Scheduled trigger&lt;/font&gt;&lt;br&gt;&lt;br&gt;&lt;font style=&quot;font-size:12px&quot;&gt;Why it is built this way:&lt;br&gt;docs/architecture/DECISIONS.md&lt;/font&gt;" style="rounded=0;whiteSpace=wrap;html=1;align=left;verticalAlign=top;fillColor=#FFFFFF;strokeColor=#B0B0B0;fontSize=14;spacingLeft=10;spacingTop=8;" vertex="1" parent="1">
          <mxGeometry x="1325" y="800" width="350" height="126" as="geometry" />
        </mxCell>

        <mxCell id="journey" value="&lt;div style=&quot;font-size:14px;border-bottom:2px solid #1A1A1A;display:inline-block;padding-bottom:3px&quot;&gt;&lt;b&gt;User Journey&lt;/b&gt;&lt;/div&gt;&lt;table cellpadding=&quot;0&quot; cellspacing=&quot;0&quot; style=&quot;margin-top:7px;border-collapse:collapse&quot;&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;1&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;DNS query, resolved at the nearest PoP&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;2&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Static assets served by the same Worker&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;3&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Begin login &#8212; the browser calls the API Worker&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;4&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Worker reads the FGA Flickr API credentials from Worker Secrets&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;5&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Worker signs with them and asks Flickr for a request token&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;6&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Worker stashes the token secret in the OAuth Durable Object&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;7&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;User authorizes FGA&#39;s write access @ Flickr &#8212; HTTP response has HTTP redirect to API OAuth callback&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;8&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Browser follows HTTP redirect instructed by Flickr to OAuth callback, carrying a verifier&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;9&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Worker reads the token secret back out and trades the verifier for the long-lived access token &#8212; the return legs of 5 and 6&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;10&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;REST API endpoints: flickrgroupaddr.com/api/v001/* &#8212; authenticated calls carrying a session cookie&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;11&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Worker calls Flickr as the user &#8212; lists groups, checks pools, adds when clear&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;12&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Lightroom plug-in opens the browser to link itself. It never calls Flickr&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td style=&quot;width:22px;vertical-align:top;font-size:13px&quot;&gt;&lt;b&gt;13&lt;/b&gt;&lt;/td&gt;&lt;td style=&quot;vertical-align:top;font-size:13px&quot;&gt;Lightroom plug-in polls for its token, then queues a batch in one call&lt;/td&gt;&lt;/tr&gt;&lt;/table&gt;" style="rounded=0;whiteSpace=wrap;html=1;align=left;verticalAlign=top;fillColor=#FFFFFF;strokeColor=#003087;strokeWidth=2;fontSize=15;spacingLeft=12;spacingTop=8;spacingRight=10;" vertex="1" parent="1">
          <mxGeometry x="1325" y="110" width="350" height="488" as="geometry" />
        </mxCell>

        <mxCell id="e1" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=0.970692;exitY=0.036635;exitDx=0;exitDy=0;exitPerimeter=0;entryX=0.010583;entryY=0.964722;entryDx=0;entryDy=0;entryPerimeter=0;" edge="1" parent="1" source="users" target="dns">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e13" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.615385;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" edge="1" parent="1" source="users" target="apirest">
          <mxGeometry x="0.55" relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e22" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.211538;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" edge="1" parent="1" source="users" target="apioauth">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e21" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=0.971615;exitY=0.964857;exitDx=0;exitDy=0;exitPerimeter=0;entryX=0.010583;entryY=0.035278;entryDx=0;entryDy=0;entryPerimeter=0;" edge="1" parent="1" source="lrc" target="dns">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e18" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.780952;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" edge="1" parent="1" source="lrc" target="apidevice">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e20" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;exitX=0.5;exitY=0;exitDx=0;exitDy=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;" edge="1" parent="1" source="lrc" target="lrcat">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e19" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" edge="1" parent="1" source="lrc" target="users">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e3" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.299270;exitDx=0;exitDy=0;entryX=0;entryY=0.529032;entryDx=0;entryDy=0;" edge="1" parent="1" source="api" target="oauthdo">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e4" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;exitX=0.5;exitY=0;exitDx=0;exitDy=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;" edge="1" parent="1" source="secrets" target="api">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e5" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" edge="1" parent="1" source="secrets" target="retry">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e6" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;strokeWidth=2;dashed=1;dashPattern=1 4;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" edge="1" parent="1" source="cron" target="retry">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e14" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;exitX=0.977733;exitY=0.952518;exitDx=0;exitDy=0;exitPerimeter=0;entryX=0.018757;entryY=0.047462;entryDx=0;entryDy=0;entryPerimeter=0;" edge="1" parent="1" source="api" target="d1">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e15" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;exitX=0.984733;exitY=0.037714;exitDx=0;exitDy=0;exitPerimeter=0;entryX=0.025148;entryY=0.962308;entryDx=0;entryDy=0;entryPerimeter=0;" edge="1" parent="1" source="retry" target="d1">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e9" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.839416;exitDx=0;exitDy=0;entryX=0;entryY=0.065327;entryDx=0;entryDy=0;" edge="1" parent="1" source="api" target="flickrapi">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e10" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.879397;entryDx=0;entryDy=0;" edge="1" parent="1" source="retry" target="flickrapi">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e11" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=14;labelBackgroundColor=#FFFFFF;exitX=0.5;exitY=0.984615;exitDx=0;exitDy=0;exitPerimeter=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;" edge="1" parent="1" source="users" target="flickrapi">
          <mxGeometry relative="1" as="geometry">
            <Array as="points">
              <mxPoint x="95" y="1050" />
              <mxPoint x="1160" y="1050" />
            </Array>
          </mxGeometry>
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


# ---------------------------------------------------------------------------
# EVERY CHECK BELOW THIS LINE IS OFF, deliberately and temporarily.
#
# Terry, 2026-08-16: the canvas is being overhauled and he is reviewing every
# render by eye, so the assertions block iteration instead of protecting it.
# Nearly all of them are pinned to coordinates the overhaul is about to move, and
# a check that fires on every intermediate state is a check nobody reads.
#
# **This is ONE flag, not a thousand commented lines, on purpose.** Restoring the
# gate is a single word, so the restoration cannot be half-done -- and a partly
# uncommented block would look restored while leaving holes.
#
# **`CLAUDE.md` says this build "refuses to write a diagram that fails any
# assertion". That is FALSE while this flag is False.** The banner below prints on
# every single run so the state cannot go unnoticed. Flip the flag back to True
# when the overhaul settles, then run and fix whatever it reports.
CHECKS_ENABLED = False

if not CHECKS_ENABLED:
    print()
    print("  ####################################################################")
    print("  #  GEOMETRY AND QUALITY CHECKS ARE DISABLED                        #")
    print("  #  Set CHECKS_ENABLED = True in scripts/build-diagram.py to restore #")
    print("  ####################################################################")
    raise SystemExit(0)


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
    "cfframe", "netb", "cflogo", "title", "date",
    # **The Worker tile became a CONTAINER on 2026-08-16** and holds three inner
    # route tiles. An edge aimed at `apidevice`, `apioauth` or `apirest` must cross
    # `api` to reach it, so treating the parent as an obstacle reports a collision
    # for every one of its own children. Same reasoning as the Flickr card above.
    "api",
    "flickrlogo", "flickr", "flickrtitle",
    # The Lightroom Classic card is a CONTAINER, exactly like the Flickr card
    # above it: edges legitimately terminate on the tiles stacked inside it, and
    # the outer frame is not a thing an arrow can collide with.
    "lrcapp", "lrctitle",
    # Cascade cards behind the OAuth tile: decoration showing there are many,
    # and the edge legitimately terminates on the tile stacked in front of them.
    "oauthdo_b1", "oauthdo_b2",
}

root = ET.parse(OUT).getroot()
cells = root.findall(".//mxCell")

# Step badges sit ON their arrows by design, so they are never obstacles.
#
# DERIVED, not listed. This was a hardcoded "n1".."n11" set, which silently
# stopped covering the badges the moment n12 and n13 were added -- every new
# badge then read as a box its own arrow collided with. Two other places in this
# file made the same mistake with the same fix, which is the argument for
# deriving anything that counts badges.
NOT_OBSTACLES |= {
    c.get("id") for c in cells if re.fullmatch(r"n\d+", c.get("id") or "")
}

boxes, edges = {}, []
for c in cells:
    g = c.find("mxGeometry")
    if c.get("vertex") == "1" and g is not None and g.get("x") is not None:
        boxes[c.get("id")] = tuple(float(g.get(k, 0)) for k in ("x", "y", "width", "height"))
    elif c.get("edge") == "1":
        edges.append(c)


def attach_point(box, style, prefix):
    """Fixed exitX/entryX if the style pins one, otherwise the box center."""
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
    "e13": "browser -> api (one channel, steps 2/3/8/10)",
    "e6": "cron -> retry",
    "e9": "api -> flickr (one arrow, steps 5/9/11)",
    "e10": "retry -> flickr",
    # Added 2026-08-16 at Terry's direction. **The plug-in's call and the Worker's
    # Durable Object write are ONE horizontal run** at y=388.5, so a reader follows
    # the device-link handshake straight across the canvas. Both attachment
    # fractions are chosen to land on that y, and a later box move silently breaks
    # that -- which is exactly what this check exists to catch.
    "e18": "plug-in -> api (the device-link call)",
    "e3": "api -> oauth Durable Object",
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
# not the center-to-center distance, which is what makes short hops deceptive.
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


# Which side of the edge-PoP boundary a tile sits on is now a CLAIM, not layout:
# Workers run at the nearest anycast PoP, while a Durable Object and a D1 primary
# each live in exactly one location. Drag a box across that line and the diagram
# starts asserting something false, so the build checks it.
# Components only. The legend is diagram furniture -- its position claims nothing
# about where code runs, so it is deliberately not asserted here.
IN_EDGE_POP = {
    "dns": True,  # authoritative DNS is anycast, answered at the nearest PoP
    "secrets": True, "cron": True, "api": True, "retry": True,
    "oauthdo": False,   # single Durable Object instance, not edge-replicated
    "d1": False,        # D1 lives in one location; every query crosses to it
}


def contains(outer, inner):
    ox, oy, ow, oh = outer
    ix, iy, iw, ih = inner
    return ix >= ox and ix + iw <= ox + ow and iy >= oy and iy + ih <= oy + oh


print("  edge-PoP containment:")
for tile, expected in IN_EDGE_POP.items():
    if tile not in boxes:
        raise SystemExit(f"Containment check names '{tile}', which is not in the diagram.")
    actually_in_pop = contains(boxes["netb"], boxes[tile])
    in_cloudflare = contains(boxes["cfframe"], boxes[tile])
    ok = actually_in_pop == expected and in_cloudflare
    where = "inside PoP" if expected else "outside PoP (single-location)"
    print(f"    {tile:9} {where:30} {'ok' if ok else 'WRONG SIDE'}")
    if not ok:
        problems += 1


# THE OPEN CHANNEL, and the diamond it makes. Settled 2026-08-13, and asserted
# THE DIAMOND IS RETIRED, and this note replaces it rather than deleting it.
#
# The old shape put the two Workers in one column with an open channel between
# them and D1 inside that channel. Terry approved it by eye -- "I like it as is,
# the diamond shape works for me" -- so it earned a check.
#
# On 2026-08-15 he replaced the arrangement: *"probably can vertically stack DNS,   DIRTY-WORDS-EXEMPT: quoting Terry
# API, App Secrets Store, and Nightly Retry logic into one vertical chain over on
# left"*. A four-tile chain fills that channel by definition, so the check could
# not survive the layout that superseded it. **The person who made the call is
# the person who overrode it**, which is the only way an aesthetic assertion
# should ever be removed.
#
# What the diamond was FOR still holds, and the chain check plus the PoP
# containment check together carry it: D1 sits outside the edge PoP, and both
# Workers reach across to it. That was always the meaning; the empty channel was
# one way of drawing it.
CHAIN = ["api", "secrets", "retry"]
columns = {boxes[t][0] for t in CHAIN}
print("  The request chain shares one column:")
for t in CHAIN:
    x, y, _, h = boxes[t]
    print(f"    {t:9} x {x:.0f}  y {y:.0f} -> {y + h:.0f}")
if len(columns) != 1:
    print(f"    -> NOT one column: {sorted(columns)}")
    problems += 1
else:
    print("    -> aligned")


# The right-hand column is deliberately flush: legend, Flickr tile, and the note
# beneath it share a left edge and a width. Ragged edges there read as sloppiness
# rather than as meaning, and a resize elsewhere is what would quietly break it.
RIGHT_COLUMN = ["justification", "flickr"]
lefts = {t: boxes[t][0] for t in RIGHT_COLUMN}
widths = {t: boxes[t][2] for t in RIGHT_COLUMN}
aligned = len(set(lefts.values())) == 1 and len(set(widths.values())) == 1
print("  right column flush:")
for t in RIGHT_COLUMN:
    print(f"    {t:9} x {lefts[t]:.0f}-{lefts[t]+widths[t]:.0f}  width {widths[t]:.0f}")
print(f"    -> {'aligned' if aligned else 'RAGGED'}")
if not aligned:
    problems += 1

# The column is also evenly spaced. Flickr's top and bottom are pinned to the API
# and Retry Workers so its two arrows stay level, so it cannot move -- the tiles
# above it absorb any change, and uneven gaps are the visible symptom.
stacked = sorted(RIGHT_COLUMN, key=lambda t: boxes[t][1])
gaps = [
    boxes[b][1] - (boxes[a][1] + boxes[a][3])
    for a, b in zip(stacked, stacked[1:])
]
even = max(gaps) - min(gaps) <= 1.0
print("  right column evenly spaced:")
for (a, b), g in zip(zip(stacked, stacked[1:]), gaps):
    print(f"    {a} -> {b}: {g:.0f}px")
print(f"    -> {'even' if even else f'UNEVEN, spread {max(gaps)-min(gaps):.0f}px'}")
if not even:
    problems += 1


# Each step badge sits just CLEAR of the arrow it numbers -- near enough to be
# obviously attached, far enough not to mask the line. Both bounds matter: too
# far and it reads as an unrelated blob, too near and it is back to hiding the
# arrow it is meant to annotate. Nothing else would catch either, since badges
# are excluded from the collision check by design.
BADGE_ON_EDGE: dict[str, str] = {}
_RETIRED_BADGE_ON_EDGE = {
    "n1": "e1",    # browser -> Cloudflare DNS
    "n13": "e18",  # Lightroom plug-in -> the Worker, its only network edge
    "n2": "e13",   # browser -> Worker, the app shell (Workers static assets)
    "n3": "e13",   # browser -> Worker, begin login
    "n4": "e4",    # Worker Secrets -> API Worker, read the FGA credentials
    "n6": "e3",    # API Worker <-> OAuth Durable Object, stash the secret (read back on return)
    # The OAuth callback. It rides the users-to-Worker channel because that is
    # literally what it is: Flickr answers the authorize page with a redirect, and
    # the BROWSER then makes a fresh request to the Worker's callback route. There
    # is no Flickr-to-Worker arrow on this canvas because there is no such call,
    # and drawing one would say the endpoint receives a trusted server-to-server
    # request when it actually receives an untrusted GET whose token and verifier
    # sit in a URL the user can read and edit.
    "n8": "e13",   # browser -> Worker, the OAuth callback
    "n10": "e13",  # browser -> Worker, authenticated calls
    # The Lightroom Classic client. Two edges, and the pair is the whole point:
    # the plug-in LAUNCHES a browser and it CALLS the API, and those are
    # different kinds of thing. Only the second is a network request.
    "n12": "e19",  # Lightroom plug-in -> browser, to link itself
    # Steps 5 and 9 get parallel arrows for the same reason steps 3 and 8 do:
    # they are separate conversations that happen at different points, and one
    # shared line made the second invisible. e9 is the login leg, e17 everything
    # afterwards.
}
NEAR_MIN, NEAR_MAX = 24.0, 32.0   # badge radius is 23; 24 clears the line by a hair, 32 still reads as attached


def point_to_segment(pt, a, b):
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(pt[0] - ax, pt[1] - ay)
    t = max(0.0, min(1.0, ((pt[0] - ax) * dx + (pt[1] - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(pt[0] - (ax + t * dx), pt[1] - (ay + t * dy))


print("  step badges hug their arrows without covering them:")
for badge, eid in BADGE_ON_EDGE.items():
    bx, by, bw, bh = boxes[badge]
    center = (bx + bw / 2, by + bh / 2)
    _, _, p, q = segments[eid]
    d = point_to_segment(center, p, q)
    if d < NEAR_MIN:
        verdict = "TOO CLOSE, masks the line"
    elif d > NEAR_MAX:
        verdict = "ADRIFT from its line"
    else:
        verdict = "ok"
    print(f"    {badge} beside {eid:4} offset {d:>5.1f}px  {verdict}")
    if verdict != "ok":
        problems += 1

# Three arrows are ROUTED rather than drawn straight, and the straight-edge
# machinery above cannot model a waypoint. Each one's long leg is horizontal, so
# the badge is checked against that run instead: the right distance from it, and
# somewhere along it rather than past either end.
#
# **They are routed because a straight line between their endpoints reads as a
# slash across the canvas.** Terry, 2026-08-15, on the Lightroom arrow before it
# was routed: *"look at the arrow from the plugin to FGA API"*.   DIRTY-WORDS-EXEMPT: quoting Terry
# A diagonal that cuts the Cloudflare frame, the PoP boundary and two columns on
# its way says nothing about what it connects. An L-shaped route down a gutter
# and along a channel says "this client reaches that Worker", which is the fact.
ROUTED_RUNS: dict[str, tuple] = {}
_RETIRED_ROUTED_RUNS = {
    # badge: (edge, run y, run x from, run x to)
    "n7": ("e11", 1080.0, 57.0, 1160.0),   # browser -> Flickr, the authorize detour
}
for badge, (eid, run_y, run_x0, run_x1) in ROUTED_RUNS.items():
    bx, by, bw, bh = boxes[badge]
    bc = (bx + bw / 2, by + bh / 2)
    off = abs(bc[1] - run_y)
    on_run = NEAR_MIN <= off <= NEAR_MAX and run_x0 <= bc[0] <= run_x1
    print(f"    {badge} beside {eid:4} offset {off:>5.1f}px  "
          f"{'ok' if on_run else 'BADLY PLACED'}")
    if not on_run:
        problems += 1

# n7 is gone with the rest of the badges.


# n7 rides a long horizontal run, so nothing about the arrow decides where along
# it the badge sits. It used to be pinned to the center of App Secrets Store,
# which was true of a layout that has since been replaced twice. ROUTED_RUNS
# above already keeps it on the line and between the ends; the exact x along a
# 1,000px run is not a thing a reader can check, so nothing asserts it now.


# Several badges can share one arrow, and when they do the eye reads them as a
# row rather than as separate marks. So the row is centered on the arrow's axis,
# sits level, and is evenly spaced. Equalities, not bands, for the same reason as
# n7 above: the alignment either reads or it does not.
#
# **The browser reaches the Worker over ONE channel, not three.** Steps 2, 3, 8
# and 10 are four things that happen on one HTTPS connection to one origin, and
# drawing them as three near-parallel arrows out of a small tile produced a
# starburst with numbers scattered through it. Terry, 2026-08-15, looking at the
# render: *"the horrific mess of arrows and badges between browser and FGA"*.   DIRTY-WORDS-EXEMPT: quoting Terry
# One channel carrying four numbers says the same thing and reads at a glance.
# **The axis is the ARROW they label, not a tile.** The first version named `dns`
# and `d1`, which was true only for one arrangement: when the Worker moved into the
# DNS column on 2026-08-15, the arrow ended exactly where the badges were required
# to sit, and the two rules became unsatisfiable together. **An assertion pinned to
# a coordinate outlives the layout that made it true**; one pinned to the thing it
# is actually about does not.
BADGE_GROUPS: dict[str, list] = {}
_RETIRED_BADGE_GROUPS = {
    "e13": ["n2", "n3", "n8", "n10"],   # every browser-to-Worker step
    "e9": ["n5", "n9", "n11"],          # every Worker-to-Flickr call, one arrow
}
by_id = {c.get("id"): c for c in cells}
for edge, members in BADGE_GROUPS.items():
    cell = next(e for e in edges if e.get("id") == edge)
    style = cell.get("style") or ""
    ax, _ = attach_point(boxes[cell.get("source")], style, "exit")
    bx, _ = attach_point(boxes[cell.get("target")], style, "entry")
    axis = (ax + bx) / 2
    centers = sorted(boxes[m][0] + 23 for m in members)
    group_mid = (centers[0] + centers[-1]) / 2
    level = max(boxes[m][1] for m in members) - min(boxes[m][1] for m in members) <= 0.5
    gaps = [round(b - a, 1) for a, b in zip(centers, centers[1:])]
    even = max(gaps) - min(gaps) <= 0.5 if len(gaps) > 1 else True
    print(f"    {edge} carries {len(members)} badges: centered {group_mid:.1f} vs "
          f"{axis:.1f}, {'level' if level else 'NOT LEVEL'}, "
          f"{'evenly spaced' if even else 'UNEVEN ' + str(gaps)}")
    if abs(group_mid - axis) > 0.5 or not level or not even:
        problems += 1


# A badged arrow MUST carry no text label. Both a badge and an edge label default
# to the arrow's midpoint, so adding one buries the other -- which is exactly how
# the first badged version shipped unreadable. The descriptions live in the
# "User journey" key instead, where they have room to be sentences.
print("  badged arrows carry no competing label:")
for badge, eid in list(BADGE_ON_EDGE.items()):
    label = (edge_by_id[eid].get("value") or "").strip()
    clean = "clear" if not label else f"HAS LABEL {label!r}"
    print(f"    {eid:4} ({badge}) {clean}")
    if label:
        problems += 1


# The step badges are a distinct visual language and MUST NOT be confusable with
# any tile. The OAuth Durable Object was originally #0051C3 against badges at
# 68 units apart in RGB, close enough to read as the same thing at a glance.
BADGE_FILL = "#003087"
MIN_COLOR_DISTANCE = 90.0


def rgb(hexcolor):
    h = hexcolor.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


badge_rgb = rgb(BADGE_FILL)
print("  badge color distinct from tile fills:")
for tile in ["dns", "secrets", "cron", "api", "retry", "oauthdo", "d1", "lrc", "lrcat"]:
    style = next(c.get("style") for c in cells if c.get("id") == tile)
    fill = re.search(r"fillColor=(#[0-9A-Fa-f]{6})", style).group(1)
    dist = math.dist(badge_rgb, rgb(fill))
    verdict = "ok" if dist >= MIN_COLOR_DISTANCE else "TOO CLOSE TO BADGE BLUE"
    print(f"    {tile:9} {fill}  distance {dist:>5.0f}  {verdict}")
    if dist < MIN_COLOR_DISTANCE:
        problems += 1


# Boxed text tiles are sized by hand, and by hand is how you get a box that
# either crowds its last line or trails 50px of dead space. This estimates the
# wrapped text height and keeps the slack inside a band.
# CHANGING EITHER TABLE BELOW INVALIDATES EVERY HAND-SET BOX HEIGHT ON THE CANVAS.
# The heights are literals in the template, chosen against whatever these values
# said at the time. Correct a constant and every box sized under the old one is
# now wrong by the size of the error -- and nothing fails, because the slack check
# only catches boxes that are too SMALL. That is exactly how justification and the
# legend ended up 14px loose after the line heights were fixed: not a bad box, a
# stale one. After touching these, re-run and re-tighten every tile in the boxed
# text check below.
CHAR_W = {40: 20.4, 28: 14.3, 26: 13.3, 20: 11.0, 19: 9.7, 18: 9.2,
          17: 8.7, 16: 8.2, 15: 7.6, 14: 7.1, 13: 6.6, 12: 6.1, 11: 5.6, 10: 5.1}
# Line heights are 1.2x the font size, which is what a browser renders for
# line-height:normal and what draw.io therefore produces. The earlier table was
# hand-written per size and drifted between 1.29x and 1.42x, which made every
# estimate high -- the journey box measured 310px against roughly 248px of real
# text, so a box with 90px of visible dead space reported a comfortable 30px of
# slack and passed. An estimator that is wrong in the generous direction is worse
# than none, because it certifies the thing it should be catching.
LINE_H = {size: round(size * 1.2) for size in CHAR_W}
# A space is far narrower than an average character -- 0.28em in Helvetica and
# Arial against roughly 0.51em for the mixed-case average above. Charging a full
# character per gap sounds harmless and is not: the journey's longest step carries
# 29 spaces, so the error compounded into a whole phantom line and the box was
# sized for text that was never going to be there.
SPACE_W = {size: size * 0.28 for size in CHAR_W}
SLACK_MIN, SLACK_MAX = 12.0, 45.0
# KNOWN GAP, measured 2026-08-13 against a render: a heading set as an
# inline-block reads about 10px short here. An inline-block sits on a line box
# taller than its own content -- the surrounding block's strut adds descender
# space beneath it -- and that is not modelled. So a tile whose heading is styled
# that way carries roughly 10px MORE text than reported, and its true slack is
# about 10px LESS. The journey is the only such tile today and it is sized from
# the render rather than the estimate. Anything below about 22px of reported slack
# on such a tile is tighter than it looks.


def text_lines(raw):
    """One entry per rendered line, each still carrying its own style tag.

    A div is a block element, so its OPENING tag ends the previous line just as
    surely as its closing tag does. Splitting on </div> alone silently glues a
    heading onto the item below it -- which is how both the journey box and the
    Flickr API tile were being measured a full line short while reporting a
    comfortable fit. Breaking *before* each opening div keeps the font-size
    declaration with the text it governs, which splitting on the tag would throw
    away.
    """
    s = re.sub(r"</div>|</tr>|</table>", "", raw)   # closing tags carry no style
    s = re.sub(r"<br\s*/?>", "\x00", s)
    s = re.sub(r"(<div[^>]*>|<tr[^>]*>)", "\x00\\1", s)
    parts = s.split("\x00")
    if parts and not re.sub(r"<[^>]*>", "", parts[0]).strip():
        parts.pop(0)                          # value opened with a div
    return parts


def wrapped_lines(text, char_w, usable, space_w):
    """Greedy word wrap, the way a browser actually breaks a line.

    Dividing total width by column width assumes text can break anywhere, and it
    cannot -- it breaks between words. One long unbreakable token ends its line
    early and wastes the rest, which is why the journey's step 8 renders on four
    lines while the arithmetic predicted three: "api.flickrgroupaddr.com/v001/*"
    will not split. Undercounting lines is the dangerous direction, because a box
    then reports slack it does not have.
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
    raw = next(c.get("value") or "" for c in cells if c.get("id") == cid)
    # ElementTree has already unescaped one level, so real tags are present.
    # Prove the split actually found lines rather than trusting that it did: one
    # that silently matches nothing measures a whole block as a single line and
    # reports it comfortably inside its box. That has happened three times now --
    # <br> unescaped out from under the token, steps moving from <br> to <div>,
    # and opening div tags not counting as breaks.
    chunks = text_lines(raw)
    if len(chunks) < 2:
        raise SystemExit(f"Text estimator found no line breaks in '{cid}' -- it would measure blind.")
    usable = boxes[cid][2] - pad_left - pad_right
    size, total = 12, 8.0  # spacingTop
    for chunk in chunks:
        # Vertical CSS costs real height. Ignoring it made the estimate low by the
        # exact amount of deliberate spacing a block carries, which is the spacing
        # most likely to be tuned by hand and least likely to be re-measured.
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
        # Whatever sits left of the text narrows the column it wraps into, and it
        # has to come off the usable width or the estimate is wide. Two shapes do
        # this here: a hanging indent (margin-left) and a fixed-width first table
        # column holding the step number (width).
        m_ind = re.search(r"margin-left:\s*(\d+)px|width:\s*(\d+)px", chunk)
        indent = int(next(g for g in m_ind.groups() if g)) if m_ind else 0
        total += wrapped_lines(text, CHAR_W[size], usable - indent, SPACE_W[size]) * LINE_H[size]
    return total


print("  boxed text fits its tile:")
slacks = {}
for cid in ["justification", "key", "journey"]:
    need = text_height(cid)
    have = boxes[cid][3]
    slack = have - need
    slacks[cid] = slack
    if slack < SLACK_MIN:
        verdict = "CRAMPED"
    elif slack > SLACK_MAX:
        verdict = "EXCESS WHITESPACE"
    else:
        verdict = "ok"
    print(f"    {cid:14} box {have:>4.0f}px  text ~{need:>4.0f}px  slack {slack:>4.0f}px  {verdict}")
    if verdict != "ok":
        problems += 1

# Reported, not asserted. These boxes are read side by side, so the eye compares
# their bottom gaps and an outlier looks like a mistake even when every one is
# individually legal -- which is how a 9px spread got noticed by a human after
# passing a check whose band is 33px wide. Any threshold tight enough to have
# caught that would be a number chosen to catch that, so this prints the figure
# and leaves the judgement where it belongs.
print(f"    spread across the three: {max(slacks.values()) - min(slacks.values()):.0f}px"
      f"  ({', '.join(f'{c} {s:.0f}' for c, s in slacks.items())})")


# The journey is a two-column table -- step number, then step text -- because that
# is the only construction where a wrapped line starts at exactly the same x as
# the first one. A rewrite of this label produced three-cell rows with the number
# duplicated into the text column, rendering as "11DNS query", and every check
# here still passed: they all read the flattened text and none looked at the
# shape. Structure needs its own assertion when the text alone cannot show damage.
journey_rows = re.findall(r"<tr[^>]*>(.*?)</tr>",
                          next(c.get("value") for c in cells if c.get("id") == "journey"))
wrong_cells = [i for i, r in enumerate(journey_rows, 1) if r.count("<td") != 2]
# Tied to the badge count rather than a literal. This check previously hardcoded
# nine rows, so splitting the login into more steps failed the build with a
# message that said "all two cells" and no explanation -- the count it was
# unhappy about was never printed. A step with no badge on the canvas, or a badge
# numbering a step that does not exist, is the defect actually worth catching.
badge_count = len([c for c in cells if re.fullmatch(r"n\d+", c.get("id") or "")])
print(f"  User Journey rows are number-plus-text pairs: {len(journey_rows)} rows vs"
      f" {badge_count} badges,"
      f" {'all two cells' if not wrong_cells else f'WRONG CELL COUNT in rows {wrong_cells}'}")
if badge_count == 0:
    print("    -> badges are deliberately OFF; the rule bites at the first one")
elif len(journey_rows) != badge_count:
    print(f"    -> {len(journey_rows)} steps but {badge_count} badges; every step needs one")
if (badge_count and len(journey_rows) != badge_count) or wrong_cells:
    problems += 1


# The Flickr mark sits directly above the word "Flickr", and the gap between them
# is deliberate. It is also the one gap on this canvas that geometry alone cannot
# predict: the Commons original is a 512x512 square whose dots occupy only the
# middle third, so ~30px of the tile's apparent gap was invisible SVG padding and
# no spacingTop could close it. The artwork is now cropped, which means a future
# session swapping in an uncropped file would silently reopen the gap.
# The title is its own cell rather than the card's label. As the card's label its
# position came from spacingTop, which only sets where draw.io STARTS laying text
# out inside a 569px-tall box -- the rendered line landed far lower than the
# arithmetic said, so the word locked visually to the Flickr API tile beneath it
# instead of to the mark above. A cell with its own geometry puts the title where
# the numbers say it is, and makes that position measurable here.
LOGO_GAP_MIN, LOGO_GAP_MAX = 6.0, 8.0
lx, ly, lw, lh = boxes["flickrlogo"]
fx, fy, fw, fh = boxes["flickr"]
tx, ty, tw, th = boxes["flickrtitle"]
gap = ty - (ly + lh)
print("  Flickr mark locked to its title:")
print(f"    mark {lw:.0f}x{lh:.0f} at y {ly:.0f}-{ly + lh:.0f}, title y {ty:.0f}-{ty + th:.0f}  gap {gap:.0f}px")
if not LOGO_GAP_MIN <= gap <= LOGO_GAP_MAX:
    print(f"    -> gap {gap:.0f}px is outside {LOGO_GAP_MIN:.0f}-{LOGO_GAP_MAX:.0f}px")
    problems += 1

# A squashed logo is a subtle, permanent embarrassment -- the only cue is that it
# looks faintly wrong, and nobody can say why. Hold every rendered mark to its own
# artwork's viewBox ratio rather than trusting draw.io's aspect flag. Both marks
# are sized by hand, so both need this.
# The Cloudflare mark is inset equally from the frame's left and top. Unequal
# margins on a corner element read as a mistake rather than as a choice, and the
# eye catches it long before it can name it -- so this is an equality, not a band.
fx0, fy0 = boxes["cfframe"][0], boxes["cfframe"][1]
left_in, top_in = boxes["cflogo"][0] - fx0, boxes["cflogo"][1] - fy0
print(f"  Cloudflare mark inset from its frame: left {left_in:.0f}px, top {top_in:.0f}px")
if abs(left_in - top_in) > 0.5:
    print("    -> insets differ; a corner element with unequal margins reads as misplaced")
    problems += 1

LOGO_ART = {"flickrlogo": "flickr-mark-tight.svg", "cflogo": "cloudflare-mark.svg"}
for cid, art in LOGO_ART.items():
    bw, bh = boxes[cid][2], boxes[cid][3]
    vb = (SVG / art).read_text(encoding="utf-8")
    vw, vh = (float(v) for v in re.search(r'viewBox="\S+ \S+ (\S+) (\S+)"', vb).groups())
    skew = abs((bw / bh) - (vw / vh)) / (vw / vh)
    print(f"    {cid:11} {bw:.0f}x{bh:.0f}  aspect {bw / bh:.3f} vs artwork {vw / vh:.3f}"
          f"  ({skew * 100:.1f}% distortion)")
    if skew > 0.01:
        print(f"    -> {cid} is visibly stretched")
        problems += 1

# Centered under the card, not merely near the middle.
off = (lx + lw / 2) - (fx + fw / 2)
print(f"    centered in the Flickr card: off by {off:.1f}px")
if abs(off) > 0.5:
    problems += 1

# The mark sits in the same margins as the Flickr API tile beneath it -- left,
# right and top all matching that tile's side inset. Two stacked elements with
# almost-equal margins look like a mistake; equal ones look designed, and the
# difference is invisible until they are side by side.
ax, ay, aw, ah = boxes["flickrapi"]
inset = ax - fx
want = {"left": lx - fx, "right": (fx + fw) - (lx + lw), "top": ly - fy}
print(f"    margins vs the Flickr API tile's {inset:.0f}px side inset:")
for edge, got in want.items():
    ok = abs(got - inset) <= 0.5
    print(f"      {edge:<6}{got:>5.0f}px  {'ok' if ok else 'MISMATCH'}")
    if not ok:
        problems += 1

# The title must sit closer to the mark than to the Flickr API tile, which is the
# whole point of locking it: whichever element it is nearest is the one a reader
# groups it with. This is the check that would have caught the earlier version.
below = ay - (ty + th)
print(f"    title clears the Flickr API tile by {below:.0f}px")
if below < 8:
    print("    -> title crowds the Flickr API tile")
    problems += 1
if below <= gap:
    print(f"    -> title is nearer the Flickr API tile ({below:.0f}px) than the mark ({gap:.0f}px)")
    problems += 1

# The title shares the mark's column, so it inherits the same margins.
if abs(tx - lx) > 0.5 or abs(tw - lw) > 0.5:
    print(f"    -> title column {tx:.0f}+{tw:.0f} does not match the mark's {lx:.0f}+{lw:.0f}")
    problems += 1


# Badges are excluded from the edge/box collision check because they are meant to
# sit beside their arrow, which means NOTHING was checking them against tiles. A
# badge overlapping a tile went unnoticed for several commits after a column
# shift moved the tile under it.
# DERIVED, not hardcoded. This read `range(1, 12)` while `badge_count` above
# built its list with a regex over the same cells -- so adding a badge extended
# one and silently not the other, and the overlap checks below would have
# skipped the new one while the journey check counted it. Exactly the drift the
# journey-row check's own comment warns about, sitting ten lines away.
BADGES = sorted(
    (c.get("id") for c in cells if re.fullmatch(r"n\d+", c.get("id") or "")),
    key=lambda n: int(n[1:]),
)
TILES = ["dns", "secrets", "cron", "oauthdo", "api", "retry",
         "d1", "users", "lrcapp", "flickrapi", "journey", "key", "justification"]


def overlaps(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


# Badges are checked against tiles and against their own arrow, but until step 9
# no two of them could plausibly meet. Now that n5 and n9 share e9, two badges on
# one arrow can be slid into each other by any change to that arrow's ends -- and
# nothing above would notice, because each would still measure a correct 26px
# offset from the line they both sit on.
print("  badges clear of each other:")
badge_clashes = [
    (a, b) for i, a in enumerate(BADGES) for b in BADGES[i + 1:]
    if a in boxes and b in boxes and overlaps(boxes[a], boxes[b])
]
for a, b in badge_clashes:
    print(f"    {a} OVERLAPS {b}")
print(f"    -> {'all clear' if not badge_clashes else f'{len(badge_clashes)} overlap(s)'}")
problems += len(badge_clashes)


print("  badges clear of every tile:")
clashes = [
    (n, t) for n in BADGES for t in TILES
    if t in boxes and overlaps(boxes[n], boxes[t])
]
for n, t in clashes:
    print(f"    {n} OVERLAPS {t}")
print(f"    -> {'all clear' if not clashes else f'{len(clashes)} overlap(s)'}")
problems += len(clashes)


# The Flickr API tile lists the method names FGA calls, and a method name that
# wraps mid-name reads as a typo rather than as a long line. This tile is not in
# the boxed-text slack check above, because its height is set by the arrows that
# must reach it rather than by its text -- so width is the only thing worth
# asserting, and it is asserted per line.
api_box = boxes["flickrapi"]
api_usable = api_box[2] - 18.0
api_raw = next(c.get("value") for c in cells if c.get("id") == "flickrapi")
api_chunks = text_lines(api_raw)
if len(api_chunks) < 2:
    raise SystemExit("Flickr API tile parsed to fewer than 2 lines -- the width check is blind.")
api_size, api_wide = 20, []
for chunk in api_chunks:
    m = re.search(r"font-size:(\d+)px", chunk)
    if m:
        api_size = int(m.group(1))
    text = re.sub(r"<[^>]*>", "", chunk).strip()
    if text and len(text) * CHAR_W[api_size] > api_usable:
        api_wide.append((text, len(text) * CHAR_W[api_size]))
print(f"  Flickr API tile lines fit its {api_usable:.0f}px width:")
for text, wpx in api_wide:
    print(f"    {text!r} needs {wpx:.0f}px")
print(f"    -> {'all fit' if not api_wide else f'{len(api_wide)} too wide'}")
problems += len(api_wide)


# "Master key" rode this arrow for two commits after the design stopped having
# one: the v1 rewrite replaced a single Secrets Store master key with the four
# entries the tile now lists, and nothing was checking the arrows against it. A
# label naming a secret the tile does not hold is a diagram describing an older
# design, and it reads as authoritative right up until someone acts on it.
secrets_raw = next(c.get("value") for c in cells if c.get("id") == "secrets")
entries = [re.sub(r"<[^>]*>", "", s).strip() for s in re.split(r"<br\s*/?>", secrets_raw)]
entries = [e for e in entries if e]
if len(entries) < 2:
    raise SystemExit("Worker Secrets tile parsed to fewer than 2 entries -- the check is blind.")
# Entries, not secrets: "FGA Flickr API credentials" is one line covering two of
# ADR-09's four, since the consumer key and secret are only ever used as a pair.
print(f"  Worker Secrets arrows name only what the tile holds ({len(entries) - 1} entries):")
for c in cells:
    if not c.get("edge") or "secrets" not in (c.get("source"), c.get("target")):
        continue
    label = (c.get("value") or "").strip()
    if not label:
        print(f"    {c.get('id'):4} unlabeled -- reads as 'this Worker reads secrets'  ok")
        continue
    known = any(label.lower() in e.lower() for e in entries)
    print(f"    {c.get('id'):4} {label!r} {'ok' if known else 'NAMES NOTHING THE TILE HOLDS'}")
    if not known:
        problems += 1


# THE LINE STYLES, and the legend row each one owns.
#
# Two styles remain. Solid is a request and its response; dotted is the nightly
# scheduled trigger, drawn weaker because a clock firing is notional rather than
# a data path. The legend has a row per style written against these exact edges,
# so making one solid does not merely change a line -- it orphans a legend entry
# that then explains nothing.
#
# DASHED IS GONE, and so is the label that rode on it. Read replicas were removed
# from the architecture on 2026-08-13 (Terry's call; see ADR-12), which deleted
# the only dashed edge -- `e16`, D1 primary to replica -- and with it the
# "Eventual consistency" label this build used to protect as load-bearing. That
# protection was correct while the split existed: the label was the entire
# difference between two tiles holding identical rows. With one database there is
# no lag to name, so the check is not relaxed here, it is obsolete. The legend
# lost its dashed row in the same change, because a legend entry for a style no
# edge uses is worse than no entry at all.
REQUIRED_EDGE_LABEL: dict[str, str] = {}
LINE_STYLE = {
    "e6": ("dotted", "cron -> retry, a scheduled trigger"),
}
print("  Load-bearing edge labels still present:")
for eid, needle in REQUIRED_EDGE_LABEL.items():
    label = (edge_by_id[eid].get("value") or "").strip()
    ok = needle.lower() in label.lower()
    print(f"    {eid:4} {label!r} {'ok' if ok else 'MISSING -- read the comment above this check'}")
    if not ok:
        problems += 1

print("  Edges still carry the line style the legend describes:")
for eid, (want, why) in LINE_STYLE.items():
    style = edge_by_id[eid].get("style") or ""
    # draw.io draws dotted as a dashed line with a short dash pattern, so the two
    # broken styles differ only by dashPattern -- checking "dashed=1" alone would
    # pass either and quietly let one collapse into the other.
    got = "dotted" if "dashPattern=" in style else "dashed" if "dashed=1" in style else "solid"
    print(f"    {eid:4} {why:<40} {got:<7} {'ok' if got == want else f'WANT {want.upper()} -- orphans a legend row'}")
    if got != want:
        problems += 1


# "DO" is banned on this project. Terry is a long-time DigitalOcean customer and
# the abbreviation collides with that in his head at exactly the moment he is
# skimming. Write "Durable Object" every time, however verbose it feels.
banned = re.findall(r"\bDOs?\b", re.sub(r"image=data:image/svg\+xml,[A-Za-z0-9+/=]+", "", OUT.read_text(encoding="utf-8")))
print(f"  no 'DO' abbreviation on the canvas: {'clean' if not banned else f'FOUND {len(banned)}'}")
if banned:
    problems += 1


# Every line a human reads starts with a capital. Terry's standing rule, and the
# reason is consistency rather than taste: a label set that capitalises eleven
# lines and not the twelfth reads as unfinished, and the eye stops on the odd one
# out at exactly the moment someone is trying to skim.
#
# Two legitimate exceptions, both listed explicitly rather than pattern-matched,
# because a clever regex here would silently excuse a real lapse:
#   - identifiers, paths and domains, where changing case changes meaning
#   - continuation lines of a sentence wrapped across two rows
# The two exceptions need different tests, and conflating them was hiding a gap.
# An identifier is lowercase because its case carries meaning, and it may be
# followed by ordinary words: "flickrgroupaddr.com DNS" is a line that OPENS with
# a domain, not a sentence someone forgot to capitalize. A continuation is the
# second row of a wrapped sentence and only ever matches whole. Matching both
# exactly meant any identifier with a word after it read as a lapse.
LOWERCASE_OPENERS = {
    "flickrgroupaddr.com": "domain",
    # ADR-18 put the app shell and the API on ONE origin, so the two tiles are told
    # apart by their path prefix rather than by a hostname. `api.flickrgroupaddr.com`
    # is deliberately gone from this list -- leaving it would let the old, wrong
    # hostname pass the capitalization check if it ever came back.
    "flickrgroupaddr.com/": "origin root",
    "flickrgroupaddr.com/api/*": "origin and path prefix",
    # The merged Worker tile lists its two routes as bare path prefixes under one
    # hostname, so each line opens with a slash. **Case is not ours to correct in a
    # URL path** -- and the alternative, capitalizing them, would print a route
    # that does not exist.
    "/": "URL path prefix",
    "flickr.groups.pools.add": "API method",
    "docs/architecture/DECISIONS.md": "path",
    # The Flickr API tile lists the surface FGA calls. These are method and
    # endpoint names, so their case is not ours to correct.
    "oauth/request_token": "OAuth endpoint",
    "oauth/authorize": "OAuth endpoint",
    "oauth/access_token": "OAuth endpoint",
    "groups.pools.getGroups": "API method",
    "groups.pools.add": "API method",
    "photos.getAllContexts": "API method",
}
LOWERCASE_CONTINUATIONS = {
    "per login attempt": "continuation of 'One Durable Object'",
    "consistency": "continuation of 'Eventual'",
    "pending requests. Stop a queue at": "continuation of 'Attempt to flush every queue with'",
    "its first throttle status": "continuation of the same sentence",
}

bad_case = []
for c in cells:
    raw = c.get("value") or ""
    for chunk in re.split(r"<br\s*/?>|</div>", raw):
        line = re.sub(r"<[^>]*>", "", chunk).replace("&nbsp;", " ").strip()
        if not line or line in LOWERCASE_CONTINUATIONS:
            continue
        if any(line.startswith(tok) for tok in LOWERCASE_OPENERS):
            continue
        first = next((ch for ch in line if ch.isalpha()), None)
        if first and first.islower():
            bad_case.append((c.get("id"), line[:50]))

print("  every label line starts with a capital:")
for cid, line in bad_case:
    print(f"    {cid}: {line!r}")
print(f"    -> {'clean' if not bad_case else f'{len(bad_case)} lowercase'}")
problems += len(bad_case)

def check_page_fit() -> None:
    """Report how the content sits against an 11x17 sheet.

    **This does NOT fail the build, and the restraint is the point.** The content
    is known to exceed the page; a check that failed every run would be scenery
    within a day. It prints the numbers so a layout change that makes the overflow
    WORSE is visible in the same breath as the change.

    **It also states the export setting**, because the file cannot enforce it and
    the wrong choice tiles the drawing across four sheets.
    """
    xs, ys = [], []
    for match in re.finditer(
        r'<mxGeometry([^/>]*)(?:/>|>)', TEMPLATE.replace("&quot;", '"')
    ):
        attrs = match.group(1)
        got = dict(re.findall(r'(\w+)="([-\d.]+)"', attrs))
        if "x" not in got or "y" not in got:
            continue
        x, y = float(got["x"]), float(got["y"])
        xs += [x, x + float(got.get("width", 0))]
        ys += [y, y + float(got.get("height", 0))]

    if not xs:
        print("  page fit: NO GEOMETRY FOUND -- the check is broken, not the layout")
        return

    width, height = max(xs) - min(xs), max(ys) - min(ys)
    scale = min(PAGE_WIDTH / width, PAGE_HEIGHT / height)

    print(f"  11x17 page fit ({PAGE_WIDTH}x{PAGE_HEIGHT} = 17x11 inches):")
    print(f"    content        {width:.0f} x {height:.0f}")
    print(f"    fits at        {scale * 100:.0f}%  ({'1:1' if scale >= 1 else 'needs Fit to Page'})")
    print("    export as PDF with FIT TO PAGE, or it tiles across four sheets")
    print("    DPI is a raster setting and does not apply to a PDF")


check_page_fit()

if problems:
    raise SystemExit("Diagram geometry check failed -- fix the layout before committing.")
