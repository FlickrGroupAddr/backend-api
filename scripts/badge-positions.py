"""Where does a step badge go? Answer it from the ARTIFACT, never from recall.

    python scripts/badge-positions.py                 # every straight edge
    python scripts/badge-positions.py e20 e4          # just these
    python scripts/badge-positions.py --diameter 30   # try another size

**This exists because the same mistake happened twice on 2026-08-16, and both
times the arithmetic was flawless on a stale number.** A badge was placed 30 units
off, using the `/oauth` and `/api` line positions from before a layout shift; then
3.2 units off, using `lrcat`'s position from before it moved. Terry caught both by
eye. **A check would not have caught either**, because a check would have read the
coordinate from the same place the mistake did.

**So this reads the generated `.drawio` and prints paste-ready geometry.** Nothing
it reports can be stale, because it re-derives every number on every run.

**It models draw.io's attachment rules rather than assuming them**, which is the
part that makes the output trustworthy:

  * A fixed `exitX`/`exitY` is used LITERALLY only when `exitPerimeter=0`.
    Otherwise draw.io treats the fraction as a DIRECTION, casts a ray from the
    shape's center through it, and returns where that ray crosses the bounding
    RECTANGLE. `mxRectanglePerimeter` knows nothing about `arcSize`.
  * An edge with no fixed fraction attaches at the shape's center, then takes the
    same perimeter projection.

**It reports both sides of the line**, because which side a badge belongs on is a
judgment about what else is nearby, and this script cannot see crowding.

**Read-only. It never writes the diagram.**
"""

import argparse
import math
import pathlib
import re
import xml.etree.ElementTree as ET

from diagram_sheets import arch_dir, authored_diagram

ROOT = pathlib.Path(__file__).resolve().parent.parent
ARCH = arch_dir(ROOT)

# Matching the badges already on the canvas: 34 across, sitting 1.5 clear of a
# 3-unit arrow when placed beside the line rather than on it.
#
# **1.5 is TERRY'S number, not a round one.** He placed the `e20` badge by eye and
# called it a tight lockup; the tool defaulted to 3 and disagreed by 1.5 units.
# **His eye is the reference here, so the default was moved to match him** rather
# than the other way round. Same reasoning as the logo gap: a band that argues with
# the approved render is the band that is wrong.
DEFAULT_DIAMETER = 34.0
DEFAULT_GAP = 1.5
ARROW_STROKE = 3.0


def newest_diagram() -> pathlib.Path:
    """The AUTHORED sheet, which is the only one whose coordinates are authored.

    **This one matters more than the two previews.** The output of this script is
    geometry Terry pastes back into `build-diagram.py`, and the other sheets hold
    the same drawing translated. Reading one of those would hand back numbers
    offset by tens of units, and they would look entirely plausible.
    """
    return authored_diagram(ROOT)


def perimeter_point(bounds: tuple[float, float, float, float],
                    pt: tuple[float, float]) -> tuple[float, float]:
    """Where the ray from the shape's center through `pt` crosses its bounds.

    This is `mxRectanglePerimeter`, and reproducing it is the whole point: it is
    what draw.io actually draws when `exitPerimeter` is left at its default of 1.
    """
    x, y, w, h = bounds
    cx, cy = x + w / 2.0, y + h / 2.0
    dx, dy = pt[0] - cx, pt[1] - cy
    if dx == 0.0 and dy == 0.0:
        return cx, cy
    if dx == 0.0:
        return cx, cy + (h / 2.0) * (1 if dy > 0 else -1)
    if dy == 0.0:
        return cx + (w / 2.0) * (1 if dx > 0 else -1), cy
    t = min((w / 2.0) / abs(dx), (h / 2.0) / abs(dy))
    return cx + dx * t, cy + dy * t


