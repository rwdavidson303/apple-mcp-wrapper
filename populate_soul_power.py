"""Populate 'Soul Power - Suggested Additions' via MusicKit REST.

v0.2 rewrite: replaces the UI-scripting path (which topped out at ~30% on
popular Motown/Stax tracks) with direct api.music.apple.com calls. Each
track needs one catalog lookup (MusicKit catalog search) plus two
authenticated REST POSTs (library add, playlist add). Dedupes against the
playlist's existing tracks so re-runs are safe.

Run with `--dry-run` to resolve every target and print what WOULD be
added without writing anything. Always do a dry run first on a new list
so matcher mistakes (wrong track, no-match) are caught before they
pollute the library.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
from typing import Optional

from apple_mcp_wrapper import catalog, musickit

PLAYLIST = "Soul Power - Suggested Additions"

TARGETS: list[tuple[str, str, str]] = [
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

    ("luther", "Luther Vandross", "A House Is Not a Home"),
    ("luther", "Luther Vandross", "Never Too Much"),
    ("luther", "Luther Vandross", "Here and Now"),
    ("luther", "Luther Vandross", "Superstar / Until You Come Back to Me (That's What I'm Gonna Do)"),
    ("luther", "Luther Vandross", "So Amazing"),
    ("luther", "Luther Vandross", "Any Love"),
    ("luther", "Luther Vandross", "Stop to Love"),

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

    ("bill", "Bill Withers", "Ain't No Sunshine"),
    ("bill", "Bill Withers", "Lovely Day"),
    ("bill", "Bill Withers", "Use Me"),
    ("bill", "Bill Withers", "Lean on Me"),
    ("bill", "Bill Withers", "Grandma's Hands"),
    ("bill", "Bill Withers", "Who Is He (And What Is He to You)"),
    ("bill", "Grover Washington Jr. & Bill Withers", "Just the Two of Us"),

    ("isaac", "Isaac Hayes", "Walk On By"),
    ("isaac", "Isaac Hayes", "By the Time I Get to Phoenix"),
    ("isaac", "Isaac Hayes", "The Look of Love"),
    ("isaac", "Isaac Hayes", "Ike's Rap II"),

    ("spinners", "The Spinners", "I'll Be Around"),
    ("spinners", "The Spinners", "Could It Be I'm Falling in Love"),
    ("spinners", "The Spinners", "One of a Kind (Love Affair)"),
    ("spinners", "The Spinners", "Mighty Love"),
    ("spinners", "The Spinners", "The Rubberband Man"),

    ("chilites", "The Chi-Lites", "A Lonely Man"),
    ("chilites", "The Chi-Lites", "Coldest Day of My Life (Part 1)"),
    ("dells", "The Dells", "The Love We Had (Stays On My Mind)"),
    ("dells", "The Dells", "Give Your Baby a Standing Ovation"),

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
    resolved_title: Optional[str] = None
    resolved_artist: Optional[str] = None
    catalog_song_id: Optional[str] = None
    status: str = "pending"
    notes: list[str] = field(default_factory=list)


def _norm(s: str) -> str:
    return (
        s.lower()
        .replace("&", "and")
        .replace(".", "")
        .replace("'", "")
        .replace("-", " ")
        .replace("(", "")
        .replace(")", "")
        .replace(",", "")
        .strip()
    )


async def load_playlist_index(playlist_id: str) -> tuple[set[str], set[tuple[str, str]]]:
    """Return (catalog_ids_in_playlist, (artist_norm, title_norm) pairs).

    Uses the playlist-with-include-tracks endpoint and follows `next`
    pagination links. The direct /tracks endpoint has been flaky right
    after bulk writes (eventual consistency), so we prefer the include
    form.
    """
    import urllib.parse
    status, payload = await musickit._request(
        "GET",
        f"/v1/me/library/playlists/{playlist_id}",
        query={"include": "tracks"},
    )
    if status != 200:
        raise RuntimeError(f"Could not fetch playlist: {status} {payload}")
    rels = payload.get("data", [{}])[0].get("relationships", {}).get("tracks", {})
    tracks = list(rels.get("data", []))
    nxt = rels.get("next")
    while nxt:
        p = urllib.parse.urlparse(nxt)
        s, py = await musickit._request(
            "GET", p.path, query=dict(urllib.parse.parse_qsl(p.query))
        )
        if s != 200:
            break
        tracks.extend(py.get("data", []))
        nxt = py.get("next")

    catalog_ids: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    for t in tracks:
        attrs = t.get("attributes", {})
        name = attrs.get("name", "")
        artist = attrs.get("artistName", "")
        if name and artist:
            pairs.add((_norm(artist), _norm(name)))
        pp = attrs.get("playParams", {})
        cid = pp.get("catalogId")
        if cid:
            catalog_ids.add(str(cid))
    return catalog_ids, pairs


async def process(
    target: tuple[str, str, str],
    playlist_id: str,
    existing_catalog_ids: set[str],
    existing_pairs: set[tuple[str, str]],
    dry_run: bool = False,
) -> Result:
    category, artist, title = target
    r = Result(category=category, artist=artist, title=title)

    match = await catalog.find_best_match(artist, title)
    if not match:
        r.status = "no-catalog-match"
        return r

    r.resolved_title = match.get("trackName")
    r.resolved_artist = match.get("artistName")
    r.catalog_song_id = str(match.get("trackId")) if match.get("trackId") else None

    if not r.catalog_song_id:
        r.status = "no-catalog-id"
        return r

    pair = (_norm(r.resolved_artist or ""), _norm(r.resolved_title or ""))
    if r.catalog_song_id in existing_catalog_ids or pair in existing_pairs:
        r.status = "already-in-playlist"
        return r

    if dry_run:
        existing_catalog_ids.add(r.catalog_song_id)
        existing_pairs.add(pair)
        r.status = "would-add"
        return r

    lib_result = await musickit.add_song_to_library(r.catalog_song_id)
    if not lib_result.get("ok"):
        r.status = "library-add-failed"
        r.notes.append(f"status={lib_result.get('status')} resp={lib_result.get('response')}")
        return r

    pl_result = await musickit.add_catalog_song_to_playlist(r.catalog_song_id, playlist_id)
    if not pl_result.get("ok"):
        r.status = "playlist-add-failed"
        r.notes.append(f"status={pl_result.get('status')} resp={pl_result.get('response')}")
        return r

    existing_catalog_ids.add(r.catalog_song_id)
    existing_pairs.add(pair)
    r.status = "added"
    return r


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve every target and print what would be added, but "
        "make no library or playlist changes. Use this first on any new "
        "target list to verify matcher resolutions before writing.",
    )
    args = parser.parse_args()

    playlist_id = await musickit.find_library_playlist_id_by_name(PLAYLIST)
    if not playlist_id:
        raise SystemExit(f"Playlist not found: {PLAYLIST!r}")
    print(f"Playlist id: {playlist_id}")
    if args.dry_run:
        print("*** DRY RUN: no writes will occur ***")

    existing_catalog_ids, existing_pairs = await load_playlist_index(playlist_id)
    print(f"Existing tracks in playlist: {len(existing_pairs)}")
    print()

    results: list[Result] = []
    for i, target in enumerate(TARGETS, 1):
        artist, title = target[1], target[2]
        print(f"[{i:3d}/{len(TARGETS)}] {artist} - {title}")
        try:
            r = await process(
                target,
                playlist_id,
                existing_catalog_ids,
                existing_pairs,
                dry_run=args.dry_run,
            )
        except Exception as e:
            r = Result(
                category=target[0], artist=artist, title=title, status=f"exception: {e}"
            )
        results.append(r)
        extra = ""
        if r.resolved_title and r.resolved_title != title:
            extra = f", resolved={r.resolved_title}"
        if r.resolved_artist and r.resolved_artist.strip().lower() != artist.strip().lower():
            extra += f", resolved_artist={r.resolved_artist}"
        print(f"    -> {r.status}{extra}")
        await asyncio.sleep(0.15)

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
            if r.resolved_artist and r.resolved_artist.strip().lower() != r.artist.strip().lower():
                label += f" (by {r.resolved_artist})"
            if r.notes:
                label += f"  [{'; '.join(r.notes)}]"
            print(f"  - {label}")

    if args.dry_run:
        print("\n*** DRY RUN complete. Re-run without --dry-run to actually write. ***")


if __name__ == "__main__":
    asyncio.run(main())
