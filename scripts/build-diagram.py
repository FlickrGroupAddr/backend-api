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
DATE = "2026-08-13"

ROOT = pathlib.Path(__file__).resolve().parent.parent
SVG = ROOT / "docs" / "architecture" / "logos"
OUT = ROOT / "docs" / "architecture" / f"FlickrGroupAddr-Architecture-{DATE}.drawio"


def embed(name: str) -> str:
    raw = (SVG / name).read_bytes()
    return "data:image/svg+xml," + base64.b64encode(raw).decode("ascii")


CF = embed("cloudflare-mark.svg")
FLICKR = embed("flickr-mark-tight.svg")
USERS = embed("users.svg")

TEMPLATE = """<mxfile host="app.diagrams.net" agent="Claude Code" version="24.0.0">
  <diagram id="fga-architecture" name="FlickrGroupAddr Architecture">
    <mxGraphModel dx="1422" dy="900" grid="0" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1900" pageHeight="1400" math="0" shadow="0">
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
          <mxGeometry x="220" y="150" width="1300" height="1080" as="geometry" />
        </mxCell>
        <mxCell id="cflogo" value="" style="shape=image;html=1;imageAspect=1;aspect=fixed;image={CF}" vertex="1" parent="1">
          <mxGeometry x="238" y="166" width="182" height="60" as="geometry" />
        </mxCell>
        <mxCell id="netb" value="Lowest-latency Cloudflare edge PoP (anycast routing)" style="rounded=0;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#F6821F;dashed=1;strokeWidth=2;verticalAlign=top;fontColor=#F6821F;fontStyle=1;fontSize=13;spacingTop=6;" vertex="1" parent="1">
          <mxGeometry x="260" y="440" width="950" height="740" as="geometry" />
        </mxCell>

        <mxCell id="users" value="Users" style="shape=image;html=1;imageAspect=1;aspect=fixed;image={USERS};fontSize=13;fontStyle=1;labelPosition=left;align=right;verticalLabelPosition=middle;verticalAlign=middle;spacingRight=10;" vertex="1" parent="1">
          <mxGeometry x="70" y="750" width="100" height="80" as="geometry" />
        </mxCell>

        <mxCell id="dns" value="&lt;b&gt;flickrgroupaddr.com DNS&lt;/b&gt;&lt;br&gt;&lt;i&gt;Cloudflare Authoritative DNS&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F6821F;strokeColor=none;fontColor=#FFFFFF;fontSize=12;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="380" y="480" width="210" height="90" as="geometry" />
        </mxCell>
        <mxCell id="pages" value="&lt;b&gt;flickrgroupaddr.com&lt;br&gt;Frontend UI&lt;/b&gt;&lt;br&gt;&lt;i&gt;Cloudflare Pages&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F6821F;strokeColor=none;fontColor=#FFFFFF;fontSize=12;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="380" y="640" width="210" height="90" as="geometry" />
        </mxCell>
        <mxCell id="secrets" value="&lt;b&gt;App Secrets Store&lt;/b&gt;&lt;br&gt;&lt;i&gt;Worker Secrets&lt;br&gt;FGA Flickr API credentials&lt;br&gt;Token key (encryption)&lt;br&gt;Session key (signing)&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#6B7280;strokeColor=none;fontColor=#FFFFFF;fontSize=12;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="640" y="908" width="220" height="115" as="geometry" />
        </mxCell>
        <mxCell id="cron" value="&lt;b&gt;Cron Trigger&lt;/b&gt;&lt;br&gt;&lt;i&gt;Nightly&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FBAD41;strokeColor=none;fontColor=#3A2200;fontSize=12;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="380" y="1040" width="210" height="100" as="geometry" />
        </mxCell>

        <mxCell id="oauthdo_b2" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#6A3D9A;strokeColor=#FFFFFF;strokeWidth=2;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="956" y="284" width="230" height="100" as="geometry" />
        </mxCell>
        <mxCell id="oauthdo_b1" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#6A3D9A;strokeColor=#FFFFFF;strokeWidth=2;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="948" y="292" width="230" height="100" as="geometry" />
        </mxCell>
        <mxCell id="oauthdo" value="&lt;b&gt;OAuth Request Token&lt;/b&gt;&lt;br&gt;&lt;i&gt;One Durable Object&lt;br&gt;per login attempt&lt;br&gt;Self-deletes after ~15 min&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#6A3D9A;strokeColor=#FFFFFF;strokeWidth=2;fontColor=#FFFFFF;fontSize=13;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="940" y="300" width="230" height="100" as="geometry" />
        </mxCell>
        <mxCell id="api" value="&lt;b&gt;api.flickrgroupaddr.com&lt;br&gt;REST API Endpoint&lt;/b&gt;&lt;br&gt;&lt;i&gt;Cloudflare Worker&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F6821F;strokeColor=none;fontColor=#FFFFFF;fontSize=13;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="940" y="740" width="230" height="100" as="geometry" />
        </mxCell>
        <mxCell id="retry" value="&lt;b&gt;Retry Worker&lt;/b&gt;&lt;br&gt;&lt;i&gt;Drains due requests&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F6821F;strokeColor=none;fontColor=#FFFFFF;fontSize=13;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="940" y="1040" width="230" height="100" as="geometry" />
        </mxCell>

        <mxCell id="d1replica" value="&lt;b&gt;Read-Only SQL DB&lt;/b&gt;&lt;br&gt;&lt;i&gt;D1 Read Replica&lt;br&gt;One replica per Cloudflare region&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#4FC3E8;strokeColor=none;fontColor=#0B2E3D;fontSize=12;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="940" y="915" width="230" height="80" as="geometry" />
        </mxCell>
        <mxCell id="d1" value="&lt;b&gt;Write-Only SQL DB&lt;/b&gt;&lt;br&gt;&lt;i&gt;D1 Primary&lt;br&gt;Users &#183; requests &#183; tokens&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#00A3E0;strokeColor=none;fontColor=#FFFFFF;fontSize=12;arcSize=12;" vertex="1" parent="1">
          <mxGeometry x="1300" y="908" width="200" height="115" as="geometry" />
        </mxCell>

        <mxCell id="flickr" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#FF0084;strokeWidth=3;arcSize=6;" vertex="1" parent="1">
          <mxGeometry x="1600" y="581" width="205" height="599" as="geometry" />
        </mxCell>
        <mxCell id="flickrtitle" value="Flickr" style="text;html=1;align=center;verticalAlign=middle;fontSize=22;fontStyle=1;fontColor=#1A1A1A;" vertex="1" parent="1">
          <mxGeometry x="1625" y="686" width="155" height="28" as="geometry" />
        </mxCell>
        <mxCell id="flickrapi" value="&lt;b&gt;Flickr API&lt;/b&gt;&lt;div style=&quot;font-size:14px&quot;&gt;&lt;i&gt;OAuth 1.0a&lt;/i&gt;&lt;/div&gt;&lt;div style=&quot;font-size:15px;border-bottom:2px solid #FFFFFF;display:inline-block;padding-bottom:3px;margin-top:60px&quot;&gt;&lt;b&gt;OAuth Endpoints&lt;/b&gt;&lt;/div&gt;&lt;div style=&quot;font-size:10px;line-height:13px;margin-top:7px&quot;&gt;oauth/request_token&lt;/div&gt;&lt;div style=&quot;font-size:10px;line-height:13px&quot;&gt;oauth/authorize&lt;/div&gt;&lt;div style=&quot;font-size:10px;line-height:13px&quot;&gt;oauth/access_token&lt;/div&gt;&lt;div style=&quot;font-size:15px;border-bottom:2px solid #FFFFFF;display:inline-block;padding-bottom:3px;margin-top:30px&quot;&gt;&lt;b&gt;API Functions&lt;/b&gt;&lt;/div&gt;&lt;div style=&quot;font-size:10px;line-height:13px;margin-top:7px&quot;&gt;groups.pools.getGroups&lt;/div&gt;&lt;div style=&quot;font-size:10px;line-height:13px&quot;&gt;photos.getAllContexts&lt;/div&gt;&lt;div style=&quot;font-size:10px;line-height:13px&quot;&gt;groups.pools.add&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FF0084;strokeColor=none;fontColor=#FFFFFF;fontSize=20;arcSize=8;verticalAlign=top;spacingTop=16;" vertex="1" parent="1">
          <mxGeometry x="1625" y="740" width="155" height="400" as="geometry" />
        </mxCell>
        <mxCell id="flickrlogo" value="" style="shape=image;html=1;imageAspect=1;aspect=fixed;image={FLICKR}" vertex="1" parent="1">
          <mxGeometry x="1625" y="606" width="155" height="73" as="geometry" />
        </mxCell>
                <mxCell id="justification" value="&lt;b&gt;Project Justification&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:11px&quot;&gt;Flickr caps how many photos a member may add to a group each day. Doing it by hand means coming back every day for weeks. FGA queues each request and keeps retrying until it lands.&lt;/font&gt;" style="rounded=0;whiteSpace=wrap;html=1;align=left;verticalAlign=top;fillColor=#FFFFFF;strokeColor=#B0B0B0;fontSize=12;spacingLeft=10;spacingTop=8;spacingRight=8;" vertex="1" parent="1">
          <mxGeometry x="1600" y="150" width="205" height="140" as="geometry" />
        </mxCell>

        <mxCell id="key" value="&lt;b&gt;Legend&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:11px&quot;&gt;&#8212;&#8212;&#8212; Request / response&lt;br&gt;&#8211; &#8211; &#8211; Scheduled or async&lt;/font&gt;&lt;br&gt;&lt;br&gt;&lt;font style=&quot;font-size:10px&quot;&gt;Why it is built this way:&lt;br&gt;docs/architecture/DECISIONS.md&lt;/font&gt;" style="rounded=0;whiteSpace=wrap;html=1;align=left;verticalAlign=top;fillColor=#FFFFFF;strokeColor=#B0B0B0;fontSize=12;spacingLeft=10;spacingTop=8;" vertex="1" parent="1">
          <mxGeometry x="1600" y="373" width="205" height="125" as="geometry" />
        </mxCell>

        <mxCell id="n1" value="1" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=22;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="304" y="553" width="46" height="46" as="geometry" />
        </mxCell>
        <mxCell id="n2" value="2" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=22;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="299" y="654" width="46" height="46" as="geometry" />
        </mxCell>
        <mxCell id="n3" value="3" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=22;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="727" y="721" width="46" height="46" as="geometry" />
        </mxCell>
        <mxCell id="n4" value="4" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=22;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="854" y="839" width="46" height="46" as="geometry" />
        </mxCell>
        <mxCell id="n5" value="5" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=22;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="1537" y="728" width="46" height="46" as="geometry" />
        </mxCell>
        <mxCell id="n6" value="6" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=22;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="1058" y="547" width="46" height="46" as="geometry" />
        </mxCell>
        <mxCell id="n7" value="7" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=22;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="727" y="1281" width="46" height="46" as="geometry" />
        </mxCell>
        <mxCell id="n8" value="8" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=22;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="452" y="813" width="46" height="46" as="geometry" />
        </mxCell>
        <mxCell id="n9" value="9" style="ellipse;whiteSpace=wrap;html=1;fillColor=#003087;strokeColor=#FFFFFF;strokeWidth=3;fontColor=#FFFFFF;fontSize=22;fontStyle=1;" vertex="1" parent="1">
          <mxGeometry x="1537" y="817" width="46" height="46" as="geometry" />
        </mxCell>

        <mxCell id="journey" value="&lt;b&gt;User Journey&lt;/b&gt;&lt;div style=&quot;font-size:11px;margin-left:18px;text-indent:-18px&quot;&gt;&lt;b&gt;1&lt;/b&gt;&amp;nbsp; DNS query, resolved at the nearest PoP&lt;/div&gt;&lt;div style=&quot;font-size:11px;margin-left:18px;text-indent:-18px&quot;&gt;&lt;b&gt;2&lt;/b&gt;&amp;nbsp; Static assets served from Cloudflare Pages&lt;/div&gt;&lt;div style=&quot;font-size:11px;margin-left:18px;text-indent:-18px&quot;&gt;&lt;b&gt;3&lt;/b&gt;&amp;nbsp; Begin login &#8212; the browser calls the API Worker&lt;/div&gt;&lt;div style=&quot;font-size:11px;margin-left:18px;text-indent:-18px&quot;&gt;&lt;b&gt;4&lt;/b&gt;&amp;nbsp; Worker reads the FGA Flickr API credentials from Worker Secrets&lt;/div&gt;&lt;div style=&quot;font-size:11px;margin-left:18px;text-indent:-18px&quot;&gt;&lt;b&gt;5&lt;/b&gt;&amp;nbsp; Worker signs with them and asks Flickr for a request token&lt;/div&gt;&lt;div style=&quot;font-size:11px;margin-left:18px;text-indent:-18px&quot;&gt;&lt;b&gt;6&lt;/b&gt;&amp;nbsp; Worker stashes the token secret in the OAuth Durable Object&lt;/div&gt;&lt;div style=&quot;font-size:11px;margin-left:18px;text-indent:-18px&quot;&gt;&lt;b&gt;7&lt;/b&gt;&amp;nbsp; Authorize at flickr.com. Flickr redirects back, and the Worker reads the secret back out and trades it for the long-lived access token &#8212; the return legs of 5 and 6&lt;/div&gt;&lt;div style=&quot;font-size:11px;margin-left:18px;text-indent:-18px&quot;&gt;&lt;b&gt;8&lt;/b&gt;&amp;nbsp; REST API endpoints: api.flickrgroupaddr.com/v001/* &#8212; authenticated calls carrying a session cookie&lt;/div&gt;&lt;div style=&quot;font-size:11px;margin-left:18px;text-indent:-18px&quot;&gt;&lt;b&gt;9&lt;/b&gt;&amp;nbsp; Worker calls Flickr as the user &#8212; lists groups, checks pools, adds when clear&lt;/div&gt;" style="rounded=0;whiteSpace=wrap;html=1;align=left;verticalAlign=top;fillColor=#FFFFFF;strokeColor=#003087;strokeWidth=2;fontSize=13;spacingLeft=12;spacingTop=8;spacingRight=10;" vertex="1" parent="1">
          <mxGeometry x="1228" y="290" width="275" height="340" as="geometry" />
        </mxCell>

        <mxCell id="e1" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;exitX=0.6;exitY=0;exitDx=0;exitDy=0;entryX=0;entryY=1;entryDx=0;entryDy=0;" edge="1" parent="1" source="users" target="dns">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e2" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.05;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" edge="1" parent="1" source="users" target="pages">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e12" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.25;exitDx=0;exitDy=0;entryX=0;entryY=0.3;entryDx=0;entryDy=0;" edge="1" parent="1" source="users" target="api">
          <mxGeometry x="0.45" relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e13" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.75;exitDx=0;exitDy=0;entryX=0;entryY=0.7;entryDx=0;entryDy=0;" edge="1" parent="1" source="users" target="api">
          <mxGeometry x="0.55" relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e3" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;" edge="1" parent="1" source="api" target="oauthdo">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e4" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=11;" edge="1" parent="1" source="secrets" target="api">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e5" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;" edge="1" parent="1" source="secrets" target="retry">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e6" value="Nightly sweep" style="rounded=0;html=1;endArrow=classic;endFill=1;strokeWidth=2;dashed=1;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;" edge="1" parent="1" source="cron" target="retry">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e7" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=11;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;" edge="1" parent="1" source="api" target="d1replica">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e8" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=11;exitX=0.5;exitY=0;exitDx=0;exitDy=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;" edge="1" parent="1" source="retry" target="d1replica">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e14" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=11;exitX=1;exitY=1;exitDx=0;exitDy=0;entryX=0;entryY=0;entryDx=0;entryDy=0;" edge="1" parent="1" source="api" target="d1">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e15" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=11;exitX=1;exitY=0;exitDx=0;exitDy=0;entryX=0;entryY=1;entryDx=0;entryDy=0;" edge="1" parent="1" source="retry" target="d1">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e16" value="Eventual&lt;br&gt;consistency" style="rounded=0;html=1;endArrow=classic;endFill=1;strokeWidth=3;dashed=1;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;exitX=0;exitY=0.4;exitDx=0;exitDy=0;entryX=1;entryY=0.4875;entryDx=0;entryDy=0;" edge="1" parent="1" source="d1" target="d1replica">
          <mxGeometry relative="1" as="geometry">
            <mxPoint x="25" y="-18" as="offset" />
          </mxGeometry>
        </mxCell>
        <mxCell id="e9" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.37;exitDx=0;exitDy=0;entryX=0;entryY=0.0925;entryDx=0;entryDy=0;" edge="1" parent="1" source="api" target="flickrapi">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e17" value="" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.74;exitDx=0;exitDy=0;entryX=0;entryY=0.185;entryDx=0;entryDy=0;" edge="1" parent="1" source="api" target="flickrapi">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e10" value="flickr.groups.pools.add" style="rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;exitX=1;exitY=0.63;exitDx=0;exitDy=0;entryX=0;entryY=0.9075;entryDx=0;entryDy=0;" edge="1" parent="1" source="retry" target="flickrapi">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
        <mxCell id="e11" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=classic;endFill=1;startArrow=classic;startFill=1;strokeWidth=3;strokeColor=#1A1A1A;fontSize=11;labelBackgroundColor=#FFFFFF;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;" edge="1" parent="1" source="users" target="flickrapi">
          <mxGeometry relative="1" as="geometry">
            <Array as="points">
              <mxPoint x="120" y="1330" />
              <mxPoint x="1702.5" y="1330" />
            </Array>
          </mxGeometry>
        </mxCell>

      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
"""