def endpoint(bounds: tuple[float, float, float, float], style: str,
             prefix: str) -> tuple[float, float]:
    """The point draw.io puts this end of the edge at."""
    x, y, w, h = bounds
    fx = re.search(rf"(?<!\w){prefix}X=([\d.]+)", style)
    fy = re.search(rf"(?<!\w){prefix}Y=([\d.]+)", style)
    literal = re.search(rf"{prefix}Perimeter=0", style) is not None
    if fx and fy:
        pt = (x + float(fx.group(1)) * w, y + float(fy.group(1)) * h)
        # **The flag is the whole difference.** Without it the fraction is only a
        # direction, and the point lands back on the bounding rectangle.
        return pt if literal else perimeter_point(bounds, pt)
    return perimeter_point(bounds, (x + w / 2.0, y + h / 2.0))


def load(path: pathlib.Path) -> tuple[dict[str, tuple[float, float, float, float]],
                                     list[ET.Element]]:
    root = ET.parse(path).getroot()
    cells = root.findall(".//mxCell")
    boxes, edges = {}, []
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
    return boxes, edges


def report(cell: ET.Element,
           boxes: dict[str, tuple[float, float, float, float]],
           diameter: float, gap: float) -> dict[str, object] | None:
    style = cell.get("style") or ""
    src, tgt = cell.get("source"), cell.get("target")
    if src not in boxes or tgt not in boxes:
        return None
    routed = "orthogonalEdgeStyle" in style
    p = endpoint(boxes[src], style, "exit")
    q = endpoint(boxes[tgt], style, "entry")
    length = math.hypot(q[0] - p[0], q[1] - p[1])
    mid = ((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0)

    r = diameter / 2.0
    # Beside the line: perpendicular to it, far enough to clear half the arrow's
    # own stroke plus the badge's radius plus the gap.
    ux, uy = (q[0] - p[0]) / length, (q[1] - p[1]) / length
    off = r + gap + ARROW_STROKE / 2.0
    side_a = (mid[0] - uy * off, mid[1] + ux * off)
    side_b = (mid[0] + uy * off, mid[1] - ux * off)

    return {
        "id": cell.get("id"), "src": src, "tgt": tgt, "routed": routed,
        "p": p, "q": q, "length": length, "mid": mid,
        "side_a": side_a, "side_b": side_b, "r": r,
    }


def geom(center: tuple[float, float], diameter: float) -> str:
    return (f'<mxGeometry x="{center[0] - diameter/2:g}" '
            f'y="{center[1] - diameter/2:g}" '
            f'width="{diameter:g}" height="{diameter:g}" as="geometry" />')


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("edges", nargs="*", help="Edge ids. Omit for all of them.")
    ap.add_argument("--diameter", type=float, default=DEFAULT_DIAMETER)
    ap.add_argument("--gap", type=float, default=DEFAULT_GAP,
                    help="Clear space between the arrow and a beside-the-line badge.")
    args = ap.parse_args()

    target = newest_diagram()
    boxes, edges = load(target)
    print(f"{target.name}, badge diameter {args.diameter:g}\n")

    wanted = set(args.edges)
    rows = []
    for cell in edges:
        if wanted and cell.get("id") not in wanted:
            continue
        row = report(cell, boxes, args.diameter, args.gap)
        if row:
            rows.append(row)

    if not rows:
        raise SystemExit("No matching edges. A typo in an edge id reports nothing.")

    for row in sorted(rows, key=lambda r: r["length"]):
        covered = args.diameter / row["length"] * 100.0
        warn = "  <-- badge covers most of the run" if covered > 55 else ""
        note = "  ROUTED: endpoints ignore waypoints" if row["routed"] else ""
        print(f"{row['id']}  {row['src']} -> {row['tgt']}{note}")
        print(f"  run     {row['p'][0]:.1f},{row['p'][1]:.1f} -> "
              f"{row['q'][0]:.1f},{row['q'][1]:.1f}   length {row['length']:.1f}"
              f"   badge covers {covered:.0f}%{warn}")
        print(f"  on line   {geom(row['mid'], args.diameter)}")
        print(f"  beside A  {geom(row['side_a'], args.diameter)}")
        print(f"  beside B  {geom(row['side_b'], args.diameter)}")
        print()
