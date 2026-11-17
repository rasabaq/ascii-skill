"""A koi pond from above, drawn in code: an example scene file for --scene.

    uv run scripts/animate.py --scene examples/koi.py -w 160 -o koi.mp4
    uv run scripts/animate.py --scene examples/koi.py -w 160 --mode halfblock -o koi.mp4

Four koi (kohaku, orange, ogon, showa) glide in slow 8-second loops under lily pads and a lotus.
The water is black on purpose: in glyph modes any tone there becomes a field of dots.
"""
import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from scenes import SS, TAU, _shrink, scene

ORANGE, WHITE, GOLD, RED, INK = (255, 115, 25), (250, 246, 238), (255, 196, 50), (230, 40, 30), (30, 30, 34)
# Each koi: base color, then patches as (s along body 0-1, side -1..1, radius in half-widths, color).
KOI = [
    (WHITE, [(0.1, 0.0, 0.7, RED), (0.36, 0.35, 1.0, RED), (0.52, -0.3, 0.9, RED), (0.72, 0.2, 0.6, RED)]),  # kohaku
    (ORANGE, [(0.04, 0.0, 0.55, WHITE), (0.55, 0.5, 0.5, WHITE)]),                                           # orange
    (GOLD, [(0.3, -0.5, 0.45, (255, 230, 140)), (0.6, 0.4, 0.4, (255, 230, 140))]),                         # ogon
    (WHITE, [(0.12, 0.3, 0.7, INK), (0.3, -0.4, 0.8, ORANGE), (0.46, 0.4, 0.75, INK),                        # showa
             (0.62, -0.2, 0.7, ORANGE), (0.8, 0.3, 0.5, INK)]),
]
TAIL_BEATS = 8  # per loop, whole number so the loop closes


def width(s):
    """Body half-width along the spine, s = 0 at the nose, 1 at the tail root."""
    if s < 0.3:
        return 0.45 + 0.55 * math.sin(math.pi / 2 * s / 0.3)
    return 1.0 - 0.85 * ((s - 0.3) / 0.7) ** 1.2


def lit(c, k):
    return tuple(max(0, min(255, round(v * k))) for v in c)


