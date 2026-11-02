# Before the hackathon

Do this while nobody is on a clock. The during-hackathon list assumes these are true. Check the event's own rules before you pick a stack, a model API, or a dataset. Sponsor prizes and banned APIs change the plan.

## Product

- [ ] Write the one-sentence pitch in `PROJECT.md`. If you cannot say it out loud, you are not ready to brief four agents.
- [ ] Write the click path in `demo/SCRIPT.md`, including the line you will say if a judge asks for something off the path.
- [ ] Pick the stack you already know how to deploy. A hackathon is a bad time to learn a host.
- [ ] List what you will not build. The orchestrator drops tasks that match that list.

## Repo and agents

- [ ] Put this kit in the project repo and commit it. Run `./scripts/setup.sh` once, on the machine the agents will use.
- [ ] Open `.worktrees/coord/coordination/job-board.csv` in Excel and replace the `EXAMPLE` rows (`python3 scripts/board.py drop-examples --as orchestrator --yes` after the real tasks exist).
- [ ] Fill the file map and the install / test / deploy commands in `PROJECT.md`. Agents are not allowed to invent those commands.
- [ ] Run the test command on a clean tree so you know it was green before an agent touched it.
- [ ] Decide who sits with which desk. Three humans do not need four keyboards: one on the orchestrator and the pitch, one on frontend, one covering backend and platform, is a workable split.
- [ ] Launch one desk and confirm it reads `.hackathon-role` and refuses to start without a claim. Then stop it. You want that failure now, not at hour two.

## Accounts, secrets, deploy

- [ ] Create the host, database, and OAuth (or auth vendor) accounts before the event. Email verification and billing holds are how evenings disappear.
- [ ] Put real keys only in `.env` or the host's secret store. Commit `.env.example` with dummy values. The platform desk owns that file.
- [ ] Decide the auth story now: a real login, or one seeded demo user. Write it in `PROJECT.md`. A demo user is enough if the script never shows signup.
- [ ] Deploy an empty app to the URL you will present. Submit that URL if the form allows edits later. Do not plan to demo `localhost`.
- [ ] Make CI run the same test command the agents will run. One command is enough.
- [ ] Sketch the integration you actually need (model API, maps, payments). Note rate limits, and decide what the fallback response is when the call fails on venue Wi-Fi.

## Demo safety

- [ ] Seed a realistic row so the first screen is not empty. Empty states look like crashes from the back row.
- [ ] Know the hotspot you will switch to. Venue Wi-Fi is a single point of failure.
- [ ] Install the tools each human will actually run (Claude Code, Codex, Cursor, Hermes Agent). `./scripts/launch.sh <desk> --print` shows the command. `./scripts/launch.sh <desk> --start claude` runs it when that CLI is on `PATH`.
- [ ] Read the event's submission checklist once, including deck length and whether a video is required, and put the deadline with timezone in `PROJECT.md`.

Ideas here are borrowed from public hackathon write-ups, not from a claimed result. Sources are in the README.
