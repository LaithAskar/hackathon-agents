# Project

Fill this in before feature work. The orchestrator's first task is this page. Other desks read it instead of guessing.

- Pitch (one sentence):
- Who it is for:
- Deadline (local time and timezone):
- Freeze time (when feature work stops):
- Demo URL (the deployed one, not localhost):
- Stack (language, framework, host, database):
- Humans on the team, and which desk each person is sitting with:

## Commands

Agents run these and do not invent new ones. Leave a line blank until it is real.

- Install:
- Dev:
- Test:
- Deploy:

## File map

Change the paths to match the repo. Tasks copy their `owned_paths` from this map.

| Desk | May edit |
| --- | --- |
| frontend | `web/` |
| backend | `server/` |
| platform | `.github/`, `.env.example`, `deploy/`, auth, database, CI |
| orchestrator | `demo/`, `PROJECT.md`, and the job board through `scripts/board.py` |

Shared files (`package.json`, `pyproject.toml`, lockfiles, the root README) are platform's unless a task says otherwise. Message the orchestrator before a second desk edits one.

## Out of scope

List what you will not build. The orchestrator drops tasks that land here.
