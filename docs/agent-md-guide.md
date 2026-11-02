# What goes in the agent files

Four desks read these files before they touch code. Fill them in before the event, while nobody is on a clock. An agent that has to guess its paths or its test command will guess differently from the other three.

## Which file holds what

| File | Read by | Put here | Edit before the event? |
| --- | --- | --- | --- |
| `AGENTS.md` | Codex, Cursor, Hermes Agent, and Claude Code (through `CLAUDE.md`) | Rules every desk shares: the turn loop, claiming, branches, secrets, humans, the desk table | Only the desk table, if you change what a desk does |
| `CLAUDE.md` | Claude Code | `@AGENTS.md` and `@coordination/RULES.md` imports, plus anything only Claude needs | Rarely |
| `agents/<role>.md` | The desk named in `.hackathon-role` | That desk's job, paths, limits, commands it runs, handback, and when it stops | Yes, all four |
| `PROJECT.md` | Every desk | The pitch, deadline, freeze time, stack, install / dev / test / deploy commands, file map | Yes. This is the one place for them |
| `demo/SCRIPT.md` | Every desk | The click path. `P0` tasks add up to it | Yes |
| `.claude/agents/*.md`, `.cursor/rules/hackathon-desk.mdc` | Claude subagents, Cursor | Thin pointers to the files above | No |

Write a fact once. The pitch, the stack, and the commands live in `PROJECT.md`, and the role files point there. A pitch copied into five files goes stale in four of them.

Commit these files before you run `./scripts/setup.sh`, because each worktree starts from that commit. A later edit reaches a desk when it is on `main` (pushed, if the team uses a remote) and the desk cuts its next task branch from it.

## The sections of a role file

Each heading below is one section of `agents/<role>.md`. The example under each is what a backend desk might say.

### Role and what it owns

One sentence on the job, then the paths it may edit. Copy the paths from the file map in `PROJECT.md`, because tasks copy their `owned_paths` from the same map.

```markdown
You build the demo API: the routes on the click path and one happy-path test each.
You own `server/`. A task's `owned_paths` can narrow that, never widen it.
```

### What it must not touch

Name the paths and the decisions. "Stay in your lane" is not a path.

```markdown
Do not edit `web/`, `deploy/`, `.github/`, `.env*`, `package.json`, or lockfiles.
Ask platform for a dependency. Ask the orchestrator for a path outside the task.
```

### Objective and pitch

Point at the pitch and name this desk's share of the click path. Do not restate the product.

```markdown
The pitch is the first line of `PROJECT.md`. Your part is steps 2 and 3 of `demo/SCRIPT.md`:
the upload returns three recipes in under five seconds.
```

### Using the job board

The commands are fixed by `scripts/board.py`. Keep them exact. Claim before any edit. The flow is `ready` → `claimed` → `in_progress` → `review` → `done`. Only the orchestrator (or a `human:name`) runs `done`.

```bash
python3 scripts/board.py list --as backend        # exit 4 means STOP: halt
python3 scripts/board.py next --as backend
python3 scripts/board.py claim T-004 --as backend
git checkout -B agent/backend/T-004 origin/main
python3 scripts/board.py start T-004 --as backend --branch agent/backend/T-004
python3 scripts/board.py review T-004 --as backend --pr "<url>"
```

### Messaging other desks

Each desk appends to its own outbox through `post.py`, and reads every outbox with `board.py messages`. Say what this desk owes the others.

```bash
python3 scripts/board.py messages
python3 scripts/post.py --from backend --to frontend --task T-004 \
  --body "POST /api/recipes {image} -> {recipes:[{id,title,minutes}]}. Errors: {error} with non-200."
```

### Stack and commands

The commands live in `PROJECT.md` under `## Commands`. Agents run those and do not invent new ones. The role file only says which ones this desk runs and when.

```markdown
Run the Test command from `PROJECT.md` before `review`. If it is blank, block the task
and ask platform for one. Do not write your own runner.
```

### Definition of done

For a worker desk, finished means `review`, not `done`. Write the checks the orchestrator will look for.

```markdown
Ready for review when: the route answers the click in the script, the Test command is green,
the change stays inside `owned_paths`, and the response shape is in your outbox and the task note.
Then `review` with the PR. The orchestrator decides `done`.
```

### When to stop and ask a human

List the triggers and the command. `need-human` freezes the row until a person answers.

```markdown
Stop and run `board.py need-human <id> --as backend --note "..."` when you need a secret or an account,
a requirement that is not in PROJECT.md or demo/SCRIPT.md, or a destructive git step.
Halt when `list` exits 4, or when a row's owner is `human:...`.
```

### Timebox

The board has no timer. The orchestrator reads the `updated` column in the CSV and the freeze time in `PROJECT.md`. Give the desk a number to act on.

```markdown
One `in_progress` task at a time. If a task is not in `review` after 45 minutes, `block` it with
a note saying what is left, and message the orchestrator. After the freeze time, fix only breaks
on the rehearsed click path.
```

## Template

Copy this into `agents/<role>.md` and replace every `<...>`. Delete a line rather than leave a placeholder in it.

````markdown
# <Desk name>

<One sentence: what this desk builds for the demo.> You own `<paths from the PROJECT.md file map>`.
Do not edit `<other desks' paths, shared manifests, .env*>`. <Who to ask for what you need instead.>

## Objective

The pitch is in `PROJECT.md`. Your part is <step numbers> of `demo/SCRIPT.md`: <what the audience sees work>.

## Start of turn

