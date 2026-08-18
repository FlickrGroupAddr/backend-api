# Where each step badge goes, and why

**RFC 2119 keywords, and the capitals are load-bearing.** MUST and MUST NOT are absolute. SHOULD is
a strong default a good argument may overrule.

**Terry placed all 32 badges by hand, against the centerlines and edges of other tiles.** Nothing in
the `.drawio` records that intent, so a later session moving a badge "to where it looks right" would
be destroying a rule it could not see. This file is that rule set, in his words, with the number the
artifact actually carries beside each one.

**Every figure below was measured from the generated diagram**, not copied from the request. Where a
rule is exact, the measurement matches it to the unit.

## The six shapes

**Almost every badge follows one of six patterns.** Read the pattern first; the per-badge table
below only says which one applies.

| Shape | Rule |
|---|---|
| **Corner pair** | Two badges sit in the opposite top corners of one tile, padded equally from the two sides AND the top |
| **Spread about a center** | A group sits on its line, evenly stepped, with the group's midpoint on a named tile's vertical centerline |
| **On a center** | A single badge sits on a named tile's vertical centerline |
| **Between two edges** | A badge sits on its line, centered between two named edges |
| **Stacked vertically** | Badges in different rows share one center x, so they line up down the page |
| **Clearance** | A badge is positioned relative to a conflicting element it has to fit around — an arrowhead, a frame edge |

**The corner padding is 8.00 units, in all four measurements, on all three tiles that use it** —
`lrc`, `devicedo` and `oauthdo`. Left gap, right gap and both top gaps are the same number, which is
what "padding from the edges" means. **That number is shared on purpose and MUST stay shared**;
three corner pairs drifting apart would read as carelessness.

**The build asserts all four gaps.** It used to assert only the horizontal pair, so a corner badge
could slide down inside its tile and nothing would notice.

## The badges

| Badges | Terry's rule | Measured |
|---|---|---|
| **1, 31** | Opposite top corners of the LrC Plugin tile, with padding from the edges | `lrc` spans 56.5 to 186.5. All four gaps 8.00 |
| **2, 7** | On their line, centered between the left of the Cloudflare tile and the left of the Edge PoP tile | `cfframe` left 231.5, `netb` left 261.5, midpoint **246.5**. Both badges sit on 246.5 |
| **3, 5** | On their line, spread equally about the center of the FGA DNS tile | Centers 333.7 and 403.7, midpoint **368.7** = `dns` center. Step 70.0 |
| **4, 28** | Opposite top corners of the Device Link User Code tile, with padding from the edges | `devicedo` spans 832.3 to 1001.3. All four gaps 8.00 |
| **6** | On its line, centered between the bottom of the LrC tile and the top of the widest part of the arrow below it | Center y 509.0. **The lower reference is the ARROWHEAD, not a tile**, so this one is not derivable from box geometry |
| **8, 9, 26** | On their line, spread equally about the center of the FGA DNS tile | Centers 298.7, 368.7, 438.7, midpoint **368.7**. Step 70.0 |
| **10, 15, 19, 25** | On their line, spread equally about the center of the FGA DNS tile | Centers 287.7 to 449.7, midpoint **368.7**. Step 54.0 |
| **11** | Breathing room from its line, vertically centered between the FGA Worker tile and the App Secrets Store tile | `api` bottom 682.7, `secrets` top 710.9, midpoint **696.8**. `n11` center y is 696.8 |
| **12, 13, 21, 22** | On their line, spread equally about the center of the Flickr OAuth State tile, within the span between the right of the Edge PoP and the right of the Cloudflare tile, with plenty of breathing room on both sides | Centers 829.8 to 1003.8, midpoint **916.8** = `oauthdo` center. Step 58.0 |
| **14, 20** | Opposite top corners of the Flickr OAuth State tile, with padding from the edges | `oauthdo` spans 832.3 to 1001.3. All four gaps 8.00 |
| **16, 17, 18** | On their line, spread equally about the center of the Nightly Retry Logic tile | Centers 549.9, 625.9, 701.9, midpoint **625.9** = `retry` center. Step 76.0 |
| **23, 24** | On their line, dodging overlap with the arrow ends and the right edge of the Edge PoP tile | Centers 789.0 and 814.1, straddling `netb`'s right edge at 804.1. **Fitted around a conflict** |
| **27** | On its line, aligned with the center of the FGA DNS tile | 368.7, exactly `dns` center |
| **29, 30** | On their line, spread equally about the center of the FGA DNS tile | Centers 333.7 and 403.7, midpoint **368.7**. Step 70.0 |
| **32** | On its line, aligned with the center of the FGA DNS tile | 368.7, exactly `dns` center |

## The vertical stacks

**Terry, 2026-08-17: *"or relative to something else: centerline of another tile, or stacked
vertically like the 3/5 and 29/30 pairs."*** So a badge can be positioned against another BADGE
rather than against a tile, and six groups do exactly that.

| Stack, top to bottom | Center x |
|---|---|
| 2 over 7 | 246.5 |
| 3 over 29 | 333.7 |
| 32 over 9 over 27 | 368.7 |
| 5 over 30 | 403.7 |
| 4 over 14 | 852.3 |
| 28 over 20 | 981.3 |

**This is why 3/5 and 29/30 share one step of 70.0 about the DNS center** — the two pairs are not
independently spread, they are one spread seen twice. **Changing the step for either pair breaks
both stacks.**

**Every stack sits inside a single column**, and the build asserts it. A stack straddling a column
boundary would come apart the moment a gap widened, because a column moves as one piece.

## What this means for the reflow

**A badge moves with the column its own center sits in, exactly like a tile.** That is what preserves
every rule above on the wider sheets, and it is not a coincidence: **each reference tile named in the
table is in the same column as the badges that point at it.** No rule reaches across a gap, so
widening a gap cannot break one.

**`scripts/build-diagram.py` defends EVERY rule in this file, on all three sheets.** The corner
padding, the even-step spreads and their midpoints, the on-axis badges, the between-edges pair, the
six vertical stacks, the centerline alignments and their pinned count. It also asserts that no badge
crosses an arrow it does not label, and that the journey and the canvas name the same routes.

**The three clearance placements are the only rules it cannot reach**, for the reason below.

## EVERY badge is relative to something. They differ in WHAT

**Terry, 2026-08-17: *"they're all relative to something, some are trying for consistent spacing or
fitting around conflicting elements."*** So none of these is arbitrary, and the useful split is not
rule-versus-judgment. It is what the reference IS.

| Relative to | Derivable from the file? | Badges |
|---|---|---|
| A tile's centerline or edge | **Yes** — box geometry carries it | Everything except the two rows below |
| Consistent spacing inside a group | **Yes** — an even step about a named center | The four spread groups |
| **A conflicting element it fits around** | **No** | 6, and 23 with 24 |

**The last row is the one that matters to a later session.** Badge 6's lower reference is *the widest
part of the arrow below it*, and an arrowhead is artwork rather than a rectangle — nothing in
`<mxGeometry>` describes it. Badges 23 and 24 fit around an arrow end and the Edge PoP's right
border, straddling it at 804.1.

**So those three cannot be recomputed, and MUST NOT be "corrected" toward a formula.** They are just
as deliberate as the rest; the thing they are measured against is simply not in the geometry. **Ask
Terry before moving one.**
