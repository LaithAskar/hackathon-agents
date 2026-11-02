#!/usr/bin/env python3
"""Append a message to the sender's outbox.

Each desk writes only coordination/messages/<desk>.md, so two agents can
post at the same time without a merge conflict. Read every file. The
orchestrator is the one who turns a message into a board change.

  python3 scripts/post.py --from frontend --to backend --task T-006 \\
    --body "Need GET /api/items to return {items:[{id,name}]}."
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import coordlib


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Post a message to another desk.")
    parser.add_argument("--from", dest="sender", required=True)
    parser.add_argument("--to", dest="target", required=True, help="A desk, human, or all")
    parser.add_argument("--task", default="")
    parser.add_argument("--body", required=True)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args(argv)
    try:
        coord = coordlib.live_coord_dir()
        path = coordlib.post_message(coord, args.sender, args.target, args.body, args.task)
    except coordlib.BoardError as err:
        coordlib.die(err)
    print(path)
    if args.commit:
        try:
            print(coordlib.git_commit_coord(coord, f"coord: message from {args.sender} to {args.target}"))
        except coordlib.BoardError as err:
            coordlib.die(err)


if __name__ == "__main__":
    main()