```bash
python3 scripts/board.py list --as <desk>
python3 scripts/board.py messages
python3 scripts/board.py next --as <desk>
```

If `list` exits 4, stop. Claim before you edit, then branch and record it:

```bash
python3 scripts/board.py claim <id> --as <desk>
git checkout -B agent/<desk>/<id> origin/main
python3 scripts/board.py start <id> --as <desk> --branch agent/<desk>/<id>
```

## How you build

- <The two or three habits that matter for this desk. Example: mock first, post the shape first.>
- Commands come from `PROJECT.md`. Run the Test command before `review`.
- Tell <desk> <what they need from you> with `python3 scripts/post.py --from <desk> --to <desk> --task <id> --body "..."`.

## Done

Ready for review when <the checks>. Then:

```bash
python3 scripts/board.py review <id> --as <desk> --pr "<url>"
```

Do not mark it `done`. <Orchestrator only: you mark `done` after review, then merge.>

## Stop and ask

- `need-human` with a note when <secrets, accounts, missing requirements, anything this team wants a person to decide>.
- Halt when `list` exits 4 or the row's owner is `human:...`.

## Timebox

One `in_progress` task. Not in `review` after <minutes>: `block` with what is left and message the orchestrator. After the freeze time in `PROJECT.md`, fix only breaks on the rehearsed path.
````

## Filled example: orchestrator

This example assumes `PROJECT.md` already says: pitch "Snap your fridge, get three dinners you can cook tonight", stack Vite + React in `web/`, FastAPI in `server/`, freeze at 15:00.

````markdown
# Orchestrator

You own the objective, the job board, and the decision that something is done. You own `demo/`,
`PROJECT.md`, and the board through `scripts/board.py`. Do not edit `web/`, `server/`, `deploy/`,
or `.github/`. If a fix is ten lines on someone else's path, assign it.

## Objective

The pitch is in `PROJECT.md`. Every `P0` row is one step of the six-click path in `demo/SCRIPT.md`,
and nothing else is `P0`.

## Start of turn

```bash
python3 scripts/board.py list --as orchestrator --ignore-stop
python3 scripts/board.py messages
python3 scripts/board.py validate
```

## How you build

- Each task fits one sitting, names the click it unblocks, and copies `owned_paths` from the file map:

```bash
python3 scripts/board.py add --as orchestrator --role backend --priority P0 \
  --paths "server/" --status ready \
  --task "POST /api/recipes takes a fridge photo and returns 3 recipes. One test. Post the shape."
```

- Answer every `blocked` and `needs_human` row in the same turn: unblock, stub, reassign, or `drop`.
- Reply in your outbox with `post.py`. If the reply changes the plan, change the board too.

## Done

Accept a `review` row only when it matches its step in `demo/SCRIPT.md` and the PR shows the Test
command passed. Then `python3 scripts/board.py done <id> --as orchestrator` and merge, or hand a human
the PR. Send it back with `reopen <id> --as orchestrator --status in_progress --note "what to fix"`.

## Stop and ask

- `need-human <id>` with a note before you drop a `P0`, change the pitch, or merge something a desk flagged as risky.
- When a human says stop: `python3 scripts/board.py stop --as orchestrator --note "..."`. Run `go` only when a human says resume.

## Timebox

Check the `updated` column each turn. A row in `in_progress` for 45 minutes gets a decision: shrink,
stub, or drop. At 15:00, add no feature tasks and drop `P1`/`P2` rows unless a human keeps them.
````

## Filled example: backend

````markdown
# Backend

You build the demo API: the routes on the click path and one happy-path test each. You own `server/`.
Do not edit `web/`, `deploy/`, `.github/`, `.env*`, or `server/requirements.txt` (ask platform for a dependency).

## Objective

The pitch is in `PROJECT.md`. Your part is steps 2 and 3 of `demo/SCRIPT.md`: the upload returns
three recipes in under five seconds, even when the vision API is slow.

## Start of turn

```bash
python3 scripts/board.py list --as backend
python3 scripts/board.py messages
python3 scripts/board.py next --as backend
```

If `list` exits 4, stop. Claim before you edit:

```bash
python3 scripts/board.py claim T-004 --as backend
git checkout -B agent/backend/T-004 origin/main
python3 scripts/board.py start T-004 --as backend --branch agent/backend/T-004
```

## How you build

- Post the response shape before you build the handler, and put it in the task note:

```bash
python3 scripts/post.py --from backend --to frontend --task T-004 \
  --body "POST /api/recipes {image} -> {recipes:[{id,title,minutes}]}. Errors: {error}, non-200."
```

- Return a cached answer when the vision call takes more than 3 seconds. The presenter can explain a cache, not a spinner.
- Run the Test command from `PROJECT.md` (`pytest server -q`) before `review`.

## Done

Ready for review when `POST /api/recipes` answers the click in step 2, `pytest server -q` is green, the
diff stays in `server/`, and frontend has the shape. Then:

```bash
python3 scripts/board.py review T-004 --as backend --pr "<url>"
```

Do not mark it `done`.

## Stop and ask

- `need-human` when you need an API key, a paid account, or a field the script does not mention.
- `block` with the exact name when you wait on an env var or a table, and message platform.
- Halt when `list` exits 4 or the owner is `human:...`.

## Timebox

One `in_progress` task. Not in `review` after 45 minutes: `block` with what is left and message the
orchestrator. After 15:00, fix only breaks on the rehearsed path.
````

The shipped files in `agents/` follow this shape without the project details. Start from them, add your paths, steps, and timebox, and keep the board commands exactly as written.
