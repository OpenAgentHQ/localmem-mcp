"""Render the animated terminal demo used on the Integrations page.

The GIF is a synthesized terminal session, not a screen recording — that keeps
it legible at any size, reproducible when the copy changes, and small enough to
commit. Colours track the SVG banner so the docs site reads as one thing.

Regenerate after editing SCRIPT below:

    pip install pillow
    python scripts/make_demo_gif.py

Writes docs/assets/demo.gif.
"""

from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_SIZE = 17
LINE_H = 27
PAD_X = 30
PAD_TOP = 68  # below the window chrome
CHROME_H = 42
WIDTH = 940

BG = (15, 14, 12)
CHROME = (33, 30, 26)
BORDER = (52, 48, 41)
TITLE = (124, 120, 111)
COMMENT = (111, 108, 100)
ACCENT = (224, 138, 99)
TEXT = (245, 242, 234)
GREEN = (114, 173, 104)
AMBER = (217, 167, 66)
MUTED = (124, 120, 111)

# Each line is (kind, text). Kinds:
#   comment  — dimmed, appears instantly
#   cmd      — shell command, typed out after a "$ " sigil
#   ask      — prompt to the agent, typed out after a "> " sigil
#   ok       — success line, appears instantly
#   tool     — tool call, appears instantly
#   note     — dimmed footer, appears instantly
#   blank    — spacer
SCRIPT: list[tuple[str, str]] = [
    ("comment", "// one server, every agent — and nothing leaves your machine"),
    ("blank", ""),
    ("cmd", "claude mcp add localmem -- uvx localmem-mcp"),
    ("ok", "connected"),
    ("cmd", "codex mcp add localmem -- uvx localmem-mcp"),
    ("ok", "connected"),
    ("cmd", "gemini mcp add localmem uvx localmem-mcp"),
    ("ok", "connected"),
    ("blank", ""),
    ("comment", "// monday, in Cursor"),
    ("ask", "Remember: we chose SQLite over Postgres — it ships in one file."),
    ("tool", "store_memory  →  #42   tags: decision, architecture"),
    ("blank", ""),
    ("comment", "// thursday, a brand new session in Zed"),
    ("ask", "What database did we pick, and why?"),
    ("tool", 'search_memory  →  0.87   "we chose SQLite over Postgres"'),
    ("blank", ""),
    ("note", "network calls: 0    ~/.localmem/memories.db"),
]

# Typing is chunked so the frame count stays reasonable; the GIF is full-frame.
CHARS_PER_FRAME = 3
MS_TYPE = 45
MS_AFTER_TYPED = 520
MS_INSTANT = 240
MS_HOLD_END = 2600

HEIGHT = PAD_TOP + LINE_H * len(SCRIPT) + 26


def _sigil(kind: str) -> tuple[str, tuple[int, int, int]]:
    if kind == "cmd":
        return "$ ", ACCENT
    if kind == "ask":
        return "> ", ACCENT
    if kind == "ok":
        return "  ✓ ", GREEN
    if kind == "tool":
        return "  ● ", AMBER
    return "", TEXT


def _body_colour(kind: str) -> tuple[int, int, int]:
    return {
        "comment": COMMENT,
        "ok": GREEN,
        "tool": TEXT,
        "note": MUTED,
    }.get(kind, TEXT)


def render(state: list[tuple[str, str]], cursor_line: int | None, font) -> Image.Image:
    """Draw one frame. `state` is the visible prefix of SCRIPT, already truncated."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, WIDTH - 1, HEIGHT - 1], outline=BORDER)
    d.rectangle([1, 1, WIDTH - 2, CHROME_H], fill=CHROME)
    d.line([1, CHROME_H, WIDTH - 2, CHROME_H], fill=BORDER)
    for i, colour in enumerate([(217, 110, 92), (217, 167, 66), (114, 173, 104)]):
        d.ellipse([22 + i * 22, 15, 34 + i * 22, 27], fill=colour)
    d.text((WIDTH // 2, 21), "localmem-mcp", font=font, fill=TITLE, anchor="mm")

    advance = font.getlength("M")
    for row, (kind, text) in enumerate(state):
        y = PAD_TOP + row * LINE_H
        if kind == "blank":
            continue
        sigil, sig_colour = _sigil(kind)
        if sigil:
            d.text((PAD_X, y), sigil, font=font, fill=sig_colour)
        d.text((PAD_X + advance * len(sigil), y), text, font=font, fill=_body_colour(kind))
        if row == cursor_line:
            cx = PAD_X + advance * (len(sigil) + len(text))
            d.rectangle([cx, y + 3, cx + advance - 1, y + 20], fill=ACCENT)

    return img


def main() -> None:
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    frames: list[Image.Image] = []
    durations: list[int] = []

    shown: list[tuple[str, str]] = []
    for kind, text in SCRIPT:
        if kind in ("cmd", "ask"):
            shown.append((kind, ""))
            idx = len(shown) - 1
            for n in range(0, len(text) + 1, CHARS_PER_FRAME):
                shown[idx] = (kind, text[:n])
                frames.append(render(shown, idx, font))
                durations.append(MS_TYPE)
            shown[idx] = (kind, text)
            frames.append(render(shown, idx, font))
            durations.append(MS_AFTER_TYPED)
        else:
            shown.append((kind, text))
            frames.append(render(shown, None, font))
            durations.append(MS_INSTANT if kind != "blank" else 60)

    durations[-1] = MS_HOLD_END

    out = pathlib.Path(__file__).resolve().parent.parent / "docs" / "assets" / "demo.gif"
    quantized = [f.quantize(colors=32, method=Image.MEDIANCUT, dither=Image.NONE) for f in frames]
    quantized[0].save(
        out,
        save_all=True,
        append_images=quantized[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    print(f"{out}  {len(frames)} frames  {out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
