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
import functools
import html
import io
import os
import random
import sys

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

# Ramps go from densest to emptiest glyph.
CHARSETS = {
    "standard": "@%#*+=-:. ",
    "detailed": "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. ",
    "blocks": "█▓▒░ ",
    "terminal": "@#o=-. ",
    "minimal": "#+. ",
    "binary": "10 ",
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
SYMBOLS = set("◆◇●•·✖✕×")  # no taller than wide, so they fill a square cell at full size
COLORS = {"matrix": "#00ff41", "amber": "#ffb000", "cyan": "#00e5ff", "magenta": "#ff3df2", "mint": "#9dffb0"}
# Monospace first, then fonts that cover braille and other symbols.
FONTS = ["Menlo.ttc", "DejaVuSansMono.ttf", "consola.ttf", "LiberationMono-Regular.ttf", "cour.ttf",
         "Courier.ttc", "Apple Symbols.ttf", "seguisym.ttf", "DejaVuSans.ttf", "NotoSansSymbols2-Regular.ttf"]
SHADES = {"█": 1.0, "▓": 0.75, "▒": 0.5, "░": 0.25}  # drawn as solid cells in PNG, so no font bleed
MAX_SIDE = 1000  # ponytail: hard cap on columns and rows; bigger grids eat GBs and nobody can read them
CELL_W = 0.6  # monospace advance in em
SUBPIXELS = {"ramp": (1, 1), "shape": (1, 1), "braille": (2, 4), "halfblock": (1, 2), "words": (1, 1), "tiles": (4, 4)}  # image pixels per cell (x, y)
# Shape mode samples each cell as a SHAPE_X x SHAPE_Y grid and gives edge cells the glyph whose ink
# sits in the same places. Symbols only: letters, brackets and ^~<>` read as noise in photos.
SHAPE_X, SHAPE_Y = 3, 4
SHAPE_CHARS = " #%'*+,-./:;=@\\_|"
SHAPE_EDGE = 0.03  # RMS contrast (0-1) inside a cell above which it counts as an edge
SHAPE_TONE = 2.0  # weight of the cell's overall brightness against where its ink sits
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


def rgb(value):
    return ImageColor.getrgb(COLORS.get(value, value))[:3]


def load(path):
    img = Image.open(io.BytesIO(sys.stdin.buffer.read()) if path == "-" else path)
    return ImageOps.exif_transpose(img)


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
            words=WORDS, seed=0, accent=None, accent_level=0.5, palette=8, cut=None, over_photo=False):
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
    """
    ramp = CHARSETS.get(charset or "standard", charset)
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
        img = img.point(stretch_lut(value_hist(img)))  # use the full tonal range, so dim photos still read
    img = ImageEnhance.Brightness(ImageEnhance.Contrast(img).enhance(contrast)).enhance(brightness)

    rows = round(width * img.height / img.width * aspect)
    if rows > MAX_SIDE:  # very tall image: shrink width to keep the shape
        width, rows = max(1, round(width * MAX_SIDE / rows)), MAX_SIDE
    rows = max(1, rows)
    pw, ph = width * sx, rows * sy  # sampled pixels; each one is square when aspect is right
    if sharpen and pw < img.width:  # unsharp mask at the scale of one output pixel, so it survives the shrink
        img = img.filter(ImageFilter.UnsharpMask(radius=img.width / pw, percent=150, threshold=2))
    # Nearest keeps pixel art crisp when upscaling; Lanczos averages well when shrinking.
    resample = Image.Resampling.NEAREST if pw >= img.width else Image.Resampling.LANCZOS
    small = img.resize((pw, ph), resample, reducing_gap=3.0)
    if mode == "halfblock":  # true colors, two pixels per cell
        px = (ImageOps.invert(small) if invert else small).load()
        return [[(HALF, px[x, 2 * r], px[x, 2 * r + 1]) for x in range(width)] for r in range(rows)]
    dark_bg = sum(back) < 384
    if mode == "words":
        return _words(small, back, invert, words, seed, accent and rgb(accent), accent_level)
    if mode == "tiles":
        return _tiles(small, width, rows, ramp if charset else None, back, dark_bg, palette, seed)

    # Ink density per pixel: on a dark background bright pixels get dense glyphs.
    top = 1 if mode == "braille" else len(ramp) - 1
    levels = [(v if dark_bg != invert else 255 - v) / 255 * top for v in small.convert("L").tobytes()]
    # Braille dots without dither: threshold at the image's mean, so mid-tone ink (a blue logo) still shows.
    if cut is None:
        cut = min(0.75, max(0.25, sum(levels) / len(levels))) if mode == "braille" and not dither else 0.5
    if dither:
        dither_levels(levels, pw, top)
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
            cells.append((ch, tuple(min(255, round(v * k)) for v in c)))
            continue
        # The glyph already shows brightness, so keep the hue but make the ink readable on the background.
        peak = max(c) or 1
        if dark_bg and peak < 64:  # a near-black pixel's hue is mostly noise: fade it to gray before brightening
            m, k = sum(c) / 3, peak / 64
            c = [m + (v - m) * k for v in c]
        scale = max(peak, 200) / peak if dark_bg else min(peak, 150) / peak
        cells.append((ch, tuple(min(255, round(v * scale)) for v in c)))
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


def _words(small, back, invert, words, seed, accent, accent_level):
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
            box = accent and (max(c) - min(c)) / 255 >= accent_level
            row[a:b] = [(ch, back, accent) if box else (ch, ink) for ch in text[a:b]]
        grid.append(row)
    return grid


def _lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _tiles(small, width, rows, ramp, back, dark_bg, palette, seed):
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
            row.append((ch, TILE_INK[_lum(t) < 140], t) if t else (ch, faint))
        grid.append(row)
    return grid


@functools.lru_cache(maxsize=8)
def _glyph_vectors(aspect):
    """(char, shape vector) for each SHAPE_CHARS glyph, drawn with the font to_png uses.
    Tone is scaled so the densest glyph matches a white cell, as in the ramp."""
    cw = 29  # glyph cell at 48px, big enough to measure
    chh = max(1, round(cw / aspect))
    f = font(48, SHAPE_CHARS)
    vecs = {}
    for ch in SHAPE_CHARS:
        im = Image.new("L", (cw, chh))
        ImageDraw.Draw(im).text((cw / 2, chh / 2), ch, font=f, fill=255, anchor="mm")
        vecs[ch] = im.resize((SHAPE_X, SHAPE_Y), Image.Resampling.BOX).tobytes()
    n = SHAPE_X * SHAPE_Y
    densest = max(sum(v) for v in vecs.values())
    tone_w = (SHAPE_TONE * n) ** 0.5
    return [(ch, _shape_vector([b / 255 for b in v], sum(v) / densest * tone_w)) for ch, v in vecs.items()]


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


def to_text(grid):
    # Next to tiles, loose glyphs are faint decoration; plain text cannot draw them faint, so it drops them.
    tiles = any(len(c) == 3 and c[0] != HALF for row in grid for c in row)
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


def to_html(grid, bg="black", fg=None, font_size=12, aspect=0.5, gap=0, under=None):
    """`gap` (px) leaves a border of page background around each background cell, for a tile look.
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
            '<body style="margin:0;background:%s"><pre style="margin:0;padding:16px;font:%dpx/%.3f Menlo,Consolas,'
            '\'DejaVu Sans Mono\',monospace%s">%s</pre></body>\n') % ((lh,) + box + (back, size, lh, photo, "\n".join(lines)))


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


