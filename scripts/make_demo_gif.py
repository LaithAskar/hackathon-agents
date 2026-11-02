#!/usr/bin/env python3
"""Render docs/demo.gif from examples/sample-project/job-board.csv.

The frames are drawn with Pillow (no screen recording). Each frame is one
moment on the Pantry sample board: tasks appear, then desks claim them and
move them through in progress, review, and done. The last frame is the CSV.

    python3 scripts/make_demo_gif.py           # write docs/demo.gif
    python3 scripts/make_demo_gif.py --check   # story matches the CSV, no Pillow

Requires Pillow to write the GIF (`pip install pillow`). Does not read or
write coordination/job-board.csv.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import coordlib  # noqa: E402

SAMPLE = ROOT / "examples" / "sample-project" / "job-board.csv"
DEFAULT_OUT = ROOT / "docs" / "demo.gif"

# Hold the empty board and the finished board a little longer than the beats
# in between. Sum is 15.7s. GIF delays are stored in centiseconds.
FRAME_MS = [1400] + [1100] * 11 + [2200]

WIDTH = 1080
HEIGHT = 704
MARGIN = 22
HEADER_H = 86
COL_HEAD_H = 30
ROW_H = 34
FOOTER_H = 48

BG = (15, 17, 21)
PANEL = (27, 31, 38)
HEADER_BAR = (22, 48, 78)
LINE = (46, 52, 62)
TEXT = (236, 239, 244)
MUTED = (164, 172, 184)
DIM = (78, 86, 98)
WHITE = (255, 255, 255)
ACCENT = (126, 196, 255)
CHANGED_BG = (36, 52, 70)

STATUS_PILL = {
    "backlog": ((72, 78, 90), (226, 230, 236)),
    "ready": ((36, 112, 184), WHITE),
    "claimed": ((176, 124, 32), WHITE),
    "in_progress": ((196, 114, 28), WHITE),
    "blocked": ((168, 64, 64), WHITE),
    "needs_human": ((168, 64, 64), WHITE),
    "review": ((124, 78, 166), WHITE),
    "done": ((32, 132, 84), WHITE),
    "dropped": ((64, 68, 76), (176, 180, 188)),
}

STATUS_LABEL = {
    "in_progress": "in progress",
    "needs_human": "needs human",
}


def load_sample() -> list[dict[str, str]]:
    rows = coordlib.load_board(SAMPLE)
    errors = coordlib.validation_errors_only(coordlib.validate_rows(rows))
    if errors:
        raise SystemExit("sample board is invalid:\n" + "\n".join(errors))
    return rows


def build_story(csv_rows: list[dict[str, str]]) -> list[dict]:
    """Moments that end on the sample CSV. Task text always comes from the file."""
    known = {row["id"] for row in csv_rows}
    state: dict[str, tuple[str, str]] = {}
    steps: list[dict] = []

    def put(task_id: str, status: str, owner: str) -> None:
        if task_id not in known:
            raise SystemExit(f"story uses {task_id}, which is not in {SAMPLE}")
        state[task_id] = (status, owner)

    def snap(caption: str, changed: list[str], when: str) -> None:
        rows = []
        for src in csv_rows:
            if src["id"] not in state:
                continue
            status, owner = state[src["id"]]
            row = dict(src)
            row["status"] = status
            row["owner"] = owner
            rows.append(row)
        steps.append({"caption": caption, "changed": changed, "rows": rows, "when": when})

    snap("Empty board on the coord branch", [], "09:00")

    put("T-001", "ready", "")
    put("T-002", "ready", "")
    snap("orchestrator adds PROJECT.md and the demo script", ["T-001", "T-002"], "09:12")

    put("T-003", "ready", "")
    put("T-007", "ready", "")
    put("T-014", "backlog", "")
    snap("Env check, sign-in screen, and a dark-mode idea", ["T-003", "T-007", "T-014"], "09:30")

    put("T-003", "claimed", "platform")
    snap("platform claims T-003", ["T-003"], "09:46")

    put("T-003", "in_progress", "platform")
    put("T-004", "ready", "")
    put("T-005", "ready", "")
    snap("platform starts the env pass. Auth and the API wait on it", ["T-003", "T-004", "T-005"], "10:20")

    put("T-001", "done", "orchestrator")
    put("T-002", "done", "orchestrator")
    put("T-003", "done", "platform")
    put("T-004", "claimed", "platform")
    put("T-007", "claimed", "frontend")
    snap(
        "Spec is done. platform claims auth. frontend claims sign-in",
        ["T-001", "T-002", "T-003", "T-004", "T-007"],
        "11:05",
    )

    put("T-004", "in_progress", "platform")
    put("T-007", "in_progress", "frontend")
    put("T-008", "ready", "")
    snap("Auth and sign-in are in progress. The list screen is next", ["T-004", "T-007", "T-008"], "11:40")

    put("T-004", "done", "platform")
    put("T-007", "done", "frontend")
    put("T-005", "claimed", "backend")
    put("T-006", "ready", "")
    put("T-008", "claimed", "frontend")
    put("T-010", "ready", "")
    put("T-011", "ready", "")
    snap(
        "Auth and sign-in land. backend claims the items API",
        ["T-004", "T-005", "T-006", "T-007", "T-008", "T-010", "T-011"],
        "12:20",
    )

    put("T-005", "in_progress", "backend")
    put("T-008", "in_progress", "frontend")
    put("T-011", "claimed", "platform")
    snap(
        "backend builds the API. frontend starts the list. platform claims deploy",
        ["T-005", "T-008", "T-011"],
        "13:10",
    )

    put("T-005", "done", "backend")
    put("T-006", "in_progress", "backend")
    put("T-009", "ready", "")
    put("T-012", "backlog", "")
    snap("Items API is done. Toggle endpoint is in progress", ["T-005", "T-006", "T-009", "T-012"], "14:05")

    put("T-006", "review", "backend")
    put("T-013", "needs_human", "platform")
    snap("Toggle PR is in review. Cookie domain needs a human", ["T-006", "T-013"], "14:50")

    put("T-014", "dropped", "")
    snap("orchestrator drops dark mode. It is off the click path", ["T-014"], "15:05")

    snap("Pantry, mid-hackathon. Claimed work stays with that desk", [], "15:10")

    if len(steps) != len(FRAME_MS):
        raise SystemExit(f"{len(steps)} frames but {len(FRAME_MS)} durations")
    for row in csv_rows:
        got = state.get(row["id"])
        expected = (row["status"], row["owner"])
        if got != expected:
            raise SystemExit(f"{row['id']}: story ends at {got}, CSV has {expected}")
    last_ids = [row["id"] for row in steps[-1]["rows"]]
    csv_ids = [row["id"] for row in csv_rows]
    if last_ids != csv_ids:
        raise SystemExit(f"last frame ids {last_ids} != CSV {csv_ids}")
    return steps


def find_font(weight: str) -> Path:
    """Prefer Inter, then fonts commonly installed on Linux and macOS."""
    names = {
        "regular": [
            "Inter-Regular.ttf",
            "DejaVuSans.ttf",
            "LiberationSans-Regular.ttf",
            "NotoSans-Regular.ttf",
        ],
        "bold": [
            "Inter-Bold.ttf",
            "Inter-SemiBold.ttf",
            "DejaVuSans-Bold.ttf",
            "LiberationSans-Bold.ttf",
            "NotoSans-Bold.ttf",
        ],
        "mono": [
            "JetBrainsMono-Regular.ttf",
            "DejaVuSansMono.ttf",
            "LiberationMono-Regular.ttf",
            "NotoSansMono-Regular.ttf",
        ],
    }[weight]
    roots = [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path.home() / ".fonts",
        Path("/Library/Fonts"),
        Path("/System/Library/Fonts"),
        Path.home() / "Library/Fonts",
    ]
    for root in roots:
        if not root.is_dir():
            continue
        for name in names:
            matches = list(root.rglob(name))
            if matches:
                return matches[0]
    raise SystemExit(
        "Could not find a TTF font for "
        f"{weight}. Install Inter or DejaVu Sans, then rerun this script."
    )


def fit(draw, text: str, font, max_width: float) -> str:
    if draw.textlength(text, font=font) <= max_width:
        return text
    ellipsis = "…"
    trimmed = text
    while trimmed and draw.textlength(trimmed + ellipsis, font=font) > max_width:
        trimmed = trimmed[:-1]
    return trimmed.rstrip() + ellipsis


def render_frames(steps: list[dict]):
    from PIL import Image, ImageDraw, ImageFont

    regular = ImageFont.truetype(str(find_font("regular")), 16)
    small = ImageFont.truetype(str(find_font("regular")), 14)
    bold = ImageFont.truetype(str(find_font("bold")), 22)
    bold_small = ImageFont.truetype(str(find_font("bold")), 14)
    mono = ImageFont.truetype(str(find_font("mono")), 14)
    fonts = (regular, small, bold, bold_small, mono)

    columns = (
        ("id", 36, 78),
        ("status", 118, 132),
        ("role", 258, 130),
        ("owner", 396, 140),
        ("task", 544, WIDTH - MARGIN - 544),
    )

    frames = []
    for step in steps:
        image = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(image)
        by_id = {row["id"]: row for row in step["rows"]}
        changed = set(step["changed"])

        draw.rounded_rectangle((MARGIN, 16, WIDTH - MARGIN, 16 + HEADER_H), 12, fill=HEADER_BAR)
        draw.text((MARGIN + 18, 36), "Pantry job board", font=bold, fill=WHITE, anchor="lm")
        draw.text(
            (MARGIN + 18, 64),
            "Sign in, add milk, check it off  ·  platform desk is auth",
            font=small,
            fill=(198, 214, 232),
            anchor="lm",
        )
        draw.rounded_rectangle((WIDTH - MARGIN - 168, 30, WIDTH - MARGIN - 16, 54), 8, fill=(14, 32, 54))
        draw.text((WIDTH - MARGIN - 92, 42), step["when"] + " UTC", font=mono, fill=ACCENT, anchor="mm")

        table_top = 16 + HEADER_H + 12
        table_bottom = table_top + COL_HEAD_H + 14 * ROW_H
        draw.rounded_rectangle((MARGIN, table_top, WIDTH - MARGIN, table_bottom), 10, fill=PANEL)

        head_y = table_top + COL_HEAD_H / 2
        for title, x, _width in columns:
            draw.text((x, head_y), title.upper(), font=bold_small, fill=MUTED, anchor="lm")
        draw.line((MARGIN + 12, table_top + COL_HEAD_H, WIDTH - MARGIN - 12, table_top + COL_HEAD_H), fill=LINE)

        for index in range(14):
            task_id = f"T-{index + 1:03d}"
            y = table_top + COL_HEAD_H + index * ROW_H
            row = by_id.get(task_id)
            if task_id in changed:
                draw.rectangle((MARGIN + 4, y + 3, MARGIN + 8, y + ROW_H - 3), fill=ACCENT)
                draw.rectangle((MARGIN + 10, y + 2, WIDTH - MARGIN - 6, y + ROW_H - 2), fill=CHANGED_BG)
            center_y = y + ROW_H / 2
            if row is None:
                draw.text((columns[0][1], center_y), task_id, font=small, fill=DIM, anchor="lm")
            else:
                draw.text((columns[0][1], center_y), task_id, font=bold_small, fill=TEXT, anchor="lm")
                label = STATUS_LABEL.get(row["status"], row["status"])
                fill, ink = STATUS_PILL.get(row["status"], ((80, 80, 80), WHITE))
                pill_w = max(96, int(draw.textlength(label, font=small)) + 18)
                pill_box = (columns[1][1], center_y - 11, columns[1][1] + pill_w, center_y + 11)
                draw.rounded_rectangle(pill_box, 11, fill=fill)
                draw.text((columns[1][1] + pill_w / 2, center_y), label, font=small, fill=ink, anchor="mm")
                draw.text((columns[2][1], center_y), row["role"], font=regular, fill=TEXT, anchor="lm")
                owner = row["owner"] or "—"
                owner_fill = TEXT if row["owner"] else DIM
                draw.text((columns[3][1], center_y), owner, font=regular, fill=owner_fill, anchor="lm")
                task = fit(draw, row["task"], regular, columns[4][2])
                task_fill = DIM if row["status"] == "dropped" else TEXT
                draw.text((columns[4][1], center_y), task, font=regular, fill=task_fill, anchor="lm")
            if index < 13:
                draw.line((MARGIN + 12, y + ROW_H, WIDTH - MARGIN - 12, y + ROW_H), fill=LINE)

        counts: dict[str, int] = {}
        for row in step["rows"]:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        summary = (
            f"{len(step['rows'])} on the board"
            f"  ·  {counts.get('done', 0)} done"
            f"  ·  {counts.get('in_progress', 0)} in progress"
            f"  ·  {counts.get('review', 0)} in review"
        )
        footer_y = table_bottom + 16
        caption = fit(draw, step["caption"], regular, WIDTH - MARGIN * 2 - 20)
        draw.text((MARGIN + 8, footer_y + 8), caption, font=regular, fill=TEXT, anchor="lm")
        draw.text((MARGIN + 8, footer_y + 30), summary, font=small, fill=MUTED, anchor="lm")
        frames.append(image)
    return frames, fonts


def quantize(frames):
    from PIL import Image

    # One palette for every frame so status colors do not flicker between beats.
    sheet = Image.new("RGB", (WIDTH, HEIGHT * len(frames)))
    for index, frame in enumerate(frames):
        sheet.paste(frame, (0, index * HEIGHT))
    palette = sheet.quantize(colors=64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    return [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]


def write_gif(frames, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    quantized = quantize(frames)
    quantized[0].save(
        dest,
        save_all=True,
        append_images=quantized[1:],
        duration=FRAME_MS,
        loop=0,
        optimize=True,
        disposal=2,
    )


def gif_duration_seconds(data: bytes) -> float:
    total = 0
    start = 0
    marker = b"\x21\xf9\x04"
    while True:
        found = data.find(marker, start)
        if found < 0:
            break
        total += int.from_bytes(data[found + 4 : found + 6], "little")
        start = found + 6
    return total / 100


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Render the Pantry job-board demo GIF.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check that the story ends on the sample CSV and do not draw",
    )
    args = parser.parse_args(argv)
    rows = load_sample()
    steps = build_story(rows)
    seconds = sum(FRAME_MS) / 1000
    if args.check:
        print(f"ok: {len(steps)} frames, {seconds:.1f}s, {len(rows)} tasks match {SAMPLE}")
        return
    try:
        frames, _fonts = render_frames(steps)
    except ModuleNotFoundError as err:
        if err.name != "PIL":
            raise
        raise SystemExit("Pillow is required to draw the GIF. Install it with: pip install pillow") from None
    write_gif(frames, args.out)
    data = args.out.read_bytes()
    written = gif_duration_seconds(data)
    size_kb = len(data) / 1024
    print(f"wrote {args.out} ({len(steps)} frames, {written:.1f}s, {size_kb:.0f} KB)")
    if not (10 <= written <= 20):
        raise SystemExit(f"GIF duration {written:.1f}s is outside 10–20s")
    if len(data) >= 3_000_000:
        raise SystemExit(f"GIF is {size_kb:.0f} KB, over the 3 MB cap")


if __name__ == "__main__":
    main()
