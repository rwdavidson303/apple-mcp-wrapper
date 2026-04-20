"""Apple Music catalog search via the public iTunes Search API.

No authentication required. Returns track metadata including the
`trackViewUrl` which is the canonical Apple Music page URL for the track.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Optional

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"


def search(query: str, limit: int = 10, country: str = "us") -> list[dict]:
    """Search the Apple Music catalog.

    Parameters
    ----------
    query:
        Free-text search, typically "artist track-title".
    limit:
        Max results. iTunes Search API caps at 200.
    country:
        Two-letter ISO country code for the catalog storefront.

    Returns
    -------
    list of dicts with keys including: trackName, artistName, collectionName,
    trackViewUrl, previewUrl, trackId, artistId, collectionId, releaseDate.
    """
    params = {
        "term": query,
        "entity": "song",
        "limit": max(1, min(int(limit), 200)),
        "country": country,
    }
    url = f"{ITUNES_SEARCH_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.load(resp)
    return data.get("results", [])


def _normalize(s: str) -> str:
    return (
        s.lower()
        .replace(".", "")
        .replace("'", "")
        .replace("-", " ")
        .replace("(", "")
        .replace(")", "")
        .strip()
    )


def find_best_match(
    artist: str,
    title: str,
    limit: int = 10,
    country: str = "us",
) -> Optional[dict]:
    """Search for a specific artist + title and return the closest catalog match.

    Ranks matches by requiring the first token of each field to appear in the
    result's corresponding field (after loose normalization). Falls back to the
    top-ranked raw result if no strict match is found.
    """
    results = search(f"{artist} {title}", limit=limit, country=country)
    if not results:
        return None

    artist_tokens = _normalize(artist).split()
    title_tokens = _normalize(title).split()
    if not artist_tokens or not title_tokens:
        return results[0]

    artist_first = artist_tokens[0]
    title_first = title_tokens[0]

    for r in results:
        a = _normalize(r.get("artistName", ""))
        t = _normalize(r.get("trackName", ""))
        if artist_first in a and title_first in t:
            return r

    return results[0]


def canonical_url(result: dict) -> Optional[str]:
    """Extract a clean Apple Music URL from a search result, stripping query args."""
    url = result.get("trackViewUrl")
    if not url:
        return None
    return url.split("?")[0] + (
        f"?i={result['trackId']}" if result.get("trackId") else ""
    )
