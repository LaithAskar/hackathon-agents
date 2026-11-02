#!/usr/bin/env bash
# Prove the kit works on a fresh clone: commit, worktrees, claim, conflict, xlsx.
set -euo pipefail

SOURCE="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
cleanup() {
  # Worktrees pin the temp repo. Remove them before deleting the directory.
  if [[ -d "${TMP}/repo/.git" ]]; then
    git -C "${TMP}/repo" worktree list --porcelain >/dev/null 2>&1 || true
    git -C "${TMP}/repo" worktree remove --force "${TMP}/repo/.worktrees/coord" >/dev/null 2>&1 || true
    git -C "${TMP}/repo" worktree remove --force "${TMP}/repo/.worktrees/orchestrator" >/dev/null 2>&1 || true
    git -C "${TMP}/repo" worktree remove --force "${TMP}/repo/.worktrees/frontend" >/dev/null 2>&1 || true
    git -C "${TMP}/repo" worktree remove --force "${TMP}/repo/.worktrees/backend" >/dev/null 2>&1 || true
    git -C "${TMP}/repo" worktree remove --force "${TMP}/repo/.worktrees/platform" >/dev/null 2>&1 || true
  fi
  rm -rf "${TMP}"
}
trap cleanup EXIT

mkdir -p "${TMP}/repo"
tar -C "${SOURCE}" \
  --exclude .git \
  --exclude .worktrees \
  --exclude .hackathon \
  --exclude __pycache__ \
  --exclude coordination/job-board.xlsx \
  -cf - . | tar -C "${TMP}/repo" -xf -

cd "${TMP}/repo"
git init -b main >/dev/null
git config user.email "smoke@example.com"
git config user.name "Smoke Test"
chmod +x scripts/*.sh scripts/*.py
git add .
git commit -q -m "init kit"

./scripts/setup.sh >/dev/null

test -f .worktrees/frontend/.hackathon-role
test "$(cat .worktrees/frontend/.hackathon-role)" = "frontend"
test -d .worktrees/backend
test -d .worktrees/platform
test -d .worktrees/orchestrator
test -f .worktrees/coord/coordination/job-board.csv
git -C .worktrees/coord rev-parse --abbrev-ref HEAD | grep -qx coord
git -C .worktrees/frontend rev-parse --abbrev-ref HEAD | grep -qx agent/frontend

# Claims land on the coord worktree, not the stale copy on main.
python3 scripts/board.py claim T-004 --as backend >/dev/null
grep -q "T-004,.*,backend,claimed," .worktrees/coord/coordination/job-board.csv
if grep -q "T-004,.*,backend,claimed," coordination/job-board.csv; then
  echo "claim wrote the main checkout instead of the coord worktree" >&2
  exit 1
fi

set +e
python3 scripts/board.py claim T-004 --as frontend >/tmp/claim-conflict.txt 2>&1
code=$?
set -e
if [[ "${code}" -eq 0 ]]; then
  echo "second claim should have failed" >&2
  exit 1
fi

set +e
python3 scripts/board.py claim T-006 --as frontend >/tmp/claim-deps.txt 2>&1
code=$?
set -e
if [[ "${code}" -eq 0 ]]; then
  echo "claim with unfinished dependencies should have failed" >&2
  exit 1
fi

python3 scripts/board.py start T-005 --as frontend --branch agent/frontend/T-005 >/dev/null
python3 scripts/board.py validate >/dev/null
python3 scripts/board.py render >/dev/null
test -f .worktrees/coord/coordination/job-board.xlsx
python3 - <<'PY'
import zipfile
from pathlib import Path
path = Path(".worktrees/coord/coordination/job-board.xlsx")
with zipfile.ZipFile(path) as archive:
    workbook = archive.read("xl/workbook.xml").decode()
    sheet = archive.read("xl/worksheets/sheet1.xml").decode()
assert "Job board" in workbook
assert "Legend" in workbook
assert "T-004" in sheet
assert "in_progress" in sheet or "claimed" in sheet
PY

python3 scripts/post.py --from backend --to frontend --task T-004 \
  --body "Happy-path shape is {items:[{id,name}]}." >/dev/null
grep -q "Happy-path shape" .worktrees/coord/coordination/messages/backend.md
if grep -q "Happy-path shape" .worktrees/coord/coordination/messages/frontend.md; then
  echo "message was written to the recipient file instead of the sender outbox" >&2
  exit 1
fi

python3 scripts/board.py release T-004 --as backend --note "smoke release" --commit >/dev/null
git -C .worktrees/coord log -1 --format=%s | grep -q "^coord:"

./scripts/launch.sh frontend --print > "${TMP}/launch.txt"
grep -q "agents/frontend.md" "${TMP}/launch.txt"
./scripts/setup.sh >/dev/null

python3 -m unittest tests/test_board.py

echo "smoke ok"
