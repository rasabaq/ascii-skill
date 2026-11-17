# /// script
# dependencies = ["pillow>=10.1"]
# ///
"""Run: uv run scripts/test_ascii.py"""
import contextlib
import io
import os
import re
import sys
import tempfile

from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from ascii import CHARSETS, PHOTO_INK, STYLES, convert, main, to_ansi, to_html, to_png, to_text, underlay  # noqa: E402

# Left half black, right half white.
img = Image.new("RGB", (40, 20), "black")
img.paste((255, 255, 255), (20, 0, 40, 20))

grid = convert(img, width=10, charset="standard")
assert len(grid) == 2 and len(grid[0]) == 10, "rows follow aspect 0.5"
assert grid[0][0][0] == " " and grid[0][-1][0] == "@", "dark bg: white is dense"
assert convert(img, width=10, bg="white")[0][0][0] == "@", "light bg: black is dense"
assert convert(img, width=10, invert=True)[0][0][0] == "@", "invert flips"
assert convert(img, width=10, charset="ab")[0][-1][0] == "a", "custom ramp"

# Transparent pixels become background (blank), any mode loads.
clear = Image.new("RGBA", (10, 10), (255, 255, 255, 0))
assert to_text(convert(clear, width=5)).strip() == ""
for mode in ("L", "P", "CMYK", "LA", "1", "I;16", "F"):
    convert(img.convert(mode) if mode not in ("I;16", "F") else img.convert("L").convert(mode), width=8)

# Dithering keeps a mid-gray from collapsing into one glyph.
gray = Image.new("L", (100, 50), 100)
assert len(set(to_text(convert(gray, width=40, charset="minimal", dither=True)))) > 2

assert "\x1b[38;2;255;255;255m@" in to_ansi(grid)
assert "<pre" in to_html(grid) and "&lt;" in to_html([[("<", (1, 2, 3))]])

# PNG keeps the source shape: a square image gives a square PNG.
sq = to_png(convert(Image.new("RGB", (300, 300), "white"), width=60))
assert abs(sq.width / sq.height - 1) < 0.05, sq.size

# Braille gets a real font, not the empty "missing glyph" box.
from ascii import _render, font  # noqa: E402
f = font(12, "⣿")
assert _render(f, "⣿") != _render(f, "\U0010fffd")

# Braille: 2x4 dots per char, with braille's own bit order (dot 7 is bottom left = 0x40).
white, black = Image.new("RGB", (40, 40), "white"), Image.new("RGB", (40, 40), "black")
assert set(to_text(convert(white, width=10, mode="braille")).replace("\n", "")) == {"⣿"}
assert to_text(convert(black, width=10, mode="braille")).strip() == ""
dot7 = Image.new("L", (2, 4))
dot7.putpixel((0, 3), 255)
assert convert(dot7, width=1, mode="braille")[0][0][0] == "⡀"

# Halfblock: one cell carries the top pixel as ink and the bottom pixel as background.
tb = Image.new("RGB", (1, 2), "red")
tb.putpixel((0, 1), (0, 0, 255))
cell = convert(tb, width=1, mode="halfblock")[0][0]
assert cell == ("▀", (255, 0, 0), (0, 0, 255)), cell
assert "48;2;0;0;255" in to_ansi([[cell]]) and "linear-gradient" in to_html([[cell]])
assert to_png([[cell]]).getpixel((0, 0)) == (255, 0, 0) and to_png([[cell]]).getpixel((0, 13)) == (0, 0, 255)
assert to_text([[cell]]).strip() in "█▓▒░"
for mode in ("braille", "halfblock"):  # every mode keeps a square image square
    out = to_png(convert(Image.new("RGB", (300, 300), "white"), width=60, mode=mode))
    assert abs(out.width / out.height - 1) < 0.05, (mode, out.size)

# Shape mode draws edges with glyphs of the same shape: an X gets / and \, a bar gets - or _.
from PIL import ImageDraw  # noqa: E402
x = Image.new("L", (300, 300))
ImageDraw.Draw(x).line((30, 290, 270, 10), fill=255, width=12)
ImageDraw.Draw(x).line((30, 10, 270, 290), fill=255, width=12)
art = to_text(convert(x, width=20, mode="shape"))
assert "/" in art and "\\" in art, art
assert "/" not in to_text(convert(x, width=20)), "ramp mode is unchanged"
bar = Image.new("L", (240, 120))
ImageDraw.Draw(bar).rectangle((0, 24, 239, 35), fill=255)
assert set(to_text(convert(bar, width=8, mode="shape")).split("\n")[0]) <= set("-_"), "horizontal bar"
assert to_text(convert(x, width=20, mode="shape", bg="white", invert=True)) == art, "invert on white = dark bg"

