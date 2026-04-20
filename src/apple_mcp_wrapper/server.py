"""MCP server for apple-mcp-wrapper.

Exposes tools for searching the Apple Music catalog (beyond the local library)
and adding catalog tracks to user playlists via macOS UI scripting.
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
def add_catalog_track_to_playlist(url: str, playlist_name: str) -> dict:
    """Add an Apple Music catalog track to a named user playlist.

    Opens the URL in Music.app and UI-scripts the Song > Add to Playlist menu
    so the track is added to both your library and the target playlist.
    Requires Accessibility permission.

    Args:
        url: Apple Music catalog URL for the target track.
        playlist_name: Exact name of the destination user playlist.

    Returns:
        {"ok": bool, "message": str}
    """
    return automation.add_catalog_track_to_playlist(url, playlist_name)


@mcp.tool()
def bulk_add_catalog_tracks_to_playlist(
    tracks: list[dict], playlist_name: str
) -> list[dict]:
    """Add multiple catalog tracks to a playlist in sequence.

    Args:
        tracks: List of dicts. Each must contain at minimum a `url` key.
                Other keys (artist, title) are preserved in the result.
        playlist_name: Destination playlist name.

    Returns:
        List of result dicts, one per input track.
    """
    return automation.bulk_add(tracks=tracks, playlist_name=playlist_name)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
