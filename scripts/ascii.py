#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow>=10.1"]
# ///
"""Turn any image into ASCII art: plain text, ANSI color, HTML, or PNG.

    uv run scripts/ascii.py photo.jpg                    # text to stdout
    uv run scripts/ascii.py photo.jpg --color            # truecolor in the terminal
    uv run scripts/ascii.py photo.jpg -o art.png --fg matrix
"""
import argparse
import base64
import collections
import colorsys
import functools
import html
import io
import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

import post

# Ramps go from densest to emptiest glyph, sorted by measured ink (Menlo).
CHARSETS = {
    "standard": "@#%*=+:-. ",
    "detailed": "@0MWBQ8#O&mqpdb$U%XaZwkhoInuC1{}YJ*xfjtzLiv[]lc?<>|)(/\\+r;\"^!~:,_-.'` ",
    "blocks": "█▓▒░ ",
    "terminal": "@#o=-. ",
    "minimal": "#+. ",
    "binary": "01 ",
    "dots": "⣿⣷⣯⣟⡿⢿⣻⣽⣾⣶⣦⣤⣀⡀ ",
    # The --style ramps: bright cells get the heaviest glyph and dark cells get none, so the photo shows there.
    "characters": "@#08SXx+=-  ",
    "lines": "┃┃╏╹'  ",
    "diagonal": "╲╲//′  ",
    "diamond": "◆◆◆◇◇◇  ",
    "dot": "●●●••·  ",
    "cross": "✖✖✖✕✕×  ",
}
# --style NAME: that ramp over the dimmed photo. For a picture it also sets (aspect, font size, columns):
# letters get room around them, dashes get a gap between rows, and symbols sit on a square grid.
STYLES = {"characters": (0.75, 16, 120), "lines": (0.4, 12, 160), "diagonal": (0.5, 12, 160),
          "diamond": (1.0, 16, 120), "dot": (1.0, 16, 120), "cross": (1.0, 16, 120)}
STYLE_UNDER = 0.9  # how strong the photo shows under a style
PHOTO_INK = 1.35  # over the photo a glyph is this much brighter than its own pixel (on a light page: darker), so it glows
# Filled marks, plus the same-weight twins shimmer swaps in (♦ for ◆, ◉ for ●, …).
# None is taller than it is wide, so each one fills a square cell at full size.
SYMBOLS = set("◆◇●•·✖✕×♦◊◉∙⋅✘✗")
COLORS = {"matrix": "#00ff41", "amber": "#ffb000", "cyan": "#00e5ff", "magenta": "#ff3df2", "mint": "#9dffb0"}
# Retro palettes for --colors. C64 is Pepto's measured palette; ZX uses 0xD7 for normal and 0xFF for bright.
RETRO = {name: tuple(tuple(bytes.fromhex(h)) for h in hexes.split()) for name, hexes in {
    "c64": "000000 ffffff 68372b 70a4b2 6f3d86 588d43 352879 b8c76f 6f4f25 433900 9a6759 444444 6c6c6c 9ad284 6c5eb5 959595",
    "pico8": "000000 1d2b53 7e2553 008751 ab5236 5f574f c2c3c7 fff1e8 ff004d ffa300 ffec27 00e436 29adff 83769c ff77a8 ffccaa",
    "gameboy": "0f380f 306230 8bac0f 9bbc0f",
    "cga": "000000 55ffff ff55ff ffffff",
    "zx": "000000 0000d7 d70000 d700d7 00d700 00d7d7 d7d700 d7d7d7 0000ff ff0000 ff00ff 00ff00 00ffff ffff00 ffffff",
    "mono": "000000 ffffff",
    "matrix": "001405 00290b 004d14 00801e 00b82a 00ff41 7dffb0",  # no black: a dark-to-phosphor green map
    "vaporwave": "1a0933 3b0f5e 6c1a8c a8259a ff3cac ff7eb6 ffb1a3 ffe3c4",  # no black: a purple-pink-peach gradient map
}.items()}
# --gradient NAME: brightness runs through these stops, dark at the first color and bright at the last.
# Luminance rises along each set, so a bright pixel stays bright and only the hue changes.
# flare, sunset, neon and horizon are cinematic glows (orange-blue, magenta-gold, cyan-pink, red-sun).
GRADIENTS = {
    "matrix": ((0.00, (0, 28, 8)), (0.45, (0, 140, 36)), (1.00, (186, 255, 196))),
    "amber": ((0.00, (42, 16, 0)), (0.42, (176, 72, 0)), (0.75, (255, 160, 32)), (1.00, (255, 226, 170))),
    "vapor": ((0.00, (26, 9, 51)), (0.35, (108, 26, 140)), (0.62, (255, 60, 172)),
              (0.82, (255, 126, 182)), (1.00, (255, 227, 196))),
    "flare": ((0.00, (6, 10, 36)), (0.28, (16, 48, 140)), (0.48, (40, 110, 220)),
              (0.68, (255, 92, 18)), (0.86, (255, 168, 48)), (1.00, (255, 244, 224))),
    "sunset": ((0.00, (18, 6, 36)), (0.30, (120, 16, 72)), (0.52, (220, 36, 96)),
               (0.74, (255, 96, 32)), (1.00, (255, 196, 120))),
    "neon": ((0.00, (6, 14, 28)), (0.32, (0, 80, 100)), (0.55, (0, 170, 185)),
             (0.78, (255, 110, 190)), (1.00, (255, 214, 230))),
    "horizon": ((0.00, (12, 8, 32)), (0.36, (150, 18, 36)), (0.58, (220, 48, 16)),
                (0.78, (255, 120, 28)), (1.00, (255, 214, 140))),
    "signal": ((0.00, (16, 28, 30)), (0.38, (32, 110, 112)), (0.66, (130, 136, 132)), (1.00, (255, 160, 48))),
}
# 8x8 Bayer matrix: each step splits every cell into 2x2 in the order 0 2 / 3 1, so thresholds spread evenly.
BAYER = [[0]]
for _ in range(3):
    BAYER = [[4 * BAYER[y % len(BAYER)][x % len(BAYER)] + (0, 2, 3, 1)[2 * (y // len(BAYER)) + x // len(BAYER)]
              for x in range(2 * len(BAYER))] for y in range(2 * len(BAYER))]
CHROMA = 5  # hue counts this much against brightness when matching colors, so grays stay gray
MIX_PENALTY = 0.05  # cost of a dither pattern's contrast: prefer mixing near colors, but still mix
# Monospace first, then fonts that cover braille and other symbols.
FONTS = ["Menlo.ttc", "DejaVuSansMono.ttf", "consola.ttf", "LiberationMono-Regular.ttf", "cour.ttf",
         "Courier.ttc", "Apple Symbols.ttf", "seguisym.ttf", "DejaVuSans.ttf", "NotoSansSymbols2-Regular.ttf"]
TONE = 1.25  # ink adds light linearly but eyes see it as a curve; higher values crush dark photos
LOCAL = 35  # % of local contrast (a wide unsharp mask) in ramp and shape mode: lifts faces out of dark, flat scenes
SATURATION = 1.25  # thin glyphs look paler than the photo, so their ink is a little more saturated (1 = unchanged)
SHADES = {"█": 1.0, "▓": 0.75, "▒": 0.5, "░": 0.25}  # drawn as solid cells in PNG, so no font bleed
MAX_SIDE = 1000  # ponytail: hard cap on columns and rows; bigger grids eat GBs and nobody can read them
CELL_W = 0.6  # monospace advance in em
SUBPIXELS = {"ramp": (1, 1), "shape": (1, 1), "braille": (2, 4), "halfblock": (1, 2), "words": (1, 1), "tiles": (4, 4),
             "led": (1, 1), "dots": (1, 1), "stipple": (1, 1)}  # image pixels per cell (x, y)
# Shape mode samples each cell as a SHAPE_X x SHAPE_Y grid and gives edge cells the glyph whose ink
# sits in the same places. Symbols only: letters, brackets and ^~<>` read as noise in photos.
SHAPE_X, SHAPE_Y = 3, 4
SHAPE_EDGE = 0.03  # RMS contrast (0-1) inside a cell above which it counts as an edge
# How much a cell's overall brightness counts against where its ink sits. High values pick the glyph
# with the same amount of ink (a bar became ":") instead of the same stroke.
SHAPE_TONE = 0.5
# Stroke masks on that grid, '#' = ink, several per glyph. A stroke can sit high or low in the cell
# and be one or two samples thick. Measured from the font, a hyphen shrinks to one lit sample, so a
# horizontal bar matched ":" (the same amount of ink) instead of "-" or "_".
SHAPE_MASKS = {
    "-": ("......###...", "...######...", "...###......", "######......", "###.........", "......######"),
    "_": (".........###", "......######"),
    "|": (".#..#..#..#.", "##.##.##.##.", ".##.##.##.##", ".#..#..#....", "....#..#..#.",
          "#..#..#..#..", "..#..#..#..#"),
    "/": ("..#.#.#..#..", "..#.####.#..", ".....#.#.#..", ".####.#.....", "..#.#.#.....", "..#..#.#.#..", ".#.#..#....."),
    "\\": ("#...#...#..#", "#..##..##..#", "...#...#...#", "...#..##..##", "#...#...#...", "#..#...#...#", ".#...#..#..."),
    "+": (".#.###.#..#.", ".#..#.###.#.", ".#.######.#."),
    "*": ("#.#.#.#.#...", "#.#.#.#.#.#.", "##..####..##"),
    ".": ("....#..#....", ".......#....", ".#..#......."),
    "'": (".#..........", ".#..#......."),
    ",": ("..........#.", ".......#..#."),
    ":": (".#.....#....",),
    "=": ("###...###...", "...###...###"),
    "#": ("############", "#########..."),
}
# Braille dot bits by (row, col) inside a cell. Dots 1-3 and 4-6 run down the columns; 7 and 8 were added later.
BRAILLE = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))
# Cells are (char, ink) or (char, ink, background): the char drawn in ink on a solid background.
# HALF with a background is a halfblock: the top half is the ink, the bottom half the background.
HALF = "▀"
# Words mode: rows of words whose ink shows the image, one level per word. Short, neutral, mixed lengths.
WORDS = "PIXEL GRID TYPE INK TONE LINE FORM LIGHT SHADE EDGE FRAME DOT GLYPH FONT MONO TEXT CHAR WORD ASCII RGB 8BIT 01 16 PX"
POSTER_BG = "#1d1f22"  # default page in words and tiles mode
PAPER = ((0xe8, 0xe6, 0xdf), (0x1d, 0x1f, 0x22))  # brightest word ink on a dark / light background
DIM = 0.12  # the faintest word sits this far from the background toward PAPER
TINT = 0.25  # how much of the photo's hue the words keep
# Tiles mode: cells that stand out from the page become solid tiles in one small palette, each with
# one random glyph; the rest stay faint glyphs on the page, so the grid of characters goes on everywhere.
TILE_GLYPHS = "#?&%/\\<>{}[]()*+=~^$@!:|0123456789ABCDEF"
TILE_INK = ((42, 44, 46), (223, 227, 224))  # dark ink on light tiles, light ink on dark ones
TILE_CUT = 40  # how much brighter (on a dark page) than the page a cell must be to become a tile, 0-255
# LED and dots modes: one round lamp or halftone dot per cell. Text output gets round glyphs by size.
ROUND = "●•· "
LED_LAMP = 0.4  # lamp radius as a share of the cell side
LED_OFF = 0.07  # an unlit lamp sits this far from the board toward white (toward black on a light board)
LED_GLOW = 0.6  # strength of the soft glow around lit lamps
DOT_MIN = 0.03  # dots mode: a cell with less ink than this (0-1) gets no dot
STIPPLE_R = 0.38  # stipple: dot radius as a share of the cell side. Same size in every cell; tone is how many are on
UNSUPPORTED = {".svg": "SVG is not supported: convert it to PNG first, e.g. rsvg-convert",
               ".heic": "HEIC needs: pip install pillow-heif"}


