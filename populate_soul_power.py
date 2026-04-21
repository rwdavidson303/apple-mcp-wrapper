"""Populate 'Soul Power - Suggested Additions' with the full foundational list.

Mirrors populate_suggestions.py but adds:
  - periodic Music.app restart every N tracks (prevents the stale-window
    failure mode that appeared after ~18 sequential UI calls last time).
"""
from __future__ import annotations

import subprocess
import time
import urllib.request
from dataclasses import dataclass, field

from apple_mcp_wrapper import automation, catalog

PLAYLIST = "Soul Power - Suggested Additions"
RESTART_EVERY = 12

TARGETS: list[tuple[str, str, str]] = [
    # foundational male voices
    ("donny", "Donny Hathaway", "A Song for You"),
    ("donny", "Donny Hathaway", "Someday We'll All Be Free"),
    ("donny", "Donny Hathaway", "I Love You More Than You'll Ever Know"),
    ("donny", "Donny Hathaway", "For All We Know"),
    ("donny", "Donny Hathaway", "The Ghetto"),
    ("donny", "Roberta Flack & Donny Hathaway", "Where Is the Love"),
    ("donny", "Roberta Flack & Donny Hathaway", "Be Real Black For Me"),

    ("marvin", "Marvin Gaye", "Let's Get It On"),
    ("marvin", "Marvin Gaye", "Distant Lover"),
    ("marvin", "Marvin Gaye", "I Want You"),
    ("marvin", "Marvin Gaye", "Trouble Man"),
    ("marvin", "Marvin Gaye", "Sexual Healing"),
    ("marvin", "Marvin Gaye", "Inner City Blues (Make Me Wanna Holler)"),
    ("marvin", "Marvin Gaye", "Mercy Mercy Me (The Ecology)"),
    ("marvin", "Marvin Gaye", "What's Going On"),
    ("marvin", "Marvin Gaye & Tammi Terrell", "You're All I Need to Get By"),
    ("marvin", "Marvin Gaye & Tammi Terrell", "Ain't No Mountain High Enough"),

    ("stevie", "Stevie Wonder", "Overjoyed"),
    ("stevie", "Stevie Wonder", "Ribbon in the Sky"),
    ("stevie", "Stevie Wonder", "As"),
    ("stevie", "Stevie Wonder", "Superwoman (Where Were You When I Needed You)"),
    ("stevie", "Stevie Wonder", "Lately"),
    ("stevie", "Stevie Wonder", "All in Love Is Fair"),
    ("stevie", "Stevie Wonder", "Golden Lady"),
    ("stevie", "Stevie Wonder", "That Girl"),

    # 60s soul foundation
    ("sam", "Sam Cooke", "A Change Is Gonna Come"),
    ("sam", "Sam Cooke", "Bring It On Home to Me"),
    ("sam", "Sam Cooke", "Cupid"),
    ("sam", "Sam Cooke", "You Send Me"),
    ("sam", "Sam Cooke", "Having a Party"),

    ("otis", "Otis Redding", "Try a Little Tenderness"),
    ("otis", "Otis Redding", "These Arms of Mine"),
    ("otis", "Otis Redding", "I've Been Loving You Too Long"),
    ("otis", "Otis Redding", "(Sittin' On) The Dock of the Bay"),
    ("otis", "Otis Redding", "I've Got Dreams to Remember"),
    ("otis", "Otis Redding", "Cigarettes and Coffee"),

    ("smokey", "Smokey Robinson & The Miracles", "The Tracks of My Tears"),
    ("smokey", "Smokey Robinson & The Miracles", "Ooo Baby Baby"),
    ("smokey", "Smokey Robinson & The Miracles", "The Hunter Gets Captured By The Game"),
    ("smokey", "Smokey Robinson", "Being With You"),
    ("smokey", "Smokey Robinson", "Cruisin'"),
    ("smokey", "Smokey Robinson", "Quiet Storm"),

    ("curtis", "Curtis Mayfield", "Superfly"),
    ("curtis", "Curtis Mayfield", "Freddie's Dead"),
    ("curtis", "Curtis Mayfield", "Move On Up"),
    ("curtis", "Curtis Mayfield", "The Makings of You"),
    ("curtis", "The Impressions", "People Get Ready"),
    ("curtis", "The Impressions", "Gypsy Woman"),
    ("curtis", "The Impressions", "So in Love"),

    # female voices rebalance
    ("gladys", "Gladys Knight & The Pips", "Midnight Train to Georgia"),
    ("gladys", "Gladys Knight & The Pips", "Neither One of Us (Wants to Be the First to Say Goodbye)"),
    ("gladys", "Gladys Knight & The Pips", "If I Were Your Woman"),
    ("gladys", "Gladys Knight & The Pips", "Help Me Make It Through the Night"),
    ("gladys", "Gladys Knight & The Pips", "Best Thing That Ever Happened to Me"),
    ("gladys", "Gladys Knight & The Pips", "I've Got to Use My Imagination"),

    ("minnie", "Minnie Riperton", "Lovin' You"),
    ("minnie", "Minnie Riperton", "Memory Lane"),
    ("minnie", "Minnie Riperton", "Reasons"),
    ("minnie", "Minnie Riperton", "Les Fleurs"),
    ("minnie", "Minnie Riperton", "Inside My Love"),

    ("phyllis", "Phyllis Hyman", "You Know How to Love Me"),
    ("phyllis", "Phyllis Hyman", "Living in Confusion"),
    ("phyllis", "Phyllis Hyman", "Meet Me on the Moon"),
    ("phyllis", "Phyllis Hyman", "Can't We Fall in Love Again"),

    ("roberta", "Roberta Flack", "Killing Me Softly With His Song"),
    ("roberta", "Roberta Flack", "Feel Like Makin' Love"),
    ("roberta", "Roberta Flack", "The First Time Ever I Saw Your Face"),

    ("chaka", "Chaka Khan", "Sweet Thing"),
    ("chaka", "Rufus & Chaka Khan", "Tell Me Something Good"),
    ("chaka", "Chaka Khan", "Through the Fire"),
    ("chaka", "Chaka Khan", "Ain't Nobody"),

    # luther (underrepresented)
    ("luther", "Luther Vandross", "A House Is Not a Home"),
    ("luther", "Luther Vandross", "Never Too Much"),
    ("luther", "Luther Vandross", "Here and Now"),
    ("luther", "Luther Vandross", "Superstar / Until You Come Back to Me (That's What I'm Gonna Do)"),
    ("luther", "Luther Vandross", "So Amazing"),
    ("luther", "Luther Vandross", "Any Love"),
    ("luther", "Luther Vandross", "Stop to Love"),

    # philly soft-soul
    ("stylistics", "The Stylistics", "Betcha By Golly Wow"),
    ("stylistics", "The Stylistics", "People Make the World Go Round"),
    ("stylistics", "The Stylistics", "You Are Everything"),
    ("stylistics", "The Stylistics", "You Make Me Feel Brand New"),
    ("stylistics", "The Stylistics", "Stop, Look, Listen (To Your Heart)"),

    ("delfonics", "The Delfonics", "La-La Means I Love You"),
    ("delfonics", "The Delfonics", "Didn't I (Blow Your Mind This Time)"),
    ("delfonics", "The Delfonics", "Ready or Not Here I Come"),

    ("bluemagic", "Blue Magic", "Sideshow"),
    ("bluemagic", "Blue Magic", "Spell"),

    ("maining", "The Main Ingredient", "Everybody Plays the Fool"),
    ("maining", "The Main Ingredient", "Just Don't Want to Be Lonely"),

    ("intruders", "The Intruders", "Cowboys to Girls"),

    # bill withers
    ("bill", "Bill Withers", "Ain't No Sunshine"),
    ("bill", "Bill Withers", "Lovely Day"),
    ("bill", "Bill Withers", "Use Me"),
    ("bill", "Bill Withers", "Lean on Me"),
    ("bill", "Bill Withers", "Grandma's Hands"),
    ("bill", "Bill Withers", "Who Is He (And What Is He to You)"),
    ("bill", "Grover Washington Jr. & Bill Withers", "Just the Two of Us"),

    # isaac hayes
    ("isaac", "Isaac Hayes", "Walk On By"),
    ("isaac", "Isaac Hayes", "By the Time I Get to Phoenix"),
    ("isaac", "Isaac Hayes", "The Look of Love"),
    ("isaac", "Isaac Hayes", "Ike's Rap II"),

    # more spinners
    ("spinners", "The Spinners", "I'll Be Around"),
    ("spinners", "The Spinners", "Could It Be I'm Falling in Love"),
    ("spinners", "The Spinners", "One of a Kind (Love Affair)"),
    ("spinners", "The Spinners", "Mighty Love"),
    ("spinners", "The Spinners", "The Rubberband Man"),

    # more chi-lites / dells
    ("chilites", "The Chi-Lites", "A Lonely Man"),
    ("chilites", "The Chi-Lites", "Coldest Day of My Life (Part 1)"),
    ("dells", "The Dells", "The Love We Had (Stays On My Mind)"),
    ("dells", "The Dells", "Give Your Baby a Standing Ovation"),

    # modern torch-bearers
    ("modern", "Leon Bridges", "Coming Home"),
    ("modern", "Leon Bridges", "River"),
    ("modern", "Leon Bridges", "Beyond"),
    ("modern", "Michael Kiwanuka", "Cold Little Heart"),
    ("modern", "Michael Kiwanuka", "Love & Hate"),
    ("modern", "Emily King", "Distance"),
    ("modern", "Black Pumas", "Colors"),
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


def _as(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def ensure_music_window() -> bool:
    script = """
    tell application "Music"
        activate
        reopen
    end tell
    delay 0.5
    tell application "System Events"
        tell (process "Music")
            set frontmost to true
            delay 0.2
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


def restart_music() -> None:
    """Full quit-and-relaunch of Music.app to clear stale window state."""
    subprocess.run(["osascript", "-e", 'tell application "Music" to quit'],
                   capture_output=True, timeout=10)
    time.sleep(2.0)
    ensure_music_window()
    time.sleep(1.0)


def add_to_playlist_applescript(track_name: str, artist: str, playlist: str) -> str:
    name_lit = _as(track_name)
    artist_lit = _as(artist)
    pl_lit = _as(playlist)
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
        try
            set existing to (every track of dest whose name is {name_lit})
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
        return r

    r.resolved_title = match.get("trackName")
    r.resolved_artist = match.get("artistName")
    r.url = catalog.canonical_url(match)

    if not r.url or not url_ok(r.url):
        r.status = "stale-url"
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
                url=r.url, track_name=r.resolved_title, artist=r.resolved_artist,
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
        if i > 1 and (i - 1) % RESTART_EVERY == 0:
            print(f"--- restarting Music.app at track {i} ---")
            restart_music()

        category, artist, title = target
        print(f"[{i:3d}/{len(TARGETS)}] {artist} - {title}")
        try:
            r = process(target)
        except Exception as e:
            r = Result(category=category, artist=artist, title=title, status=f"exception: {e}")
        results.append(r)
        extra = ""
        if r.resolved_title and r.resolved_title != title:
            extra = f", resolved={r.resolved_title}"
        print(f"    -> {r.status} (lib={r.in_library}, pl={r.in_playlist}{extra})")
        time.sleep(0.3)

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
