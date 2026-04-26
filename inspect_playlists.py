"""Read current contents of 'Damn…That's Strong' and 'Blues You Can Use'."""
from __future__ import annotations
import asyncio
import json
import urllib.parse
from apple_mcp_wrapper import musickit


async def fetch_tracks(playlist_id: str) -> list[dict]:
    status, payload = await musickit._request(
        "GET",
        f"/v1/me/library/playlists/{playlist_id}",
        query={"include": "tracks"},
    )
    if status != 200:
        raise RuntimeError(f"GET playlist failed: {status} {payload}")
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
    out = []
    for t in tracks:
        a = t.get("attributes", {})
        out.append({
            "name": a.get("name", ""),
            "artist": a.get("artistName", ""),
            "album": a.get("albumName", ""),
        })
    return out


async def main() -> None:
    targets = {
        "Damn…That's Strong": "p.rQ0RUMKQ5d7",
        "Blues You Can Use": "p.9BVPiP1ak2A",
    }
    for name, pid in targets.items():
        print(f"\n=== {name} (id {pid}) ===")
        tracks = await fetch_tracks(pid)
        print(f"{len(tracks)} tracks\n")
        for i, t in enumerate(tracks, 1):
            print(f"  {i:3d}. {t['artist']} - {t['name']}  [{t['album']}]")


if __name__ == "__main__":
    asyncio.run(main())