def rgb(value):
    return ImageColor.getrgb(COLORS.get(value, value))[:3]


def gradient(name, t):
    """RGB at position t (0-1) along GRADIENTS[name]. 0 is the dark stop, 1 the bright one."""
    stops = GRADIENTS[name]
    if t <= stops[0][0]:
        return stops[0][1]
    if t >= stops[-1][0]:
        return stops[-1][1]
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        if t <= p1:
            k = (t - p0) / (p1 - p0)
            return tuple(round(a + (b - a) * k) for a, b in zip(c0, c1))
    return stops[-1][1]


def map_gradient(c, name):
    """The gradient color at c's brightness. Hue is replaced; dark stays dark and bright stays bright."""
    r, g, b = c[:3]
    return gradient(name, (0.299 * r + 0.587 * g + 0.114 * b) / 255)


def grade_image(img, name):
    """Recolor an image by brightness through a named gradient. Used for the photo under --gradient glyphs."""
    lut = [map_gradient((i, i, i), name) for i in range(256)]
    gray = img.convert("L")
    return Image.merge("RGB", [gray.point([c[k] for c in lut]) for k in range(3)])


def load(path):
    img = Image.open(io.BytesIO(sys.stdin.buffer.read()) if path == "-" else path)
    return ImageOps.exif_transpose(img)


def _scatter(levels, width, steps):
    """Shift each level by up to ±steps, from a hash of its cell. A smooth ramp then mixes the glyphs
    on either side of a tone instead of painting one character across the whole row. Stable per cell."""
    out = []
    for i, level in enumerate(levels):
        x, y = i % width, i // width
        n = (x * 374761393 + y * 668265263) & 0xFFFFFFFF
        n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
        out.append(level + ((n & 65535) / 32767.5 - 1) * steps)
    return out


def dither_levels(levels, width, top):
    """Floyd-Steinberg in place: snap each level to a whole number 0..top and spread the error."""
    for i, old in enumerate(levels):
        new = min(top, max(0, round(old)))
        err, levels[i] = old - new, new
        x = i % width
        for off, w, ok in ((1, 7, x + 1 < width), (width - 1, 3, x > 0),
                           (width, 5, True), (width + 1, 1, x + 1 < width)):
            if ok and i + off < len(levels):
                levels[i + off] += err * w / 16


def bayer(x, y):
    """Ordered-dither threshold (0-1) at output pixel (x, y). It depends only on the position, so a
    still area gets the same pattern in every frame: no crawl in animation."""
    return (BAYER[y % 8][x % 8] + 0.5) / 64


def _ycc(c, chroma):
    """Brightness and two color-difference axes (JPEG's YCbCr). Plain distance here matches the eye better
    than RGB; `chroma` sets how much hue counts against brightness."""
    r, g, b = c
    k = chroma ** 0.5
    return 0.299 * r + 0.587 * g + 0.114 * b, k * (0.5 * b - 0.1687 * r - 0.3313 * g), k * (0.5 * r - 0.4187 * g - 0.0813 * b)


def _dot(u, v):
    return sum(a * b for a, b in zip(u, v))


@functools.lru_cache(maxsize=1 << 16)
def _mix(c, pal, ordered):
    """(a, b, t): the two palette colors whose mix a + t(b - a) looks most like c (t in 0-1), after
    Yliluoma's ordered dither. The pattern's own contrast t(1 - t)|b - a|^2 is a small extra cost, so near
    colors mix before far ones: a gray stays gray, not a black-and-white checker.
    Without `ordered` it is just the nearest color (t = 0). Black and white first map to the palette's
    darkest and lightest color. A palette without black (Game Boy greens) is shades of one tint, so it
    matches on brightness alone."""
    lums = [_lum(p) for p in pal]
    k = CHROMA if min(lums) == 0 else 0
    q = _ycc([min(lums) + v * (max(lums) - min(lums)) / 255 for v in c], k)
    pts = {p: _ycc(p, k) for p in pal}
    near = sorted(pal, key=lambda p: sum((x - y) ** 2 for x, y in zip(q, pts[p])))  # nearest first
    if not ordered:
        return near[0], near[0], 0
    best = None
    for i, a in enumerate(near[:4]):  # ponytail: only mixes of the 4 nearest colors; good mixes are local
        u = [x - y for x, y in zip(q, pts[a])]
        for b in near[i:4]:
            d = [x - y for x, y in zip(pts[b], pts[a])]
            dd = _dot(d, d)
            t = min(1, max(0, _dot(u, d) / dd)) if dd else 0
            e = [x - t * y for x, y in zip(u, d)]
            err = _dot(e, e) + MIX_PENALTY * t * (1 - t) * dd
            if best is None or err < best[0]:
                best = err, a, b, t
    return best[1:]


def snap(c, colors, x=0, y=0, ordered=False):
    """Color c snapped to a palette (a RETRO name or a list of RGB colors). With `ordered`, Bayer-dither
    between the two colors whose mix matches c, at output pixel (x, y)."""
    a, b, t = _mix(tuple(c[:3]), tuple(map(tuple, RETRO[colors] if isinstance(colors, str) else colors)), ordered)
    return b if t > bayer(x, y) else a


def snap_grid(grid, colors, ordered=False):
    """Every color in the grid snapped to a palette. The dither runs on output pixels: one per cell,
    two per halfblock cell (top and bottom), so the pattern is square and stays put between frames."""
    return [[(c[0],) + tuple(snap(v, colors, x, 2 * y + k if c[0] == HALF else y, ordered)
                             for k, v in enumerate(c[1:])) for x, c in enumerate(row)] for y, row in enumerate(grid)]


def value_hist(img):
    """Histogram (256 counts) of each RGB pixel's brightest channel."""
    r, g, b = img.split()
    return ImageChops.lighter(ImageChops.lighter(r, g), b).histogram()


