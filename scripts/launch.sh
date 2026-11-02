#!/usr/bin/env bash
# Print (or start) the coding agent for one desk.
# Usage: scripts/launch.sh <orchestrator|frontend|backend|platform> [--print|--start claude|codex|hermes|cursor]
set -euo pipefail

ROLE="${1:-}"
MODE="${2:---print}"
TOOL="${3:-}"

case "${ROLE}" in
  orchestrator|frontend|backend|platform) ;;
  *)
    echo "Usage: scripts/launch.sh <orchestrator|frontend|backend|platform> [--print|--start claude|codex|hermes|cursor]" >&2
    exit 1
    ;;
esac

if [[ "${MODE}" == "--start" && -z "${TOOL}" ]]; then
  echo "Usage: scripts/launch.sh ${ROLE} --start claude|codex|hermes|cursor" >&2
  exit 1
fi

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${ROOT}" ]]; then
  echo "Run this from the kit repository." >&2
  exit 1
fi
COMMON="$(git -C "${ROOT}" rev-parse --git-common-dir)"
if [[ "${COMMON}" != /* ]]; then
  COMMON="$(cd "${ROOT}" && cd "${COMMON}" && pwd)"
fi
MAIN="$(dirname "${COMMON}")"
DESK="${MAIN}/.worktrees/${ROLE}"

if [[ ! -f "${DESK}/.hackathon-role" ]]; then
  echo "No worktree at ${DESK}. Run ./scripts/setup.sh first." >&2
  exit 1
fi

PROMPT="You are the ${ROLE} desk on a 4-agent hackathon team. Your role file is .hackathon-role. Read AGENTS.md, agents/${ROLE}.md, coordination/RULES.md, PROJECT.md, and demo/SCRIPT.md before you edit anything. Claim a task with python3 scripts/board.py before you change product code. Do not mark tasks done unless you are the orchestrator."

echo "cd ${DESK}"
echo
echo "# Claude Code"
echo "claude $(printf '%q' "${PROMPT}")"
echo
echo "# Codex"
echo "codex $(printf '%q' "${PROMPT}")"
echo
echo "# Hermes Agent (loads AGENTS.md from this folder)"
echo "hermes"
echo "# Then paste: Follow agents/${ROLE}.md. You are the ${ROLE} desk."
echo
echo "# Cursor"
echo "cursor ${DESK}"
echo "# AGENTS.md and .cursor/rules load with the folder. Paste the same first instruction if the chat is empty."

if [[ "${MODE}" == "--print" || "${MODE}" == "" ]]; then
  exit 0
fi

if [[ "${MODE}" != "--start" ]]; then
  echo "Unknown mode ${MODE}. Use --print or --start." >&2
  exit 1
fi

if ! command -v "${TOOL}" >/dev/null 2>&1; then
  echo "${TOOL} is not on PATH. Install it, then re-run, or paste the command above." >&2
  exit 1
fi

cd "${DESK}"
case "${TOOL}" in
  claude|codex)
    exec "${TOOL}" "${PROMPT}"
    ;;
  hermes)
    exec hermes
    ;;
  cursor)
    exec cursor "${DESK}"
    ;;
  *)
    echo "Unknown tool ${TOOL}. Use claude, codex, hermes, or cursor." >&2
    exit 1
    ;;
esac
