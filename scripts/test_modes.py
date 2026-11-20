# /// script
# dependencies = ["pillow>=10.1"]
# ///
"""LED and dots modes. Run: uv run scripts/test_modes.py"""
import os
import sys
import tempfile

from PIL import Image, ImageChops, ImageDraw, ImageSequence, ImageStat

sys.path.insert(0, os.path.dirname(__file__))
import animate  # noqa: E402
from ascii import ROUND, SUBPIXELS, convert, main, to_html, to_png, to_text  # noqa: E402

assert {"led", "dots", "stipple"} <= set(SUBPIXELS)
tmp = tempfile.mkdtemp()
ramp = Image.linear_gradient("L").rotate(90).resize((200, 100)).convert("RGB")  # dark left, bright right

for mode in ("led", "dots"):
    grid = convert(ramp, 40, aspect=1.0, mode=mode, autocontrast=False)
    text = to_text(grid)
    assert set(text) <= set(ROUND + "\n") and set("●•·") <= set(text), (mode, text)  # round glyphs by size
    assert text.split("\n")[0].startswith(" ") and text.split("\n")[0].endswith("●"), mode
    assert to_png(grid, mode=mode, aspect=1.0).tobytes() == to_png(grid, mode=mode, aspect=1.0).tobytes(), "deterministic"
    assert "●" in to_html(grid, aspect=1.0)

# Halftone tone is right from a distance: a flat gray's mean is the gray, on black and on white paper.
for bg in ("black", "white"):
    for v in (30, 90, 128, 200, 240):
        g = convert(Image.new("RGB", (60, 60), (v, v, v)), 12, aspect=1.0, mode="dots", bg=bg, autocontrast=False)
        mean = ImageStat.Stat(to_png(g, bg, mode="dots", font_size=20, aspect=1.0).convert("L")).mean[0]
        assert abs(mean - v) < 2.5, (bg, v, mean)
orange = convert(Image.new("RGB", (60, 60), (200, 80, 30)), 12, aspect=1.0, mode="dots", autocontrast=False)
assert [round(c) for c in ImageStat.Stat(to_png(orange, mode="dots", font_size=20, aspect=1.0)).mean] == [200, 80, 30]

# LED: every lamp is the same round disc on an even grid; unlit lamps stay faintly visible.
white = convert(Image.new("RGB", (40, 40), "white"), 4, aspect=1.0, mode="led")
lit = to_png(white, "none", mode="led", font_size=26, aspect=1.0).getchannel("A")  # no glow: just the lamps
assert lit.size == (64, 64)
cell = lit.crop((0, 0, 16, 16))
assert all(lit.crop((x, y, x + 16, y + 16)).tobytes() == cell.tobytes() for x in (0, 16, 48) for y in (0, 32, 48)), "even grid"
assert cell.tobytes() == cell.transpose(Image.Transpose.FLIP_LEFT_RIGHT).tobytes() == cell.transpose(Image.Transpose.TRANSPOSE).tobytes()
assert cell.getpixel((8, 8)) == 255 and cell.getpixel((0, 0)) == 0 and 0 < cell.getpixel((8, 1)) < 255, "round, soft edge"
assert to_png(white, mode="led", font_size=26, aspect=1.0).getpixel((24, 24)) == (255, 255, 255)
dark = to_png(convert(Image.new("RGB", (40, 40)), 4, aspect=1.0, mode="led"), mode="led", font_size=26, aspect=1.0)
assert 0 < dark.getpixel((8, 8))[0] < 40 and dark.getpixel((0, 0)) == (0, 0, 0), "unlit lamp on a black board"
amber = to_png(convert(ramp, 20, aspect=1.0, mode="led"), fg=(255, 176, 0), mode="led", font_size=26, aspect=1.0)
assert amber.getpixel((19 * 16 + 8, 8))[2] < 60, "--fg colors the lamps"

# A still part of the picture stays byte-identical when another part changes (glow and corner dots are local).
a = ramp.copy()
b = ramp.copy()
ImageDraw.Draw(b).rectangle((150, 0, 199, 99), fill=(255, 0, 0))
for mode, fs in (("led", 26), ("dots", 20)):
    pa, pb = (to_png(convert(im, 40, aspect=1.0, mode=mode, autocontrast=False), mode=mode, font_size=fs, aspect=1.0)
              for im in (a, b))
    left = (0, 0, pa.width // 2, pa.height)
    assert pa.crop(left).tobytes() == pb.crop(left).tobytes() and pa.tobytes() != pb.tobytes(), mode

# Transparent background: dots and lamps carry their own alpha.
assert to_png(grid, "none", mode="dots", aspect=1.0).mode == "RGBA"

# Stipple: same-size dots. White fills the grid, black leaves it empty, a mid gray lights half the cells.
cells = lambda im: convert(im, 16, aspect=1.0, mode="stipple", autocontrast=False)
on = lambda g: sum(ch == "●" for row in g for ch, _ in row)
white, black, gray = (cells(Image.new("RGB", (64, 64), c)) for c in ("white", "black", (128, 128, 128)))
assert on(white) == 16 * 16 and on(black) == 0 and on(gray) == 16 * 16 // 2, (on(white), on(black), on(gray))
board = to_png(white, mode="stipple", font_size=14, aspect=1.0)
assert board.size == (16 * 8, 16 * 8) and board.getpixel((0, 0)) == (0, 0, 0) and board.getpixel((4, 4))[0] > 200
assert board.crop((0, 0, 8, 8)).tobytes() == board.crop((8, 0, 16, 8)).tobytes(), "every dot is the same disc"

# CLI: square cells for files (16 px lamps, 12 px dots), text keeps aspect 0.5.
src = os.path.join(tmp, "in.png")
ramp.save(src)
main([src, "--mode", "led", "-w", "10", "-o", os.path.join(tmp, "led.png")])
assert Image.open(os.path.join(tmp, "led.png")).size == (160, 80)
main([src, "--mode", "dots", "-w", "10", "--bg", "white", "-o", os.path.join(tmp, "dots.png")])
assert Image.open(os.path.join(tmp, "dots.png")).size == (120, 60)
main([src, "--mode", "dots", "-w", "10", "-o", os.path.join(tmp, "dots.txt")])
assert len(open(os.path.join(tmp, "dots.txt"), encoding="utf-8").read().splitlines()) == 2

# Animation: a scene in both modes to GIF and the HTML player, and an effect on a still.
for mode in ("led", "dots"):
    gif = os.path.join(tmp, mode + ".gif")
    animate.main(["--scene", "planet", "--mode", mode, "-w", "24", "-o", gif])
    im = Image.open(gif)
    assert im.n_frames > 20 and im.width == 24 * (16 if mode == "led" else 12), (mode, im.size)
    assert len({f.convert("RGB").tobytes() for f in ImageSequence.Iterator(im)}) > 10
    animate.main(["--scene", "planet", "--mode", mode, "-w", "24", "-o", os.path.join(tmp, mode + ".html")])
animate.main([src, "--effect", "matrix", "--mode", "led", "--fg", "amber", "-w", "12", "-o", os.path.join(tmp, "fx.gif")])
fx = Image.open(os.path.join(tmp, "fx.gif"))
fx.seek(fx.n_frames - 1)
last = fx.convert("RGB")
assert ImageChops.difference(last, Image.open(os.path.join(tmp, "fx.gif")).convert("RGB")).getbbox(), "the effect moves"
print("ok")
