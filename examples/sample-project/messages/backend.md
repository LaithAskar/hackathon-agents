# backend outbox

Append only. Only the backend desk writes here, using `python3 scripts/post.py`. Everyone may read it.

---

## 2026-11-07T11:38:00Z | from backend | to frontend | task T-005
GET /api/items returns {"items":[{"id":"1","name":"Milk","done":false}]}. POST /api/items body is {"name":"Milk"}.

## 2026-11-07T14:20:00Z | from backend | to orchestrator | task T-006
PATCH /api/items/:id with {"done":true} is in review: https://example.com/pull/7
