# Coordination rules

The job board and the outboxes are how four agents share one hackathon without sharing one folder. Humans can do every step below in Excel or in a terminal.

## Where the live files are

`./scripts/setup.sh` creates:

| Path | Branch | Who works here |
| --- | --- | --- |
| `.worktrees/coord` | `coord` | Nobody writes product code. The live CSV and outboxes are here. |
| `.worktrees/orchestrator` | `desk/orchestrator` | Orchestrator |
| `.worktrees/frontend` | `desk/frontend` | Frontend |
| `.worktrees/backend` | `desk/backend` | Backend |
| `.worktrees/platform` | `desk/platform` | Platform |

`python3 scripts/board.py` and `python3 scripts/post.py` always read and write the coord copy when that worktree exists, even if you run them from another desk. Commit those updates with `--commit` when a teammate on another machine needs them, then push `coord`.

### More than one laptop

The lock only stops two desks on the same machine. Each laptop has its own `coord` worktree, so a claim on one laptop is invisible to the others until it is pushed and pulled.

- Push `coord` once from the first laptop (`git -C .worktrees/coord push -u origin coord`). Run `./scripts/setup.sh` on the other laptops after that. It starts their `coord` from `origin/coord`.
- Before a claim, pull: `git -C .worktrees/coord pull --rebase origin coord`.
- Claim with `--commit`, then push right away: `git -C .worktrees/coord push origin coord`.
- If the push is rejected, pull with `--rebase` again. A conflict on that row means another laptop claimed it first. Keep their line, and do not start the task.

Open this file in Excel:

```text
.worktrees/coord/coordination/job-board.csv
```

Before setup, the copy at `coordination/job-board.csv` is the one to open. After setup, that copy goes stale until someone merges `coord` into `main`.

`python3 scripts/board.py render` writes `job-board.xlsx` next to the live CSV (colors, frozen header, a legend sheet). It is gitignored. Saving the workbook does not update the board. If you edit in Excel, edit the CSV (or Save As CSV, UTF-8, same headers) and then run `python3 scripts/board.py validate`.

Close Excel before an agent runs a board command. The command rewrites the whole file under a lock (`.job-board.lock`).

## Columns

| Column | Rule |
| --- | --- |
| `id` | `T-001`, `T-002`, … The `add` command picks the next id. |
| `task` | One sitting of work. Name the demo click it unblocks. |
| `role` | Desk that should do it: `orchestrator`, `frontend`, `backend`, `platform`. |
| `owner` | Who claimed it. Empty until then. A person uses `human:name`. |
| `status` | See the flow below. |
| `priority` | `P0` is on the demo click path. `P1` if there is time. `P2` will probably be cut. |
| `depends_on` | Other ids, separated by semicolons. All must be `done` before a claim. |
| `branch` | `agent/<desk>/<id>`, cut from `main`. |
| `pr` | Link, once it exists. |
| `owned_paths` | Paths this task may change, separated by semicolons. |
| `notes` | Short facts. A human note starts with `HUMAN:`. Seed rows start with `EXAMPLE`. |
| `updated` | UTC timestamp. The scripts set this. |

`python3 scripts/board.py validate` checks ids, the status list, owners, dependency links, and whether two active tasks cover the same path. Path overlap prints a `warning:` and does not fail the command. Fix it anyway.

## Status flow

```text
backlog → ready → claimed → in_progress → review → done
                 ↘ blocked ↗
                 ↘ needs_human
any active state → dropped
```

| Status | Meaning |
| --- | --- |
| `backlog` | Not releasable. Only the orchestrator moves it to `ready`. |
| `ready` | The desk in `role` may claim it, if dependencies are `done`. |
| `claimed` | Owner wrote their name and has not finished. No one else takes it. |
| `in_progress` | Owner is on the task branch. |
| `blocked` | Cannot move. The note says why. |
| `needs_human` | An agent stopped. A person has to answer. Agents do not keep editing that task. |
| `review` | Branch or PR is up. Waiting on the orchestrator. |
| `done` | Orchestrator accepted it. It counts. |
| `dropped` | Cut from the demo. Leave it unless the orchestrator reopens it. |

Only the orchestrator (or `--as human:name`) may `add`, move `backlog` to `ready`, `drop`, or mark `done`. A desk never marks its own task `done`.

## Claim, then code

