"""Apple Music catalog search.

Primary path uses MusicKit's /v1/catalog/{storefront}/search (full catalog,
requires auth). The iTunes Search API `search()` helper is kept as a
no-auth fallback, but `find_best_match()` now uses MusicKit exclusively
and enforces a title-similarity check so it returns None instead of an
unrelated song when the requested track isn't found.
"""
from __future__ import annotations

import difflib
import json
import urllib.parse
import urllib.request
from typing import Optional

from . import musickit

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
    s = s.lower()
    for ch in "'’`":
        s = s.replace(ch, "")
    for ch in ".,;:!?/()[]{}\"":
        s = s.replace(ch, " ")
    s = s.replace("-", " ").replace("&", "and")
    return " ".join(s.split())


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


_TITLE_SIM_THRESHOLD = 0.72


def _title_similar(target: str, candidate: str) -> bool:
    """True if candidate title is plausibly the same song as target.

    Rules:
      1. Identical normalized forms: pass.
      2. SequenceMatcher ratio >= 0.72: pass (catches spelling variants
         like Freddie's/Freddy's, case/punctuation differences).
      3. Substring match: pass only if the shorter normalized string is
         at least 7 chars and contains at least 2 words. This prevents
         single-word substrings like "You" matching "Who Is He (And What
         Is He to You)".
      4. Otherwise: fail.
    """
    a = _normalize(target)
    b = _normalize(candidate)
    if not a or not b:
        return False
    if a == b:
        return True
    if difflib.SequenceMatcher(None, a, b).ratio() >= _TITLE_SIM_THRESHOLD:
        return True
    if a in b or b in a:
        shorter = a if len(a) < len(b) else b
        if len(shorter) >= 7 and len(shorter.split()) >= 2:
            return True
    return False


def _song_to_legacy_shape(r: dict) -> dict:
    """Return a MusicKit song resource in the iTunes-Search-API-style dict
    keys that the rest of this codebase already consumes."""
    a = r.get("attributes", {})
    return {
        "trackName": a.get("name", ""),
        "artistName": a.get("artistName", ""),
        "collectionName": a.get("albumName", ""),
        "trackViewUrl": a.get("url", ""),
        "trackId": r.get("id", ""),
        "previewUrl": (a.get("previews") or [{}])[0].get("url", ""),
    }


def find_best_match(
    artist: str,
    title: str,
    limit: int = 25,
    country: str = "us",
) -> Optional[dict]:
    """Search the Apple Music catalog for a specific artist + title.

    Requires that the returned song's title is plausibly similar to the
    requested title. If no result passes the similarity check, returns
    None (rather than a random song by the same artist, which is what
    the previous iTunes-Search-API-based matcher did).

    Preference tiers (within titles that pass similarity):
      1. Exact normalized artist match, non-compilation album, exact title.
      2. Exact normalized artist match, non-compilation album.
      3. Exact normalized artist match, compilation ok.
      4. Artist first-token contained in result's artistName, non-compilation.
      5. Top remaining viable result.
    """
    results = musickit.catalog_search_songs(
        f"{artist} {title}", limit=limit, storefront=country
    )
    if not results:
        return None

    viable = [
        r
        for r in results
        if _title_similar(title, r.get("attributes", {}).get("name", ""))
    ]
    if not viable:
        return None

    artist_n = _normalize(artist)
    artist_tokens = [t for t in artist_n.split() if t not in {"the", "and"}]
    title_n = _normalize(title)

    def is_compilation(r: dict) -> bool:
        coll = r.get("attributes", {}).get("albumName", "").lower()
        return any(h in coll for h in _COMPILATION_HINTS)

    def artist_matches_exactly(r: dict) -> bool:
        return _normalize(r.get("attributes", {}).get("artistName", "")) == artist_n

    def artist_overlap(r: dict) -> bool:
        if not artist_tokens:
            return False
        a = _normalize(r.get("attributes", {}).get("artistName", ""))
        a_tokens = set(a.split())
        return any(t in a_tokens for t in artist_tokens)

    def title_matches_exactly(r: dict) -> bool:
        return _normalize(r.get("attributes", {}).get("name", "")) == title_n

    def has_version_suffix(r: dict) -> bool:
        """Catches '(Live)', '(Remix)', '(Extended)', '(Album Version)', etc."""
        name_n = _normalize(r.get("attributes", {}).get("name", ""))
        return any(
            marker in name_n
            for marker in (
                " live",
                " remix",
                " extended",
                " instrumental",
                " acoustic",
                " demo",
                " karaoke",
                " edit",
                " re recorded",
                " rerecorded",
                " remastered",
                " mono",
            )
        )

    def rank_within_tier(r: dict) -> tuple:
        # Sort ascending: lower = better. Prefer exact title, non-version,
        # non-compilation, then shorter title (as a tiebreaker for picking
        # the canonical studio cut over extended/mixed versions).
        return (
            0 if title_matches_exactly(r) else 1,
            1 if has_version_suffix(r) else 0,
            1 if is_compilation(r) else 0,
            len(r.get("attributes", {}).get("name", "")),
        )

    tier1 = [r for r in viable if artist_matches_exactly(r)]
    if tier1:
        return _song_to_legacy_shape(min(tier1, key=rank_within_tier))

    tier2 = [r for r in viable if artist_overlap(r)]
    if tier2:
        return _song_to_legacy_shape(min(tier2, key=rank_within_tier))

    # No artist overlap anywhere: safer to return None than a random same-title
    # song by a different artist.
    return None


def canonical_url(result: dict) -> Optional[str]:
    """Extract a clean Apple Music URL from a search result, stripping query args."""
    url = result.get("trackViewUrl")
    if not url:
        return None
    base = url.split("?")[0]
    tid = result.get("trackId")
    return base + (f"?i={tid}" if tid else "")
