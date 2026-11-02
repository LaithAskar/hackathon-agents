#!/usr/bin/env python3
"""Shared job-board and outbox helpers for the four hackathon desks.

The CSV in coordination/job-board.csv is the source of truth. Agents should
change it through this module (see scripts/board.py) so a claim is one locked
read-modify-write, not a blind edit that races another desk.
"""

from __future__ import annotations

import csv
import io
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

COLUMNS = [
    "id",
    "task",
    "role",
    "owner",
    "status",
    "priority",
    "depends_on",
    "branch",
    "pr",
    "owned_paths",
    "notes",
    "updated",
]

AGENTS = ("orchestrator", "frontend", "backend", "platform")

STATUSES = (
    "backlog",
    "ready",
    "claimed",
    "in_progress",
    "blocked",
    "needs_human",
    "review",
    "done",
    "dropped",
)

PRIORITIES = ("P0", "P1", "P2")

# Statuses where someone is expected to be touching the owned paths.
ACTIVE = ("claimed", "in_progress", "review", "blocked", "needs_human")

TRANSITIONS = {
    "backlog": {"ready", "dropped", "needs_human"},
    "ready": {"claimed", "backlog", "dropped", "needs_human"},
    "claimed": {"in_progress", "ready", "blocked", "needs_human", "dropped"},
    "in_progress": {"review", "blocked", "needs_human", "dropped", "ready"},
    "blocked": {"ready", "claimed", "in_progress", "dropped", "needs_human"},
    "needs_human": {"ready", "claimed", "in_progress", "dropped"},
    "review": {"done", "in_progress", "dropped"},
    "done": {"review", "in_progress"},
    "dropped": {"backlog", "ready"},
}

ID_RE = re.compile(r"^T-\d+$")
ACTOR_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


class BoardError(Exception):
    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def repo_main_root() -> Path | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    if not out:
        return None
    common = Path(out)
    if not common.is_absolute():
        common = (Path.cwd() / common).resolve()
    else:
        common = common.resolve()
    return common.parent


def live_coord_dir() -> Path:
    """Directory that holds the live job-board.csv and messages/.

    After scripts/setup.sh, that directory is the coord worktree, so every
    desk writes one shared board instead of the stale copy on its own branch.
    HACKATHON_COORD_DIR overrides discovery (used by tests).
    """
    override = os.environ.get("HACKATHON_COORD_DIR")
    if override:
        path = Path(override)
        if not path.is_dir():
            raise BoardError(f"HACKATHON_COORD_DIR is not a directory: {path}")
        return path
    root = repo_main_root()
    if root is not None:
        coord_board = root / ".worktrees" / "coord" / "coordination" / "job-board.csv"
        if coord_board.is_file():
            return coord_board.parent
        main_board = root / "coordination" / "job-board.csv"
        if main_board.is_file():
            return main_board.parent
    local = Path.cwd() / "coordination"
    if (local / "job-board.csv").is_file():
        return local
    raise BoardError(
        "Could not find coordination/job-board.csv. Run this from the repo, or set HACKATHON_COORD_DIR."
    )


def board_path(coord_dir: Path | None = None) -> Path:
    return (coord_dir or live_coord_dir()) / "job-board.csv"


def messages_dir(coord_dir: Path | None = None) -> Path:
    return (coord_dir or live_coord_dir()) / "messages"


def stop_path(coord_dir: Path | None = None) -> Path:
    return (coord_dir or live_coord_dir()) / "STOP"


def read_stop(coord_dir: Path | None = None) -> str | None:
    path = stop_path(coord_dir)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text or "STOP file is present. All desks halt."


def valid_actor(value: str) -> bool:
    if value in AGENTS:
        return True
    if value.startswith("human:") and ACTOR_RE.match(value) and len(value) > len("human:"):
        return True
    return False


def split_list(cell: str) -> list[str]:
    if not cell.strip():
        return []
    parts = re.split(r"[;]", cell)
    return [part.strip() for part in parts if part.strip()]


