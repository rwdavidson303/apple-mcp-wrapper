"""Populate a single playlist from a *_targets.json file.

Usage: python populate_one.py <targets.json> [--dry-run]

Reuses process_playlist() from populate_pending_three.py.
"""
from __future__ import annotations
import argparse
import asyncio
import json
from pathlib import Path

from populate_pending_three import process_playlist


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets_file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    spec = json.loads(Path(args.targets_file).read_text())
    s = await process_playlist(spec, args.dry_run)
    print(f"\n--- {spec['playlist_name']} ---")
    for status, items in s.items():
        if items:
            print(f"  {status}: {len(items)}")
            for it in items:
                print(f"     - {it}")


if __name__ == "__main__":
    asyncio.run(main())
