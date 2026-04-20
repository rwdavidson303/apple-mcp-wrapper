"""macOS AppleScript + UI scripting helpers for the Music app.

Accessibility permission is required for UI-scripting paths. Grant it via:
System Settings -> Privacy & Security -> Accessibility.

Known issues (tested on macOS 15, Music.app 1.5):

* Apple Music URLs opened via `open` with the `https://music.apple.com/...`
  scheme sometimes land the app on the Home view instead of the intended
  album page. Using the `itmss://` scheme is more reliable.
* Even on the album page, catalog content may briefly show a
  "Something went wrong" panel before populating. Callers should be tolerant
  of retries.
* The Song -> Add to Playlist menu requires the track row to be focused /
  selected. `open location` alone does not select the row; we explicitly
  press the Down arrow to move focus onto the first track after the page
  loads.
"""
from __future__ import annotations

import json
import shlex
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


def open_catalog_url(url: str) -> None:
    """Open an Apple Music catalog URL in Music.app.

    Normalizes `https://music.apple.com/...` URLs to `itmss://music.apple.com/...`
    because the itmss scheme navigates the Music app to the target album more
    reliably than the https one when invoked via `open`.
    """
    if url.startswith("https://music.apple.com"):
        url = "itmss://" + url[len("https://") :]
    ensure_music_running()
    subprocess.run(["open", url], check=True)


def _escape_as_str(s: str) -> str:
    """Escape a Python string for embedding as an AppleScript string literal."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def add_catalog_track_to_playlist(
    url: str,
    playlist_name: str,
    wait_seconds: float = 3.5,
) -> dict:
    """Open an Apple Music catalog URL and add the featured track to `playlist_name`.

    Assumes Music.app's preference "Add songs to Library when adding to
    playlists" is enabled (default on). On success the track ends up in the
    library and in the named playlist.

    Returns a dict with keys: ok (bool), message (str).

    Approach:
      1. Open the URL via itmss://
      2. Wait for page load
      3. Press Down arrow twice to move focus to the first track row
      4. Invoke Song -> Add to Playlist via menu bar
      5. Select the submenu item matching `playlist_name`

    If Music shows a "Something went wrong" retry state, callers should retry
    after a few seconds.
    """
    open_catalog_url(url)
    time.sleep(wait_seconds)

    escaped_name = _escape_as_str(playlist_name)
    script = f"""
    tell application "Music" to activate
    delay 0.3
    tell application "System Events"
        tell process "Music"
            set frontmost to true
            delay 0.2
            -- Move focus into the track list. The exact keystrokes may need
            -- tuning depending on how Music has rendered the album page.
            key code 125 -- Down arrow
            delay 0.15
            key code 125 -- Down arrow
            delay 0.2
            try
                click menu item "Add to Playlist" of menu 1 of menu bar item "Song" of menu bar 1
                delay 0.6
                click menu item {escaped_name} of menu 1 of menu item "Add to Playlist" of menu 1 of menu bar item "Song" of menu bar 1
                return "ok"
            on error errMsg
                key code 53 -- Escape to dismiss any open menu
                return "menu-err: " & errMsg
            end try
        end tell
    end tell
    """
    try:
        out = run_osascript(script)
    except Exception as e:
        return {"ok": False, "message": f"osascript exception: {e}"}

    if out.strip().lower() == "ok":
        return {"ok": True, "message": f"Added catalog track to {playlist_name}"}
    return {"ok": False, "message": out}


def bulk_add(tracks: list[dict], playlist_name: str, per_track_delay: float = 0.5) -> list[dict]:
    """Add many catalog tracks in sequence. Each item in `tracks` needs `url`.

    Returns a per-track list of result dicts.
    """
    results = []
    for i, t in enumerate(tracks):
        url = t.get("url")
        if not url:
            results.append({"ok": False, "message": "missing url", "input": t})
            continue
        res = add_catalog_track_to_playlist(url, playlist_name)
        res["input"] = t
        results.append(res)
        time.sleep(per_track_delay)
    return results
