# During the hackathon

Times below are a shape, not a promise. Move them to match a 12-hour event or a weekend. The point of a checkpoint is to cut scope while you can still demo, which is the discipline in [fshot's hackathon plugin](https://github.com/fshot/claude-plugin-hackathoner) and in [Julien Dubois's playbook](https://www.julien-dubois.com/conferences/winning-the-hackathon/index-en.html).

## Open

- [ ] One human reads the pitch and the click path out loud. If they changed overnight, edit `demo/SCRIPT.md` before agents claim work.
- [ ] Orchestrator puts only `P0` tasks on `ready`. Each `P0` is one step of the script.
- [ ] Each desk claims before it edits, on its own worktree, on branch `agent/<desk>/<id>` from `main`.
- [ ] Frontend starts from mocked data so there is something to click before the API exists.
- [ ] Backend posts the JSON shape in its outbox before frontend wires the real call.
- [ ] Platform gets the public URL serving something, even a shell, and pastes it into `PROJECT.md`.

## While building

- [ ] Timebox a task. When it slips, the orchestrator stubs it, shrinks it, or drops it. A stuck `P0` does not get a quieter hour.
- [ ] One `in_progress` task per desk. Parallel agents are four desks, not four tasks on one desk.
- [ ] Run the test command in `PROJECT.md` before `review`. No command in that file means platform writes one before features pile up.
- [ ] Integrate only through `main`. The orchestrator accepts `review` into `done` and merges, or hands a human the PR.
- [ ] Checkpoint: a person who did not write the code walks the click path on the deployed URL. Fix what they could not follow.
- [ ] Keep a human in the loop on auth, secrets, and anything `needs_human`. Agents stop that task until the note is answered.
- [ ] Optional overnight: leave only claimed `P0` tasks that have a test command, and review the PRs in the morning. Drop what does not match the script. Do not measure the night in pull-request count.

## Freeze

Do this with a few hours left, not with a few minutes left. [Pranjul Rathour's demo checklist](https://pranjulrathour.github.io/blog/hackathon-demo-that-works-live/) and the [Hackathon Playbook cheat sheet](https://thehackathonplaybook.dev/cheat-sheet) both treat the last stretch as rehearsal, not as a feature window. Put your freeze time in `PROJECT.md`.

- [ ] The orchestrator stops adding tasks. `P1` and `P2` rows get `dropped` unless a human un-drops them.
- [ ] The only edits are breaks on the rehearsed path: a dead click, a crash, a missing env var, type that is too small to read.
- [ ] Walk the deployed URL in a fresh browser, logged out, with the seeded data. Not localhost.
- [ ] Cache or mock any external call that is slow or rate-limited. If a judge asks, say you did that.
- [ ] Record a short backup of the click path. If you play it, say it is a recording.
- [ ] Rehearse the backup network path once (hotspot or cached response).
- [ ] Zoom the browser, raise the font, and close notifications and unrelated tabs.
- [ ] Write the first sentence and the last sentence. The middle is the click path you already froze.

## In the room

- [ ] Open the deployed URL before your name is called so the cold start is over.
- [ ] One person speaks. Another person runs the keyboard. The third watches the next click.
- [ ] If something breaks, say what it was in one sentence, switch to the backup you rehearsed, and keep going.
- [ ] Submit before the cutoff you wrote down, even if a last commit is tempting.

## Commands you will actually run

```bash
python3 scripts/board.py list --as orchestrator
python3 scripts/board.py next --as frontend
python3 scripts/board.py claim T-010 --as backend
python3 scripts/board.py review T-010 --as backend --pr "<url>"
python3 scripts/board.py done T-010 --as orchestrator
python3 scripts/board.py drop T-011 --as orchestrator --note "off the click path"
python3 scripts/board.py stop --as orchestrator --note "freeze: demo breaks only"
python3 scripts/post.py --from backend --to frontend --task T-010 --body "Shape is ..."
```
