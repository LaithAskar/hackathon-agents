#!/usr/bin/env python3
"""Edit the shared hackathon job board.

The live board is coordination/job-board.csv. After setup, that file in the
coord worktree is the one every desk updates. Open it in Excel. Run
`render` when you want a colored .xlsx. Do not hand-edit the xlsx back into
the workflow: the CSV stays the source of truth.

Examples:
  python3 scripts/board.py list --as frontend
  python3 scripts/board.py claim T-004 --as backend
  python3 scripts/board.py start T-004 --as backend --branch agent/backend/T-004
  python3 scripts/board.py review T-004 --as backend --pr https://github.com/org/repo/pull/1
  python3 scripts/board.py done T-004 --as orchestrator
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import coordlib


def mutate(args, action):
    path = coordlib.board_path()
    with coordlib.lock_board(path):
        rows = coordlib.load_board(path)
        message = action(rows)
        coordlib.save_board(path, rows)
    print(message)
    if getattr(args, "commit", False):
        note = getattr(args, "commit_message", None) or message.split("\n", 1)[0]
        print(coordlib.git_commit_coord(path.parent, f"coord: {note}"))
    return rows


def cmd_list(args: argparse.Namespace) -> None:
    coord = coordlib.live_coord_dir()
    reason = coordlib.read_stop(coord)
    rows = coordlib.load_board(coordlib.board_path(coord))
    print(f"Board: {coordlib.board_path(coord)}")
    if reason:
        print(f"STOP: {reason}", file=sys.stderr)
    text = coordlib.format_board(rows, args.as_agent)
    print(text or "(no tasks)")
    if reason and not args.ignore_stop:
        raise SystemExit(4)


def cmd_next(args: argparse.Namespace) -> None:
    rows = coordlib.load_board(coordlib.board_path())
    row = coordlib.next_task(rows, args.as_agent)
    if row is None:
        print(f"{args.as_agent} is idle. Tell the orchestrator.")
        raise SystemExit(0)
    print(coordlib.format_row(row, rows))


def cmd_messages(args: argparse.Namespace) -> None:
    folder = coordlib.messages_dir()
    for path in sorted(folder.glob("*.md")):
        if path.name == "README.md":
            continue
        print(f"===== {path}")
        print(path.read_text(encoding="utf-8").rstrip())
        print()


def cmd_validate(args: argparse.Namespace) -> None:
    rows = coordlib.load_board(coordlib.board_path())
    messages = coordlib.validate_rows(rows)
    errors = coordlib.validation_errors_only(messages)
    for message in messages:
        stream = sys.stderr if message.startswith("warning:") else sys.stderr
        if message.startswith("warning:"):
            print(message, file=sys.stderr)
        else:
            print(message, file=stream)
    if errors:
        raise SystemExit(1)
    print(f"ok: {len(rows)} tasks")


def cmd_render(args: argparse.Namespace) -> None:
    coord = coordlib.live_coord_dir()
    rows = coordlib.load_board(coordlib.board_path(coord))
    dest = Path(args.out) if args.out else coord / "job-board.xlsx"
    coordlib.render_xlsx(rows, dest)
    print(dest)


def cmd_claim(args: argparse.Namespace) -> None:
    def action(rows):
        return coordlib.claim(rows, args.id, args.as_agent)

    mutate(args, action)


def cmd_release(args: argparse.Namespace) -> None:
    def action(rows):
        return coordlib.release(rows, args.id, args.as_agent, args.note or "")

    mutate(args, action)


def cmd_status(args: argparse.Namespace, status: str) -> None:
    def action(rows):
        return coordlib.set_status(
            rows,
            args.id,
            args.as_agent,
            status,
            note=args.note or "",
            branch=getattr(args, "branch", "") or "",
            pr=getattr(args, "pr", "") or "",
            owner=args.owner if getattr(args, "owner", None) is not None else None,
            role=args.role if getattr(args, "role", None) else None,
        )

    mutate(args, action)


def cmd_add(args: argparse.Namespace) -> None:
    def action(rows):
        return coordlib.add_task(
            rows,
            args.as_agent,
            args.task,
            role=args.role,
            priority=args.priority,
            depends_on=args.depends_on or "",
            owned_paths=args.paths or "",
            notes=args.note or "",
            status=args.status,
        )

    mutate(args, action)


def cmd_drop_examples(args: argparse.Namespace) -> None:
    if not args.yes:
        raise coordlib.BoardError("Refusing to delete EXAMPLE rows without --yes.")

    def action(rows):
        kept = coordlib.drop_examples(rows)
        removed = len(rows) - len(kept)
        rows[:] = kept
        return f"Removed {removed} EXAMPLE rows."

    mutate(args, action)


def cmd_stop(args: argparse.Namespace) -> None:
    coord = coordlib.live_coord_dir()
    path = coordlib.stop_path(coord)
    reason = (args.note or "Humans paused the desks.").strip()
    path.write_text(reason + "\n", encoding="utf-8")
    print(f"Wrote {path}")
    if args.commit:
        print(coordlib.git_commit_coord(coord, "coord: STOP"))


def cmd_go(args: argparse.Namespace) -> None:
    actor = coordlib.require_actor(args.as_agent)
    if not coordlib.actor_is_lead(actor):
        raise coordlib.BoardError("Only the orchestrator, or a human:name, clears STOP.")
    path = coordlib.stop_path()
    if path.is_file():
        path.unlink()
        print(f"Removed {path}")
    else:
        print("No STOP file.")
    if args.commit:
        print(coordlib.git_commit_coord(path.parent, "coord: resume"))


def add_common(parser: argparse.ArgumentParser, mutating: bool = False) -> None:
    parser.add_argument("--as", dest="as_agent", required=True, help="orchestrator, frontend, backend, platform, or human:name")
    if mutating:
        parser.add_argument("--commit", action="store_true", help="Commit the board on the coord worktree")
        parser.add_argument("--note", default="", help="Appended to the notes column")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Update the shared hackathon job board.")
    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list", help="Show the live board")
    list_cmd.add_argument("--as", dest="as_agent", default="")
    list_cmd.add_argument("--ignore-stop", action="store_true")
    list_cmd.set_defaults(func=cmd_list)

    next_cmd = sub.add_parser("next", help="Print the one task this desk should touch")
    next_cmd.add_argument("--as", dest="as_agent", required=True)
    next_cmd.set_defaults(func=cmd_next)

    messages = sub.add_parser("messages", help="Print every desk's outbox from the live coord copy")
    messages.set_defaults(func=cmd_messages)

    validate = sub.add_parser("validate", help="Check ids, owners, dependencies, and path overlap")
    validate.set_defaults(func=cmd_validate)

    render = sub.add_parser("render", help="Write a formatted workbook next to the CSV")
    render.add_argument("--out", default="")
    render.set_defaults(func=cmd_render)

    claim = sub.add_parser("claim", help="Write your name on a ready task before you edit code")
    add_common(claim, mutating=True)
    claim.add_argument("id")
    claim.set_defaults(func=cmd_claim)

    release = sub.add_parser("release", help="Clear your name and set the task back to ready")
    add_common(release, mutating=True)
    release.add_argument("id")
    release.set_defaults(func=cmd_release)

    start = sub.add_parser("start", help="Move a claimed task to in_progress")
    add_common(start, mutating=True)
    start.add_argument("id")
    start.add_argument("--branch", default="")
    start.set_defaults(func=lambda args: cmd_status(args, "in_progress"))

    block = sub.add_parser("block", help="Mark a task blocked")
    add_common(block, mutating=True)
    block.add_argument("id")
    block.set_defaults(func=lambda args: cmd_status(args, "blocked"))

    human = sub.add_parser("need-human", help="Stop this task until a person answers")
    add_common(human, mutating=True)
    human.add_argument("id")
    human.set_defaults(func=lambda args: cmd_status(args, "needs_human"))

    review = sub.add_parser("review", help="Hand the task to the orchestrator with a branch or PR")
    add_common(review, mutating=True)
    review.add_argument("id")
    review.add_argument("--branch", default="")
    review.add_argument("--pr", default="")
    review.set_defaults(func=lambda args: cmd_status(args, "review"))

    done = sub.add_parser("done", help="Orchestrator accepts a task that is in review")
    add_common(done, mutating=True)
    done.add_argument("id")
    done.set_defaults(func=lambda args: cmd_status(args, "done"))

    drop = sub.add_parser("drop", help="Orchestrator cuts a task from the demo")
    add_common(drop, mutating=True)
    drop.add_argument("id")
    drop.set_defaults(func=lambda args: cmd_status(args, "dropped"))

    ready = sub.add_parser("ready", help="Orchestrator releases a backlog task")
    add_common(ready, mutating=True)
    ready.add_argument("id")
    ready.set_defaults(func=lambda args: cmd_status(args, "ready"))

    reopen = sub.add_parser("reopen", help="Orchestrator sends a done or dropped task back")
    add_common(reopen, mutating=True)
    reopen.add_argument("id")
    reopen.add_argument("--status", choices=("in_progress", "review", "ready", "backlog"), default="in_progress")
    reopen.set_defaults(func=lambda args: cmd_status(args, args.status))

    assign = sub.add_parser("assign", help="Orchestrator sets the desk and moves backlog to ready")
    add_common(assign, mutating=True)
    assign.add_argument("id")
    assign.add_argument("--role", required=True)
    assign.set_defaults(func=lambda args: cmd_status(args, "ready"))

    add = sub.add_parser("add", help="Orchestrator adds a task")
    add_common(add, mutating=True)
    add.add_argument("--task", required=True)
    add.add_argument("--role", required=True)
    add.add_argument("--priority", default="P1", choices=("P0", "P1", "P2"))
    add.add_argument("--depends-on", dest="depends_on", default="")
    add.add_argument("--paths", default="", help="Semicolon-separated owned paths")
    add.add_argument("--status", choices=("backlog", "ready"), default="ready")
    add.set_defaults(func=cmd_add)

    examples = sub.add_parser("drop-examples", help="Delete rows whose notes start with EXAMPLE")
    add_common(examples, mutating=True)
    examples.add_argument("--yes", action="store_true")
    examples.set_defaults(func=cmd_drop_examples)

    stop = sub.add_parser("stop", help="Halt every desk by writing coordination/STOP")
    stop.add_argument("--as", dest="as_agent", required=True)
    stop.add_argument("--note", default="")
    stop.add_argument("--commit", action="store_true")
    stop.set_defaults(func=cmd_stop)

    go = sub.add_parser("go", help="Remove coordination/STOP")
    go.add_argument("--as", dest="as_agent", required=True)
    go.add_argument("--commit", action="store_true")
    go.set_defaults(func=cmd_go)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except coordlib.BoardError as err:
        coordlib.die(err)


if __name__ == "__main__":
    main()
