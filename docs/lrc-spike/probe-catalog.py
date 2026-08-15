#!/usr/bin/env python3
"""Read a Lightroom Classic catalog directly, read-only, and report what a FGA
client would need from it.

WHY THIS EXISTS. On 2026-08-15 this answered, in about two minutes and without
launching Lightroom, whether Terry's catalog held Adobe's Flickr publish service
and whether its published photos carried Flickr photo ids. That is the
PRECONDITION for the Lua spike beside this file. It is NOT the premise the spike
measures -- reading SQLite proves the DATA exists, and proves nothing about
whether the SDK hands that data to a plug-in that did not create it.

SAFETY, and this is the part to read before running it.

  Opens with mode=ro AND immutable=1. `immutable=1` tells SQLite the file cannot
  change underneath it, so it takes NO locks and creates NO -wal, -shm or
  journal sidecar. Nothing is written and the original cannot be touched. That
  is what makes reading a 1.8 GB catalog acceptable without first copying it.

  `immutable=1` is a PROMISE THE CALLER MAKES, and it is false while Lightroom
  holds the file. This script refuses to run when Lightroom is up.

A NOTE ON A WRONG MEMORY THIS CORRECTS. A note once claimed the harness blocked
reading a `.lrcat`. It never did. `Copy-Item` on one was refused by the
permission classifier, and "copying was refused" became "reading is blocked"
with no test in between -- which left the whole investigation parked for a day
behind something that takes two minutes.

    python docs/lrc-spike/probe-catalog.py [path-to.lrcat]
"""

import pathlib
import re
import sqlite3
import subprocess
import sys
import urllib.parse

DEFAULT = pathlib.Path(r"C:\Photography\LR Catalog\TDO Lightroom Catalog.lrcat")


def lightroom_is_running() -> bool:
    """True if any Lightroom process is up. immutable=1 would be a lie then."""
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Lightroom.exe"],
            capture_output=True, text=True, timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return "Lightroom.exe" in out


def connect(catalog: pathlib.Path) -> sqlite3.Connection:
    uri = "file:" + urllib.parse.quote(catalog.as_posix()) + "?mode=ro&immutable=1"
    print(f"opening {uri}\n")
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    return con


def pass_1_shape(con: sqlite3.Connection) -> None:
    """Is this the real catalog, and which tables carry publish state?"""
    q = con.execute
    tables = [r[0] for r in q("SELECT name FROM sqlite_master WHERE type='table'")]
    print(f"tables: {len(tables)}")

    print("publish / remote / plugin tables:")
    for t in sorted(tables):
        if any(k in t for k in ("Publish", "Remote", "Plugin")):
            n = q(f"SELECT COUNT(*) AS n FROM [{t}]").fetchone()["n"]
            print(f"  {t:<48} {n:>8} rows")

    print("\nscale:")
    for t in ("Adobe_images", "AgLibraryFile", "AgLibraryCollection"):
        if t in tables:
            n = q(f"SELECT COUNT(*) AS n FROM [{t}]").fetchone()["n"]
            print(f"  {t:<28} {n:>9}")


def pass_2_services(con: sqlite3.Connection) -> None:
    """Which publish services exist, and do the remote ids look like Flickr?

    NOTE THE TRAP THIS PASS EXPOSED. `creationId` on the service row reads
    `com.adobe.ag.export.service.connection` -- a generic export-service marker,
    NOT the plug-in identity. The SDK's `service:getPluginId()` returns
    `com.adobe.lightroom.export.flickr` instead. Never predict the plug-in id
    from this column.
    """
    q = con.execute

    print("\ncreationId across published collections:")
    for r in q(
        "SELECT creationId, COUNT(*) AS n FROM AgLibraryPublishedCollection "
        "GROUP BY creationId ORDER BY n DESC"
    ):
        print(f"  {r['creationId']:<52} {r['n']:>4}")

    print("\npublish SERVICES (top-level, no parent):")
    for r in q(
        "SELECT id_local, creationId, name FROM AgLibraryPublishedCollection "
        "WHERE parent IS NULL ORDER BY name"
    ):
        print(f"  [{r['id_local']}] {r['creationId']}")
        print(f"        name={r['name']!r}")

    print("\nsample remote photos:")
    for r in q(
        "SELECT rp.remoteId, rp.url, pc.name AS collection "
        "FROM AgRemotePhoto rp "
        "LEFT JOIN AgLibraryPublishedCollection pc ON pc.id_local = rp.collection "
        "WHERE rp.remoteId IS NOT NULL ORDER BY rp.id_local LIMIT 3"
    ):
        print(f"  remoteId={r['remoteId']!r}")
        print(f"      url={r['url']!r}")
        print(f"      collection={r['collection']!r}")

    total = q("SELECT COUNT(*) AS n FROM AgRemotePhoto WHERE remoteId IS NOT NULL").fetchone()["n"]
    flickr = q("SELECT COUNT(*) AS n FROM AgRemotePhoto WHERE url LIKE '%flickr%'").fetchone()["n"]
    numeric = q(
        "SELECT COUNT(*) AS n FROM AgRemotePhoto "
        "WHERE remoteId GLOB '[0-9]*' AND length(remoteId) >= 8"
    ).fetchone()["n"]
    print(f"\n  remote photos with a remoteId              : {total}")
    print(f"  whose url mentions flickr                 : {flickr}")
    print(f"  remoteId looks like a Flickr id (8+ digits): {numeric}")


def pass_3_find(con: sqlite3.Connection, needle: str = "flickr") -> None:
    """Sweep EVERY text column in EVERY table for a keyword.

    This is the pass that found where plug-in identity actually lives, after
    `creationId` turned out not to carry it. Slow and indiscriminate on purpose:
    when a schema is unfamiliar, asking every column beats guessing the right
    one. It is how `AgPhotoPropertySpec.sourcePlugin` was found.
    """
    q = con.execute
    print(f"\ncolumns mentioning {needle!r}:")
    tables = [r["name"] for r in q("SELECT name FROM sqlite_master WHERE type='table'")]
    hits = 0
    for t in tables:
        for c in [r["name"] for r in q(f"PRAGMA table_info([{t}])")]:
            try:
                n = q(
                    f"SELECT COUNT(*) AS n FROM [{t}] "
                    f"WHERE CAST([{c}] AS TEXT) LIKE ?", (f"%{needle}%",)
                ).fetchone()["n"]
            except sqlite3.Error:
                continue
            if n:
                sample = q(
                    f"SELECT CAST([{c}] AS TEXT) AS v FROM [{t}] "
                    f"WHERE CAST([{c}] AS TEXT) LIKE ? LIMIT 1", (f"%{needle}%",)
                ).fetchone()["v"]
                flat = re.sub(r"\s+", " ", sample)[:120]
                print(f"  {t}.{c}: {n} rows, e.g. {flat!r}")
                hits += 1
    print(f"  -> {hits} column(s)")


def main() -> int:
    catalog = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT

    if not catalog.exists():
        print(f"catalog not found: {catalog}")
        return 1

    if lightroom_is_running():
        print("REFUSING TO RUN: Lightroom is open, so immutable=1 would be a lie.")
        return 1

    con = connect(catalog)
    try:
        pass_1_shape(con)
        pass_2_services(con)
        pass_3_find(con)
    finally:
        con.close()

    print("\nRead-only. Nothing was written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
