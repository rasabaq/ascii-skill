"""Post effects baked into a rendered image: scan lines, bloom, chromatic aberration, CRT, vignette, grain.

    import post
    img = post.apply(to_png(grid), post.parse("crt"), row=img.height // len(grid))

Every effect is a fixed function of the image size, so a still area of an animation stays the same in
every frame: the masks, the curvature map and the grain are built once per size and reused. Nothing
moves on its own, so nothing flickers. The order is always bloom, curvature, chroma, masks, grain.
"""
import argparse
import functools
import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

EFFECTS = ("scan", "bloom", "chroma", "crt", "vignette", "grain")
SCAN = 0.22  # how much the gap between two scan lines darkens
SCAN_PX = 3  # wanted scan line pitch in px; the real pitch divides the text row, so lines never drift
BLOOM = (90, 0.9)  # glow starts at this brightness (0-255), and its strength
CRT_BLOOM = 0.45  # crt alone adds a lighter bloom
CHROMA = 1 / 600  # red/blue split at the left and right edges, as a share of the width; none in the centre
CURVE = 0.08  # crt bulge: how far the corners bend in, as a share of the half size
BEZEL = 0.012  # crt: dark border around the curved screen, as a share of the size
VIGNETTE = 0.5  # how much the far corners darken
CRT_VIGNETTE = 0.3
GRAIN = 8  # grain strength: spread (std) of the noise around mid gray; overlay blend, so black and white stay clean
SS = 4  # the screen mask is drawn at up to 4x and shrunk, for smooth curved edges


def parse(text):
    """argparse type for --post: 'crt,grain' -> ('crt', 'grain') in the fixed order."""
    names = {n.strip() for n in text.split(",") if n.strip()}
    bad = names - set(EFFECTS)
    if bad or not names:
        raise argparse.ArgumentTypeError("unknown post effect %r: use a comma list of %s"
                                         % (",".join(sorted(bad)) or text, ", ".join(EFFECTS)))
    return tuple(n for n in EFFECTS if n in names)


@functools.lru_cache(maxsize=8)
def _mesh(w, h, k=0.0, r=0.0, s=1.0, scale=1, n=32):
    """Image.transform MESH data for a smooth warp: n x n output boxes, each mapped to a source quad.
    In -1..1 coords the screen point (u, v) shows the picture point u * (1 + k*v^2 + r*(u^2+v^2)) * s
    (and the same for v). k bows the edges like a CRT; r grows radially, for chromatic aberration."""
    W, H = w * scale, h * scale
    n = min(n, W, H)  # every box at least 1 px
    xs = [round(i * W / n) for i in range(n + 1)]
    ys = [round(j * H / n) for j in range(n + 1)]

    def src(x, y):  # box corners in px; the warp is exact at each one, so no warp means no change
        u, v = 2 * x / W - 1, 2 * y / H - 1
        d = r * (u * u + v * v)
        return (u * (1 + k * v * v + d) * s + 1) * W / 2, (v * (1 + k * u * u + d) * s + 1) * H / 2
    return [((x0, y0, x1, y1), src(x0, y0) + src(x0, y1) + src(x1, y1) + src(x1, y0))
            for x0, x1 in zip(xs, xs[1:]) for y0, y1 in zip(ys, ys[1:])]


def _crt_mesh(w, h, scale=1):
    """The CRT bulge. The bezel scale s keeps the whole picture on screen; the rounded screen corners
    (see _mask) clip only the outer tip of each picture corner."""
    return _mesh(w, h, k=CURVE, s=1 + 2 * BEZEL, scale=scale)


def _curve(img):
    return img.transform(img.size, Image.Transform.MESH, _crt_mesh(*img.size), Image.Resampling.BICUBIC,
                         fillcolor=(0, 0, 0))