def _ink_offset(f, ch):
    """(dx, dy) in whole px that moves `ch`, drawn with anchor "mm", so its ink is centred on the anchor point.
    Fonts set symbols a little below the middle of the line, which shows when they fill a square cell."""
    s = 2 * f.size
    im = Image.new("L", (2 * s, 2 * s))
    ImageDraw.Draw(im).text((s, s), ch, font=f, fill=255, anchor="mm")
    left, top, right, bottom = im.getbbox() or (s, s, s, s)
    return round(s - (left + right) / 2), round(s - (top + bottom) / 2)


def to_png(grid, bg="black", fg=None, font_size=12, aspect=0.5, gap=0, under=None):
    """`gap` (px) leaves a border of background around each background cell, for a tile look.
    A pair (x, y) sets each side; (0, y) keeps a word's box whole and only parts the rows.
    `under` is an image drawn behind the glyphs instead of the flat background, stretched to fit."""
    gx, gy = gap if isinstance(gap, tuple) else (gap, gap)
    cw = max(1, round(font_size * CELL_W))
    chh = max(1, round(cw / aspect))  # cell shape matches the aspect used to sample the image
    dot = max(1, round(min(cw / 2, chh / 4)))  # braille dot size in px
    glyphs = {c[0] for row in grid for c in row if c[0] not in SHADES and c[0] != HALF and not _braille(c[0])}
    f = font(min(font_size, round(chh / 1.2)), "".join(glyphs))  # glyphs shrink to fit short cells (square tiles)
    big = font(font_size, "".join(glyphs))  # symbols do not: they fill a square cell at full size, centred by their ink
    nudge = {ch: _ink_offset(big, ch) for ch in glyphs & SYMBOLS}
    mode, back = ("RGBA", (0, 0, 0, 0)) if bg == "none" else ("RGB", rgb(bg))
    size = (len(grid[0]) * cw, len(grid) * chh)
    img = Image.new(mode, size, back) if under is None else under.convert(mode).resize(size, Image.LANCZOS)
    draw = ImageDraw.Draw(img)
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
            elif ch in SHADES:
                k = SHADES[ch]
                fill = ink + (round(255 * k),) if mode == "RGBA" else tuple(round(b + (i - b) * k) for b, i in zip(back, ink))
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
    return img


