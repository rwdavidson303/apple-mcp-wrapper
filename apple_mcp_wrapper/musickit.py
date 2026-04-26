"""MusicKit API client for reliable library and playlist writes.

Uses the public api.music.apple.com REST endpoints with a Developer Token
extracted from music.apple.com and a Music User Token from the same web
player. Both tokens live in a gitignored .env file at the repo root.

The web-player Developer Token's root_https_origin is pinned to apple.com,
so every request includes Origin and Referer headers to match. Without
those headers the API returns 401.

All HTTP calls are async (httpx.AsyncClient) so asyncio cancellation
propagates correctly. Sync urllib calls used to block FastMCP threadpool
workers, leaving in-flight requests running after a user-cancel and
killing the stdio transport with late responses.
"""
from __future__ import annotations

import asyncio
import os
import urllib.parse
from pathlib import Path
from typing import Optional

import httpx

API_BASE = "https://api.music.apple.com"
ORIGIN = "https://music.apple.com"
REFERER = "https://music.apple.com/"

_CREDS_CACHE: dict[str, str] | None = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _credentials() -> tuple[str, str]:
    global _CREDS_CACHE
    if _CREDS_CACHE is None:
        env_path = _repo_root() / ".env"
        file_vals = _load_env_file(env_path)
        _CREDS_CACHE = {
            "dev": os.environ.get("MUSICKIT_DEVELOPER_TOKEN")
            or file_vals.get("MUSICKIT_DEVELOPER_TOKEN", ""),
            "user": os.environ.get("MUSICKIT_USER_TOKEN")
            or file_vals.get("MUSICKIT_USER_TOKEN", ""),
        }
    dev = _CREDS_CACHE["dev"]
    user = _CREDS_CACHE["user"]
    if not dev or dev.startswith("PASTE_"):
        raise RuntimeError(
            "MUSICKIT_DEVELOPER_TOKEN is not set. Paste it into .env "
            "or export it as an environment variable."
        )
    if not user or user.startswith("PASTE_"):
        raise RuntimeError(
            "MUSICKIT_USER_TOKEN is not set. Paste it into .env "
            "or export it as an environment variable."
        )
    return dev, user


async def _request(
    method: str,
    path: str,
    *,
    query: Optional[dict] = None,
    body: Optional[dict] = None,
) -> tuple[int, dict]:
    dev, user = _credentials()
    headers = {
        "Authorization": f"Bearer {dev}",
        "Music-User-Token": user,
        "Origin": ORIGIN,
        "Referer": REFERER,
        "Accept": "application/json",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    async with httpx.AsyncClient(base_url=API_BASE, timeout=15.0) as client:
        resp = await client.request(
            method,
            path,
            params=query,
            json=body,
            headers=headers,
        )
    try:
        payload = resp.json() if resp.content else {}
    except ValueError:
        payload = {"_raw": resp.text}
    return resp.status_code, payload


def extract_catalog_song_id(url_or_id: str) -> str:
    """Return a bare catalog song ID given a Music URL or an ID string.

    Accepts:
      - https://music.apple.com/us/album/foo/12345?i=67890  -> 67890
      - https://music.apple.com/us/song/foo/67890           -> 67890
      - itmss://... variants                                 -> 67890
      - "67890"                                              -> 67890
    """
    s = url_or_id.strip()
    if s.isdigit():
        return s
    parsed = urllib.parse.urlparse(s)
    qs = urllib.parse.parse_qs(parsed.query)
    if "i" in qs and qs["i"]:
        return qs["i"][0]
    segments = [seg for seg in parsed.path.split("/") if seg]
    for seg in reversed(segments):
        if seg.isdigit():
            return seg
    raise ValueError(f"Could not extract catalog song ID from: {url_or_id!r}")


async def catalog_search_songs(
    query: str,
    limit: int = 25,
    storefront: str = "us",
) -> list[dict]:
    """Search the Apple Music catalog for songs.

    Uses /v1/catalog/{storefront}/search?types=songs. Returns the raw
    song resources list (each with id, type, attributes.name, .artistName,
    .albumName, .url). Unlike the iTunes Search API, this indexes the full
    Apple Music catalog.

    Retries on 429 (rate limit) and 5xx with exponential backoff, since
    bulk runs can briefly exceed Apple's rate ceiling.
    """
    delays = [0.5, 1.5, 4.0]
    for delay in [0.0] + delays:
        if delay:
            await asyncio.sleep(delay)
        status, payload = await _request(
            "GET",
            f"/v1/catalog/{storefront}/search",
            query={"term": query, "types": "songs", "limit": max(1, min(int(limit), 25))},
        )
        if status == 200:
            return payload.get("results", {}).get("songs", {}).get("data", []) or []
        if status == 429 or 500 <= status < 600:
            continue
        return []
    return []


async def add_song_to_library(catalog_song_id_or_url: str) -> dict:
    song_id = extract_catalog_song_id(catalog_song_id_or_url)
    status, payload = await _request(
        "POST",
        "/v1/me/library",
        query={"ids[songs]": song_id},
    )
    ok = status in (200, 201, 202, 204)
    return {
        "ok": ok,
        "status": status,
        "catalog_song_id": song_id,
        "response": payload,
    }


async def list_library_playlists() -> list[dict]:
    out: list[dict] = []
    path = "/v1/me/library/playlists"
    query: Optional[dict] = {"limit": 100}
    while True:
        status, payload = await _request("GET", path, query=query)
        if status != 200:
            raise RuntimeError(
                f"list_library_playlists failed ({status}): {payload}"
            )
        out.extend(payload.get("data", []))
        nxt = payload.get("next")
        if not nxt:
            break
        parsed = urllib.parse.urlparse(nxt)
        path = parsed.path
        query = {k: v for k, v in urllib.parse.parse_qsl(parsed.query)}
    return out


async def find_library_playlist_id_by_name(name: str) -> Optional[str]:
    target = name.strip().lower()
    for p in await list_library_playlists():
        pname = p.get("attributes", {}).get("name", "")
        if pname.strip().lower() == target:
            return p.get("id")
    return None


async def add_catalog_song_to_playlist(
    catalog_song_id_or_url: str,
    playlist_id: str,
) -> dict:
    song_id = extract_catalog_song_id(catalog_song_id_or_url)
    status, payload = await _request(
        "POST",
        f"/v1/me/library/playlists/{playlist_id}/tracks",
        body={"data": [{"id": song_id, "type": "songs"}]},
    )
    ok = status in (200, 201, 202, 204)
    return {
        "ok": ok,
        "status": status,
        "catalog_song_id": song_id,
        "playlist_id": playlist_id,
        "response": payload,
    }
