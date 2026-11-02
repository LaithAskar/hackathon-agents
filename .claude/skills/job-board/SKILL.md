---
name: job-board
description: Claim, update, and hand off tasks on the shared hackathon CSV job board, and post a message to another desk. Use before starting work, when blocked, or when a task is ready for review.
---

# Job board

The source of truth is `coordination/job-board.csv` on the `coord` worktree after setup. Do not edit that file by hand while another desk might be claiming. Use the scripts. They lock the file and write one row change.

```bash
python3 scripts/board.py list --as "$DESK"
python3 scripts/board.py next --as "$DESK"
python3 scripts/board.py messages
python3 scripts/board.py claim T-000 --as "$DESK"
python3 scripts/board.py start T-000 --as "$DESK" --branch "agent/$DESK/T-000"
python3 scripts/board.py block T-000 --as "$DESK" --note "why"
python3 scripts/board.py need-human T-000 --as "$DESK" --note "what a person must decide"
python3 scripts/board.py review T-000 --as "$DESK" --pr "https://..." --branch "agent/$DESK/T-000"
python3 scripts/board.py done T-000 --as orchestrator
python3 scripts/board.py validate
python3 scripts/board.py render
python3 scripts/post.py --from "$DESK" --to backend --task T-000 --body "one concrete ask"
```

Replace `$DESK` with the contents of `.hackathon-role`.

Rules that are easy to miss:

- `claim` before any product edit. If it exits non-zero, do not start.
- Workers never run `done`. The orchestrator does, from `review`.
- `blocked`, `needs_human`, and `dropped` require `--note`.
- Post messages only through `scripts/post.py`, which appends to the sender's outbox.
- `list` exiting 4 means `coordination/STOP`. Halt.
- `--commit` records the board on branch `coord` when another machine needs it.

Full contract: `coordination/RULES.md`.