OUT.write_text(
    TEMPLATE.replace("{CF}", CF)
    .replace("{FLICKR}", FLICKR)
    .replace("{USERS}", USERS)
    .replace("{DATE}", DATE),
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
    "cfframe", "netb", "cflogo", "title", "date",
    "flickrlogo", "flickr", "flickrtitle",
    # Step badges sit ON their arrows by design, so they are not obstacles.
    "n1", "n2", "n3", "n4", "n5", "n6", "n7", "n8", "n9",
    # Cascade cards behind the OAuth tile: decoration showing there are many,
    # and the edge legitimately terminates on the tile stacked in front of them.
    "oauthdo_b1", "oauthdo_b2",
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
    "e12": "users -> api (begin login)",
    "e13": "users -> api (authenticated)",
    "e6": "cron -> retry",
    "e9": "api -> flickr (login)",
    "e17": "api -> flickr (as the user)",
    "e10": "retry -> flickr",
    # Added after D1 Primary was resized to align with App Secrets Store. Both
    # ends were anchored at 0.5, so they were level only while the two tiles
    # happened to share a centre -- a coincidence, not a constraint. Resizing
    # either one tilted the arrow, and nothing was watching.
    "e16": "d1 -> replica",
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


# Which side of the edge-PoP boundary a tile sits on is now a CLAIM, not layout:
# Workers run at the nearest anycast PoP, while a Durable Object and a D1 primary
# each live in exactly one location. Drag a box across that line and the diagram
# starts asserting something false, so the build checks it.
# Components only. The legend is diagram furniture -- its position claims nothing
# about where code runs, so it is deliberately not asserted here.
IN_EDGE_POP = {
    "dns": True,  # authoritative DNS is anycast, answered at the nearest PoP
    "pages": True, "secrets": True, "cron": True, "api": True, "retry": True,
    "d1replica": True,  # a read replica exists in every region, including this PoP's
    "oauthdo": False,   # single Durable Object instance, not edge-replicated
    "d1": False,        # the primary is one location; every write crosses to it
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


# The right-hand column is deliberately flush: legend, Flickr tile, and the note
# beneath it share a left edge and a width. Ragged edges there read as sloppiness
# rather than as meaning, and a resize elsewhere is what would quietly break it.
RIGHT_COLUMN = ["justification", "key", "flickr"]
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
BADGE_ON_EDGE = {
    "n1": "e1",    # users -> Cloudflare DNS
    "n2": "e2",    # users -> Cloudflare Pages
    "n3": "e12",   # users -> API Worker, begin login
    "n4": "e4",    # Worker Secrets -> API Worker, read the FGA credentials
    "n5": "e9",    # API Worker <-> Flickr, request token (access token on the return)
    "n6": "e3",    # API Worker <-> OAuth Durable Object, stash the secret (read back on return)
    "n8": "e13",   # users -> API Worker, authenticated calls
    # Steps 5 and 9 get parallel arrows for the same reason steps 3 and 8 do:
    # they are separate conversations that happen at different points, and one
    # shared line made the second invisible. e9 is the login leg, e17 everything
    # afterwards.
    "n9": "e17",   # API Worker -> Flickr, acting as the user after login
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
    centre = (bx + bw / 2, by + bh / 2)
    _, _, p, q = segments[eid]
    d = point_to_segment(centre, p, q)
    if d < NEAR_MIN:
        verdict = "TOO CLOSE, masks the line"
    elif d > NEAR_MAX:
        verdict = "ADRIFT from its line"
    else:
        verdict = "ok"
    print(f"    {badge} beside {eid:4} offset {d:>5.1f}px  {verdict}")
    if verdict != "ok":
        problems += 1

# n7 rides the orthogonal Users-to-Flickr route, whose long leg is the horizontal
# run between its two waypoints; the straight-edge machinery above cannot model it.
n7x, n7y, n7w, n7h = boxes["n7"]
n7c = (n7x + n7w / 2, n7y + n7h / 2)
run_y, run_x0, run_x1 = 1330.0, 120.0, 1702.5
n7_off = abs(n7c[1] - run_y)
on_run = NEAR_MIN <= n7_off <= NEAR_MAX and run_x0 <= n7c[0] <= run_x1
print(f"    n7 beside e11  offset {n7_off:>5.1f}px  {'ok' if on_run else 'BADLY PLACED'}")
if not on_run:
    problems += 1

# n7 rides a 1,580px horizontal run, so nothing about the arrow decides where
# along it the badge belongs -- which is exactly why it looked arbitrary. It is
# pinned to the centre of App Secrets Store directly above it. An equality, not a
# tolerance, because the alignment either reads or it does not.
sx, _, sw, _ = boxes["secrets"]
drift = n7c[0] - (sx + sw / 2)
print(f"    n7 centred under App Secrets Store: off by {drift:.1f}px")
if abs(drift) > 0.5:
    problems += 1


# A badged arrow MUST carry no text label. Both a badge and an edge label default
# to the arrow's midpoint, so adding one buries the other -- which is exactly how
# the first badged version shipped unreadable. The descriptions live in the
# "User journey" key instead, where they have room to be sentences.
print("  badged arrows carry no competing label:")
for badge, eid in list(BADGE_ON_EDGE.items()) + [("n7", "e11")]:
    label = (edge_by_id[eid].get("value") or "").strip()
    clean = "clear" if not label else f"HAS LABEL {label!r}"
    print(f"    {eid:4} ({badge}) {clean}")
    if label:
        problems += 1


# The step badges are a distinct visual language and MUST NOT be confusable with
# any tile. The OAuth Durable Object was originally #0051C3 against badges at
# 68 units apart in RGB, close enough to read as the same thing at a glance.
BADGE_FILL = "#003087"
MIN_COLOUR_DISTANCE = 90.0


def rgb(hexcolour):
    h = hexcolour.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


badge_rgb = rgb(BADGE_FILL)
print("  badge colour distinct from tile fills:")
for tile in ["dns", "pages", "secrets", "cron", "api", "retry", "oauthdo", "d1"]:
    style = next(c.get("style") for c in cells if c.get("id") == tile)
    fill = re.search(r"fillColor=(#[0-9A-Fa-f]{6})", style).group(1)
    dist = math.dist(badge_rgb, rgb(fill))
    verdict = "ok" if dist >= MIN_COLOUR_DISTANCE else "TOO CLOSE TO BADGE BLUE"
    print(f"    {tile:9} {fill}  distance {dist:>5.0f}  {verdict}")
    if dist < MIN_COLOUR_DISTANCE:
        problems += 1


# Boxed text tiles are sized by hand, and by hand is how you get a box that
# either crowds its last line or trails 50px of dead space. This estimates the
# wrapped text height and keeps the slack inside a band.
CHAR_W = {20: 11.0, 15: 7.6, 14: 7.1, 13: 6.6, 12: 6.1, 11: 5.6, 10: 5.1}
LINE_H = {20: 26, 15: 20, 14: 18, 13: 18, 12: 17, 11: 15, 10: 14}
SLACK_MIN, SLACK_MAX = 12.0, 45.0


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
    s = re.sub(r"</div>", "", raw)            # closing tags carry no style info
    s = re.sub(r"<br\s*/?>", "\x00", s)
    s = re.sub(r"(<div[^>]*>)", "\x00\\1", s)
    parts = s.split("\x00")
    if parts and not re.sub(r"<[^>]*>", "", parts[0]).strip():
        parts.pop(0)                          # value opened with a div
    return parts


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
        m = re.search(r"font-size:(\d+)px", chunk)
        if m:
            size = int(m.group(1))
        text = re.sub(r"<[^>]*>", "", chunk).replace("&nbsp;", " ").strip()
        if not text:
            total += LINE_H[size]
            continue
        total += max(1, math.ceil(len(text) * CHAR_W[size] / usable)) * LINE_H[size]
    return total


print("  boxed text fits its tile:")
for cid in ["justification", "key", "journey"]:
    need = text_height(cid)
    have = boxes[cid][3]
    slack = have - need
    if slack < SLACK_MIN:
        verdict = "CRAMPED"
    elif slack > SLACK_MAX:
        verdict = "EXCESS WHITESPACE"
    else:
        verdict = "ok"
    print(f"    {cid:14} box {have:>4.0f}px  text ~{need:>4.0f}px  slack {slack:>4.0f}px  {verdict}")
    if verdict != "ok":
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

# A squashed logo is a subtle, permanent embarrassment. Hold the rendered box to
# the artwork's own viewBox ratio rather than trusting draw.io's aspect flag.
vb = (SVG / "flickr-mark-tight.svg").read_text(encoding="utf-8")
vw, vh = (float(v) for v in re.search(r'viewBox="\S+ \S+ (\S+) (\S+)"', vb).groups())
skew = abs((lw / lh) - (vw / vh)) / (vw / vh)
print(f"    aspect {lw / lh:.3f} vs artwork {vw / vh:.3f}  ({skew * 100:.1f}% distortion)")
if skew > 0.01:
    print("    -> mark is visibly stretched")
    problems += 1

# Centred under the card, not merely near the middle.
off = (lx + lw / 2) - (fx + fw / 2)
print(f"    centred in the Flickr card: off by {off:.1f}px")
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
BADGES = ["n1", "n2", "n3", "n4", "n5", "n6", "n7", "n8", "n9"]
TILES = ["dns", "pages", "secrets", "cron", "oauthdo", "api", "retry",
         "d1replica", "d1", "users", "flickrapi", "journey", "key", "justification"]


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
# ADR-03's four, since the consumer key and secret are only ever used as a pair.
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
    "api.flickrgroupaddr.com": "hostname",
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

if problems:
    raise SystemExit("Diagram geometry check failed -- fix the layout before committing.")