def stretch_lut(h, cutoff=1):
    """Autocontrast as a lookup table for img.point. `h` is the histogram of each pixel's brightest channel
    (value_hist), so a flat color stays as it is, the brightest channel just reaches 255, and one curve serves
    R, G and B, so hues stay. `cutoff` is the percent of pixels clipped at each end."""
    cut, acc, lo, hi = sum(h) * cutoff // 100, 0, 0, 255
    for lo in range(256):
        acc += h[lo]
        if acc > cut:
            break
    acc = 0
    for hi in range(255, -1, -1):
        acc += h[hi]
        if acc > cut:
            break
    if hi <= lo:
        return list(range(256)) * 3
    return [min(255, max(0, round((v - lo) * 255 / (hi - lo)))) for v in range(256)] * 3


def flatten(img, back):
    """Any image as plain RGB: transparency becomes the `back` color."""
    if img.mode.startswith(("I", "F")):  # 16/32-bit grayscale: stretch its real range to 8-bit
        img = img.convert("F")
        lo, hi = img.getextrema()
        img = img.point(lambda v: (v - lo) * 255 / ((hi - lo) or 1)).convert("L")
    img = img.convert("RGBA")
    return Image.alpha_composite(Image.new("RGBA", img.size, back + (255,)), img).convert("RGB")