def load_board(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise BoardError(f"Missing job board: {path}")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise BoardError(
            f"{path} is not UTF-8. In Excel, use File > Save As > CSV UTF-8 (Comma delimited), then run validate."
        ) from None
    for number, line in enumerate(text.splitlines(), start=1):
        if line.startswith(("<<<<<<<", ">>>>>>>")) or line == "=======":
            raise BoardError(
                f"{path} line {number} is a git merge conflict marker. Resolve the conflict in the CSV "
                "(keep the row of whoever claimed first), commit it, then run validate."
            )
    with io.StringIO(text, newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise BoardError(f"{path} is empty.")
        header = [name.strip() for name in reader.fieldnames]
        if header != COLUMNS:
            raise BoardError(
                "Job board header mismatch.\n"
                f"  expected: {','.join(COLUMNS)}\n"
                f"  found:    {','.join(header)}"
            )
        rows: list[dict[str, str]] = []
        for raw in reader:
            if raw is None:
                continue
            row = {column: (raw.get(column) or "").strip() for column in COLUMNS}
            if not any(row.values()):
                continue
            rows.append(row)
    return rows


def save_board(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in COLUMNS})
    os.replace(tmp, path)


def lock_board(path: Path):
    """Exclusive lockfile next to the CSV. Returned context manager."""
    from contextlib import contextmanager

    try:
        import fcntl
    except ImportError:
        # Windows Python (Git Bash) has no fcntl.
        fcntl = None
        import msvcrt

    @contextmanager
    def _locked():
        path.parent.mkdir(parents=True, exist_ok=True)
        lock = path.with_name(".job-board.lock")
        handle = lock.open("a+", encoding="utf-8")
        try:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            else:
                handle.seek(0)
                while True:
                    try:
                        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                        break
                    except OSError:
                        continue
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            else:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            handle.close()

    return _locked()


def index_rows(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for row in rows:
        task_id = row.get("id", "")
        if task_id in found:
            raise BoardError(f"Duplicate task id {task_id}.")
        found[task_id] = row
    return found


def require_row(rows: list[dict[str, str]], task_id: str) -> dict[str, str]:
    found = index_rows(rows)
    if task_id not in found:
        raise BoardError(f"No task {task_id}.")
    return found[task_id]


def deps_of(row: dict[str, str]) -> list[str]:
    return split_list(row.get("depends_on", ""))


def unfinished_deps(rows: list[dict[str, str]], row: dict[str, str]) -> list[str]:
    found = {item["id"]: item for item in rows}
    pending = []
    for dep in deps_of(row):
        other = found.get(dep)
        if other is None or other.get("status") != "done":
            pending.append(dep)
    return pending


def append_note(row: dict[str, str], note: str) -> None:
    note = note.strip()
    if not note:
        return
    existing = row.get("notes", "").strip()
    row["notes"] = f"{existing} | {note}" if existing else note


def touch(row: dict[str, str]) -> None:
    row["updated"] = now_stamp()


def check_transition(row: dict[str, str], new_status: str) -> None:
    current = row.get("status", "")
    if new_status not in STATUSES:
        raise BoardError(f"Unknown status {new_status!r}. Use one of: {', '.join(STATUSES)}.")
    if current == new_status:
        return
    allowed = TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise BoardError(
            f"{row.get('id')} cannot go from {current} to {new_status}. "
            f"Allowed: {', '.join(sorted(allowed)) or '(none)'}."
        )


def actor_is_lead(actor: str) -> bool:
    """The orchestrator desk, or a human who has stepped in."""
    return actor == "orchestrator" or actor.startswith("human:")


def require_actor(actor: str) -> str:
    actor = actor.strip()
    if not valid_actor(actor):
        raise BoardError(
            f"Unknown desk {actor!r}. Use one of {', '.join(AGENTS)}, or human:name."
        )
    return actor


def require_owner_or_lead(row: dict[str, str], actor: str) -> None:
    if actor_is_lead(actor):
        return
    owner = row.get("owner", "")
    if owner != actor:
        raise BoardError(
            f"{row.get('id')} is owned by {owner or '(nobody)'}. {actor} cannot change it."
        )


def validate_rows(rows: list[dict[str, str]]) -> list[str]:
    """Return a list of error strings. Empty means the board is valid."""
    errors: list[str] = []
    warnings: list[str] = []
    seen: dict[str, dict[str, str]] = {}
    for row in rows:
        task_id = row.get("id", "")
        if not ID_RE.match(task_id):
            errors.append(f"{task_id or '(blank)'}: id must look like T-001.")
            continue
        if task_id in seen:
            errors.append(f"{task_id}: duplicate id.")
        seen[task_id] = row
        if not row.get("task"):
            errors.append(f"{task_id}: task text is empty.")
        role = row.get("role", "")
        if role and role not in AGENTS:
            errors.append(f"{task_id}: role {role!r} is not a desk.")
        owner = row.get("owner", "")
        if owner and not valid_actor(owner):
            errors.append(f"{task_id}: owner {owner!r} is not a desk or human:name.")
        status = row.get("status", "")
        if status not in STATUSES:
            errors.append(f"{task_id}: status {status!r} is not valid.")
        priority = row.get("priority", "")
        if priority and priority not in PRIORITIES:
            errors.append(f"{task_id}: priority {priority!r} must be P0, P1, or P2.")
        if status in {"claimed", "in_progress", "review", "done"} and not owner:
            errors.append(f"{task_id}: status {status} needs an owner.")
        if status == "review" and not (row.get("branch") or row.get("pr")):
            errors.append(f"{task_id}: review needs a branch or a pr.")
        if not row.get("updated"):
            errors.append(f"{task_id}: updated is empty.")
        if owner in AGENTS and role and owner != role and not owner.startswith("human:"):
            # A human can own any row. A desk should only own its role,
            # unless the orchestrator is holding it while integrating.
            if owner != "orchestrator":
                errors.append(
                    f"{task_id}: owner {owner} does not match role {role}. "
                    "Reassign the role, or release the claim."
                )
    for row in rows:
        for dep in deps_of(row):
            if not ID_RE.match(dep):
                errors.append(f"{row.get('id')}: depends_on entry {dep!r} is not a task id.")
            elif dep not in seen:
                errors.append(f"{row.get('id')}: depends_on {dep}, which does not exist.")
            elif dep == row.get("id"):
                errors.append(f"{row.get('id')}: cannot depend on itself.")
    cycle = find_cycle({task_id: [d for d in deps_of(row) if d in seen and d != task_id] for task_id, row in seen.items()})
    if cycle:
        errors.append(f"{cycle[0]}: depends_on cycle {' -> '.join(cycle)}. No task in it can be claimed.")
    active_paths: list[tuple[str, str]] = []
    for row in rows:
        if row.get("status") not in ACTIVE:
            continue
        for owned in split_list(row.get("owned_paths", "")):
            active_paths.append((row.get("id", ""), owned.strip("/")))
    for i, (left_id, left) in enumerate(active_paths):
        for right_id, right in active_paths[i + 1 :]:
            if left_id == right_id or not left or not right:
                continue
            if left == right or left.startswith(right + "/") or right.startswith(left + "/"):
                warnings.append(
                    f"warning: {left_id} and {right_id} both cover '{left}' / '{right}'."
                )
    return errors + warnings


def find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    state: dict[str, str] = {}

    def visit(node: str, path: list[str]) -> list[str] | None:
        state[node] = "open"
        for dep in graph.get(node, []):
            if state.get(dep) == "open":
                return path[path.index(dep):] + [dep]
            if dep not in state:
                found = visit(dep, path + [dep])
                if found:
                    return found
        state[node] = "closed"
        return None

    for node in graph:
        if node not in state:
            found = visit(node, [node])
            if found:
                return found
    return None


def validation_errors_only(messages: list[str]) -> list[str]:
    return [message for message in messages if not message.startswith("warning:")]


def next_id(rows: list[dict[str, str]]) -> str:
    highest = 0
    for row in rows:
        match = ID_RE.match(row.get("id", ""))
        if match:
            highest = max(highest, int(row["id"].split("-", 1)[1]))
    return f"T-{highest + 1:03d}"


def claim(rows: list[dict[str, str]], task_id: str, actor: str) -> str:
    actor = require_actor(actor)
    row = require_row(rows, task_id)
    if actor.startswith("human:"):
        return human_take(row, actor)
    role = row.get("role", "")
    if role and role != actor:
        raise BoardError(
            f"{task_id} is on the {role} desk. {actor} cannot claim it.",
            code=2,
        )
    owner = row.get("owner", "")
    if owner and owner != actor:
        raise BoardError(
            f"{task_id} is already claimed by {owner}. Leave it, or ask them to release it.",
            code=2,
        )
    if owner == actor and row.get("status") in ACTIVE:
        return f"{task_id} is already claimed by {actor} ({row.get('status')})."
    if row.get("status") != "ready":
        raise BoardError(
            f"{task_id} is {row.get('status')}, not ready. Ask the orchestrator to mark it ready before you claim it.",
            code=2,
        )
    pending = unfinished_deps(rows, row)
    if pending:
        raise BoardError(
            f"{task_id} is waiting on {', '.join(pending)}. Do not start it.",
            code=3,
        )
    if not role:
        row["role"] = actor
    row["owner"] = actor
    row["status"] = "claimed"
    touch(row)
    return f"Claimed {task_id} as {actor}. Create the branch, then start the task before editing product code."


def human_take(row: dict[str, str], actor: str) -> str:
    """A person outranks the board: they may take any open row, even from a desk."""
    task_id = row.get("id", "")
    if row.get("status") in {"done", "dropped"}:
        raise BoardError(f"{task_id} is {row.get('status')}. Reopen it before you take it.")
    previous = row.get("owner", "")
    row["owner"] = actor
    if row.get("status") in {"backlog", "ready"}:
        row["status"] = "claimed"
    touch(row)
    if previous and previous != actor:
        append_note(row, f"HUMAN: {actor} took this from {previous}")
        return f"{actor} took {task_id} from {previous}. Tell {previous} to stop."
    return f"Claimed {task_id} as {actor}."


def release(rows: list[dict[str, str]], task_id: str, actor: str, note: str = "") -> str:
    actor = require_actor(actor)
    row = require_row(rows, task_id)
    require_owner_or_lead(row, actor)
    if row.get("status") not in {"claimed", "in_progress", "blocked", "needs_human"}:
        raise BoardError(f"{task_id} is {row.get('status')} and cannot be released.")
    row["owner"] = ""
    row["status"] = "ready"
    append_note(row, note or f"released by {actor}")
    touch(row)
    return f"Released {task_id}. Status is ready and owner is empty."


def set_status(
    rows: list[dict[str, str]],
    task_id: str,
    actor: str,
    status: str,
    *,
    note: str = "",
    branch: str = "",
    pr: str = "",
    owner: str | None = None,
    role: str | None = None,
) -> str:
    actor = require_actor(actor)
    row = require_row(rows, task_id)
    if status == "claimed":
        message = claim(rows, task_id, actor if not actor.startswith("human:") else row.get("role", ""))
        append_note(row, note)
        if branch:
            row["branch"] = branch
        if pr:
            row["pr"] = pr
        return message
    if status == "done" and not actor_is_lead(actor):
        raise BoardError("Only the orchestrator marks a task done, after review. A human:name may also accept it.")
    if status == "dropped" and not actor_is_lead(actor):
        raise BoardError("Only the orchestrator drops a task. A human:name may also drop it.")
    if status == "ready" and row.get("status") == "backlog" and not actor_is_lead(actor):
        raise BoardError("Only the orchestrator moves backlog to ready.")
    if row.get("status") in {"done", "dropped"} and not actor_is_lead(actor):
        raise BoardError(f"{task_id} is {row.get('status')}. Only the orchestrator, or a human:name, reopens it.")
    if not actor_is_lead(actor):
        require_owner_or_lead(row, actor)
    check_transition(row, status)
    if status in {"blocked", "needs_human", "dropped"} and not note.strip():
        raise BoardError(f"{task_id}: {status} needs --note so the other desks know why.")
    if status in {"in_progress", "review"}:
        pending = unfinished_deps(rows, row)
        if pending and row.get("status") != "review":
            raise BoardError(
                f"{task_id} is waiting on {', '.join(pending)}.",
                code=3,
            )
    if status == "review" and not (branch or pr or row.get("branch") or row.get("pr")):
        raise BoardError(f"{task_id}: move to review with --branch or --pr.")
    if branch:
        row["branch"] = branch
    if pr:
        row["pr"] = pr
    if owner is not None:
        if owner and not valid_actor(owner):
            raise BoardError(f"Owner {owner!r} is not a desk or human:name.")
        row["owner"] = owner
    if role is not None:
        if role and role not in AGENTS:
            raise BoardError(f"Role {role!r} is not a desk.")
        if not actor_is_lead(actor):
            raise BoardError("Only the orchestrator changes role.")
        row["role"] = role
        if row.get("owner") in AGENTS and row.get("owner") != role:
            row["owner"] = ""
    if status in {"claimed", "in_progress", "review", "done"} and not row.get("owner"):
        raise BoardError(f"{task_id} needs an owner before it can be {status}.")
    row["status"] = status
    append_note(row, note)
    touch(row)
    return f"{task_id} is now {status}."


def add_task(
    rows: list[dict[str, str]],
    actor: str,
    task: str,
    *,
    role: str,
    priority: str = "P1",
    depends_on: str = "",
    owned_paths: str = "",
    notes: str = "",
    status: str = "backlog",
) -> str:
    actor = require_actor(actor)
    if not actor_is_lead(actor):
        raise BoardError("Only the orchestrator adds tasks. Send them a message if you need one.")
    task = task.strip()
    if not task:
        raise BoardError("Task text is empty.")
    if role not in AGENTS:
        raise BoardError(f"Role must be one of: {', '.join(AGENTS)}.")
    if priority not in PRIORITIES:
        raise BoardError("Priority must be P0, P1, or P2.")
    if status not in {"backlog", "ready"}:
        raise BoardError("New tasks start as backlog or ready.")
    task_id = next_id(rows)
    row = {column: "" for column in COLUMNS}
    row.update(
        {
            "id": task_id,
            "task": task,
            "role": role,
            "owner": "",
            "status": status,
            "priority": priority,
            "depends_on": ";".join(split_list(depends_on)),
            "owned_paths": ";".join(split_list(owned_paths)),
            "notes": notes.strip(),
            "updated": now_stamp(),
        }
    )
    # Validate deps against the board including this row's id, so a typo fails
    # before the row is appended.
    probe = rows + [row]
    for dep in deps_of(row):
        if dep == task_id or not any(item["id"] == dep for item in rows):
            raise BoardError(f"depends_on {dep} does not exist.")
    messages = validation_errors_only(validate_rows(probe))
    # The new row is internally valid; ignore messages about older rows so a
    # slightly messy board can still accept a new task. Re-check this row only.
    mine = [message for message in messages if message.startswith(task_id)]
    if mine:
        raise BoardError("\n".join(mine))
    rows.append(row)
    return f"Added {task_id} on the {role} desk ({status}, {priority})."


def drop_examples(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    kept = []
    removed = 0
    for row in rows:
        if row.get("notes", "").startswith("EXAMPLE"):
            removed += 1
            continue
        kept.append(row)
    if removed == 0:
        raise BoardError("No rows with notes starting EXAMPLE.")
    return kept


def priority_key(row: dict[str, str]) -> tuple[int, str]:
    order = {"P0": 0, "P1": 1, "P2": 2}
    return (order.get(row.get("priority", ""), 9), row.get("id", ""))


def next_task(rows: list[dict[str, str]], actor: str) -> dict[str, str] | None:
    actor = require_actor(actor)
    if actor.startswith("human:"):
        return None
    mine = [row for row in rows if row.get("owner") == actor or row.get("role") == actor]

    def pick(status: str, owned: bool) -> dict[str, str] | None:
        choices = []
        for row in mine:
            if row.get("status") != status:
                continue
            if owned and row.get("owner") != actor:
                continue
            if not owned and row.get("owner"):
                continue
            if status == "ready" and unfinished_deps(rows, row):
                continue
            choices.append(row)
        choices.sort(key=priority_key)
        return choices[0] if choices else None

    for status in ("in_progress", "claimed"):
        found = pick(status, True)
        if found:
            return found
    return pick("ready", False)


def format_row(row: dict[str, str], rows: list[dict[str, str]]) -> str:
    pending = unfinished_deps(rows, row)
    dep = row.get("depends_on") or "-"
    if pending:
        dep = dep + " (waiting)"
    owner = row.get("owner") or "-"
    return (
        f"{row.get('id'):<6} {row.get('status', ''):<12} {row.get('priority', ''):<3} "
        f"role={row.get('role') or '-':<13} owner={owner:<16} deps={dep:<16} "
        f"{row.get('task', '')}"
    )


def format_board(rows: list[dict[str, str]], actor: str | None = None) -> str:
    ordered = sorted(rows, key=lambda row: (priority_key(row), row.get("status", "")))
    if actor and actor in AGENTS:
        ordered.sort(key=lambda row: (0 if row.get("role") == actor or row.get("owner") == actor else 1, priority_key(row)))
    lines = [format_row(row, rows) for row in ordered]
    return "\n".join(lines)


def render_xlsx(rows: list[dict[str, str]], dest: Path) -> None:
    """Write a formatted workbook with stdlib only, so a fresh clone needs no pip install."""
    import zipfile
    from xml.sax.saxutils import escape

    def clean(value: str) -> str:
        return "".join(ch for ch in value if ch in "\t\n\r" or ord(ch) >= 32)

    def cell(ref: str, value: str, style: int) -> str:
        text = escape(clean(value))
        space = ' xml:space="preserve"' if value[:1].isspace() or value[-1:].isspace() or "\n" in value else ""
        return f'<c r="{ref}" t="inlineStr" s="{style}"><is><t{space}>{text}</t></is></c>'

    def col_letter(index: int) -> str:
        letters = ""
        while index:
            index, rem = divmod(index - 1, 26)
            letters = chr(65 + rem) + letters
        return letters

    status_style = {
        "backlog": 3,
        "ready": 4,
        "claimed": 5,
        "in_progress": 6,
        "blocked": 7,
        "needs_human": 7,
        "review": 8,
        "done": 9,
        "dropped": 3,
    }
    header = "".join(cell(f"{col_letter(i)}1", name, 1) for i, name in enumerate(COLUMNS, start=1))
    body = []
    for row_number, row in enumerate(rows, start=2):
        pieces = []
        for col_index, name in enumerate(COLUMNS, start=1):
            style = 2
            if name == "status":
                style = status_style.get(row.get("status", ""), 2)
            pieces.append(cell(f"{col_letter(col_index)}{row_number}", row.get(name, ""), style))
        body.append(f'<row r="{row_number}">{"".join(pieces)}</row>')
    last_row = max(1, len(rows) + 1)
    last_col = col_letter(len(COLUMNS))
    sheet = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetViews>
    <sheetView workbookViewId="0">
      <pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>
    </sheetView>
  </sheetViews>
  <cols>
    <col min="1" max="1" width="10" customWidth="1"/>
    <col min="2" max="2" width="56" customWidth="1"/>
    <col min="3" max="6" width="16" customWidth="1"/>
    <col min="7" max="10" width="28" customWidth="1"/>
    <col min="11" max="11" width="42" customWidth="1"/>
    <col min="12" max="12" width="22" customWidth="1"/>
  </cols>
  <sheetData>
    <row r="1">{header}</row>
    {"".join(body)}
  </sheetData>
  <autoFilter ref="A1:{last_col}{last_row}"/>
</worksheet>
'''
    legend_rows = [
        ("status", "meaning"),
        ("backlog", "Orchestrator has not released this yet."),
        ("ready", "Unblocked. The desk named in role may claim it."),
        ("claimed", "Owner wrote their name. They have not started editing, or just have."),
        ("in_progress", "Owner is working on their branch."),
        ("blocked", "Waiting on a dependency, a decision, or another desk."),
        ("needs_human", "A person has to answer. Agents stop this task."),
        ("review", "PR is up. Only the orchestrator can mark it done."),
        ("done", "Accepted. It counts toward the demo."),
        ("dropped", "Cut. Do not resume it unless the orchestrator reopens it."),
        ("", ""),
        ("column", "meaning"),
        ("role", "Which desk should do the work."),
        ("owner", "Who claimed it. Empty until someone writes their name."),
        ("depends_on", "Task ids separated by semicolons. All must be done before a claim."),
        ("owned_paths", "Files this task may edit, separated by semicolons."),
        ("branch / pr", "Where the work lives. Review needs at least one of them."),
    ]
    legend_body = []
    for row_number, (left, right) in enumerate(legend_rows, start=1):
        style = 1 if row_number in {1, 12} else 2
        legend_body.append(
            f'<row r="{row_number}">{cell(f"A{row_number}", left, style)}{cell(f"B{row_number}", right, style)}</row>'
        )
    legend = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <cols>
    <col min="1" max="1" width="18" customWidth="1"/>
    <col min="2" max="2" width="78" customWidth="1"/>
  </cols>
  <sheetData>
    {"".join(legend_body)}
  </sheetData>
</worksheet>
'''
    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="11"/><name val="Calibri"/></font>
    <font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
  </fonts>
  <fills count="11">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1F4E79"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF2F2F2"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFE7E6E6"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFD6EAF8"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFCF3CF"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFDEBD0"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF5B7B1"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFE8DAEF"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFD5F5E3"/></patternFill></fill>
  </fills>
  <borders count="1"><border/></borders>
  <cellStyleXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
  </cellStyleXfs>
  <cellXfs count="10">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
    <xf numFmtId="0" fontId="0" fillId="4" borderId="0" xfId="0" applyFill="1"/>
    <xf numFmtId="0" fontId="0" fillId="5" borderId="0" xfId="0" applyFill="1"/>
    <xf numFmtId="0" fontId="0" fillId="6" borderId="0" xfId="0" applyFill="1"/>
    <xf numFmtId="0" fontId="0" fillId="7" borderId="0" xfId="0" applyFill="1"/>
    <xf numFmtId="0" fontId="0" fillId="8" borderId="0" xfId="0" applyFill="1"/>
    <xf numFmtId="0" fontId="0" fillId="9" borderId="0" xfId="0" applyFill="1"/>
    <xf numFmtId="0" fontId="0" fillId="10" borderId="0" xfId="0" applyFill="1"/>
  </cellXfs>
  <cellStyles count="1">
    <cellStyle name="Normal" xfId="0" builtinId="0"/>
  </cellStyles>
</styleSheet>
'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>
'''
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
'''
    workbook = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Job board" sheetId="1" r:id="rId1"/>
    <sheet name="Legend" sheetId="2" r:id="rId2"/>
  </sheets>
</workbook>
'''
    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
'''
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/styles.xml", styles)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
        archive.writestr("xl/worksheets/sheet2.xml", legend)


def post_message(
    coord_dir: Path,
    sender: str,
    target: str,
    body: str,
    task: str = "",
) -> Path:
    sender = require_actor(sender)
    if sender.startswith("human:"):
        outfile = messages_dir(coord_dir) / "human.md"
    else:
        outfile = messages_dir(coord_dir) / f"{sender}.md"
    target = target.strip()
    if target != "all" and target != "human" and not valid_actor(target) and target not in AGENTS:
        if target not in {"all", "human"}:
            raise BoardError(
                f"Unknown recipient {target!r}. Use a desk name, human, or all."
            )
    body = body.strip()
    if not body:
        raise BoardError("Message body is empty.")
    task_bit = f" | task {task.strip()}" if task.strip() else ""
    entry = (
        f"\n## {now_stamp()} | from {sender} | to {target}{task_bit}\n"
        f"{body}\n"
    )
    outfile.parent.mkdir(parents=True, exist_ok=True)
    if not outfile.is_file():
        title = sender
        outfile.write_text(
            f"# {title} outbox\n\nAppend only. Only {title} writes here.\n\n---\n",
            encoding="utf-8",
        )
    with outfile.open("a", encoding="utf-8") as handle:
        handle.write(entry)
    return outfile


def git_commit_coord(coord_dir: Path, message: str) -> str:
    """Commit board and message updates on the coord worktree. No-op if clean."""
    root = coord_dir.parent if coord_dir.name == "coordination" else coord_dir
    if not (root / ".git").exists() and not (root / ".git").is_file():
        return "Skipped commit (not a worktree)."
    # Desks commit at the same moment. Serialize on the board lock so git's index.lock never collides.
    with lock_board(board_path(coord_dir)):
        return _git_commit(root, message)


def _git_commit(root: Path, message: str) -> str:
    add = subprocess.run(
        ["git", "-C", str(root), "add", "-A", "--", "coordination"],
        text=True,
        capture_output=True,
    )
    if add.returncode != 0:
        raise BoardError(add.stderr.strip() or "git add failed")
    diff = subprocess.run(["git", "-C", str(root), "diff", "--cached", "--quiet"])
    if diff.returncode == 0:
        return "No coordination changes to commit."
    commit = subprocess.run(
        ["git", "-C", str(root), "commit", "-m", message],
        text=True,
        capture_output=True,
    )
    if commit.returncode != 0:
        raise BoardError(commit.stderr.strip() or commit.stdout.strip() or "git commit failed")
    return commit.stdout.strip() or "Committed coordination update."


def die(err: BoardError) -> None:
    print(str(err), file=sys.stderr)
    raise SystemExit(err.code)
