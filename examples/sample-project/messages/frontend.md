# frontend outbox

Append only. Only the frontend desk writes here, using `python3 scripts/post.py`. Everyone may read it.

---

## 2026-11-07T11:24:00Z | from frontend | to orchestrator | task T-007
Sign-in screen renders against a mocked session. Click 1 of the demo script works with no API.

## 2026-11-07T14:46:00Z | from frontend | to backend | task T-008
List screen will POST /api/items with {"name":"Milk"} once T-009 starts. Still on mocked items.
