#!/usr/bin/env python3
"""Library tests for the job board. No network, no extra packages."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import coordlib  # noqa: E402


def sample_rows():
    return coordlib.load_board(ROOT / "coordination" / "job-board.csv")


def gif_delays_cs(data: bytes) -> list[int]:
    delays = []
    start = 0
    marker = b"\x21\xf9\x04"
    while True:
        found = data.find(marker, start)
        if found < 0 or found + 6 > len(data):
            break
        delays.append(int.from_bytes(data[found + 4 : found + 6], "little"))
        start = found + 6
    return delays


class BoardTest(unittest.TestCase):
    def test_seed_validates(self):
        rows = sample_rows()
        messages = coordlib.validate_rows(rows)
        self.assertEqual(coordlib.validation_errors_only(messages), [])
        self.assertGreaterEqual(len(rows), 8)

    def test_sample_project_board_validates(self):
        board = ROOT / "examples" / "sample-project" / "job-board.csv"
        rows = coordlib.load_board(board)
        messages = coordlib.validate_rows(rows)
        self.assertEqual(messages, [])
        self.assertGreaterEqual(len(rows), 10)
        self.assertLessEqual(len(rows), 15)
        self.assertEqual(
            {row["role"] for row in rows},
            {"orchestrator", "frontend", "backend", "platform"},
        )
        statuses = {row["status"] for row in rows}
        for status in ("backlog", "ready", "claimed", "in_progress", "review", "done", "needs_human", "dropped"):
            self.assertIn(status, statuses)
        env = os.environ.copy()
        env["HACKATHON_COORD_DIR"] = str(board.parent)
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "board.py"), "validate"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok: ", result.stdout)
        messages_dir = board.parent / "messages"
        outboxes = [path for path in messages_dir.glob("*.md") if path.name != "README.md"]
        self.assertGreaterEqual(len(outboxes), 2)
        for path in outboxes:
            text = path.read_text(encoding="utf-8")
            self.assertIn("| from ", text)
            self.assertIn("| to ", text)

    def test_demo_gif_story_and_file(self):
        check = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "make_demo_gif.py"), "--check"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(check.returncode, 0, check.stderr)
        data = (ROOT / "docs" / "demo.gif").read_bytes()
        self.assertTrue(data.startswith(b"GIF8"))
        self.assertIn(b"NETSCAPE2.0", data)
        self.assertLess(len(data), 3_000_000)
        delays = gif_delays_cs(data)
        self.assertGreaterEqual(len(delays), 8)
        seconds = sum(delays) / 100
        self.assertGreaterEqual(seconds, 10)
        self.assertLessEqual(seconds, 20)

    def test_claim_conflict_and_dependency(self):
        rows = sample_rows()
        message = coordlib.claim(rows, "T-004", "backend")
        self.assertIn("Claimed T-004", message)
        self.assertEqual(rows[3]["owner"], "backend")
        self.assertEqual(rows[3]["status"], "claimed")
        with self.assertRaises(coordlib.BoardError) as conflict:
            coordlib.claim(rows, "T-004", "frontend")
        self.assertEqual(conflict.exception.code, 2)
        again = coordlib.claim(rows, "T-004", "backend")
        self.assertIn("already claimed", again)
        with self.assertRaises(coordlib.BoardError) as blocked:
            coordlib.claim(sample_rows(), "T-006", "frontend")
        self.assertEqual(blocked.exception.code, 3)

    def test_human_takes_a_row_from_a_desk(self):
        rows = sample_rows()
        coordlib.claim(rows, "T-004", "backend")
        message = coordlib.claim(rows, "T-004", "human:laith")
        self.assertIn("took T-004 from backend", message)
        row = next(item for item in rows if item["id"] == "T-004")
        self.assertEqual(row["owner"], "human:laith")
        self.assertIn("HUMAN:", row["notes"])
        with self.assertRaises(coordlib.BoardError) as refused:
            coordlib.claim(rows, "T-004", "backend")
        self.assertEqual(refused.exception.code, 2)
        coordlib.claim(rows, "T-001", "human:laith")
        self.assertEqual(rows[0]["status"], "claimed")
        self.assertEqual(coordlib.validation_errors_only(coordlib.validate_rows(rows)), [])

    def test_assign_clears_the_old_desk(self):
        rows = sample_rows()
        coordlib.claim(rows, "T-004", "backend")
        coordlib.set_status(rows, "T-004", "backend", "blocked", note="stuck")
        coordlib.set_status(rows, "T-004", "orchestrator", "ready", role="frontend")
        self.assertIn("Claimed", coordlib.claim(rows, "T-004", "frontend"))
        self.assertEqual(coordlib.validation_errors_only(coordlib.validate_rows(rows)), [])

    def test_only_the_lead_reopens(self):
        rows = sample_rows()
        coordlib.set_status(rows, "T-009", "orchestrator", "done")
        with self.assertRaises(coordlib.BoardError):
            coordlib.set_status(rows, "T-009", "backend", "in_progress")
        coordlib.set_status(rows, "T-007", "orchestrator", "dropped", note="cut")
        with self.assertRaises(coordlib.BoardError):
            coordlib.set_status(rows, "T-007", "platform", "ready")
        coordlib.set_status(rows, "T-007", "orchestrator", "ready")

    def test_validate_reports_a_dependency_cycle(self):
        rows = sample_rows()
        rows[0]["depends_on"] = "T-002"
        rows[1]["depends_on"] = "T-001"
        errors = coordlib.validation_errors_only(coordlib.validate_rows(rows))
        self.assertTrue(any("cycle" in error for error in errors), errors)

    def test_claim_is_idempotent_after_start(self):
        rows = sample_rows()
        coordlib.claim(rows, "T-004", "backend")
        coordlib.set_status(rows, "T-004", "backend", "in_progress")
        self.assertIn("already claimed", coordlib.claim(rows, "T-004", "backend"))

    def test_bad_saves_fail_with_a_plain_error(self):
        source = (ROOT / "coordination" / "job-board.csv").read_text(encoding="utf-8-sig")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "job-board.csv"
            path.write_text(source.replace("Fill in", "Fill in caf\u00e9"), encoding="cp1252")
            with self.assertRaises(coordlib.BoardError) as encoding:
                coordlib.load_board(path)
            self.assertIn("CSV UTF-8", str(encoding.exception))
            lines = source.splitlines()
            lines[4:5] = ["<<<<<<< HEAD", lines[4], "=======", lines[4], ">>>>>>> theirs"]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaises(coordlib.BoardError) as conflict:
                coordlib.load_board(path)
            self.assertIn("merge conflict", str(conflict.exception))

    def test_lock_without_fcntl(self):
        calls = []

        class FakeMsvcrt:
            LK_LOCK = 1
            LK_UNLCK = 0

            @staticmethod
            def locking(fd, mode, size):
                calls.append((mode, size))

        saved = {name: sys.modules.get(name) for name in ("fcntl", "msvcrt")}
        sys.modules["fcntl"] = None
        sys.modules["msvcrt"] = FakeMsvcrt
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with coordlib.lock_board(Path(tmp) / "job-board.csv"):
                    pass
        finally:
            for name, module in saved.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module
        self.assertEqual(calls, [(1, 1), (0, 1)])

    def test_worker_cannot_mark_done(self):
        rows = sample_rows()
        with self.assertRaises(coordlib.BoardError):
            coordlib.set_status(rows, "T-009", "backend", "done")
        message = coordlib.set_status(rows, "T-009", "orchestrator", "done", note="accepted")
        self.assertIn("done", message)
        self.assertEqual(
            next(row for row in rows if row["id"] == "T-009")["status"],
            "done",
        )

    def test_start_requires_claim(self):
        rows = sample_rows()
        with self.assertRaises(coordlib.BoardError):
            coordlib.set_status(rows, "T-004", "backend", "in_progress", branch="agent/backend/T-004")
        coordlib.claim(rows, "T-004", "backend")
        coordlib.set_status(rows, "T-004", "backend", "in_progress", branch="agent/backend/T-004")
        row = next(item for item in rows if item["id"] == "T-004")
        self.assertEqual(row["status"], "in_progress")
        self.assertEqual(row["branch"], "agent/backend/T-004")

    def test_review_needs_a_pointer(self):
        rows = sample_rows()
        coordlib.claim(rows, "T-004", "backend")
        coordlib.set_status(rows, "T-004", "backend", "in_progress")
        with self.assertRaises(coordlib.BoardError):
            coordlib.set_status(rows, "T-004", "backend", "review")
        coordlib.set_status(rows, "T-004", "backend", "review", pr="https://example.com/pull/9")
        row = next(item for item in rows if item["id"] == "T-004")
        self.assertEqual(row["status"], "review")

    def test_path_overlap_warns(self):
        rows = sample_rows()
        coordlib.claim(rows, "T-004", "backend")
        messages = coordlib.validate_rows(rows)
        self.assertTrue(any("T-004" in message and "T-009" in message for message in messages))
        self.assertEqual(coordlib.validation_errors_only(messages), [])

    def test_round_trip_and_xlsx(self):
        rows = sample_rows()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "job-board.csv"
            coordlib.save_board(dest, rows)
            loaded = coordlib.load_board(dest)
            self.assertEqual(loaded[0]["id"], "T-001")
            self.assertEqual(list(loaded[0].keys()), coordlib.COLUMNS)
            workbook = Path(tmp) / "job-board.xlsx"
            coordlib.render_xlsx(loaded, workbook)
            with zipfile.ZipFile(workbook) as archive:
                sheet = archive.read("xl/worksheets/sheet1.xml").decode()
                styles = archive.read("xl/styles.xml").decode()
                legend = archive.read("xl/worksheets/sheet2.xml").decode()
            self.assertIn("T-001", sheet)
            self.assertIn("frozen", sheet)
            self.assertLess(sheet.index("</sheetData>"), sheet.index("<autoFilter"))
            self.assertIn("claimed", legend)
            self.assertIn("<fills", styles)

    def test_drop_examples_and_add(self):
        rows = sample_rows()
        kept = coordlib.drop_examples(rows)
        self.assertEqual(kept, [])
        message = coordlib.add_task(
            kept,
            "orchestrator",
            "Ship the click path",
            role="frontend",
            priority="P0",
            owned_paths="web/",
            status="ready",
        )
        self.assertIn("T-001", message)
        self.assertEqual(kept[0]["role"], "frontend")
        with self.assertRaises(coordlib.BoardError):
            coordlib.add_task(kept, "frontend", "nope", role="frontend")

    def test_next_resumes_a_claim(self):
        row = coordlib.next_task(sample_rows(), "frontend")
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["id"], "T-005")

    def test_stop_and_message_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            coord = Path(tmp)
            (coord / "messages").mkdir()
            (coord / "messages" / "frontend.md").write_text("# frontend outbox\n\n---\n", encoding="utf-8")
            os.environ["HACKATHON_COORD_DIR"] = str(coord)
            try:
                path = coordlib.stop_path(coord)
                path.write_text("Judging in 10 minutes.\n", encoding="utf-8")
                self.assertIn("Judging", coordlib.read_stop(coord) or "")
                outfile = coordlib.post_message(coord, "frontend", "backend", "Need the shape.", "T-006")
                text = outfile.read_text(encoding="utf-8")
                self.assertIn("to backend", text)
                self.assertIn("Need the shape.", text)
                self.assertTrue(str(outfile).endswith("frontend.md"))
            finally:
                os.environ.pop("HACKATHON_COORD_DIR", None)

    def test_cli_respects_coord_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            coord = Path(tmp)
            coordlib.save_board(coord / "job-board.csv", sample_rows())
            env = os.environ.copy()
            env["HACKATHON_COORD_DIR"] = str(coord)
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "board.py"), "claim", "T-004", "--as", "backend"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            updated = coordlib.load_board(coord / "job-board.csv")
            row = next(item for item in updated if item["id"] == "T-004")
            self.assertEqual(row["status"], "claimed")
            original = coordlib.load_board(ROOT / "coordination" / "job-board.csv")
            original_row = next(item for item in original if item["id"] == "T-004")
            self.assertEqual(original_row["status"], "ready")


if __name__ == "__main__":
    unittest.main()