1. `python3 scripts/board.py claim T-014 --as backend`
2. In your desk worktree, branch from main:

```bash
git fetch origin
git checkout -B agent/backend/T-014 origin/main
```

If there is no remote yet, branch from local `main`.

3. `python3 scripts/board.py start T-014 --as backend --branch agent/backend/T-014`
4. Edit only `owned_paths`. Run the test command from `PROJECT.md`.
5. Push and open a PR into `main`. Put the link on the board:

```bash
python3 scripts/board.py review T-014 --as backend --pr "<url>" --branch agent/backend/T-014
```

6. Stop. Tell the orchestrator in your outbox if the PR needs context.
7. The orchestrator checks the demo script, then `python3 scripts/board.py done T-014 --as orchestrator`.

`claim` is idempotent for the same desk. A second desk gets a non-zero exit and must not start.

Release a claim you will not finish:

```bash
python3 scripts/board.py release T-014 --as backend --note "stopping for the night"
```

## Messages

Outboxes:

```text
coordination/messages/orchestrator.md
coordination/messages/frontend.md
coordination/messages/backend.md
coordination/messages/platform.md
coordination/messages/human.md
```

Append with the script so you only touch your own file:

```bash
python3 scripts/post.py --from backend --to frontend --task T-014 \
  --body "GET /api/items returns {items:[{id,name}]}."
```

Read every outbox at the start of a turn with `python3 scripts/board.py messages`. It prints the live copies on `coord`. The `coordination/messages/` folder inside a desk worktree is stale. Respond in your own file, not by editing theirs. The orchestrator turns a real decision into a board edit. Chat that never hits the board did not happen, for the other desks.

Use messages for API shapes, a path you must borrow, a blocker, and handoffs. Keep them short.

## Merge conflicts

Worktrees stop two agents from overwriting the same working tree. They do not stop logical conflicts. These rules cover that:

- One task branch per task, named `agent/<desk>/<id>`.
- `owned_paths` is the file lock. Do not edit outside it. If you must, message first and wait.
- Do not take a task whose path overlaps a row that is `claimed`, `in_progress`, `review`, `blocked`, or `needs_human`.
- Integrate through `main`. After the orchestrator marks a task `done`, other desks rebase onto `main`. Do not merge a sibling desk's unfinished branch.
- The orchestrator, or a human, merges the PR. Agents do not push to `main`.
- If `main` moved under you, rebase your task branch. Do not copy files across worktrees by hand.

A green test command in `PROJECT.md` is part of the task. If the repo has no tests yet, the platform desk's first job includes a single command the others can run, even if that command is "the app boots and this curl succeeds."

## Humans step in

Suggested seating for three people, not a requirement: one human on the orchestrator and the pitch, one on frontend, one moving between backend and platform. Anyone may type into any session.

When a human steps in:

- Their chat instruction wins over this file.
- Record it. `--as human:name`, or a note that starts with `HUMAN:`.
- To take a task away from an agent, run `python3 scripts/board.py claim T-014 --as human:name` (or set `owner` to `human:name` in Excel) and tell the agent to stop. Agents do not reclaim a `human:` owner.
- To halt everyone, `python3 scripts/board.py stop --as orchestrator --note "reason"`. That writes `coordination/STOP`. `list` then exits 4. Clear it with `python3 scripts/board.py go --as orchestrator` when work should resume.
- To cut scope, the orchestrator marks the row `dropped` with a note. Agents do not argue by reopening it.

## What the orchestrator owes the board

- Tasks are demo-sized. The `task` text says how to tell it is finished.
- `P0` rows, taken together, are the click path in `demo/SCRIPT.md` and nothing else.
- New `P1` / `P2` work stops when the team is inside the freeze window from the during-hackathon checklist.
- A `blocked` or `needs_human` row gets a decision: unblock, stub, reassign, or drop. It does not sit until the demo.
- Example rows ship with the kit so the sheet is not empty. Their notes start with `EXAMPLE`. Delete them once the real pitch is on the board:

```bash
python3 scripts/board.py drop-examples --as orchestrator --yes
```

## Secrets

Never commit `.env`, credentials, database dumps, or private keys. The platform desk owns `.env.example`. If a secret lands in git, stop feature work, remove it from the branch, rotate the key, and write a `needs_human` note. Do not "fix" a leak by adding the file to `.gitignore` and leaving the object in history without telling a human.
