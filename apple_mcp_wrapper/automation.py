"""macOS AppleScript + UI scripting helpers for the Music app.

Accessibility permission is required for UI-scripting paths. Grant it via:
System Settings -> Privacy & Security -> Accessibility.

Working flow for adding catalog tracks to the library (verified on macOS 15 /
Music.app 1.5):

  1. `open itmss://music.apple.com/...` navigates Music to the album page.
     The `https://music.apple.com` scheme sometimes lands on Home instead.
  2. Walk the Accessibility tree to the track row whose AXDescription matches
     the target title. Track rows live under:
         window 1 > first AXSplitGroup > second AXScrollArea
           > first AXList (collection) > second AXList (section)
  3. Click the row's "More" (...) AXButton. The resulting popup menu is drawn
     with a native UI bit that does not appear in the Accessibility tree, so
     its items cannot be read or clicked by name.
  4. `keystroke "add"` triggers type-ahead on the invisible popup and lands
     focus on "Add to Library".
  5. Return activates it. The track is in the library.

Once the track is in the library, callers should use the standard apple-music
MCP (action=add_track on its `manage_playlist` tool) to drop it into any user
playlist. This module intentionally does not try to also add to a playlist;
that responsibility stays with the library-aware MCP.
"""
from __future__ import annotations

import subprocess
import time
from typing import Optional


def run_osascript(script: str, timeout: int = 30) -> str:
    """Run an AppleScript snippet and return stdout."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"osascript failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


def ensure_music_running() -> None:
    """Make sure Music.app is running with a visible window."""
    run_osascript(
        """
        tell application "Music"
            activate
            reopen
        end tell
        """
    )
    time.sleep(0.5)


def _to_itmss(url: str) -> str:
    if url.startswith("https://music.apple.com"):
        return "itmss://" + url[len("https://") :]
    return url


def open_catalog_url(url: str) -> None:
    """Open an Apple Music catalog URL in Music.app, preferring itmss://."""
    ensure_music_running()
    subprocess.run(["open", _to_itmss(url)], check=True)


def _as_str(s: str) -> str:
    """Escape a Python string as an AppleScript string literal."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def is_track_in_library(track_name: str, artist: Optional[str] = None) -> bool:
    """Check whether a track is already in the user's library."""
    name_lit = _as_str(track_name)
    if artist:
        artist_lit = _as_str(artist)
        where = f"name is {name_lit} and artist is {artist_lit}"
    else:
        where = f"name is {name_lit}"
    script = f"""
    tell application "Music"
        try
            set matches to (every track of library playlist 1 whose {where})
            return (count of matches) as string
        on error
            return "0"
        end try
    end tell
    """
    try:
        return int(run_osascript(script)) > 0
    except Exception:
        return False


def add_catalog_track_to_library(
    url: str,
    track_name: str,
    *,
    wait_seconds: float = 4.0,
    skip_if_in_library: bool = True,
    artist: Optional[str] = None,
) -> dict:
    """Add an Apple Music catalog track to the user's library via UI scripting.

    Parameters
    ----------
    url:
        Apple Music catalog URL. Converted to itmss:// automatically.
    track_name:
        Exact track title as Music displays it. Used to locate the track row
        in the album view's Accessibility tree via its AXDescription.
    wait_seconds:
        Time to wait for the catalog album page to load before looking for
        the track row. Default 4 seconds; raise for slow networks.
    skip_if_in_library:
        If True (default) and the track is already in the library, return
        early with ok=True and no UI activity.
    artist:
        Optional. Tightens the `skip_if_in_library` check; not required.

    Returns
    -------
    dict with keys:
      - ok (bool)
      - message (str)
      - already_in_library (bool, optional)
    """
    if skip_if_in_library and is_track_in_library(track_name, artist):
        return {
            "ok": True,
            "message": f"{track_name} already in library; skipped",
            "already_in_library": True,
        }

    open_catalog_url(url)
    time.sleep(wait_seconds)

    name_lit = _as_str(track_name)
    script = f"""
    tell application "Music" to activate
    delay 0.3
    tell application "System Events"
        tell (process "Music")
            set frontmost to true
            delay 0.3
            try
                set sg to first UI element of window 1 whose role is "AXSplitGroup"
                set mainSA to item 2 of (UI elements of sg whose role is "AXScrollArea")
                set coll to first UI element of mainSA whose role is "AXList"
                set sectionLists to (UI elements of coll whose role is "AXList")
                if (count of sectionLists) < 2 then return "err: track list section not found"
                set trackList to item 2 of sectionLists
                set targetRow to missing value
                set targetName to {name_lit}
                set rowDescsStr to ""
                ignoring case
                    repeat with aRow in (UI elements of trackList)
                        try
                            set rowDesc to description of aRow
                            set rowDescsStr to rowDescsStr & " | " & rowDesc
                            if rowDesc = targetName then
                                set targetRow to contents of aRow
                                exit repeat
                            end if
                        end try
                    end repeat
                end ignoring
                if targetRow is missing value then
                    ignoring case
                        repeat with aRow in (UI elements of trackList)
                            try
                                set rowDesc to description of aRow
                                if rowDesc contains targetName then
                                    set targetRow to contents of aRow
                                    exit repeat
                                end if
                                if targetName contains rowDesc and (count of rowDesc) > 4 then
                                    set targetRow to contents of aRow
                                    exit repeat
                                end if
                            end try
                        end repeat
                    end ignoring
                end if
                if targetRow is missing value then
                    return "err: row not found for " & targetName & " (rows:" & rowDescsStr & ")"
                end if
                set moreBtn to first UI element of targetRow whose role is "AXButton"
                click moreBtn
                delay 1.0
                keystroke "add"
                delay 0.4
                key code 36
                return "ok"
            on error errMsg
                try
                    key code 53
                end try
                return "err: " & errMsg
            end try
        end tell
    end tell
    """

    try:
        out = run_osascript(script, timeout=20)
    except Exception as e:
        return {"ok": False, "message": f"osascript exception: {e}"}

    if out.strip() != "ok":
        return {"ok": False, "message": out}

    # Give Music a moment to sync before confirming.
    time.sleep(1.2)
    if is_track_in_library(track_name, artist):
        return {"ok": True, "message": f"Added {track_name} to library"}
    return {
        "ok": False,
        "message": (
            "UI flow completed but track did not appear in library after sync. "
            "The type-ahead may have landed on a different item, or Music needs "
            "more time. Check manually and retry with a longer wait_seconds."
        ),
    }


def bulk_add_catalog_tracks_to_library(
    tracks: list[dict],
    per_track_delay: float = 0.6,
) -> list[dict]:
    """Add many catalog tracks to the library in sequence.

    Each track dict must contain `url` and `track_name` (or `title`). `artist`
    is optional but improves duplicate detection.
    """
    results = []
    for t in tracks:
        url = t.get("url")
        name = t.get("track_name") or t.get("title")
        if not url or not name:
            results.append(
                {"ok": False, "message": "missing url or track_name", "input": t}
            )
            continue
        res = add_catalog_track_to_library(
            url=url, track_name=name, artist=t.get("artist")
        )
        res["input"] = t
        results.append(res)
        time.sleep(per_track_delay)
    return results
