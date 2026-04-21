"""Populate 'Blues 6/23/23 - Suggestions' with catalog tracks.

For each (artist, title) target:
  1. Look it up via iTunes Search API.
  2. HEAD-check the Apple Music URL (skip stale 404s).
  3. If the track is already in the user's library, skip the UI flow.
  4. Otherwise, UI-script Add to Library via the wrapper.
  5. Once in library, AppleScript-duplicate into the Suggestions playlist.

Prints a running log and a final summary.
"""
from __future__ import annotations

import subprocess
import time
import urllib.request
from dataclasses import dataclass, field

from apple_mcp_wrapper import automation, catalog

PLAYLIST = "Blues 6/23/23 - Suggestions"

TARGETS: list[tuple[str, str, str]] = [
    # (category, artist, title)
    ("essentials", "Peggy Scott Adams", "Bill"),
    ("essentials", "Millie Jackson", "If Loving You Is Wrong I Don't Want to Be Right"),
    ("essentials", "Bobby Rush", "Sue"),
    ("essentials", "Bobby Rush", "Night Fishin'"),
    ("essentials", "Theodis Ealey", "Stand Up in It"),
    ("essentials", "Betty Wright", "Tonight Is the Night"),
    ("essentials", "Betty Wright", "Clean Up Woman"),
    ("essentials", "Clarence Carter", "Patches"),
    ("essentials", "Clarence Carter", "Slip Away"),
    ("essentials", "Shirley Brown", "Woman to Woman"),
    ("essentials", "Denise LaSalle", "Someone Else Is Steppin' In"),
    ("essentials", "Denise LaSalle", "Down Home Blues"),
    ("essentials", "Mel Waiters", "Hole in the Wall"),
    ("essentials", "Mel Waiters", "Smaller The Club"),
    ("essentials", "Z.Z. Hill", "Down Home Blues"),
    ("essentials", "Z.Z. Hill", "Cheating in the Next Room"),
    ("essentials", "Z.Z. Hill", "Someone Else Is Steppin' In"),
    ("essentials", "Bobby Bland", "Ain't No Love in the Heart of the City"),
    ("newer", "O.B. Buchana", "Booty Scoot"),
    ("newer", "Nellie Tiger Travis", "Mr. Sexy Man"),
    ("newer", "Nellie Tiger Travis", "I'm a Woman"),
    ("newer", "Pokey Bear", "My Sidepiece"),
    ("newer", "J-Wonn", "I Got This Record"),
    ("newer", "Sir Charles Jones", "Friday"),
    ("newer", "T.K. Soul", "Try Me"),
    ("deep", "Marvin Gaye", "Distant Lover"),
    ("deep", "Marvin Gaye", "If I Should Die Tonight"),
    ("deep", "Luther Ingram", "If Loving You Is Wrong"),
    ("deep", "Al Green", "Simply Beautiful"),
    ("deep", "Al Green", "For the Good Times"),
    ("deep", "The Stylistics", "You Make Me Feel Brand New"),
    ("deep", "Blue Magic", "Sideshow"),
    ("deep", "Blue Magic", "Stop to Start"),
    ("deep", "The Manhattans", "Kiss and Say Goodbye"),
]


@dataclass
class Result:
    category: str
    artist: str
    title: str
    resolved_title: str | None = None
    resolved_artist: str | None = None
    url: str | None = None
    status: str = "pending"
    in_library: bool = False
    in_playlist: bool = False
    notes: list[str] = field(default_factory=list)


def url_ok(url: str) -> bool:
    req = urllib.request.Request(url, method="HEAD")
    try:
        resp = urllib.request.urlopen(req, timeout=8)
        return 200 <= resp.status < 400
    except Exception:
        return False


def ensure_music_window() -> bool:
    """Force Music to the foreground with a usable window; return True if ok."""
    script = """
    tell application "Music"
        activate
        reopen
    end tell
    delay 0.6
    tell application "System Events"
        tell (process "Music")
            set frontmost to true
            delay 0.3
            try
                if (count of windows) < 1 then return "no-window"
                set w to window 1
                try
                    if value of attribute "AXMinimized" of w then
                        set value of attribute "AXMinimized" of w to false
                        delay 0.3
                    end if
                end try
                return "ok"
            on error e
                return "err: " & e
            end try
        end tell
    end tell
    """
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() == "ok"
    except Exception:
        return False