@functools.lru_cache(maxsize=4)
def _mask(w, h, row, names):
    """One RGB multiply mask for all still effects: scan lines, vignette and the CRT screen shape."""
    crt = "crt" in names
    mask = Image.new("L", (w, h), 255)
    if "scan" in names or crt:  # a soft cos^2 dip between lines; the pitch divides the text row height
        pitch = row / max(1, round(row / SCAN_PX)) if row else SCAN_PX
        col = Image.new("L", (1, h))
        col.putdata([round(255 * (1 - SCAN * (0.5 - 0.5 * math.cos(2 * math.pi * (y + 0.5) / pitch))))
                     for y in range(h)])
        mask = ImageChops.multiply(mask, col.resize((w, h), Image.Resampling.NEAREST))
    if "vignette" in names or crt:  # smooth falloff in r^2, drawn small and scaled up
        k = VIGNETTE if "vignette" in names else CRT_VIGNETTE
        n = 64
        small = Image.new("L", (n, n))
        small.putdata([round(255 * (1 - k * ((((x + 0.5) / n * 2 - 1) ** 2 + ((y + 0.5) / n * 2 - 1) ** 2) / 2) ** 1.5))
                       for y in range(n) for x in range(n)])
        mask = ImageChops.multiply(mask, small.resize((w, h), Image.Resampling.BICUBIC))
    if crt:  # rounded screen, warped like the picture, drawn bigger so its curved edge is smooth
        ss = max(1, min(SS, int((16e6 / (w * h)) ** 0.5)))  # at most ~16M px while drawing
        big = Image.new("L", (w * ss, h * ss))
        ImageDraw.Draw(big).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), radius=min(w, h) * ss // 14, fill=255)
        screen = big.transform(big.size, Image.Transform.MESH, _crt_mesh(w, h, ss), Image.Resampling.NEAREST)
        mask = ImageChops.multiply(mask, screen.resize((w, h), Image.Resampling.BOX))
    return mask.convert("RGB")


def _bloom(img, strength, row):
    """Glow from the bright parts: a tight and a wide blur of them, screened on top, so glyphs stay crisp.
    The blur sizes follow the text row height, so big glyphs get a big glow."""
    t = BLOOM[0]
    bright = img.point([max(0, v - t) * 255 // (255 - t) for v in range(256)] * 3)
    cell = max(2, row / 3.5 if row else img.width / 160)
    glow = Image.blend(bright.filter(ImageFilter.GaussianBlur(cell)), bright.filter(ImageFilter.GaussianBlur(cell * 4)), 0.5)
    return ImageChops.screen(img, glow.point([round(v * strength) for v in range(256)] * 3))


def _chroma(img):
    """Red pushed outward and blue pulled inward, growing with r^2: the centre stays clean and the
    left and right edges split by CHROMA of the width, the corners by twice that."""
    w, h = img.size
    r, g, b = img.split()
    k = CHROMA * 2  # shift at the edge middle is r * w / 2
    out = [ch.transform(img.size, Image.Transform.MESH, _mesh(w, h, r=sign * k), Image.Resampling.BILINEAR)
           for ch, sign in ((r, -1), (b, 1))]
    return Image.merge("RGB", (out[0], g, out[1]))


@functools.lru_cache(maxsize=4)
def _grain(w, h):
    """Fixed grain: seeded noise, softened a little. Static, so it never crawls and GIFs stay small."""
    noise = Image.frombytes("L", (w, h), random.Random(1).randbytes(w * h)).filter(ImageFilter.GaussianBlur(0.6))
    # uniform bytes blurred by 0.6 px have a spread (std) of about 39; scale that to GRAIN
    # ponytail: one still grain for every frame; seeded per-frame tiles if a moving film look is ever wanted
    return noise.point([max(0, min(255, round(128 + (v - 128) * GRAIN / 39))) for v in range(256)]).convert("RGB")


def apply(img, names, row=0):
    """Return `img` with the post effects in `names` (from parse), as an RGB image.
    `row` is the text row height in px, so scan lines line up with the rows. Transparency becomes black."""
    if not names:
        return img
    if img.mode != "RGB":
        flat = Image.new("RGB", img.size)
        flat.paste(img, mask=img.getchannel("A") if "A" in img.getbands() else None)
        img = flat
    if "bloom" in names or "crt" in names:
        img = _bloom(img, BLOOM[1] if "bloom" in names else CRT_BLOOM, row)
    if "crt" in names:
        img = _curve(img)
    if "chroma" in names:
        img = _chroma(img)
    if {"scan", "vignette", "crt"} & set(names):
        img = ImageChops.multiply(img, _mask(img.width, img.height, row, names))
    if "grain" in names:
        img = ImageChops.overlay(img, _grain(*img.size))
    return img
