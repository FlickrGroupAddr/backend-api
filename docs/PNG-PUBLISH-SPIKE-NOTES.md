# Spike: can a Lightroom Classic plug-in publish PNG to Flickr?

**RFC 2119 keywords, and the capitals are load-bearing.** MUST and MUST NOT are absolute. SHOULD is
a strong default a good argument may overrule. MAY is optional.

**Terry, 2026-08-18.** He believes Adobe's bundled Flickr publish plug-in is JPEG only. He edits RAW
from a Canon R5, so even minimum-compression JPEG discards data he still holds, and he would rather
publish the render as PNG.

**The answer is YES on both halves, and his belief about Adobe's plug-in is correct.**

**Spiked 2026-08-18. Nothing was built and nothing was uploaded.**

---

## The two questions, answered separately

| Question | Answer |
|---|---|
| Does the LrC SDK let a publish service declare PNG? | **YES.** `PNG` is a documented member of `allowFileFormats` |
| Does Flickr accept PNG uploads? | **YES, and it keeps them AS PNG** |

### Adobe's sample really is JPEG only, and it is a CHOICE rather than a limit

`Sample Plugins/flickr.lrdevplugin/FlickrExportServiceProvider.lua`, from the vendored SDK 15.3:

```lua
exportServiceProvider.allowFileFormats = { 'JPEG' }
```

**That one line is the whole restriction.** The SDK's own reference documents the legal values for
the property, and PNG is among them:

> If present, this should be an array containing one or more of the following strings: **JPEG PSD
> PSB TIFF DNG PNG JXL AVIF ORIGINAL**

Read from `API Reference/modules/SDK - Export service provider.html` inside
`vendor/LrC_15.3_202604090947-8f3672ed.release_SDK.zip`, per `vendor/README.md`'s rule that the
archive is authoritative and the web mirrors are LR5-era.

**A plug-in MAY also force the format outright** rather than only restricting the menu.
`exportSettings.LR_format` is the export setting key, and the Flickr sample names it in a commented
example of `updateExportSettings`. So a publish service can pin PNG without the user choosing it.

### Flickr accepts PNG, and the parentheses are the important part

Flickr's own help page, *Flickr upload requirements*, updated one month before this spike:

> **Photo formats:** JPEG · PNG · GIF (non-animated) · TIFF (will be converted to & saved as a
> JPEG) · BMP (will be converted to & saved as a JPEG) · HEIF/HEIC (will be converted & saved as a
> JPEG) (Flickr app only)

**PNG and JPEG are the only two formats with no conversion note.** TIFF and BMP are accepted and
then thrown away — Flickr stores a JPEG.

**So PNG is not merely one lossless option. On Flickr it is the ONLY one.** JXL and AVIF are legal
in the SDK and Flickr does not list either. TIFF would look like it worked and would silently
deliver the exact loss Terry is trying to avoid. **That is the finding worth keeping**: the obvious
alternative fails in the one way nobody checks.

**RAW is not supported at all**, which independently rules out `ORIGINAL` as a format choice — and
`ORIGINAL` would have published the untouched CR3 and dropped every edit anyway.

### The real constraint is the 200 MB cap, and 16-bit PNG probably breaks it

Flickr's stated photo limits:

| | |
|---|---|
| Per photo | **200 MB** |
| RAW | Not supported |
| Aspect | No wider than **31.25x** its height, which can refuse a panorama |

**An R5 frame is 8192 x 5464, or 44,761,088 pixels.** Uncompressed RGB is therefore:

| Depth | Uncompressed | At 75-95% after PNG's filter and deflate |
|---|---|---|
| 8-bit | 128.1 MB | 96.0 - 121.7 MB — **fits** |
| 16-bit | 256.1 MB | 192.1 - 243.3 MB — **over the cap at anything but the best case** |

**These are ESTIMATES and MUST be replaced by a measurement before anybody relies on them.** PNG's
compression on photographic content is weak and varies with the image; a smooth sky compresses and
a forest does not. **The honest test is one real export of a real R5 frame at each depth.**

**The practical reading: 8-bit PNG is safe, 16-bit PNG is a coin flip.** That matters more than it
looks, because 16-bit is the reason to prefer PNG over JPEG in the first place — an 8-bit PNG and a
quality-100 JPEG hold the same 8 bits per channel, and the PNG's advantage narrows to the absence of
DCT artifacts.

---

## What this does NOT mean for FGA

**This is a SEPARATE plug-in from ours, and the distinction MUST NOT blur.** FGA's Lightroom client
queues group adds against photos Flickr already holds. It does not publish, it does not render, and
it does not upload a byte of image data. Nothing on the architecture diagram changes.

**So a PNG publish service is a second plug-in that happens to share a catalog**, not a feature of
the one being built. It is closer to a fork of Adobe's sample than to anything in `src/`.

**And the cross-plug-in premise already measured for FGA cuts both ways here.** A third-party
plug-in can enumerate Adobe's Flickr publish service and read `getRemoteId()` — see
`docs/LRC-CLIENT-NOTES.md`. **A PNG publish service would create its OWN publish service**, so its
photos would carry ITS remote ids, and FGA would have to enumerate both.

---

## If Terry says go

**Nothing here is built.** Recorded so the next session does not re-derive it.

- **Start from `Sample Plugins/flickr.lrdevplugin/`** in the vendored archive. It is Adobe's own
  reference implementation, it declares `LrSdkVersion = 3.0` from roughly 2010, and it still runs
  against 15.3.
- **Change `allowFileFormats` to `{ 'PNG' }`**, or leave the menu open and pin
  `exportSettings.LR_format` in `updateExportSettings`.
- **Measure one real R5 export at 8-bit and at 16-bit** before choosing a default. The table above
  is arithmetic, not evidence.
- **Decide what happens when a file exceeds 200 MB.** Flickr answers `error 8, Filesize was too
  large`. **ADR-01 applies to the retry question** — a size refusal is terminal and MUST NOT be
  retried into.
- **`flickr.people.getUploadStatus` reports the account's file and bandwidth limits**, per Flickr's
  upload API documentation, so a plug-in MAY check before rendering rather than after uploading.

## Sources

- The vendored SDK archive, per `vendor/README.md`: `API Reference/modules/SDK - Export service
  provider.html` and `Sample Plugins/flickr.lrdevplugin/FlickrExportServiceProvider.lua`.
- [Flickr upload requirements](https://www.flickrhelp.com/hc/en-us/articles/4404079649300-Flickr-upload-requirements)
  — read in a browser, because it answers `403` to a plain fetch.
- [Flickr upload API](https://www.flickr.com/services/api/upload.api.html) — error 5 *"Filetype was
  not recognised"*, error 8 *"Filesize was too large"*, and `flickr.people.getUploadStatus`. <!-- DIRTY-WORDS-EXEMPT: Flickr's own error string, quoted verbatim -->

