# Hackathon desks

This repo runs four coding agents as one team: orchestrator, frontend, backend, and platform. Three humans sit with them. The agents do not share a working folder.

You are exactly one desk. Read `.hackathon-role` in the worktree root. If it says `frontend`, you are frontend, even if the prompt is vague. If that file is missing, do not edit product code. Ask which desk you are, or tell the human to run `./scripts/setup.sh` and `./scripts/launch.sh <desk> --print`.

Read `coordination/RULES.md`, `PROJECT.md`, and `demo/SCRIPT.md` before you change the product. `coordination/RULES.md` is the contract. This file is the short version that every tool loads (`AGENTS.md` for Codex, Cursor, and Hermes Agent; Claude Code loads it from `CLAUDE.md`).

## The loop

On every turn:

1. Run `python3 scripts/board.py list --as <desk>`. If it exits with code 4, a `coordination/STOP` file is present. Halt unless you are the orchestrator and a human told you to clear it.
2. Read `coordination/messages/*.md` (every outbox, newest entries at the bottom).
3. Do one task. Prefer `python3 scripts/board.py next --as <desk>`.
4. Update the board before you stop, even if you are blocked.

Commands (live board, safe to run from any worktree after setup):

```bash
python3 scripts/board.py list --as frontend
python3 scripts/board.py next --as frontend
python3 scripts/board.py claim T-004 --as backend
python3 scripts/board.py start T-004 --as backend --branch agent/backend/T-004
python3 scripts/board.py block T-004 --as backend --note "why"
python3 scripts/board.py need-human T-004 --as backend --note "what you need"
python3 scripts/board.py review T-004 --as backend --pr https://example.com/pull/1
python3 scripts/board.py done T-004 --as orchestrator
python3 scripts/post.py --from frontend --to backend --task T-006 --body "..."
```

Add `--commit` on board or post commands when another laptop needs the update. That commit lands on the `coord` branch, not on your task branch.

## Claiming

The `owner` column is a name, not a vibe. Nobody edits product code for a task until `claim` succeeds and prints their name.

- Claim only a row whose `role` is your desk and whose `status` is `ready`.
- `claim` refuses a row someone else already owns. Do not race it by editing the CSV by hand.
- `claim` refuses a row whose `depends_on` tasks are not `done`.
- Then create `agent/<desk>/<id>` from latest `main`, record it with `start`, and only then edit files under `owned_paths`.
- You do not mark your own work `done`. Move it to `review` with a branch or PR. The orchestrator accepts it.
- If you stop mid-task, `release` it or set `blocked` / `needs_human` with a note.

Status flow: `backlog` → `ready` → `claimed` → `in_progress` → `review` → `done`. Side doors: `blocked`, `needs_human`, `dropped`.

## Files, branches, secrets

- Stay inside `owned_paths` for the task. Another active row covering the same path is a stop signal. Message the orchestrator.
- Shared manifests (`package.json`, `pyproject.toml`, lockfiles, the root README) belong to the platform desk unless the task says otherwise. Message before you touch one.
- Do not commit `.env`, keys, tokens, or dumps. `.env.example` is the only env file in git.
- Do not force-push `main` or `coord`. Do not merge another desk's branch into yours. Rebase your task branch onto `main` when you need their accepted work.
- The live spreadsheet is `.worktrees/coord/coordination/job-board.csv`. Excel can open that CSV. `python3 scripts/board.py render` writes a colored `.xlsx` beside it. The CSV is the source of truth. Do not edit the `.xlsx` and expect agents to see it.
- Each desk appends only to its own file in `coordination/messages/`. Read all of them.

## Humans

A person on the team outranks the board. If they type an instruction, follow it, then update the board so the other desks can see the decision. They can also run commands as `--as human:name`, write `HUMAN:` at the start of a note, or create `coordination/STOP` (`python3 scripts/board.py stop --as orchestrator --note "..."`).

Do not invent product requirements that are not in `PROJECT.md`, `demo/SCRIPT.md`, or a task. If the pitch is still blank, the only useful work is the orchestrator's first task: fill it in.

## Desks

| Desk | Does | Does not |
| --- | --- | --- |
| orchestrator | Splits the demo into tasks, assigns `role`, unblocks, accepts `done`, watches the deadline | Build features on the other desks' paths |
| frontend | The demo UI, including a mock until the API is real | Auth servers, migrations, CI, unrelated API redesign |
| backend | The demo API and a happy-path test. Posts the response shape. | Visual polish, deploy host config |
| platform | Auth, database, `.env.example`, CI, deploy, third-party integrations | New screens or new product endpoints |

Role details: `agents/orchestrator.md`, `agents/frontend.md`, `agents/backend.md`, `agents/platform.md`.