def convert(img, width=100, charset=None, aspect=0.5, contrast=1.0, brightness=1.0,
            invert=False, dither=False, bg="black", mode="ramp", sharpen=False, autocontrast=True,
            words=WORDS, seed=0, accent=None, accent_level=0.5, palette=8, cut=None, over_photo=False, tone=False,
            backdrop=0.0, gradient=None, mix=0):
    """Return rows of (char, (r, g, b)) cells. `aspect` is char width / char height.

    mode "shape" maps brightness like "ramp", then gives each cell with an edge the ASCII symbol whose
    ink sits where the cell's light sits, for sharper contours. mode "braille" packs 2x4 pixels into each braille glyph. mode "halfblock" gives
    ("▀", top_rgb, bottom_rgb) cells: the top pixel is the ink, the bottom one the cell background.
    mode "words" fills each row with `words` (space or comma separated) and lights each word by the image
    under it; with `accent` (a color) words whose color is at least `accent_level` (0-1) saturated get a box.
    mode "tiles" gives (glyph, ink, tile) cells where the image stands out from `bg`, tile colors snapped
    to `palette` colors (a count, or a list of RGB colors to reuse), and faint (glyph, ink) cells elsewhere.
    Glyphs are random from `seed`, or ramp glyphs when `charset` is given.
    autocontrast=False skips the per-image tonal stretch (animate.py applies one shared stretch).
    `cut` (0-1) sets the braille dot threshold; animate.py passes one for the whole clip.
    over_photo=True is for glyphs drawn over the photo (see `underlay`): each ink keeps its pixel's own
    color, a little brighter than the dimmed photo. Without it every ink is made bright enough to read on a flat page.
    `tone=True` keeps each glyph's true color instead of brightening it to read on the page: for --colors,
    where the palette then carries the tone (a gradient palette lights dark parts dimly, not brightly).
    `backdrop` (0-1) gives ramp, shape and braille cells a background of their own true color at that strength,
    as (char, ink, background) cells: glyphs alone cover little of a cell, so color fields (paintings) read dim.
    `dither` is True (Floyd-Steinberg) or "bayer" (ordered, anchored to the pixel grid, so it holds still in
    animation). Halfblock has no levels to dither: snap its colors with snap_grid(grid, "pico8", ordered=True).
    `gradient` (a GRADIENTS name) replaces each color with that gradient at the pixel's brightness.
    `mix` (ramp only) scatters each level by up to this many glyph steps, so a gradient is a texture of
    nearby characters instead of stripes. mode "stipple" is fixed-size dots on a square grid; a cell is
    on when its brightness beats the Bayer threshold there, so tone is density, not dot size.
    """
    ramp = CHARSETS.get("standard" if charset is None else charset, charset)
    if len(ramp) < 2:
        raise ValueError("charset needs at least 2 characters")
    if not 1 <= width <= MAX_SIDE:
        raise ValueError("width must be 1-%d" % MAX_SIDE)
    if aspect <= 0 or contrast < 0 or brightness < 0:
        raise ValueError("aspect must be > 0; contrast and brightness must be >= 0")
    if mode not in SUBPIXELS:
        raise ValueError("mode must be one of: " + ", ".join(SUBPIXELS))
    sx, sy = SUBPIXELS[mode]
    back = rgb(bg)
    img = flatten(img, back)
    if autocontrast:
        img = img.point(stretch_lut(value_hist(img)))  # full tonal range, same hues: dim photos still read
    img = ImageEnhance.Brightness(ImageEnhance.Contrast(img).enhance(contrast)).enhance(brightness)
    if LOCAL and mode in ("ramp", "shape"):
        img = img.filter(ImageFilter.UnsharpMask(radius=img.width / 12, percent=LOCAL, threshold=0))

    rows = round(width * img.height / img.width * aspect)
    if rows > MAX_SIDE:  # very tall image: shrink width to keep the shape
        width, rows = max(1, round(width * MAX_SIDE / rows)), MAX_SIDE
    rows = max(1, rows)
    pw, ph = width * sx, rows * sy  # sampled pixels; each one is square when aspect is right
    if sharpen and pw < img.width:  # unsharp mask at the scale of one output pixel, so it survives the shrink
        img = img.filter(ImageFilter.UnsharpMask(radius=img.width / pw, percent=150, threshold=2))
    # Nearest keeps pixel art crisp when upscaling; Lanczos averages well when shrinking (on either axis).
    resample = Image.Resampling.NEAREST if pw >= img.width and ph >= img.height else Image.Resampling.LANCZOS
    small = img.resize((pw, ph), resample, reducing_gap=3.0)
    if mode == "halfblock":  # true colors, two pixels per cell
        px = (ImageOps.invert(small) if invert else small).load()

        def col(p):
            return map_gradient(p, gradient) if gradient else p
        return [[(HALF, col(px[x, 2 * r]), col(px[x, 2 * r + 1])) for x in range(width)] for r in range(rows)]
    dark_bg = sum(back) < 384
    if mode == "words":
        return _words(small, back, invert, words, seed, accent and rgb(accent), accent_level, gradient)
    if mode == "tiles":
        return _tiles(small, width, rows, ramp if charset else None, back, dark_bg, palette, seed, gradient)
    if mode in ("led", "dots"):
        grid = _lamps(small, back, ramp if charset else ROUND, mode == "led", invert)
        if gradient:
            grid = [[(ch, map_gradient(c, gradient)) for ch, c in row] for row in grid]
        return grid
    if mode == "stipple":
        return _stipple(small, back, invert, gradient)

    # Ink density per pixel: on a dark background bright pixels get dense glyphs.
    top = 1 if mode == "braille" else len(ramp) - 1
    g = 1 if mode == "braille" else TONE  # braille thresholds dots at the mean instead
    levels = [((v / 255) ** g if dark_bg != invert else 1 - (v / 255) ** g) * top for v in small.convert("L").tobytes()]
    # Braille dots without dither: threshold at the image's mean, so mid-tone ink (a blue logo) still shows.
    if cut is None:
        cut = min(0.75, max(0.25, sum(levels) / len(levels))) if mode == "braille" and not dither else 0.5
    if dither == "bayer":  # ordered: round up where the level beats the fixed threshold at this pixel
        levels = [min(top, int(v + bayer(i % pw, i // pw))) for i, v in enumerate(levels)]
    elif dither:
        dither_levels(levels, pw, top)
    if mix and mode == "ramp":  # after dither: a smooth field becomes a mix of the glyphs around that tone
        levels = _scatter(levels, pw, mix)
    # Braille color is the average of the cell's 8 pixels.
    raw = (small if sx == sy == 1 else small.resize((width, rows), Image.Resampling.BOX)).tobytes()
    if mode != "braille":
        chars = [ramp[top - min(top, max(0, round(level)))] for level in levels]
        if mode == "shape":
            fine = img.convert("L").resize((width * SHAPE_X, rows * SHAPE_Y), Image.Resampling.BOX)
            _shape_chars(chars, (fine if dark_bg != invert else ImageOps.invert(fine)).tobytes(), width, aspect, ramp[-2])
    cells = []
    for i in range(width * rows):
        if mode == "braille":
            r, x = divmod(i, width)
            bits = sum(BRAILLE[dy][dx] for dy in range(4) for dx in range(2)
                       if levels[(r * 4 + dy) * pw + x * 2 + dx] >= cut)
            ch = chr(0x2800 + bits) if bits else " "
        else:
            ch = chars[i]
        c = raw[i * 3:i * 3 + 3]
        if over_photo:
            k = PHOTO_INK if dark_bg else 1 / PHOTO_INK
            boosted = tuple(min(255, round(v * k)) for v in c)
            cells.append((ch, map_gradient(boosted, gradient) if gradient else boosted))
            continue
        if gradient:  # the stops carry the tone, so dark ink stays the dark stop instead of being brightened
            ink = map_gradient(c, gradient)
            bgc = tuple(round(b + (v - b) * backdrop) for b, v in zip(back, ink))
            cells.append((ch, ink, bgc) if backdrop else (ch, ink))
            continue
        true = c  # backdrops and --colors use the pixel's true color
        if not tone:
            mean = sum(c) / 3
            c = [min(255, max(0, mean + (v - mean) * SATURATION)) for v in c]
        # The glyph already shows brightness, so keep the hue but make the ink readable on the background.
        peak = max(c) or 1
        if dark_bg and peak < 64 and not tone:  # a near-black pixel's hue is mostly noise: fade it to gray before brightening
            m, k = sum(c) / 3, peak / 64
            c = [m + (v - m) * k for v in c]
        scale = 1 if tone else max(peak, 200) / peak if dark_bg else min(peak, 150) / peak
        ink = tuple(min(255, round(v * scale)) for v in c)
        cells.append((ch, ink, tuple(round(b + (v - b) * backdrop) for b, v in zip(back, true))) if backdrop else (ch, ink))
    return [cells[r * width:(r + 1) * width] for r in range(rows)]


def _word_rows(vocab, width, rows, seed):
    """Per row: (text, [(start, end) of each word]). Words are one space apart and each row starts
    mid-word at its own offset. Depends only on the arguments, so animation frames share one layout."""
    rng, longest, out = random.Random(seed), max(map(len, vocab)), []
    for _ in range(rows):
        off = rng.randrange(longest + 1)
        text, spans, prev = "", [], None
        while len(text) < off + width:
            prev = w = rng.choice([v for v in vocab if v != prev] or vocab)  # no word twice in a row
            spans.append((max(0, len(text) - off), min(width, len(text) + len(w) - off)))
            text += w + " "
        out.append((text[off:off + width], [(a, b) for a, b in spans if a < b]))
    return out


def _words(small, back, invert, words, seed, accent, accent_level, gradient=None):
    """Word poster cells: each word gets one ink from the mean color under all its cells."""
    vocab = words.replace(",", " ").upper().split()
    if not vocab:
        raise ValueError("words needs at least one word")
    width, rows = small.size
    px = small.load()
    dark_bg = sum(back) < 384
    paper = PAPER[0 if dark_bg else 1]
    dim = tuple(b + (p - b) * DIM for b, p in zip(back, paper))
    grid = []
    for y, (text, spans) in enumerate(_word_rows(vocab, width, rows, seed)):
        row = [(" ", paper)] * width
        for a, b in spans:
            c = [sum(px[x, y][k] for x in range(a, b)) / (b - a) for k in range(3)]
            lum = (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) / 255
            t = (lum if dark_bg != invert else 1 - lum) ** 1.5
            t = t * t * (3 - 2 * t)  # S-curve: dark areas sink to the faint floor, the subject stands out
            ink = [d + (p - d) * t for d, p in zip(dim, paper)]
            if max(c) > 0:  # keep some of the photo's hue, at the same peak brightness
                ink = [i + (v * max(ink) / max(c) - i) * TINT for i, v in zip(ink, c)]
            ink = tuple(min(255, round(v)) for v in ink)
            if gradient:
                ink = map_gradient(ink, gradient)
            box = accent and (max(c) - min(c)) / 255 >= accent_level
            if box and gradient:  # the box takes the gradient; the letters stay a color that reads on it
                box_c = map_gradient(accent, gradient)
                row[a:b] = [(ch, TILE_INK[_lum(box_c) < 140], box_c) for ch in text[a:b]]
            else:
                row[a:b] = [(ch, back, accent) if box else (ch, ink) for ch in text[a:b]]
        grid.append(row)
    return grid


def _lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _tiles(small, width, rows, ramp, back, dark_bg, palette, seed, gradient=None):
    """Each cell takes the most common of its 4x4 samples: the page, or a palette color. So edges stay crisp
    and blends between two colors never use up a palette slot."""
    page, sign = _lum(back), 1 if dark_bg else -1
    lit = [(v - page) * sign > TILE_CUT for v in small.convert("L").tobytes()]
    if isinstance(palette, int):  # one palette from the subject's own pixels, so the page does not use up colors
        if not 1 <= palette <= 256:
            raise ValueError("palette must be 1-256")
        raw = small.tobytes()
        subject = [raw[i * 3:i * 3 + 3] for i, t in enumerate(lit) if t] or [bytes(back)]
        strip = Image.frombytes("RGB", (len(subject), 1), b"".join(subject))
        palette = sorted(c for _, c in strip.quantize(palette).convert("RGB").getcolors(256))
    pal = Image.new("P", (1, 1))
    pal.putpalette([v for i in range(256) for v in palette[i % len(palette)]])
    idx = small.quantize(palette=pal, dither=Image.Dither.NONE).tobytes()
    tone = small.convert("L").resize((width, rows), Image.Resampling.BOX).tobytes()
    faint = tuple(round(b + ((255 if dark_bg else 0) - b) * 0.12) for b in back)
    rng = random.Random(seed)
    pw, top = width * 4, len(ramp or " ") - 1
    grid = []
    for r in range(rows):
        row = []
        for x in range(width):
            ch = rng.choice(TILE_GLYPHS)  # drawn for every cell, so a cell keeps its glyph from frame to frame
            if ramp:  # dense glyphs where the cell stands out from the page, as in ramp mode
                v = tone[r * width + x]
                ch = ramp[top - round((v if dark_bg else 255 - v) / 255 * top)]
            votes = collections.Counter(idx[i] % len(palette) if lit[i] else -1
                                        for y in range(r * 4, r * 4 + 4) for i in range(y * pw + x * 4, y * pw + x * 4 + 4))
            k = votes.most_common(1)[0][0]
            t = palette[k] if k >= 0 else None
            if t and gradient:
                t = map_gradient(t, gradient)
            row.append((ch, TILE_INK[_lum(t) < 140], t) if t else (ch, faint))
        grid.append(row)
    return grid


def _stipple(small, back, invert, gradient=None):
    """Fixed-size dots. Brightness picks how many cells are on (Bayer), not how big the dot is, so a globe
    or a rocket stays a grid of equal dots. On a light page the dark pixels are the ink."""
    px, grid, dark = small.load(), [], sum(back) < 384
    for y in range(small.height):
        row = []
        for x in range(small.width):
            c = px[x, y]
            if invert:
                h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in c))
                c = tuple(round(v * 255) for v in colorsys.hls_to_rgb(h, 1 - l, s))
            amt = _lum(c) / 255 if dark else 1 - _lum(c) / 255
            on = amt > bayer(x, y)
            if gradient and on:
                c = map_gradient(c, gradient)
            row.append(("●" if on else " ", c))
        grid.append(row)
    return grid


def _stipple_png(grid, bg, fg, cw, chh):
    """One disc per lit cell, the same radius in every cell. Empty cells stay the page."""
    back = (0, 0, 0) if bg == "none" else rgb(bg)
    cols, rows = len(grid[0]), len(grid)
    W, H = cols * cw, rows * chh
    radius = STIPPLE_R * min(cw, chh)
    cx, cy = (cw - 1) / 2, (chh - 1) / 2
    dot = [min(255, max(0, round((radius + 0.6 - math.hypot(x - cx, y - cy)) * 255)))
           for y in range(chh) for x in range(cw)]
    on = Image.new("L", (cols, rows))
    on.putdata([0 if ch == " " else 255 for row in grid for ch, _ in row])
    coverage = ImageChops.multiply(_tile(dot, cw, chh, cols, rows), on.resize((W, H), Image.Resampling.NEAREST))
    colors = Image.new("RGB", (cols, rows))
    colors.putdata([fg or c for row in grid for _ch, c in row])
    colors = colors.resize((W, H), Image.Resampling.NEAREST)
    if bg == "none":
        colors.putalpha(coverage)
        return colors
    return Image.composite(colors, Image.new("RGB", (W, H), back), coverage)


def _ink(c, back):
    """(amount, ink): a dot of color `ink` covering `amount` (0-1) of a cell on `back` gives the cell the mean
    color c. The ink is the farthest color from `back` in c's direction, so the tone lives in the area."""
    a = max((v - b) / (255 - b) if v > b else (b - v) / b if v < b else 0 for v, b in zip(c, back))
    return a, tuple(round(b + (v - b) / a) for v, b in zip(c, back)) if a else back


def _lamps(small, back, ramp, led, invert):
    """LED and dots cells: (round glyph by ink amount, color). An LED cell's color is its lamp's light, in
    len(ramp) - 1 steps; a dots cell keeps the true color, so to_png can size its dot exactly.
    `invert` flips lightness but keeps the hue: an orange planet on black prints as dark orange on white."""
    top, px, grid = len(ramp) - 1, small.load(), []
    for y in range(small.height):
        row = []
        for x in range(small.width):
            c = px[x, y]
            if invert:
                h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in c))
                c = tuple(round(v * 255) for v in colorsys.hls_to_rgb(h, 1 - l, s))
            a, ink = _ink(c, back)
            k = round(a * top)
            if led:
                row.append((ramp[top - k], tuple(round(b + (i - b) * k / top) for i, b in zip(ink, back))))
            else:  # any visible dot gets at least the smallest glyph
                row.append((ramp[top - max(k, a >= DOT_MIN)], c))
        grid.append(row)
    return grid


