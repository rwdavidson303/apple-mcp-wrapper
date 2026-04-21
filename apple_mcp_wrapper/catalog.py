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


_COMPILATION_HINTS = (
    "various artists",
    "deeply rooted",
    "now that's what i call",
    "greatest slow jams",
    "ultimate r&b",
    "100 greatest",
    "love songs collection",
    "hits collection",
    "essential r&b",
    "the best of r&b",
)


def find_best_match(
    artist: str,
    title: str,
    limit: int = 25,
    country: str = "us",
) -> Optional[dict]:
    """Search for a specific artist + title and return the closest catalog match.

    Preference tiers:
      1. Exact artist match (case/punctuation-insensitive), not a compilation.
      2. Exact artist match, compilation ok.
      3. Artist first-token present in result's artistName, not a compilation.
      4. Fallback: top raw result.

    Within a tier, prefer the shortest track title (to avoid live / extended /
    remix cuts when the canonical studio version exists).
    """
    results = search(f"{artist} {title}", limit=limit, country=country)
    if not results:
        return None

    artist_n = _normalize(artist)
    artist_tokens = artist_n.split()
    if not artist_tokens:
        return results[0]
    artist_first = artist_tokens[0]

    def is_compilation(r: dict) -> bool:
        coll = r.get("collectionName", "").lower()
        return any(h in coll for h in _COMPILATION_HINTS)

    def artist_matches_exactly(r: dict) -> bool:
        return _normalize(r.get("artistName", "")) == artist_n

    def artist_contains(r: dict) -> bool:
        a = _normalize(r.get("artistName", ""))
        return artist_first in a

    def shortest(rs: list[dict]) -> Optional[dict]:
        if not rs:
            return None
        return min(rs, key=lambda r: len(r.get("trackName", "")))

    tier1 = [r for r in results if artist_matches_exactly(r) and not is_compilation(r)]
    if tier1:
        return shortest(tier1)

    tier2 = [r for r in results if artist_matches_exactly(r)]
    if tier2:
        return shortest(tier2)

    tier3 = [r for r in results if artist_contains(r) and not is_compilation(r)]
    if tier3:
        return shortest(tier3)

    return results[0]


def canonical_url(result: dict) -> Optional[str]:
    """Extract a clean Apple Music URL from a search result, stripping query args."""
    url = result.get("trackViewUrl")
    if not url:
        return None
    return url.split("?")[0] + (
        f"?i={result['trackId']}" if result.get("trackId") else ""
    )
