# apple-mcp-wrapper

An MCP server that extends the existing Apple Music MCP with two capabilities
it doesn't have:

1. **Apple Music catalog search** (not just your library) via the public iTunes
   Search API.
2. **Adding catalog tracks to the library** via macOS UI scripting of the
   Music app, so Claude (or any MCP client) can surface tracks that aren't
   yet in your library.

Playlist adds are deliberately *not* handled here. Once a track is in the
library, the existing apple-music MCP's `manage_playlist` tool (action=add_track)
does that cleanly. The two MCPs compose: this one fills the catalog gap.

## Tools exposed

| Tool | Purpose |
| ---- | ------- |
| `catalog_search` | Search the Apple Music catalog by free-text query |
| `catalog_find_best_match` | Search for a specific artist + title and return the closest match |
| `open_catalog_url` | Open an Apple Music catalog URL in the Music app |
| `is_track_in_library` | Check whether a track is already in the user's library |
| `add_catalog_track_to_library` | Open a catalog URL and UI-script "Add to Library" |
| `bulk_add_catalog_tracks_to_library` | Batch version of the above |

## Install

```bash
git clone https://github.com/rwdavidson303/apple-mcp-wrapper.git
cd apple-mcp-wrapper
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Register as an MCP server in Claude Code

Add this block to `~/.claude.json` alongside the existing `apple-music` entry:

```json
{
  "mcpServers": {
    "apple-mcp-wrapper": {
      "type": "stdio",
      "command": "/absolute/path/to/apple-mcp-wrapper/.venv/bin/python",
      "args": ["-m", "apple_mcp_wrapper.server"],
      "env": {}
    }
  }
}
```

Restart Claude Code. The tools will appear as `mcp__apple-mcp-wrapper__*`.

## Accessibility permission (required)

UI-scripting tools need Accessibility access for the process running the MCP
server (the terminal or Claude Code itself, depending on how you launch it).
Grant it at:

**System Settings -> Privacy & Security -> Accessibility -> add your
terminal (Terminal, iTerm, or whichever you use).**

Without this, the catalog search tools still work; the add-to-library tools
will fail with an AppleScript "not allowed assistive access" error.

## How it works (end-to-end example)

Typical flow when Claude is asked to add "Patches" by Clarence Carter to a
playlist the user owns:

1. `mcp__apple-mcp-wrapper__catalog_find_best_match(artist="Clarence Carter", title="Patches")`
   returns the catalog track's `trackViewUrl`.
2. `mcp__apple-mcp-wrapper__add_catalog_track_to_library(url, track_name="Patches", artist="Clarence Carter")`
   opens the URL in Music.app via `itmss://`, walks the Accessibility tree to
   the track row, clicks its More (...) button, and uses type-ahead
   ("add" + Return) to activate "Add to Library". The popup is AX-opaque, but
   the macOS type-ahead behavior reliably lands on the right item.
3. Once the track is in the library, call
   `mcp__apple-music__manage_playlist(action="add_track", playlistName="...", trackId="Patches Clarence Carter")`
   from the existing apple-music MCP to land it in the target playlist.

## Status

- `catalog_search`, `catalog_find_best_match`: **stable**, covered by tests.
- `open_catalog_url`: **stable**.
- `is_track_in_library`: **stable**.
- `add_catalog_track_to_library`, `bulk_add_catalog_tracks_to_library`:
  **working** on macOS 15 / Music.app 1.5. The UI-scripting path is brittle by
  nature; the main risk is Apple reordering the More-button popup such that
  "add" no longer jumps to "Add to Library". If that happens, tune the
  `keystroke` call in `apple_mcp_wrapper/automation.py`.

## License

MIT.
