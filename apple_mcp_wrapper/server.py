"""MCP server for apple-mcp-wrapper.

Exposes tools for searching the Apple Music catalog (beyond the local library)
and adding catalog tracks to the library via macOS UI scripting. Playlist
adds are intentionally delegated to the existing apple-music MCP
(`manage_playlist` with action=add_track), which handles library tracks
cleanly once this wrapper has placed the track there.
"""
from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from . import automation, catalog

mcp = FastMCP("apple-mcp-wrapper")


@mcp.tool()
def catalog_search(query: str, limit: int = 10, country: str = "us") -> list[dict]:
    """Search the Apple Music catalog (not your library) via the iTunes Search API.

    Args:
        query: Free-text search, typically "artist track-title".
        limit: Max results to return (1-200).
        country: Two-letter ISO country code for the storefront.

    Returns:
        A list of track metadata dicts with fields including trackName,
        artistName, collectionName, trackViewUrl, previewUrl, trackId.
    """
    return catalog.search(query=query, limit=limit, country=country)


@mcp.tool()
def catalog_find_best_match(
    artist: str,
    title: str,
    limit: int = 10,
    country: str = "us",
) -> Optional[dict]:
    """Find the best Apple Music catalog match for a specific artist + title.

    Args:
        artist: Artist name, e.g. "Clarence Carter".
        title: Track title, e.g. "Patches".
        limit: Max candidates to consider.
        country: Storefront code.

    Returns:
        The best match result dict, or None if no catalog results were found.
    """
    return catalog.find_best_match(
        artist=artist, title=title, limit=limit, country=country
    )


@mcp.tool()
def open_catalog_url(url: str) -> dict:
    """Open an Apple Music catalog URL in Music.app.

    Accepts https://music.apple.com/... URLs; rewrites to itmss:// for
    reliable navigation. Does not add the track to anything.

    Args:
        url: An Apple Music catalog URL.
    """
    automation.open_catalog_url(url)
    return {"ok": True, "opened": url}


@mcp.tool()
def is_track_in_library(track_name: str, artist: Optional[str] = None) -> dict:
    """Check whether a track is already in the user's Music library.

    Args:
        track_name: Exact track title.
        artist: Optional artist name to narrow the match.
    """
    return {"in_library": automation.is_track_in_library(track_name, artist)}


@mcp.tool()
def add_catalog_track_to_library(
    url: str,
    track_name: str,
    artist: Optional[str] = None,
    wait_seconds: float = 4.0,
    skip_if_in_library: bool = True,
) -> dict:
    """Add an Apple Music catalog track to the user's library via UI scripting.

    Opens the catalog URL in Music.app, locates the track row in the album
    view's Accessibility tree, clicks its More (...) button, then uses
    type-ahead ("add" + Return) to activate "Add to Library". Requires
    Accessibility permission for the process running this MCP server.

    After the track is in the library, use the existing apple-music MCP's
    `manage_playlist` (action=add_track) tool to place it in any user playlist.

    Args:
        url: Apple Music catalog URL.
        track_name: Exact track title as Music displays it.
        artist: Optional artist name (tightens duplicate detection).
        wait_seconds: Time to wait for the album page to load.
        skip_if_in_library: If True, skip the UI flow when the track is
            already in the library.

    Returns:
        {"ok": bool, "message": str, "already_in_library": bool (optional)}
    """
    return automation.add_catalog_track_to_library(
        url=url,
        track_name=track_name,
        artist=artist,
        wait_seconds=wait_seconds,
        skip_if_in_library=skip_if_in_library,
    )


@mcp.tool()
def bulk_add_catalog_tracks_to_library(tracks: list[dict]) -> list[dict]:
    """Add multiple catalog tracks to the library in sequence.

    Args:
        tracks: List of dicts. Each must contain `url` and `track_name`
                (or `title`). `artist` is optional but recommended.

    Returns:
        List of result dicts, one per input track.
    """
    return automation.bulk_add_catalog_tracks_to_library(tracks)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