# Words mode: rows are whole vocabulary words (cut only at the edges), and one level per word.
vocab = ["ALPHA", "BE", "GAMMA", "DELTAS"]
dark = Image.new("RGB", (400, 200), (10, 10, 10))
rows = convert(dark, width=40, mode="words", words=" ".join(vocab), seed=7)
for row in to_text(rows).splitlines():
    parts = row.split(" ")
    assert all(p in vocab for p in parts[1:-1] if p), row  # inner words are whole
    assert any(v.endswith(parts[0]) for v in vocab) and any(v.startswith(parts[-1]) for v in vocab), row  # cut at the edges
assert to_text(rows) == to_text(convert(dark, width=40, mode="words", words="alpha,be gamma DELTAS", seed=7))
base = convert(dark, width=40, mode="words", words="WWWWWWWW", autocontrast=False)
col = next(i for i in range(10, 40) if base[5][i][0] == "W")
lit = dark.copy()
lit.paste((255, 255, 255), (col * 10, 100, col * 10 + 10, 120))  # a bright square exactly under cell (col, 5)
row = convert(lit, width=40, mode="words", words="WWWWWWWW", autocontrast=False)[5]
on = [i for i in range(40) if row[i] != base[5][i]]
assert col in on and on == list(range(on[0], on[-1] + 1)) and len({row[i][1] for i in on}) == 1, on
assert len(on) == 8 or 0 in on or 39 in on, "the whole word lights up, not one letter"
orange = dark.copy()
orange.paste((242, 140, 40), (0, 0, 400, 50))
acc = convert(orange, width=40, mode="words", accent="#f28c28", autocontrast=False)
assert all(len(c) == 3 and c[2] == (242, 140, 40) for c in acc[0] if c[0] != " "), "accent words get a box"
assert all(len(c) == 2 for r in acc[3:] for c in r), "only the orange words"
assert all(len(c) == 2 for r in convert(orange, width=40, mode="words") for c in r), "no accent unless asked"
assert "\x1b[49m " in to_ansi(acc), "the box ends with its word"
assert not re.search(r"background[^>]*>[^<]* ", to_html(acc, gap=(0, 2))), "no space inside a box"
# Tiles: a rainbow square on a dark page. Subject cells are (glyph, ink, tile), page cells (glyph, faint ink).
poster = Image.new("RGB", (200, 200), (20, 20, 20))
for i in range(120):
    poster.paste((255, 2 * i, 255 - 2 * i), (40 + i, 40, 41 + i, 160))
tiles = convert(poster, width=20, aspect=1.0, mode="tiles", palette=4, seed=7)
assert len(tiles) == 20 and len(tiles[10][10]) == 3 and len(tiles[0][0]) == 2, tiles[10][10]
assert len({c[2] for row in tiles for c in row if len(c) == 3}) <= 4, "palette size is respected"
assert tiles == convert(poster, width=20, aspect=1.0, mode="tiles", palette=4, seed=7), "same seed, same grid"
assert tiles != convert(poster, width=20, aspect=1.0, mode="tiles", palette=4, seed=8)
fixed = [(255, 0, 0), (0, 0, 255)]
assert {c[2] for row in convert(poster, width=20, mode="tiles", palette=fixed) for c in row if len(c) == 3} <= set(fixed)
assert set(to_text(tiles)) <= {" ", "\n"} | {c[0] for row in tiles for c in row if len(c) == 3}, "text drops page glyphs"
assert "\x1b[49m" in to_ansi(tiles), "background resets after a tile"
# HTML: ramp at aspect 0.5 keeps the font's own advance; square tiles get centred, cell-wide glyph boxes.
page = to_html(grid)
assert "width:0.6em;font-style" in page and "font:12px/1.200 " in page and "<i>" not in page
page = to_html(tiles, font_size=40, aspect=1.0, gap=1)
assert "font:20px/1.200 " in page and "width:1.200em;text-align:center" in page and "border-radius:3px" in page
sq = to_png(tiles, font_size=40, aspect=1.0, gap=1)
assert sq.size == (480, 480) and sq.getpixel((240, 250)) == (0, 0, 0) and sq.getpixel((242, 250)) == tiles[10][10][2], "gap"

# Size caps: huge widths are refused, tall strips are capped.
assert len(convert(Image.new("L", (3, 2000)), width=40)) <= 1000
tmp = os.path.join(tempfile.mkdtemp(), "in.png")
img.save(tmp)
with contextlib.redirect_stdout(io.StringIO()) as said:
    main([tmp, "-o", tmp + ".png"])  # happy path writes a file
assert said.getvalue() == tmp + ".png\n", "prints the output path"
main([tmp, "--mode", "halfblock", "--sharpen", "-o", tmp + ".html"])
assert os.path.getsize(tmp + ".png") > 0
main([tmp, "--mode", "tiles", "-w", "4", "-o", tmp + ".tiles.png"])  # tiles defaults: square 48 px cells
assert Image.open(tmp + ".tiles.png").size == (4 * 48, 2 * 48)
for argv in (["-w", "0"], ["-w", "5000"], ["-o", "/no/such/dir/x.png"], ["-o", "x.xyz"], ["--font-size", "0"],
             ["--under", "2", "-o", tmp + ".png"], ["--under", "0.5"]):  # --under is 0-1 and needs a picture
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            main([tmp] + argv)  # each must fail with a clean usage error, not a traceback
    except SystemExit as e:
        assert e.code == 2, argv
    else:
        raise AssertionError(argv)

