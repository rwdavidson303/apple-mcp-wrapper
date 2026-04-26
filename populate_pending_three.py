"""Populate the three pending playlists from their *_targets.json files.

Resolves each target via MusicKit catalog (with iTunes Search fallback if
strict matcher returns None), dedupes against existing playlist contents,
and adds via the MusicKit REST API. Supports --dry-run.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.parse
from pathlib import Path

from apple_mcp_wrapper import catalog, musickit


PROJECT_ROOT = Path(__file__).parent
TARGET_FILES = [
    "damn_thats_strong_targets.json",
    "blues_you_can_use_targets.json",
    "bluessoul_targets.json",
]


def _norm(s: str) -> str:
    return (
        s.lower()
        .replace("&", "and")
        .replace(".", "")
        .replace("'", "")
        .replace("’", "")
        .replace("-", " ")
        .replace("(", "")
        .replace(")", "")
        .replace(",", "")
        .strip()
    )


async def load_existing(playlist_id: str) -> tuple[set[str], set[tuple[str, str]]]:
    status, payload = await musickit._request(
        "GET",
        f"/v1/me/library/playlists/{playlist_id}",
        query={"include": "tracks"},
    )
    if status != 200:
        raise RuntimeError(f"GET {playlist_id} -> {status} {payload}")
    rels = payload.get("data", [{}])[0].get("relationships", {}).get("tracks", {})
    tracks = list(rels.get("data", []))
    nxt = rels.get("next")
    while nxt:
        p = urllib.parse.urlparse(nxt)
        s, py = await musickit._request(
            "GET", p.path, query=dict(urllib.parse.parse_qsl(p.query))
        )
        if s != 200:
            break
        tracks.extend(py.get("data", []))
        nxt = py.get("next")
    cids: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    for t in tracks:
        a = t.get("attributes", {})
        nm, ar = a.get("name", ""), a.get("artistName", "")
        if nm and ar:
            pairs.add((_norm(ar), _norm(nm)))
        cid = a.get("playParams", {}).get("catalogId")
        if cid:
            cids.add(str(cid))
    return cids, pairs


async def resolve_track(artist: str, title: str) -> dict | None:
    """Try strict matcher first, fall back to iTunes Search."""
    m = await catalog.find_best_match(artist, title)
    if m and m.get("trackId"):
        return m
    # Fallback: free-text search via iTunes API
    results = await catalog.search(f"{artist} {title}", limit=10)
    if not results:
        return None
    a_norm = _norm(artist)
    t_norm = _norm(title)
    a_first = a_norm.split()[0] if a_norm.split() else ""
    t_first = t_norm.split()[0] if t_norm.split() else ""
    for r in results:
        ra = _norm(r.get("artistName", ""))
        rt = _norm(r.get("trackName", ""))
        if a_first and a_first in ra and t_first and t_first in rt:
            return r
    return None


async def process_playlist(spec: dict, dry_run: bool) -> dict:
    playlist_name = spec["playlist_name"]
    playlist_id = spec["playlist_id"]
    targets = spec["targets"]
    print(f"\n{'='*72}\n{playlist_name}  (id {playlist_id})  -- {len(targets)} targets\n{'='*72}")
    existing_cids, existing_pairs = await load_existing(playlist_id)
    print(f"Existing tracks in playlist: {len(existing_pairs)}")
    summary: dict[str, list[str]] = {
        "added": [],
        "would-add": [],
        "already-in-playlist": [],
        "no-catalog-match": [],
        "playlist-add-failed": [],
        "library-add-failed": [],
        "exception": [],
    }
    for i, (artist, title) in enumerate(targets, 1):
        label = f"{artist} - {title}"
        print(f"[{i:3d}/{len(targets)}] {label}")
        try:
            match = await resolve_track(artist, title)
            if not match:
                summary["no-catalog-match"].append(label)
                print("    -> no-catalog-match")
                continue
            cid = str(match.get("trackId"))
            ra = match.get("artistName", "")
            rt = match.get("trackName", "")
            pair = (_norm(ra), _norm(rt))
            note = ""
            if rt and rt.lower() != title.lower():
                note += f"  [resolved: {rt}]"
            if ra and ra.lower() != artist.lower():
                note += f"  [by: {ra}]"
            if cid in existing_cids or pair in existing_pairs:
                summary["already-in-playlist"].append(label + note)
                print(f"    -> already-in-playlist{note}")
                continue
            if dry_run:
                existing_cids.add(cid)
                existing_pairs.add(pair)
                summary["would-add"].append(label + note)
                print(f"    -> would-add{note}")
                continue
            lib = await musickit.add_song_to_library(cid)
            if not lib.get("ok"):
                summary["library-add-failed"].append(
                    f"{label} (cid {cid})  status={lib.get('status')}"
                )
                print(f"    -> library-add-failed status={lib.get('status')}")
                continue
            pl = await musickit.add_catalog_song_to_playlist(cid, playlist_id)
            if not pl.get("ok"):
                summary["playlist-add-failed"].append(
                    f"{label} (cid {cid})  status={pl.get('status')}"
                )
                print(f"    -> playlist-add-failed status={pl.get('status')}")
                continue
            existing_cids.add(cid)
            existing_pairs.add(pair)
            summary["added"].append(label + note)
            print(f"    -> added{note}")
        except Exception as e:
            summary["exception"].append(f"{label}  [{e}]")
            print(f"    -> exception: {e}")
        await asyncio.sleep(0.18)
    return summary


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    grand: dict[str, dict] = {}
    for fname in TARGET_FILES:
        path = PROJECT_ROOT / fname
        if not path.exists():
            print(f"!! missing {fname}, skipping")
            continue
        spec = json.loads(path.read_text())
        if not spec.get("targets"):
            print(f"\n{spec.get('playlist_name', fname)}: no targets in file, skipping")
            continue
        grand[spec["playlist_name"]] = await process_playlist(spec, args.dry_run)

    print(f"\n{'='*72}\nGRAND SUMMARY\n{'='*72}")
    for pname, s in grand.items():
        print(f"\n--- {pname} ---")
        for status, items in s.items():
            if items:
                print(f"  {status}: {len(items)}")
                for it in items:
                    print(f"     - {it}")


if __name__ == "__main__":
    asyncio.run(main())