def underlay(img, bg, strength):
    """The photo to draw behind the glyphs (the `under` of to_png and to_html): the original picture, untouched,
    only dimmed toward the page. `strength` (0-1) is how much of the photo shows; 1 is the photo as it is."""
    back = rgb(bg)
    return Image.blend(Image.new("RGB", img.size, back), flatten(img, back), strength)


def add_poster_args(p):
    """Style, words and tiles options, shared with animate.py."""
    p.add_argument("--style", choices=STYLES, help="the photo look: small glyphs in the photo's colors over the "
                   "dimmed photo. Sets -c, and for a picture -w, --aspect, --font-size and --under %g, unless you give them"
                   % STYLE_UNDER)
    p.add_argument("--words", default=WORDS, help="words mode: vocabulary, space or comma separated")
    p.add_argument("--seed", type=int, default=0, help="words/tiles: seed for the layout or glyphs (default 0)")
    p.add_argument("--accent", help="words mode: box color for the most colorful words, e.g. #f28c28")
    p.add_argument("--accent-level", type=float, default=0.5, help="words mode: saturation 0-1 a word needs for a box")
    p.add_argument("--palette", type=int, default=8, help="tiles: number of tile colors, 1-256 (default 8)")


def poster_defaults(a, image):
    """Fill options left unset. Tiles: square cells, big glyphs, a thin gap. Words and tiles: a charcoal page.
    A style: its ramp, and for a picture its cell shape, glyph size and columns, over the photo.
    Words: the gap only parts stacked rows, so a word's box stays whole. Text stays at aspect 0.5,
    because a terminal char is twice as tall as it is wide."""
    tiles = a.mode == "tiles"
    defaults = {"aspect": 1.0 if tiles and image else 0.5, "font_size": 80 if tiles else 12,
                "bg": POSTER_BG if a.mode in ("words", "tiles") else "black"}
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
    p.add_argument("--aspect", type=float, help="char width / height (default 0.5; tiles: 1 for PNG/HTML)")
    p.add_argument("--contrast", type=float, default=1.0, help="1.0 = unchanged")
    p.add_argument("--brightness", type=float, default=1.0, help="1.0 = unchanged")
    p.add_argument("--invert", action="store_true", help="swap light and dark")
    p.add_argument("--dither", action="store_true", help="Floyd-Steinberg dithering")
    p.add_argument("--bg", help="black (default; %s in words and tiles mode), white, none (PNG/HTML only), or any color" % POSTER_BG)
    p.add_argument("--fg", help="one ink color: %s, or any color. Default: colors from the photo" % ", ".join(COLORS))
    p.add_argument("--color", action="store_true", help="truecolor ANSI escape codes in text output")
    p.add_argument("--font-size", type=int, help="PNG/HTML font size in px (default 12; tiles: 80)")
    p.add_argument("--mode", choices=SUBPIXELS, default="ramp",
                   help="ramp (default): one glyph per pixel; shape: edges drawn with matching symbols; braille: 2x4 dots per char; "
                        "halfblock: 2 colors per char; words: a poster of words lit by the image; "
                        "tiles: square color tiles with one glyph each")
    p.add_argument("--sharpen", action="store_true", help="unsharp mask before shrinking, for crisper edges")
    p.add_argument("--gap", type=int, help="PNG/HTML: px of background around each background cell (tiles: default 1); "
                   "words mode: px between boxes in stacked rows (default font size / 8)")
    p.add_argument("--under", type=float, metavar="0-1", help="PNG/HTML: draw the original photo behind the "
                   "glyphs; the number is how strong it shows (try 0.5)")
    add_poster_args(p)
    a = p.parse_args(argv)
    ext = os.path.splitext(a.output or "")[1].lower()
    if ext not in ("", ".txt", ".html", ".htm", ".png", ".jpg", ".jpeg", ".webp"):
        p.error("unknown output extension %r: use .txt, .html, .png, .jpg or .webp" % ext)
    if a.under and ext in ("", ".txt"):
        p.error("--under needs .png, .jpg, .webp or .html output")
    poster_defaults(a, ext not in ("", ".txt"))
    if a.width is None:
        a.width = 100
    if a.font_size < 1 or not 0 <= (a.under or 0) <= 1:
        p.error("need --font-size >= 1 and --under 0-1")
    try:
        img = load(a.image)
        grid = convert(img, a.width, a.charset, a.aspect, a.contrast, a.brightness,
                       a.invert, a.dither, "black" if a.bg == "none" else a.bg, a.mode, a.sharpen,
                       words=a.words, seed=a.seed, accent=a.accent, accent_level=a.accent_level, palette=a.palette,
                       over_photo=bool(a.under))
        fg = rgb(a.fg) if a.fg and a.mode != "words" else None  # word ink carries the image, one color would hide it
        under = underlay(img, "black" if a.bg == "none" else a.bg, a.under) if a.under else None
        if ext in (".png", ".jpg", ".jpeg", ".webp"):
            img = to_png(grid, a.bg, fg, a.font_size, a.aspect, a.gap, under)
            (img.convert("RGB") if ext in (".jpg", ".jpeg") else img).save(a.output)
        elif ext in (".html", ".htm"):
            with open(a.output, "w", encoding="utf-8") as out:
                out.write(to_html(grid, a.bg, fg, a.font_size, a.aspect, a.gap, under))
        else:
            text = to_ansi(grid, fg) if a.color else to_text(grid)
            if a.output:
                with open(a.output, "w", encoding="utf-8") as out:
                    out.write(text)
            else:
                sys.stdout.write(text)
        if a.output:
            print(a.output)  # so scripts can tell it worked
    except Image.UnidentifiedImageError as e:
        hint = {".svg": " (SVG is not supported: convert it to PNG first, e.g. rsvg-convert)",
                ".heic": " (HEIC needs: pip install pillow-heif)"}.get(os.path.splitext(a.image)[1].lower(), "")
        p.error(str(e) + hint)
    except (OSError, ValueError, Image.DecompressionBombError) as e:
        p.error(str(e))


if __name__ == "__main__":
    main()
