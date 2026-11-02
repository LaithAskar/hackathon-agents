# Claude Code

@AGENTS.md

@coordination/RULES.md

This checkout is one desk, not the whole team. If `.hackathon-role` exists, read it and follow `agents/<that role>.md` before any edit. If it does not exist, you are not set up: tell the human to run `./scripts/setup.sh` from the main checkout and open a desk with `./scripts/launch.sh <desk> --print`.

Do not point several agents at this same working directory. Each desk has its own git worktree. Do not mark a task `done` unless `.hackathon-role` is `orchestrator`.

Prefer the shared job board (`python3 scripts/board.py`) over a private todo list, so Codex, Cursor, and Hermes Agent sessions see the same work.

`.claude/agents/` holds the four desks for a session that must hand off a bounded task. The normal setup is four separate sessions, one per worktree. Subagents are not a substitute for claiming the task on the board.
