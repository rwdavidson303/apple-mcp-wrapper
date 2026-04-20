# apple-mcp-wrapper

An MCP server that extends the existing Apple Music MCP with two capabilities
it doesn't have:

1. **Apple Music catalog search** (not just your library) via the public iTunes
   Search API.
2. **Adding catalog tracks to a playlist** via macOS UI scripting of the Music
   app, so Claude (or any MCP client) can add tracks that aren't yet in your
   library.

## Tools exposed

| Tool | Purpose |
| ---- | ------- |
| `catalog_search` | Search the Apple Music catalog by free-text query |
| `catalog_find_best_match` | Search for a specific artist + title and return the closest match |
| `open_catalog_url` | Open an Apple Music catalog URL in the Music app |
| `add_catalog_track_to_playlist` | Open a catalog URL in Music and UI-script "Add to Playlist" |
| `bulk_add_catalog_tracks_to_playlist` | Batch version: artist + title list into a playlist |

## Install

```bash
git clone https://github.com/rwdavidson303/apple-mcp-wrapper.git
cd apple-mcp-wrapper
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Register as an MCP server in Claude Code

Add this block to `~/Library/Application Support/Claude/claude_desktop_config.json`
(or your `~/.claude.json`, wherever your MCP config lives), alongside the
existing `apple-music` entry:

```json
{
  "mcpServers": {
    "apple-mcp-wrapper": {
      "command": "/absolute/path/to/apple-mcp-wrapper/.venv/bin/python",
      "args": ["-m", "apple_mcp_wrapper.server"]
    }
  }
}
```

Restart Claude Code. The tools will appear as `mcp__apple-mcp-wrapper__*`.

## Accessibility permission (required)

UI-scripting tools need Accessibility access for the terminal running the MCP
server. Grant it at:

**System Settings -> Privacy & Security -> Accessibility -> add your
terminal (Terminal, iTerm, or whichever you use).**

Without this, only the catalog search tools will work; anything that touches
the Music app UI will fail.

## Design notes

The existing `apple-music` MCP handles playlists, library tracks, playback
control, and search, but only against the local library. This wrapper does not
replace it. It lives alongside and fills the catalog gap.

The add-to-playlist flow works like this:

1. Given an Apple Music catalog URL (from `catalog_search` or provided by the
   user), open it in the Music app via the `itmss://` URL scheme.
2. UI-script the "Song -> Add to Playlist -> <name>" menu path, relying on
   Music's default setting "Add songs to Library when adding to playlists" so
   the track ends up both in the library and in the target playlist.

The UI-scripting path is brittle by nature. If Apple changes the Music app UI,
tune the AppleScript in `apple_mcp_wrapper/automation.py`.

## Status

Early. Catalog search is solid (hits iTunes Search API directly). The UI
scripting for "add to playlist" is scaffolded and annotated with the menu path
that works, but has only been tested against Music.app on macOS 15. See
`automation.py` for known failure modes and where to extend.

## License

MIT.
