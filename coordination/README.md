# Board and outboxes

The CSV is the job board. Excel opens it. Git can diff it. Agents update it with `python3 scripts/board.py` so two desks cannot claim the same row.

After `./scripts/setup.sh`, open the live file, not the stale copy on your task branch:

```text
.worktrees/coord/coordination/job-board.csv
```

Colored view, regenerated whenever you want it:

```bash
python3 scripts/board.py render
```

That writes `job-board.xlsx` beside the CSV. The workbook is for reading. The CSV stays the file agents edit.

Messages are markdown outboxes in `messages/`. Each desk appends only to its own file. Read the protocol in `RULES.md`.
