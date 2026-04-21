"""MusicKit API client for reliable library and playlist writes.

Uses the public api.music.apple.com REST endpoints with a Developer Token
extracted from music.apple.com and a Music User Token from the same web
player. Both tokens live in a gitignored .env file at the repo root.

The web-player Developer Token's root_https_origin is pinned to apple.com,
so every request includes Origin and Referer headers to match. Without
those headers the API returns 401.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

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


def _request(
    method: str,
    path: str,
    *,
    query: Optional[dict] = None,
    body: Optional[dict] = None,
) -> tuple[int, dict]:
    dev, user = _credentials()
    url = f"{API_BASE}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query, doseq=True)}"
    data_bytes = None
    headers = {
        "Authorization": f"Bearer {dev}",
        "Music-User-Token": user,
        "Origin": ORIGIN,
        "Referer": REFERER,
        "Accept": "application/json",
    }
    if body is not None:
        data_bytes = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            raw = resp.read()
    except urllib.error.HTTPError as e:
        raw = e.read() if hasattr(e, "read") else b""
        status = e.code
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        payload = {"_raw": raw.decode("utf-8", errors="replace")}
    return status, payload


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


def add_song_to_library(catalog_song_id_or_url: str) -> dict:
    song_id = extract_catalog_song_id(catalog_song_id_or_url)
    status, payload = _request(
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


def list_library_playlists() -> list[dict]:
    out: list[dict] = []
    path = "/v1/me/library/playlists"
    query: Optional[dict] = {"limit": 100}
    while True:
        status, payload = _request("GET", path, query=query)
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


def find_library_playlist_id_by_name(name: str) -> Optional[str]:
    target = name.strip().lower()
    for p in list_library_playlists():
        pname = p.get("attributes", {}).get("name", "")
        if pname.strip().lower() == target:
            return p.get("id")
    return None


def add_catalog_song_to_playlist(
    catalog_song_id_or_url: str,
    playlist_id: str,
) -> dict:
    song_id = extract_catalog_song_id(catalog_song_id_or_url)
    status, payload = _request(
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
