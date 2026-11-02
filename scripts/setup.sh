#!/usr/bin/env bash
# Create one git worktree per desk, plus a coord worktree that owns the live board.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${ROOT}" ]]; then
  echo "This folder is not a git repository. Run git init, commit the kit, then re-run scripts/setup.sh." >&2
  exit 1
fi
cd "${ROOT}"

if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
  echo "Make an initial commit before setup so the worktrees have a starting commit." >&2
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "warning: uncommitted changes are not copied into new worktrees. Commit first, then re-run setup." >&2
fi

# When setup is launched from inside a desk, ROOT is that desk. Always operate
# on the main checkout that owns .git.
COMMON="$(git rev-parse --git-common-dir)"
if [[ "${COMMON}" != /* ]]; then
  COMMON="$(cd "${ROOT}" && cd "${COMMON}" && pwd)"
fi
MAIN="$(dirname "${COMMON}")"
cd "${MAIN}"

mkdir -p "${MAIN}/.worktrees"

add_worktree() {
  local path="$1"
  local branch="$2"
  if [[ -d "${path}/.git" || -f "${path}/.git" ]]; then
    echo "worktree already present: ${path}"
    return 0
  fi
  if [[ -e "${path}" ]]; then
    echo "Refusing to overwrite ${path}. Remove it or pick a clean tree." >&2
    exit 1
  fi
  if git show-ref --verify --quiet "refs/heads/${branch}"; then
    git worktree add "${path}" "${branch}"
  elif git show-ref --verify --quiet "refs/remotes/origin/${branch}"; then
    git worktree add --track -b "${branch}" "${path}" "origin/${branch}"
  else
    git worktree add -b "${branch}" "${path}" HEAD
  fi
}

# A teammate may already have pushed the live board. Start from it, not from main.
if git remote get-url origin >/dev/null 2>&1; then
  git fetch --quiet origin coord 2>/dev/null || true
fi

add_worktree "${MAIN}/.worktrees/coord" "coord"
# Desk branches are desk/<role>, not agent/<role>: git cannot hold both
# agent/backend and the task branches agent/backend/<id>.
for role in orchestrator frontend backend platform; do
  add_worktree "${MAIN}/.worktrees/${role}" "desk/${role}"
  printf '%s\n' "${role}" > "${MAIN}/.worktrees/${role}/.hackathon-role"
done

cat <<EOF

Desks are ready under ${MAIN}/.worktrees

  coord          live job board (do not write product code here)
  orchestrator   pitch, demo script, board, accept/reject
  frontend       UI
  backend        API and tests
  platform       auth, data, env, CI, deploy

Open the live board in Excel:
  ${MAIN}/.worktrees/coord/coordination/job-board.csv

Colored workbook (generated, not the source of truth):
  python3 scripts/board.py render

Launch commands:
  ./scripts/launch.sh orchestrator --print
  ./scripts/launch.sh frontend --print
  ./scripts/launch.sh backend --print
  ./scripts/launch.sh platform --print

Fill in PROJECT.md, then replace the EXAMPLE rows:
  python3 scripts/board.py drop-examples --as orchestrator --yes
EOF