@scene(480, 360, 200, 25)
def koi(w, h, n, seed):
    """Koi glide around the pond, tails beating slowly, under drifting lily pads."""
    rng = random.Random(seed)
    W, H = w * SS, h * SS
    fish = []
    for i, (base, patches) in enumerate(KOI):
        # each fish circles its own part of the pond, so they cross now and then instead of piling up
        fish.append(dict(cx=W * (0.36 + 0.28 * (i % 2)), cy=H * (0.38 + 0.24 * (i // 2)),
                         ax=W * rng.uniform(0.2, 0.26), ay=H * rng.uniform(0.17, 0.22),
                         ph=i / len(KOI) + rng.uniform(-0.04, 0.04), dir=rng.choice((1, -1)),
                         size=rng.uniform(0.9, 1.1) * W * 0.28, base=base, patches=patches))
    pads = [(x * W, y * H, rng.uniform(16, 22) * SS, rng.random()) for x, y in ((0.1, 0.16), (0.9, 0.84), (0.88, 0.14))]

    out = []
    for k in range(n):
        t = k / n
        im = Image.new("RGB", (W, H))
        for f in fish:
            draw_koi(im, f, t)
        draw = ImageDraw.Draw(im)
        for i, (x, y, r, p) in enumerate(pads):  # lily pads drift on a small circle and turn slowly
            x += math.cos(TAU * (t + p)) * 6 * SS
            y += math.sin(TAU * (t + p)) * 6 * SS
            a = math.degrees(TAU * p) + 15 * math.sin(TAU * t)
            draw.pieslice((x - r, y - r, x + r, y + r), a + 20, a + 360, fill=(46, 128, 60))
            draw.pieslice((x - 0.8 * r, y - 0.8 * r, x + 0.8 * r, y + 0.8 * r), a + 20, a + 360, fill=(58, 150, 70))
            for v in range(1, 8):  # veins from the center
                va = math.radians(a + 20 + v * 42)
                draw.line([(x, y), (x + math.cos(va) * 0.9 * r, y + math.sin(va) * 0.9 * r)], fill=(40, 112, 52), width=SS)
            if i == 0:  # a pink lotus on the first pad
                for pk in range(8):
                    pa = TAU * pk / 8 + TAU * p
                    px, py = x + math.cos(pa) * 0.32 * r, y + math.sin(pa) * 0.32 * r
                    draw.ellipse((px - 0.28 * r, py - 0.28 * r, px + 0.28 * r, py + 0.28 * r), fill=(255, 150, 190))
                draw.ellipse((x - 0.18 * r, y - 0.18 * r, x + 0.18 * r, y + 0.18 * r), fill=(255, 220, 90))
        out.append(_shrink(im, w, h))
    return out


def draw_koi(im, f, t):
    W, H = im.size
    L, N = f["size"], 32
    hw = 0.15 * L

    def at(u):  # a point on this fish's oval path; u in turns
        a = TAU * (f["dir"] * u + f["ph"])
        return f["cx"] + f["ax"] * math.cos(a), f["cy"] + f["ay"] * math.sin(a)

    per = TAU * math.hypot(f["ax"], f["ay"]) / math.sqrt(2)  # rough path length
    spine = [at(t - j / N * L / per) for j in range(N + 1)]
    pts = []
    for j, (x, y) in enumerate(spine):  # bend the spine: a wave runs from head to tail
        x2, y2 = spine[min(j + 1, N)]
        x1, y1 = spine[max(j - 1, 0)]
        d = math.hypot(x2 - x1, y2 - y1) or 1
        nx, ny = (y2 - y1) / d, -(x2 - x1) / d
        s = j / N
        off = math.sin(TAU * (TAIL_BEATS * t - 1.1 * s + f["ph"])) * 0.1 * L * s ** 1.6
        pts.append((x + nx * off, y + ny * off, nx, ny))

    def body(s, side=0.0):  # a point on the body: s along it, side -1..1 across it
        fj = s * N
        j = min(int(fj), N - 1)
        q = fj - j
        x = pts[j][0] * (1 - q) + pts[j + 1][0] * q
        y = pts[j][1] * (1 - q) + pts[j + 1][1] * q
        nx, ny = pts[j][2], pts[j][3]
        r = side * hw * width(s)
        return x + nx * r, y + ny * r

    # Work in a crop around the fish, so the blurs stay cheap.
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    m = int(0.4 * L)
    ox, oy = int(min(xs)) - m, int(min(ys)) - m
    bw, bh = int(max(xs)) + m - ox, int(max(ys)) + m - oy

    def P(xy):
        return xy[0] - ox, xy[1] - oy

    outline = [P(body(i / 40, 1)) for i in range(41)] + [P(body(1 - i / 40, -1)) for i in range(41)]
    mask = Image.new("L", (bw, bh))
    md = ImageDraw.Draw(mask)
    md.polygon(outline, fill=255)
    hx, hy = P(body(0.02))
    md.ellipse((hx - 0.45 * hw, hy - 0.45 * hw, hx + 0.45 * hw, hy + 0.45 * hw), fill=255)  # round snout

    # Fins: see-through, with rays.
    fins = Image.new("L", (bw, bh))
    fd = ImageDraw.Draw(fins)
    rays = []
    tx, ty, nx, ny = pts[-1]
    bx, by = tx - pts[-4][0], ty - pts[-4][1]
    bl = math.hypot(bx, by) or 1
    bx, by = bx / bl, by / bl

    def tail(along, side):
        return P((tx + bx * along * L + nx * side * L, ty + by * along * L + ny * side * L))

    fan = [tail(-0.04, 0.03), tail(0.17, 0.15), tail(0.23, 0.12), tail(0.13, 0.0), tail(0.23, -0.12),
           tail(0.17, -0.15), tail(-0.04, -0.03)]
    fd.polygon(fan, fill=170)
    rays += [(tail(-0.02, 0), tail(0.21 - 0.05 * abs(v), 0.13 * v)) for v in (-1, -0.6, -0.25, 0.25, 0.6, 1)]
    for side in (1, -1):  # pectoral fins: broad paddles just behind the head
        root = body(0.2, 0.75 * side)
        a, b = body(0.2), body(0.34)
        dx, dy = b[0] - a[0], b[1] - a[1]
        ex, ey = body(0.2, 2.1 * side)
        tip = (ex + dx * 1.3, ey + dy * 1.3)
        back = body(0.33, 0.8 * side)
        fd.polygon([P(root), P(tip), P(((tip[0] + back[0]) / 2 + dx * 0.4, (tip[1] + back[1]) / 2 + dy * 0.4)), P(back)],
                   fill=150)
        rays += [(P(root), P((root[0] + (tip[0] - root[0]) * 0.9 + dx * v, root[1] + (tip[1] - root[1]) * 0.9 + dy * v)))
                 for v in (0, 0.5, 1)]
        pel, pel_tip = body(0.55, 0.7 * side), body(0.66, 1.5 * side)  # small pelvic fins
        fd.polygon([P(pel), P(pel_tip), P(body(0.63, 0.6 * side))], fill=140)

    fin_ink = lit(f["base"], 0.8)
    fin_ink = tuple(round(v * 0.7 + 70) for v in fin_ink)
    im.paste(fin_ink, (ox, oy), fins)
    rd = ImageDraw.Draw(im)
    for a, b in rays:
        rd.line([(a[0] + ox, a[1] + oy), (b[0] + ox, b[1] + oy)], fill=lit(fin_ink, 0.78), width=max(1, SS))

    # Body color: base, then the patches with soft, uneven edges.
    col = Image.new("RGB", (bw, bh), f["base"])
    cd = ImageDraw.Draw(col)
    for s, side, rad, c in f["patches"]:
        r = rad * hw * width(s)
        for dx, dy, kr in ((0, 0, 1), (0.4, 0.3, 0.7), (-0.35, -0.3, 0.75), (0.2, -0.5, 0.55)):  # lumpy blob
            cx, cy = P(body(s, side))
            cx, cy = cx + dx * r, cy + dy * r
            cd.ellipse((cx - kr * r, cy - kr * r, cx + kr * r, cy + kr * r), fill=c)
    col = col.filter(ImageFilter.GaussianBlur(0.25 * SS))
    # Scales: a faint net of arcs that rides with the body.
    scales = Image.new("L", (bw, bh))
    sd = ImageDraw.Draw(scales)
    for i in range(5, N - 3):
        for v in (-0.6, -0.2, 0.2, 0.6):
            cx, cy = P(body(i / N, v + (0.2 if i % 2 else 0)))
            r = 0.14 * hw
            sd.arc((cx - r, cy - r, cx + r, cy + r), 200, 340, fill=40, width=SS)
    col = ImageChops.subtract(col, Image.merge("RGB", (scales,) * 3))
    # Round body: a highlight along the back and darker flanks.
    hl = Image.new("L", (bw, bh))
    ImageDraw.Draw(hl).line([P(body(i / 20)) for i in range(2, 17)], fill=110, width=int(0.5 * hw))
    hl = hl.filter(ImageFilter.GaussianBlur(0.25 * hw))
    col = ImageChops.add(col, Image.merge("RGB", (hl,) * 3))
    edge = mask.filter(ImageFilter.GaussianBlur(0.4 * hw)).point(lambda v: 95 + v * 160 // 255)
    col = ImageChops.multiply(col, Image.merge("RGB", (edge,) * 3))
    cd = ImageDraw.Draw(col)
    # Dorsal fin: a thin ridge down the middle of the back.
    cd.line([P(body(i / 20)) for i in range(6, 14)], fill=lit(f["base"], 0.72), width=max(1, int(0.12 * hw)))
    # Eyes and whiskers.
    for side in (1, -1):
        ex, ey = P(body(0.07, 0.62 * side))
        er = 0.13 * hw
        cd.ellipse((ex - er, ey - er, ex + er, ey + er), fill=(15, 15, 18))
        cd.ellipse((ex - 0.4 * er, ey - 0.4 * er, ex, ey), fill=(220, 220, 220))
    im.paste(col, (ox, oy), mask)
    for side in (1, -1):
        a, b = body(0.0, 0.3 * side), body(0.06, 0.3 * side)
        dx, dy = a[0] - b[0], a[1] - b[1]
        wx, wy = body(0.0, 1.0 * side)
        rd.line([a, (a[0] + dx * 1.2 + (wx - a[0]) * 0.6, a[1] + dy * 1.2 + (wy - a[1]) * 0.6)],
                fill=lit(f["base"], 0.85), width=max(1, SS))
