"""A frosted donut with sprinkles, spinning in the light. It loops: the last frame flows into the first.

    uv run skills/ascii-art/scripts/animate.py --scene examples/donut.py --mode braille -w 80 -o donut.gif
"""
import math
import random

from PIL import Image, ImageDraw
from scenes import SS, TAU, _shrink, scene


def _rot(ax, ay, az):
    """Rotation matrix Rz @ Ry @ Rx, as rows."""
    cx, sx, cy, sy, cz, sz = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay), math.cos(az), math.sin(az)
    return ((cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx),
            (sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx),
            (-sy, cy * sx, cy * cx))


def _apply(m, p):
    return (m[0][0] * p[0] + m[0][1] * p[1] + m[0][2] * p[2],
            m[1][0] * p[0] + m[1][1] * p[1] + m[1][2] * p[2],
            m[2][0] * p[0] + m[2][1] * p[1] + m[2][2] * p[2])


def _unit(v):
    d = math.sqrt(sum(c * c for c in v)) or 1
    return tuple(c / d for c in v)


@scene(320, 240, 80, 25)
def donut(w, h, n, seed):
    """Small flat-shaded quads drawn back to front (painter's algorithm), with diffuse and specular light,
    so the brightness alone shows the shape. Pink icing with drips sits on top, so the golden dough shows
    on the sides and underneath."""
    rng = random.Random(seed)
    big, small, nu, nv = 1.0, 0.48, 192, 72
    dist = 4.2
    f = 0.42 * h * SS * dist / (big + small)
    light = _unit((-0.5, 0.8, -1))
    half = _unit((light[0], light[1], light[2] - 1))
    drips = [(rng.uniform(0, TAU), rng.uniform(0.04, 0.09), rng.uniform(0.25, 0.5)) for _ in range(14)]

    def edge(a):
        """Lowest sin(tube angle) the icing reaches at ring angle a: a wavy line with drips hanging off it."""
        e = 0.3 + 0.06 * math.sin(5 * a + 1) + 0.04 * math.sin(11 * a)
        for at, width, depth in drips:
            gap = math.remainder(a - at, TAU) / width
            e -= depth * math.exp(-gap * gap)
        return e

    def point(a, b, lift=0.0):
        r = big + (small + lift) * math.cos(b)
        return r * math.cos(a), r * math.sin(a), (small + lift) * math.sin(b)

    def cut(poly, side):
        """The part of a polygon of (a, b, value) corners where side(value) >= 0, split along the line."""
        out = []
        for p, q in zip(poly, poly[1:] + poly[:1]):
            sp, sq = side(p[2]), side(q[2])
            if sp >= 0:
                out.append(p)
            if (sp >= 0) != (sq >= 0):
                out.append(tuple(x + (y - x) * sp / (sp - sq) for x, y in zip(p, q)))
        return out

    # Icing on top, a pale baked ring under its edge, golden dough below. Quads that cross a border
    # are split along it, so the borders are smooth curves and not steps.
    layers = ((0, 9, (255, 150, 200)), (-0.12, 0, (250, 215, 150)), (-9, -0.12, (205, 125, 50)))
    verts = [point(TAU * i / nu, TAU * j / nv) for i in range(nu) for j in range(nv)]
    quads = []
    for i in range(nu):
        for j in range(nv):
            a, b = TAU * (i + 0.5) / nu, TAU * (j + 0.5) / nv  # quad center and its normal
            nrm = (math.cos(a) * math.cos(b), math.sin(a) * math.cos(b), math.sin(b))
            ctr = point(a, b)
            corners = [(TAU * ii / nu, TAU * jj / nv) for ii, jj in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))]
            poly = [(ca, cb, math.sin(cb) - edge(ca)) for ca, cb in corners]
            for lo, hi, col in layers:
                if all(lo <= v < hi for _a, _b, v in poly):
                    idx = [i * nv + j, (i + 1) % nu * nv + j, (i + 1) % nu * nv + (j + 1) % nv, i * nv + (j + 1) % nv]
                    quads.append((idx, ctr, nrm, col, 0.0))
                    break
                piece = cut(cut(poly, lambda v: v - lo), lambda v: hi - v)
                if len(piece) > 2:
                    quads.append((list(range(len(verts), len(verts) + len(piece))), ctr, nrm, col, 0.0))
                    verts += [point(pa, pb) for pa, pb, _v in piece]
    inks = [(255, 255, 255), (90, 130, 255), (255, 230, 40), (60, 200, 100), (175, 100, 245), (255, 255, 255)]  # bright, so no dot goes dark
    sprinkles = 0
    while sprinkles < 75:  # short bars lying on the icing, a little above it
        a, b = rng.uniform(0, TAU), rng.uniform(0, math.pi)
        if math.sin(b) < edge(a) + 0.15:
            continue
        nrm = (math.cos(a) * math.cos(b), math.sin(a) * math.cos(b), math.sin(b))
        ta, tb = (-math.sin(a), math.cos(a), 0.0), (-math.cos(a) * math.sin(b), -math.sin(a) * math.sin(b), math.cos(b))
        turn = rng.uniform(0, TAU)
        along = tuple(math.cos(turn) * p + math.sin(turn) * q for p, q in zip(ta, tb))
        across = tuple(-math.sin(turn) * p + math.cos(turn) * q for p, q in zip(ta, tb))
        c = point(a, b, 0.02)
        corners = [tuple(c[k] + u * 0.095 * along[k] + v * 0.034 * across[k] for k in range(3))
                   for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        idx = list(range(len(verts), len(verts) + 4))
        verts += corners
        quads.append((idx, c, nrm, rng.choice(inks), 0.06))  # drawn just after the icing under it
        sprinkles += 1
    out = []
    for k in range(n):
        t = k / n  # every motion below turns a whole number of times per loop, so it loops
        # Spin once around the donut's own axis, then tilt it toward the camera: seen from above and
        # rocking gently, never so far side-on that the hole closes.
        spin = _rot(0, 0, TAU * t)
        view = _rot(math.pi + 0.8 + 0.15 * math.sin(TAU * t), 0.25 * math.sin(TAU * t + 1.2), 0.2 * math.cos(TAU * t))
        m = tuple(zip(*[_apply(view, col) for col in zip(*spin)]))
        pts = []
        for p in verts:
            x, y, z = _apply(m, p)
            d = f / (z + dist)
            pts.append((w * SS / 2 + x * d, 0.44 * h * SS - y * d))  # a little above the middle: the near side looks bigger
        faces = []
        for idx, ctr, nrm, col, bias in quads:
            c, nn = _apply(m, ctr), _apply(m, nrm)
            facing = (c[0] * nn[0] + c[1] * nn[1] + (c[2] + dist) * nn[2]) / math.dist(c, (0, 0, -dist))
            if facing >= (-0.3 if bias else 0):  # faces away from the camera; sprinkles also hide edge-on
                continue
            dif = nn[0] * light[0] + nn[1] * light[1] + nn[2] * light[2]
            spec = max(0.0, nn[0] * half[0] + nn[1] * half[1] + nn[2] * half[2]) ** 30
            s = 0.4 + 0.6 * (0.5 + 0.5 * dif) ** 2  # never too dark, so the back still shows as glyphs
            faces.append((c[2] - bias, [pts[q] for q in idx],
                          tuple(min(255, round(v * s + 255 * 0.5 * spec)) for v in col)))
        im = Image.new("RGB", (w * SS, h * SS))
        draw = ImageDraw.Draw(im)
        for _z, poly, col in sorted(faces, key=lambda fc: -fc[0]):
            draw.polygon(poly, fill=col, outline=col)
        out.append(_shrink(im, w, h))
    return out