def add_to_playlist_applescript(track_name: str, artist: str, playlist: str) -> str:
    def escape(s: str) -> str:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

    name_lit = escape(track_name)
    artist_lit = escape(artist)
    pl_lit = escape(playlist)
    script = f"""
    tell application "Music"
        try
            set src to (first track of library playlist 1 whose name is {name_lit} and artist is {artist_lit})
        on error
            try
                set src to (first track of library playlist 1 whose name is {name_lit})
            on error
                return "err: not in library"
            end try
        end try
        try
            set dest to user playlist {pl_lit}
        on error
            return "err: playlist not found"
        end try
        -- avoid duplicate adds
        try
            set existing to (every track of dest whose name is {name_lit} and artist is {artist_lit})
            if (count of existing) > 0 then return "already-in-playlist"
        end try
        try
            duplicate src to dest
            return "ok"
        on error dupErr
            return "err: " & dupErr
        end try
    end tell
    """
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=15,
    )
    return result.stdout.strip() or result.stderr.strip()


def process(target: tuple[str, str, str]) -> Result:
    category, artist, title = target
    r = Result(category=category, artist=artist, title=title)

    match = catalog.find_best_match(artist, title)
    if not match:
        r.status = "no-catalog-match"
        r.notes.append("iTunes search returned nothing")
        return r

    r.resolved_title = match.get("trackName")
    r.resolved_artist = match.get("artistName")
    r.url = catalog.canonical_url(match)

    if not r.url:
        r.status = "no-url"
        return r

    if not url_ok(r.url):
        r.status = "stale-url"
        r.notes.append(f"URL HEAD failed: {r.url}")
        return r

    if automation.is_track_in_library(r.resolved_title, r.resolved_artist):
        r.in_library = True
    else:
        last_msg = ""
        for attempt in range(3):
            if not ensure_music_window():
                r.notes.append(f"attempt {attempt+1}: Music window unreachable")
                time.sleep(1.5)
                continue
            add_result = automation.add_catalog_track_to_library(
                url=r.url,
                track_name=r.resolved_title,
                artist=r.resolved_artist,
            )
            last_msg = add_result.get("message", "")
            if add_result.get("ok"):
                r.in_library = automation.is_track_in_library(
                    r.resolved_title, r.resolved_artist
                )
                if r.in_library:
                    break
            r.notes.append(f"attempt {attempt+1}: {last_msg}")
            time.sleep(1.5)
        if not r.in_library:
            r.status = "library-add-failed"
            return r

    pl_result = add_to_playlist_applescript(
        r.resolved_title, r.resolved_artist, PLAYLIST
    )
    if pl_result in ("ok", "already-in-playlist"):
        r.in_playlist = True
        r.status = "added" if pl_result == "ok" else "already-in-playlist"
    else:
        r.status = "playlist-add-failed"
        r.notes.append(pl_result)

    return r


def main() -> None:
    results: list[Result] = []
    for i, target in enumerate(TARGETS, 1):
        category, artist, title = target
        print(f"[{i:2d}/{len(TARGETS)}] {artist} - {title}")
        try:
            r = process(target)
        except Exception as e:
            r = Result(category=category, artist=artist, title=title, status=f"exception: {e}")
        results.append(r)
        print(f"   -> {r.status}  (lib={r.in_library}, pl={r.in_playlist}"
              f"{', resolved=' + r.resolved_title if r.resolved_title and r.resolved_title != title else ''})")
        if r.notes:
            for n in r.notes:
                print(f"      note: {n}")
        time.sleep(0.4)

    print("\n=== SUMMARY ===")
    buckets: dict[str, list[Result]] = {}
    for r in results:
        buckets.setdefault(r.status, []).append(r)
    for status, items in sorted(buckets.items()):
        print(f"\n{status}: {len(items)}")
        for r in items:
            label = f"{r.artist} - {r.title}"
            if r.resolved_title and r.resolved_title != r.title:
                label += f" (resolved: {r.resolved_title})"
            print(f"  - {label}")


if __name__ == "__main__":
    main()
