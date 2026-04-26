"""Read current contents of BluesSoul."""
from __future__ import annotations
import asyncio
import urllib.parse
from apple_mcp_wrapper import musickit


async def main() -> None:
    pid = "p.0YGWf0kAbWo"
    status, payload = await musickit._request(
        "GET",
        f"/v1/me/library/playlists/{pid}",
        query={"include": "tracks"},
    )
    if status != 200:
        raise SystemExit(f"GET failed: {status} {payload}")
    rels = payload.get("data", [{}])[0].get("relationships", {}).get("tracks", {})
    tracks = list(rels.get("data", []))
    nxt = rels.get("next")
    while nxt:
        p = urllib.parse.urlparse(nxt)
        s, py = await musickit._request("GET", p.path, query=dict(urllib.parse.parse_qsl(p.query)))
        if s != 200:
            break
        tracks.extend(py.get("data", []))
        nxt = py.get("next")
    print(f"BluesSoul: {len(tracks)} tracks\n")
    for i, t in enumerate(tracks, 1):
        a = t.get("attributes", {})
        print(f"  {i:3d}. {a.get('artistName','')} - {a.get('name','')}  [{a.get('albumName','')}]")


if __name__ == "__main__":
    asyncio.run(main())