# Style ramps: the brightest cell gets the heaviest glyph, a dark cell gets none.
for name in STYLES:
    row = convert(img, width=10, charset=name)[0]
    assert row[0][0] == " " and row[-1][0] == CHARSETS[name][0] != " ", (name, row)
# Over the photo each ink keeps its pixel's color, a little brighter; on a flat page it is pushed up to read.
dim = Image.new("RGB", (40, 20), (100, 20, 20))
assert convert(dim, 4, autocontrast=False)[0][0][1][0] >= 200
assert convert(dim, 4, autocontrast=False, over_photo=True)[0][0][1] == tuple(round(v * PHOTO_INK) for v in (100, 20, 20))
assert convert(dim, 4, autocontrast=False, over_photo=True, bg="white")[0][0][1][0] < 100, "darker on a light page"
# The underlay is the photo itself, only dimmed toward the page: the hard edge in `img` stays hard.
soft = underlay(img, "black", 0.5)
assert soft.size == img.size and soft.getpixel((2, 10)) == (0, 0, 0) and 120 <= soft.getpixel((38, 10))[0] <= 128
assert underlay(img, "black", 1).tobytes() == img.convert("RGB").tobytes(), "strength 1 is the photo, untouched"
assert underlay(img.convert("RGBA"), "white", 0).getpixel((2, 10)) == (255, 255, 255), "strength 0 is the page"
# to_png and to_html draw it behind the glyphs instead of the flat page.
blank = [[(" ", (0, 0, 0))] * 4] * 2
assert to_png(blank, under=Image.new("RGB", (8, 8), (9, 99, 199))).getpixel((3, 3)) == (9, 99, 199)
page = to_html(blank, under=Image.new("RGB", (8, 8), (9, 99, 199)))
assert "data:image/jpeg;base64," in page and "display:inline-block" in page and "base64" not in to_html(blank)
# A symbol fills its square cell (24 px here), centred by its ink, so diamonds touch. Other glyphs shrink to fit.
lone = lambda ch: to_png([[(" ", (0, 0, 0))] * 3, [(" ", (0, 0, 0)), (ch, (255, 255, 255)), (" ", (0, 0, 0))],
                          [(" ", (0, 0, 0))] * 3], font_size=40, aspect=1.0).getbbox()
left, top, right, bottom = lone("◆")
assert right - left >= 22 and bottom - top >= 22 and abs(left + right - 72) <= 2 and abs(top + bottom - 72) <= 2, lone("◆")
assert lone("#")[2] - lone("#")[0] < 16, lone("#")
page = to_html([[("◆", (1, 2, 3))]], font_size=20, aspect=1.0)
assert "font:20px/0.600 " in page and "<i>◆</i>" in page
# Halfblock with a gap: a mosaic. Each pixel becomes its own tile with the page around it.
mosaic = to_png([[cell]], gap=1)
assert mosaic.getpixel((0, 0)) == (0, 0, 0) and mosaic.getpixel((1, 1)) == (255, 0, 0) and mosaic.getpixel((1, 8)) == (0, 0, 255)
assert mosaic.getpixel((3, 6)) == (0, 0, 0), "the gap also parts the two pixels of a cell"
# --style fills -c, and for a picture the cell shape, size, columns and the photo under the glyphs.
main([tmp, "--style", "diamond", "-o", tmp + ".style.png"])
styled = Image.open(tmp + ".style.png")
assert styled.size == (120 * 10, 60 * 10) and styled.getpixel((2, 300)) == (0, 0, 0)
assert 221 <= styled.getpixel((1199, 0))[0] <= 237, "between the glyphs the photo shows at 0.9"
main([tmp, "--style", "diamond", "-w", "30", "--under", "0", "-o", tmp + ".style.png"])  # your own options win
styled = Image.open(tmp + ".style.png")
assert styled.size == (30 * 10, 15 * 10) and styled.getpixel((299, 0)) == (0, 0, 0)
with contextlib.redirect_stdout(io.StringIO()) as said:
    main([tmp, "--style", "diamond"])  # text: just the ramp, at the usual 100 columns
assert said.getvalue().splitlines()[0] == " " * 50 + "◆" * 50, said.getvalue().splitlines()[0]

pink = Image.new("RGB", (40, 40), (3, 6, 4))  # near-black page with a faint green tint
ImageDraw.Draw(pink).ellipse((8, 8, 32, 32), fill=(230, 90, 160))
inks = [rgb for row in convert(pink, 20) for ch, rgb in row if ch.strip()]
assert any(r > g + 60 for r, g, b in inks), "a pink subject stays pink: one contrast curve for R, G and B"
assert all(abs(r - g) < 40 or r > g for r, g, b in inks), "the dark page's faint tint does not become bright green"
print("ok")