@functools.lru_cache(maxsize=8)
def _screen(cw, chh, diagonal):
    """One cell of the dot screen: (k, dist, slot, radius). `dist` is each pixel's distance to the nearest dot
    centre in 1/k px, as bytes; `slot` says which dot that is (0 the cell's centre; 1-4 its top-left, top-right,
    bottom-left, bottom-right corner, on the 45° grid). `radius[q]` is the dot radius (+0.5 px, in 1/k px)
    whose drawn coverage is q/255 of the cell, found from the exact coverage the renderer gives: tone is right."""
    pts = [(cw / 2, chh / 2)] + ([(0, 0), (cw, 0), (0, chh), (cw, chh)] if diagonal else [])
    near = [min((math.hypot(x + 0.5 - u, y + 0.5 - v), i) for i, (u, v) in enumerate(pts))
            for y in range(chh) for x in range(cw)]
    k = 255 / (max(d for d, _ in near) + 1)
    dist = [round(d * k) for d, _ in near]
    hist = collections.Counter(dist)
    cover = [sum(m * min(1, max(0, (r - d) / k)) for d, m in hist.items()) / len(dist) for r in range(256)]
    radius = [min(range(256), key=lambda r: abs(cover[r] - q / 255)) for q in range(256)]
    return k, dist, [i for _, i in near], radius


def _tile(data, cw, chh, cols, rows):
    """Repeat one cell's pixels over a cols x rows grid."""
    cell = Image.new("L", (cw, chh))
    cell.putdata(data)
    row = Image.new("L", (cw * cols, chh))
    for x in range(cols):
        row.paste(cell, (x * cw, 0))
    out = Image.new("L", (cw * cols, chh * rows))
    for y in range(rows):
        out.paste(row, (0, y * chh))
    return out


def _lamp_png(grid, bg, fg, cw, chh, led):
    """LED lamps or halftone dots. Anti-aliasing comes from a distance field: each pixel is covered by
    (dot radius - distance to the dot centre + 0.5), clipped to 0-1, so edges are smooth with no supersampling.
    Lit LED lamps get a glow: one blurred copy of their light over the board."""
    back = (0, 0, 0) if bg == "none" else rgb(bg)
    cols, rows = len(grid[0]), len(grid)
    W, H = cols * cw, rows * chh
    diagonal = not led  # dots sit on a grid turned 45 degrees, as in print; it hides the grid better
    k, dist, slot, radius = _screen(cw, chh, diagonal)
    ink_lum = fg and _lum(fg) - _lum(back)

    def look(ch, c):  # the cell's color seen from afar
        if ch == " ":
            return back
        if not fg:
            return c
        a = _ink(c, back)[0] if led else min(1, max(0, (_lum(c) - _lum(back)) / (ink_lum or 1)))
        return tuple(round(b + (f - b) * a) for f, b in zip(fg, back))

    cells = [[look(c[0], c[1]) for c in row] for row in grid]
    coverage = _tile(dist, cw, chh, cols, rows)
    if led:  # every lamp has one size: the coverage is one lamp, repeated; unlit lamps are faint
        off = tuple(round(b + ((255 if sum(back) < 384 else 0) - b) * LED_OFF) for b in back)
        lamp = round((LED_LAMP * min(cw, chh) + 0.5) * k)
        coverage = coverage.point(lambda d: min(255, max(0, round((lamp - d) * 255 / k))))
        light = Image.new("RGB", (cols, rows))
        light.putdata([tuple(max(0, v - b) for v, b in zip(c, back)) for row in cells for c in row])
        lamps = Image.new("RGB", (cols, rows))
        lamps.putdata([tuple(min(255, max(0, o + v - b)) for o, v, b in zip(off, c, back)) for row in cells for c in row])
        lamps = lamps.resize((W, H), Image.Resampling.NEAREST)
        if bg == "none":
            lamps.putalpha(coverage)
            return lamps
        glow = Image.composite(light.resize((W, H), Image.Resampling.NEAREST), Image.new("RGB", (W, H)), coverage)
        glow = glow.filter(ImageFilter.GaussianBlur(cw * 0.5)).point(lambda v: round(v * LED_GLOW))
        # Screen, not add: the glow lights the board and dim lamps but cannot push a lit lamp to white.
        return ImageChops.screen(Image.composite(lamps, Image.new("RGB", (W, H), back), coverage), glow)
    points = [(cells, 0, 0)]
    if diagonal:  # a dot on each cell corner, with the mean color of the 4 cells around it
        def at(x, y):
            return cells[min(rows - 1, max(0, y))][min(cols - 1, max(0, x))]
        corners = [[tuple(sum(v) / 4 for v in zip(at(x - 1, y - 1), at(x, y - 1), at(x - 1, y), at(x, y)))
                    for x in range(cols + 1)] for y in range(rows + 1)]
        points += [(corners, 0, 0), (corners, 1, 0), (corners, 0, 1), (corners, 1, 1)]
    ink = rad = None
    for s, (pts, dx, dy) in enumerate(points):
        amounts = [[_ink(c, back) for c in row[dx:dx + cols]] for row in pts[dy:dy + rows]]
        a_img, i_img = Image.new("L", (cols, rows)), Image.new("RGB", (cols, rows))
        a_img.putdata([radius[round(a * 255)] for row in amounts for a, _ in row])
        i_img.putdata([tuple(round(v) for v in i) for row in amounts for _, i in row])
        a_img, i_img = (im.resize((W, H), Image.Resampling.NEAREST) for im in (a_img, i_img))
        if s == 0:
            rad, ink = a_img, i_img
        else:
            mask = _tile([255 * (v == s) for v in slot], cw, chh, cols, rows)
            rad.paste(a_img, mask=mask)
            ink.paste(i_img, mask=mask)
    coverage = ImageChops.subtract(rad, coverage, scale=k / 255)
    if bg == "none":
        ink.putalpha(coverage)
        return ink
    return Image.composite(ink, Image.new("RGB", (W, H), back), coverage)


@functools.lru_cache(maxsize=8)
def _glyph_vectors(aspect):
    """(char, shape vector) for each stroke mask. Masks live in the sample grid, so `aspect` does not
    change them (it stays so the call site is unchanged). Tone is the mask's coverage on the same 0-1
    scale as the cell's mean brightness: a full mask matches a white cell."""
    del aspect
    n = SHAPE_X * SHAPE_Y
    tone_w = (SHAPE_TONE * n) ** 0.5
    out = []
    for ch, group in SHAPE_MASKS.items():
        for mask in group:
            if len(mask) != n or set(mask) - set(".#"):
                raise ValueError("shape mask for %r must be %d of . and #" % (ch, n))
            v = [1.0 if bit == "#" else 0.0 for bit in mask]
            out.append((ch, _shape_vector(v, mask.count("#") / n * tone_w)))
    return out


def _shape_vector(v, tone):
    """Where the ink sits (minus the mean, unit length, so only the pattern counts) + tone."""
    mean = sum(v) / len(v)
    v = [x - mean for x in v]
    norm = sum(x * x for x in v) ** 0.5 or 1
    return [x / norm for x in v] + [tone]


def _shape_chars(chars, ink, width, aspect, faintest):
    """Give each edge cell the glyph of nearest shape; flat cells keep their ramp glyph.
    `ink` holds SHAPE_X x SHAPE_Y samples (0-255) per cell, brighter = more ink."""
    glyphs = _glyph_vectors(aspect)
    n, fw = SHAPE_X * SHAPE_Y, width * SHAPE_X
    tone_w = (SHAPE_TONE * n) ** 0.5
    cache = {}
    for c in range(len(chars)):
        x0, y0 = c % width * SHAPE_X, c // width * SHAPE_Y
        vec = [ink[(y0 + j) * fw + x0 + i] / 255 for j in range(SHAPE_Y) for i in range(SHAPE_X)]
        tone = sum(vec) / n
        if sum((v - tone) ** 2 for v in vec) < SHAPE_EDGE ** 2 * n:
            continue
        vec = _shape_vector(vec, tone * tone_w)
        key = tuple(round(v * 16) for v in vec)  # near-identical cells share one lookup
        ch = cache.get(key)
        if ch is None:
            ch = cache[key] = min(glyphs, key=lambda g: sum((a - b) ** 2 for a, b in zip(g[1], vec)))[0]
        if ch != " " or chars[c] != faintest:  # keep faint marks: they may be a hairline
            chars[c] = ch


def _shade(cell):
    """Plain-text stand-in for a two-color cell: a shade block by mean brightness (dense = bright)."""
    lum = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in cell[1:]) / 2
    return "█▓▒░ "[4 - min(4, round(lum / 255 * 4))]


