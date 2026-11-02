# Sample project: Pantry

A filled board for a fake hackathon app. Pantry is a household grocery list: sign in, add an item, check it off. The tasks cover the orchestrator, frontend, backend, and platform desks. Auth (the session cookie) sits on the platform desk, which is this kit's auth role.

This is not a product, and it is not the live board. During a hackathon the file agents edit is still `coordination/job-board.csv`.

```bash
HACKATHON_COORD_DIR=examples/sample-project python3 scripts/board.py validate
```

`messages/` has a few outbox entries in the same shape `python3 scripts/post.py` appends. Newest entry at the bottom.

The loop in `docs/demo.gif` is this board filling in. Regenerate it with `python3 scripts/make_demo_gif.py`.
