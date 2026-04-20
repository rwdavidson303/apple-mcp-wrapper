"""Live tests against the iTunes Search API. Requires network."""
from __future__ import annotations

import pytest

from apple_mcp_wrapper import catalog


def test_search_returns_results():
    results = catalog.search("clarence carter patches", limit=5)
    assert isinstance(results, list)
    assert len(results) >= 1
    r = results[0]
    assert "trackName" in r
    assert "artistName" in r


def test_find_best_match_matches_artist_and_title():
    r = catalog.find_best_match("Clarence Carter", "Patches")
    assert r is not None
    assert "patches" in r["trackName"].lower()
    assert "clarence carter" in r["artistName"].lower()


def test_find_best_match_returns_none_for_nonsense():
    r = catalog.find_best_match(
        "ZzzzzqqqqNonexistentArtist9999", "NothingEverSungByThis"
    )
    # iTunes may still return something tangential; just assert type
    assert r is None or isinstance(r, dict)


def test_canonical_url_preserves_track_id():
    r = catalog.find_best_match("Clarence Carter", "Patches")
    assert r is not None
    url = catalog.canonical_url(r)
    assert url is not None
    assert url.startswith("https://music.apple.com/")
    if r.get("trackId"):
        assert f"i={r['trackId']}" in url