def to_text(grid, tiles=False):
    # tiles=True: loose glyphs between tiles are faint decoration; plain text cannot draw them faint, so it drops them.
    return "\n".join("".join(_shade(c) if c[0] == HALF else " " if tiles and len(c) == 2 else c[0]
                             for c in row).rstrip() for row in grid) + "\n"


def _ansi(cell, fg):
    if len(cell) == 3:  # (char, fg, bg) cells keep their own colors
        return "\x1b[38;2;%d;%d;%d;48;2;%d;%d;%dm%s" % (cell[1] + cell[2] + cell[:1])
    return cell[0] if cell[0] == " " else "\x1b[38;2;%d;%d;%dm%s" % ((fg or cell[1]) + cell[:1])


def to_ansi(grid, fg=None):
    # A one-color cell after a two-color one resets the background, so the tile color does not bleed on.
    return "\n".join("".join(("\x1b[49m" if len(p) == 3 and len(c) == 2 else "") + _ansi(c, fg)
                             for p, c in zip([()] + row, row)).rstrip() + "\x1b[0m" for row in grid) + "\n"


def _corner(cw, gap):
    """Corner radius in px of a tile `cw` px wide: slightly rounded, none without a gap."""
    return min(cw // 4, max(gap, cw // 12)) if gap else 0


def _html_run(style, run, boxed=False):
    # Fallback braille fonts are wider than 0.6em, so each braille glyph gets a fixed-width box.
    text = "".join("<i>%s</i>" % html.escape(ch) if boxed or _braille(ch) else html.escape(ch) for ch in run)
    return '<span style="%s">%s</span>' % (style, text) if style else text


def to_html(grid, bg="black", fg=None, font_size=12, aspect=0.5, gap=0, glow=0, under=None):
    """`glow` (0-1) adds a soft bloom around the glyphs. `gap` (px) leaves a border of page background around each background cell, for a tile look.
    A pair (x, y) sets each side; (0, y) keeps a word's box whole and only parts the rows.
    Glyphs shrink to fit short cells, as in to_png; then each glyph sits centred in its own cell-wide box.
    A grid of only symbols keeps its glyph size, as in to_png, and always gets the boxes, because browsers
    draw symbols with a fallback font of another width.
    `under` is an image drawn behind the glyphs, stretched to fit, as in to_png."""
    back = "transparent" if bg == "none" else "#%02x%02x%02x" % rgb(bg)
    cw = font_size * CELL_W  # cell width in px
    chars = {c[0] for row in grid for c in row} - {" "}
    symbols = bool(chars) and chars <= SYMBOLS
    size = font_size if symbols else min(font_size, round(cw / aspect / 1.2))  # glyph px
    boxed = symbols or size < font_size
    gx, gy = gap if isinstance(gap, tuple) else (gap, gap)
    shadow = "#000" if bg == "none" else back
    if not (gx or gy):
        edge = ""
    elif gx == gy:  # tiles: an even border and rounded corners
        edge = ";box-shadow:inset 0 0 0 %dpx %s;border-radius:%dpx" % (gx, shadow, gx + _corner(round(cw), gx))
    else:  # word boxes: only the rows part
        edge = ";box-shadow:inset %dpx %dpx %s,inset -%dpx -%dpx %s" % ((gx, gy, shadow) * 2)
    lines = []
    for row in grid:
        parts, run, run_style = [], "", None
        for c in row:
            if len(c) == 3 and c[0] == HALF:  # halfblock: a gradient paints exact halves, whatever the font
                style, ch = "background:linear-gradient(#%02x%02x%02x 50%%,#%02x%02x%02x 50%%)" % (c[1] + c[2]), " "
            elif len(c) == 3:  # glyph on its own background
                style, ch = "color:#%02x%02x%02x;background:#%02x%02x%02x" % (c[1] + c[2]) + edge, c[0]
            else:
                style, ch = "color:#%02x%02x%02x" % (fg or c[1]), c[0]
            tile = gx and len(c) == 3 and c[0] != HALF  # with a gap every cell is its own tile, never merged
            if (style != run_style or tile) and (ch != " " or len(c) == 3 or "background" in (run_style or "")):
                if run:
                    parts.append(_html_run(run_style, run, boxed))
                run, run_style = "", style
            run += ch
        if run:
            parts.append(_html_run(run_style, run, boxed))
        lines.append("".join(parts))
    lh = cw / aspect / size  # in em of the glyph font
    box = ("%.3f" % (cw / size), "text-align:center;") if boxed else (CELL_W, "")
    photo = ""
    if under:  # a small JPEG in the page itself; the <pre> shrinks to the art, so the photo fits it exactly
        data = io.BytesIO()
        under.convert("RGB").resize((len(grid[0]) * 4, len(grid) * round(4 / aspect))).save(data, "JPEG", quality=80)
        photo = (";display:inline-block;background:url(data:image/jpeg;base64,%s) 0 0/100%% 100%% content-box no-repeat"
                 % base64.b64encode(data.getvalue()).decode())
    # Spans fill the whole line height, so cell backgrounds meet with no gap between rows.
    return ('<!doctype html><meta charset="utf-8"><title>ASCII art</title>\n'
            '<style>pre span{display:inline-block;vertical-align:top;height:%.3fem}'
            'pre i{display:inline-block;width:%sem;%sfont-style:normal}</style>\n'
            '<body style="margin:0;min-height:100vh;display:grid;place-items:center;background:%s">'
            '<pre style="margin:0;padding:16px;font:%dpx/%.3f Menlo,Consolas,\'DejaVu Sans Mono\',monospace%s%s">%s</pre></body>\n'
            ) % ((lh,) + box + (back, size, lh, _glow_css(glow, font_size), photo, "\n".join(lines)))


def _glow_css(glow, font_size):
    """CSS bloom for to_html and the animate.py player: text-shadow takes each glyph's own color."""
    return ";text-shadow:0 0 %.1fpx" % (font_size * 0.7 * glow) if glow else ""


def _render(f, ch):
    im = Image.new("L", (64, 64))
    ImageDraw.Draw(im).text((8, 8), ch, font=f, fill=255)
    return im.tobytes()


def font(size, chars=""):
    """First font in FONTS that has a real glyph (not the empty box) for every char."""
    first = None
    for name in FONTS:
        try:
            f = ImageFont.truetype(name, size)
        except OSError:
            continue
        first = first or f
        missing = _render(f, "\U0010fffd")
        if all(_render(f, c) != missing for c in chars):
            return f
    return first or ImageFont.load_default(size)


def _braille(ch):
    return "\u2800" <= ch <= "\u28ff"


@functools.lru_cache(maxsize=8)
def _dots(size, k):
    """Mask (L) of a whole image: 255 where the Bayer threshold is below k, so it covers a share k."""
    w, h = size
    rows = [bytes(255 * (k > bayer(x, y)) for x in range(w)) for y in range(8)]
    return Image.frombytes("L", size, b"".join(rows[y % 8] for y in range(h)))


def _ink_offset(f, ch):
    """(dx, dy) in whole px that moves `ch`, drawn with anchor "mm", so its ink is centred on the anchor point.
    Fonts set symbols a little below the middle of the line, which shows when they fill a square cell."""
    s = 2 * f.size
    im = Image.new("L", (2 * s, 2 * s))
    ImageDraw.Draw(im).text((s, s), ch, font=f, fill=255, anchor="mm")
    left, top, right, bottom = im.getbbox() or (s, s, s, s)
    return round(s - (left + right) / 2), round(s - (top + bottom) / 2)


def to_png(grid, bg="black", fg=None, font_size=12, aspect=0.5, gap=0, glow=0, under=None, mode="ramp", pure=False):
    """`glow` (0-1) adds a soft bloom around bright glyphs (not with bg "none"). `gap` (px) leaves a border of background around each background cell, for a tile look.
    A pair (x, y) sets each side; (0, y) keeps a word's box whole and only parts the rows.
    `under` is an image drawn behind the glyphs instead of the flat background, stretched to fit.
    `pure` (for --colors) adds no new colors: glyphs are not antialiased, and ░▒▓ are fixed dot patterns
    of ink on the page, as a terminal font draws them, instead of a blend.
    mode "led" or "dots" draws each cell as a lamp or a halftone dot instead of its glyph."""
    gx, gy = gap if isinstance(gap, tuple) else (gap, gap)
    cw = max(1, round(font_size * CELL_W))
    chh = max(1, round(cw / aspect))  # cell shape matches the aspect used to sample the image
    if mode == "stipple":
        return _stipple_png(grid, bg, fg, cw, chh)
    if mode in ("led", "dots"):
        return _lamp_png(grid, bg, fg, cw, chh, mode == "led")
    dot = max(1, round(min(cw / 2, chh / 4)))  # braille dot size in px
    glyphs = {c[0] for row in grid for c in row if c[0] not in SHADES and c[0] != HALF and not _braille(c[0])}
    f = font(min(font_size, round(chh / 1.2)), "".join(glyphs))  # glyphs shrink to fit short cells (square tiles)
    big = font(font_size, "".join(glyphs))  # symbols do not: they fill a square cell at full size, centred by their ink
    nudge = {ch: _ink_offset(big, ch) for ch in glyphs & SYMBOLS}
    pix, back = ("RGBA", (0, 0, 0, 0)) if bg == "none" else ("RGB", rgb(bg))  # pix: `mode` is the art mode here
    size = (len(grid[0]) * cw, len(grid) * chh)
    if size[0] * size[1] > 2 * Image.MAX_IMAGE_PIXELS:  # past Pillow's own bomb limit: GBs of RAM
        raise ValueError("image would be %dx%d px; lower -w or --font-size" % size)
    img = Image.new(pix, size, back) if under is None else under.convert(pix).resize(size, Image.LANCZOS)
    draw = ImageDraw.Draw(img)
    if pure:
        draw.fontmode = "1"
    for y, row in enumerate(grid):
        for x, (ch, c, *under) in enumerate(row):
            ink = fg or c
            if under and ch != HALF:  # glyph on its own background (a tile when gap > 0)
                draw.rounded_rectangle((x * cw + gx, y * chh + gy, (x + 1) * cw - 1 - gx, (y + 1) * chh - 1 - gy),
                                       radius=_corner(cw, min(gx, gy)), fill=under[0])
                if ch != " ":
                    draw.text((x * cw + cw / 2, y * chh + chh / 2), ch, font=f, fill=c, anchor="mm")
            elif under:  # halfblock: top half is the ink, bottom half the cell background; a gap parts all pixels
                mid = y * chh + chh // 2
                draw.rectangle((x * cw + gx, y * chh + gy, (x + 1) * cw - 1 - gx, mid - 1 - gy), fill=c)
                draw.rectangle((x * cw + gx, mid + gy, (x + 1) * cw - 1 - gx, (y + 1) * chh - 1 - gy), fill=under[0])
            elif ch in SHADES and pure:
                box = (x * cw, y * chh, (x + 1) * cw, (y + 1) * chh)
                img.paste(ink + (255,) * (pix == "RGBA"), box, _dots(img.size, SHADES[ch]).crop(box))
            elif ch in SHADES:
                k = SHADES[ch]
                fill = ink + (round(255 * k),) if pix == "RGBA" else tuple(round(b + (i - b) * k) for b, i in zip(back, ink))
                draw.rectangle((x * cw, y * chh, (x + 1) * cw - 1, (y + 1) * chh - 1), fill=fill)
            elif _braille(ch):  # draw the dots on an even 2x4 grid; font dots are tiny and unevenly spaced
                for dy, dx in ((dy, dx) for dy in range(4) for dx in range(2) if ord(ch) & BRAILLE[dy][dx]):
                    cx, cy = round(x * cw + (dx + 0.5) * cw / 2 - dot / 2), round(y * chh + (dy + 0.5) * chh / 4 - dot / 2)
                    draw.ellipse((cx, cy, cx + dot - 1, cy + dot - 1), fill=ink)
            elif ch in nudge:
                dx, dy = nudge[ch]
                draw.text((x * cw + cw / 2 + dx, y * chh + chh / 2 + dy), ch, font=big, fill=ink, anchor="mm")
            elif ch != " ":
                draw.text((x * cw + cw / 2, y * chh + chh / 2), ch, font=f, fill=ink, anchor="mm")
    if glow and pix == "RGB":  # bloom: a blurred copy screened over the art, like light bleeding on a CRT
        img = ImageChops.screen(img, img.filter(ImageFilter.GaussianBlur(font_size * 0.7)).point(lambda v: round(v * glow)))
    return img


# --look NAME: a recipe of flags. They go first, so any flag the user also types wins.
LOOKS = {
    "matrix": ["-c", "01", "--colors", "matrix", "--contrast", "1.25", "--post", "scan,bloom,vignette"],
    "vaporwave": ["--mode", "halfblock", "--colors", "vaporwave", "--dither", "bayer", "--contrast", "1.15",
                  "--post", "chroma,scan,bloom,vignette"],
    "terminal": ["-c", "terminal", "--fg", "amber", "--post", "crt"],
    "noir": ["-c", "standard", "--fg", "#ece9e2", "--contrast", "1.3", "--post", "grain,vignette"],
    "vhs": ["--mode", "halfblock", "--post", "chroma,scan,grain,vignette"],
    "c64": ["--mode", "halfblock", "--colors", "c64", "--dither", "bayer"],
    "pico8": ["--mode", "halfblock", "--colors", "pico8", "--dither", "bayer"],
    "gameboy": ["--mode", "halfblock", "--colors", "gameboy", "--dither", "bayer"],
    "scoreboard": ["--mode", "led", "--fg", "amber"],
    "newspaper": ["--mode", "dots", "--bg", "white", "--fg", "black"],
}


def parse_look(p, argv, files):
    """Parse argv. With --look NAME the recipe's flags go first, so flags the user typed still win.
    A recipe's post effects are dropped when the output is not one of `files` (text, HTML, terminal)."""
    argv = sys.argv[1:] if argv is None else list(argv)
    a = p.parse_args(argv)
    if not a.look:
        return a
    typed = a.post
    a = p.parse_args(LOOKS[a.look] + argv)
    if not typed and os.path.splitext(a.output or "")[1].lower() not in files:
        a.post = ()
    return a


def _unit(text):
    """argparse type: a number from 0 to 1."""
    v = float(text)
    if not 0 <= v <= 1:
        raise argparse.ArgumentTypeError("must be 0-1, got %s" % text)
    return v


def stamp_title(img, title, place="bottom", fill=None):
    """Draw a large headline on a rendered picture. `title` may contain newlines (or the two characters \\n).
    The size shrinks until the longest line fits the width. Place is 'top' or 'bottom', flush left."""
    lines = [ln for ln in title.replace("\\n", "\n").split("\n")]
    lines = lines or [""]
    margin = max(12, img.width // 24)
    size = max(18, img.width // 10)
    font = None
    while size >= 14:
        for name in ("DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "Arial Bold.ttf"):
            try:
                font = ImageFont.truetype(name, size)
                break
            except OSError:
                continue
        if font is None:
            font = ImageFont.load_default(size)
        if max(font.getlength(ln) for ln in lines) <= img.width - 2 * margin:
            break
        size -= 2
        font = None
    if font is None:
        font = ImageFont.load_default(14)
    if fill is None:
        corner = img.getpixel((min(2, img.width - 1), min(2, img.height - 1)))
        fill = (255, 255, 255) if sum(corner[:3]) < 384 else (16, 16, 16)
    gap = max(2, size // 8)
    heights = []
    for ln in lines:
        box = font.getbbox(ln)
        heights.append(box[3] - box[1])
    block = sum(heights) + gap * (len(lines) - 1)
    y = margin if place == "top" else max(margin, img.height - margin - block)
    draw = ImageDraw.Draw(img)
    for ln, h in zip(lines, heights):
        draw.text((margin, y), ln, font=font, fill=fill)
        y += h + gap
    return img


def underlay(img, bg, strength):
    """The photo to draw behind the glyphs (the `under` of to_png and to_html): the original picture, untouched,
    only dimmed toward the page. `strength` (0-1) is how much of the photo shows; 1 is the photo as it is."""
    back = rgb(bg)
    return Image.blend(Image.new("RGB", img.size, back), flatten(img, back), strength)


def add_poster_args(p):
    """--look, --backdrop, the photo styles, and the words and tiles options, shared with animate.py."""
    p.add_argument("--look", choices=LOOKS, help="a recipe of flags: %s; your own flags win" % ", ".join(LOOKS))
    p.add_argument("--backdrop", type=_unit, default=0.0, metavar="K",
                   help="ramp/shape/braille: give each cell a background of its own color at strength 0-1 (try 0.35)")
    p.add_argument("--style", choices=STYLES, help="the photo look: small glyphs in the photo's colors over the "
                   "dimmed photo. Sets -c, and for a picture -w, --aspect, --font-size and --under %g, unless you give them"
                   % STYLE_UNDER)
    p.add_argument("--words", default=WORDS, help="words mode: vocabulary, space or comma separated")
    p.add_argument("--seed", type=int, default=0, help="words/tiles: seed for the layout or glyphs (default 0)")
    p.add_argument("--accent", help="words mode: box color for the most colorful words, e.g. #f28c28")
    p.add_argument("--accent-level", type=float, default=0.5, help="words mode: saturation 0-1 a word needs for a box")
    p.add_argument("--palette", type=int, default=8, help="tiles: number of tile colors, 1-256 (default 8)")
    p.add_argument("--gradient", choices=GRADIENTS, help="recolor by brightness through a gradient: %s. "
                   "Dark takes the first stop, bright the last. With --under, the photo is graded the same way"
                   % ", ".join(GRADIENTS))


def poster_defaults(a, image):
    """Fill options left unset. Tiles: square cells, big glyphs, a thin gap. Words and tiles: a charcoal page.
    --colors: the palette's darkest color as the page (the Game Boy's dark green); words mode ignores it, as --fg.
    A style: its ramp, and for a picture its cell shape, glyph size and columns, over the photo.
    Words: the gap only parts stacked rows, so a word's box stays whole. LED and dots: square cells, 16 and
    12 px. Text stays at aspect 0.5, because a terminal char is twice as tall as it is wide."""
    tiles = a.mode == "tiles"
    if a.mode == "words":
        a.colors = None  # word ink carries the image
    square = a.mode in ("tiles", "led", "dots", "stipple")
    defaults = {"aspect": 1.0 if square and image else 0.5,
                "font_size": {"tiles": 80, "led": 26, "dots": 20, "stipple": 14}.get(a.mode, 12),
                "bg": POSTER_BG if a.mode in ("words", "tiles") else
                "#%02x%02x%02x" % min(RETRO[a.colors], key=_lum) if a.colors else "black"}
    if a.style:
        defaults["charset"] = a.style
        if image:  # text keeps the terminal's cell shape and has no photo under it
            defaults["aspect"], defaults["font_size"], defaults["width"] = STYLES[a.style]
            defaults["under"] = STYLE_UNDER
    for k, v in defaults.items():
        if getattr(a, k) is None:
            setattr(a, k, v)
    if a.mode == "words":
        a.gap = (0, max(1, round(a.font_size / 8)) if a.gap is None else a.gap)
    elif a.gap is None:
        a.gap = 1 if tiles else 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Turn an image into ASCII art.")
    p.add_argument("image", help="image path, or - for stdin")
    p.add_argument("-o", "--output", help="write .txt, .html, .png, .jpg or .webp; default prints to stdout")
    p.add_argument("-w", "--width", type=int, help="columns, 1-%d (default 100)" % MAX_SIDE)
    p.add_argument("-c", "--charset",
                   help="%s, or your own ramp from dense to empty (default standard; tiles: random glyphs)"
                   % ", ".join(CHARSETS))
    p.add_argument("--aspect", type=float, help="char width / height (default 0.5; tiles, led, dots: 1 for PNG/HTML)")
    p.add_argument("--contrast", type=float, default=1.0, help="1.0 = unchanged")
    p.add_argument("--brightness", type=float, default=1.0, help="1.0 = unchanged")
    p.add_argument("--invert", action="store_true", help="swap light and dark")
    p.add_argument("--dither", nargs="?", const="fs", choices=("fs", "bayer"),
                   help="Floyd-Steinberg dithering; --dither bayer: ordered 8x8 crosshatch, also for --colors")
    p.add_argument("--colors", choices=RETRO, help="snap every color to this retro palette")
    p.add_argument("--bg", help="black (default; %s in words and tiles mode), white, none (PNG/HTML only), or any color" % POSTER_BG)
    p.add_argument("--fg", help="one ink color: %s, or any color. Default: colors from the photo" % ", ".join(COLORS))
    p.add_argument("--color", action="store_true", help="truecolor ANSI escape codes in text output")
    p.add_argument("--font-size", type=int, help="PNG/HTML font size in px (default 12; tiles: 80; led: 26; dots: 20)")
    p.add_argument("--mode", choices=SUBPIXELS, default="ramp",
                   help="ramp (default): one glyph per pixel; shape: edges drawn with matching symbols; braille: 2x4 dots per char; "
                        "halfblock: 2 colors per char; words: a poster of words lit by the image; "
                        "tiles: square color tiles with one glyph each; led: an LED board; dots: a halftone print; "
                        "stipple: fixed-size dots, tone is how many are on")
    p.add_argument("--mix", nargs="?", const=1.5, type=float, default=0, metavar="STEPS",
                   help="ramp: scatter each cell by up to this many glyph steps so a gradient mixes nearby "
                        "characters instead of banding into stripes. --mix alone is 1.5; 0 is off")
    p.add_argument("--title", help="PNG/HTML: large headline over the art. Use \\n for a line break")
    p.add_argument("--title-place", choices=("top", "bottom"), default="bottom",
                   help="where --title sits (default bottom)")
    p.add_argument("--sharpen", action="store_true", help="unsharp mask before shrinking, for crisper edges")
    p.add_argument("--gap", type=int, help="PNG/HTML: px of background around each background cell (tiles: default 1); "
                   "words mode: px between boxes in stacked rows (default font size / 8)")
    p.add_argument("--glow", type=float, default=0, help="PNG/HTML: soft bloom around the glyphs, 0-1 (try 0.8)")
    p.add_argument("--under", type=float, metavar="0-1", help="PNG/HTML: draw the original photo behind the "
                   "glyphs; the number is how strong it shows (try 0.5)")
    add_poster_args(p)
    p.add_argument("--post", type=post.parse, default=(), metavar="LIST",
                   help="PNG/JPG/WebP: post effects, comma separated: %s" % ", ".join(post.EFFECTS))
    a = parse_look(p, argv, (".png", ".jpg", ".jpeg", ".webp"))
    ext = os.path.splitext(a.output or "")[1].lower()
    if ext not in ("", ".txt", ".html", ".htm", ".png", ".jpg", ".jpeg", ".webp"):
        p.error("unknown output extension %r: use .txt, .html, .png, .jpg or .webp" % ext)
    if a.post and ext not in (".png", ".jpg", ".jpeg", ".webp"):
        p.error("--post needs a .png, .jpg or .webp output")
    if a.under and ext in ("", ".txt"):
        p.error("--under needs .png, .jpg, .webp or .html output")
    poster_defaults(a, ext not in ("", ".txt"))
    if a.width is None:
        a.width = 100
    if a.font_size < 1 or not 0 <= a.glow <= 1 or not 0 <= (a.under or 0) <= 1 or (a.mix or 0) < 0:
        p.error("need --font-size >= 1, --glow 0-1, --under 0-1 and --mix >= 0")
    if a.title and ext not in (".png", ".jpg", ".jpeg", ".webp", ".html", ".htm"):
        p.error("--title needs a .png, .jpg, .webp or .html output")
    try:
        img = load(a.image)
        grid = convert(img, a.width, a.charset, a.aspect, a.contrast, a.brightness,
                       a.invert, a.dither, "black" if a.bg == "none" else a.bg, a.mode, a.sharpen,
                       words=a.words, seed=a.seed, accent=a.accent, accent_level=a.accent_level,
                       palette=RETRO[a.colors] if a.colors else a.palette, over_photo=bool(a.under),
                       tone=bool(a.colors), backdrop=a.backdrop, gradient=a.gradient, mix=a.mix)
        fg = rgb(a.fg) if a.fg and a.mode != "words" else None  # word ink carries the image, one color would hide it
        if a.colors:
            grid, fg = snap_grid(grid, a.colors, a.dither == "bayer"), fg and snap(fg, a.colors)
        page = "black" if a.bg == "none" else a.bg
        src = grade_image(flatten(img, rgb(page)), a.gradient) if a.gradient and a.under else img
        under = underlay(src, page, a.under) if a.under else None
        if ext in (".png", ".jpg", ".jpeg", ".webp"):
            img = to_png(grid, a.bg, fg, a.font_size, a.aspect, a.gap, a.glow, under, a.mode, pure=bool(a.colors))
            img = post.apply(img, a.post, img.height // len(grid))
            if a.title:
                img = stamp_title(img, a.title, a.title_place)
            (img.convert("RGB") if ext in (".jpg", ".jpeg") else img).save(a.output)
        elif ext in (".html", ".htm"):
            page = to_html(grid, a.bg, fg, a.font_size, a.aspect, a.gap, a.glow, under)
            if a.title:
                block = "<div style='font:700 42px/1.05 DejaVu Sans,sans-serif;padding:24px 28px'>%s</div>" % (
                    "<br>".join(html.escape(ln) for ln in a.title.replace("\\n", "\n").split("\n")))
                page = page.replace("</body>", block + "</body>") if a.title_place == "bottom" else page.replace(
                    "<pre ", block + "<pre ", 1)
            with open(a.output, "w", encoding="utf-8") as out:
                out.write(page)
        else:
            text = to_ansi(grid, fg) if a.color else to_text(grid, a.mode == "tiles")
            if a.output:
                with open(a.output, "w", encoding="utf-8") as out:
                    out.write(text)
            else:
                if hasattr(sys.stdout, "reconfigure"):  # art is Unicode: never die on an ascii or cp1252 pipe
                    sys.stdout.reconfigure(encoding="utf-8")
                sys.stdout.write(text)
        if a.output:
            print(a.output)  # so scripts can tell it worked
    except Image.UnidentifiedImageError as e:
        hint = UNSUPPORTED.get(os.path.splitext(a.image)[1].lower())
        p.error(str(e) + (" (%s)" % hint if hint else ""))
    except (OSError, ValueError, Image.DecompressionBombError) as e:
        p.error(str(e))


if __name__ == "__main__":
    main()
