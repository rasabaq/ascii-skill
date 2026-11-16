"""Looping animations drawn in code, so animate.py can make ASCII motion with no footage.

    uv run scripts/animate.py --scene fire -o fire.gif

    from scenes import SCENES, DEFAULTS, frames
    imgs = SCENES["donut"](320, 240, 80, 0)      # n PIL images
    pairs = frames("donut")                      # [(RGB image, ms)] at the scene's own size and fps

A scene is `scene(w, h, n, seed) -> list of n images`. It draws one full loop: frame i is time t = i / n,
so frame n would be frame 0 again and the last frame flows into the first.
"""
import colorsys
import math
import random

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from ascii import font

SCENES = {}  # name -> scene function
DEFAULTS = {}  # name -> (width, height, frames, fps)
TAU = 2 * math.pi
SS = 2  # vector scenes draw at 2x and shrink, for smooth edges


def scene(w, h, n, fps):
    def add(fn):
        SCENES[fn.__name__], DEFAULTS[fn.__name__] = fn, (w, h, n, fps)
        return fn
    return add


def frames(name, seed=0, fps=None):
    """(RGB image, ms) pairs for animate.py. Another fps keeps the loop length and changes the frame count."""
    w, h, n, rate = DEFAULTS[name]
    fps = fps or rate
    n = max(2, round(n * fps / rate))
    return [(im.convert("RGB"), 1000 / fps) for im in SCENES[name](w, h, n, seed)]


def _lut(stops):
    """256 colors through (position 0-1, rgb) stops."""
    out = []
    for i in range(256):
        v = i / 255
        for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
            if v <= p1:
                k = (v - p0) / ((p1 - p0) or 1)
                out.append(tuple(round(a + (b - a) * k) for a, b in zip(c0, c1)))
                break
    return out


def _colorize(gray, lut):
    return Image.merge("RGB", [gray.point([c[k] for c in lut]) for k in range(3)])


def _shrink(im, w, h):
    return im.resize((w, h), Image.Resampling.LANCZOS)


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
def fire(w, h, n, seed):
    """Cellular fire: random embers in the bottom row, and every step each cell becomes the average of
    the cells under it, minus a little cooling, so heat rises and fades into flame tongues. Cooling
    grows with height and toward the sides, so the fire tapers to a point, and it sits on a glowing
    bed of embers. The embers repeat every n steps and a cell only remembers one grid height of
    history, so after a warm-up the flames repeat every n frames: a seamless loop."""
    gw, gh = max(8, w // 3), max(8, h // 3) + 2  # the 2 bottom rows (raw embers) are cut off
    rng = random.Random(seed)
    edge, side = max(1, gw // 4), gw // 10  # embers fade out toward the sides, so the fire has a shape
    reach = [max(0, min(1, (x + 1 - side) / edge, (gw - x - side) / edge)) for x in range(gw)]
    embers, x = [[0] * gw for _ in range(n)], 0
    while x < gw:  # clumps of 2-4 columns that stay hot or dark for a few frames make flame tongues
        width, t = rng.randint(2, 4), 0
        while t < n:
            hold, hot = rng.randint(3, 9), rng.random() < 0.6
            for tt in range(t, min(n, t + hold)):
                for xx in range(x, min(gw, x + width)):
                    embers[tt][xx] = round(255 * reach[xx] * rng.uniform(0.8, 1) * (1 if hot else 0.4))
            t += hold
        x += width
    # Cooling map: smooth noise that wraps in x and in time. A cell at row y in step s uses map row
    # (y + s) % n, so a cold patch rises with the heat and carves the flames into tongues.
    noise = Image.frombytes("L", (gw, n), rng.randbytes(gw * n))
    tiled = Image.new("L", (gw * 3, n * 3))
    for i in range(9):
        tiled.paste(noise, (i % 3 * gw, i // 3 * n))
    noise = ImageOps.autocontrast(tiled.filter(ImageFilter.GaussianBlur(1.5)).crop((gw, n, 2 * gw, 2 * n)))
    mean = 255 * 1.4 / gh  # flames reach about 3/4 of the way up
    cool = [round(mean * 3 * (v / 255) ** 2) for v in noise.tobytes()]
    taper = [round(mean * (0.5 * (1 - y / gh) ** 2 + 2 * ((x - gw / 2) / gw) ** 2 * (1 - y / gh)))
             for y in range(gh) for x in range(gw)]  # more cooling up high and off to the sides
    lut = _lut([(0, (0, 0, 0)), (0.1, (90, 0, 0)), (0.3, (220, 45, 0)), (0.5, (255, 125, 0)),
                (0.7, (255, 205, 50)), (0.9, (255, 250, 200)), (1, (255, 255, 255))])
    # The ember bed: a low mound across the bottom, glowing in two blotchy patterns that cross-fade
    # once per loop. It is mixed in as heat, so it shares the flame colors and meets them smoothly.
    bh = max(4, round(0.13 * h))
    mound = Image.new("L", (w, h))
    ImageDraw.Draw(mound).ellipse((0.08 * w, h - bh, 0.92 * w, h + bh), fill=255)
    mound = mound.filter(ImageFilter.GaussianBlur(max(1, h / 60)))
    bed = []
    for _ in range(2):
        spots = Image.frombytes("L", (max(4, w // 10), max(4, h // 10)), rng.randbytes(max(4, w // 10) * max(4, h // 10)))
        spots = ImageOps.autocontrast(spots.resize((w, h), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(1)))
        bed.append(spots.point(lambda v: 30 + 170 * (v / 255) ** 1.5))  # dark red cracks, orange coals
    heat = [0] * (gw * gh)
    out, warm = [], (gh // n + 1) * n  # at least one grid height, ending on a multiple of n
    last = (gh - 1) * gw
    for step in range(warm + n):
        new = heat[:]
        new[last:] = embers[step % n]
        for y in range(gh - 1):
            row, b1, b2, c = y * gw, (y + 1) * gw, min(y + 2, gh - 1) * gw, (y + step) % n * gw
            for x in range(gw):
                v = (heat[b1 + x - 1 if x else b1] + heat[b1 + x] + heat[b1 + x + 1 if x < gw - 1 else b1 + x]
                     + heat[b2 + x]) // 4 - cool[c + x] - taper[row + x]
                new[row + x] = v if v > 0 else 0
        heat = new
        if step >= warm:
            # A cell shows no brighter than its brightest neighbor below, plus a little: hot patches cut
            # off from the flames below fade out instead of floating away as blobs.
            show = heat[:]
            for y in range(gh - 2, -1, -1):
                row, b = y * gw, (y + 1) * gw
                for x in range(gw):
                    below = max(show[b + max(0, x - 1):b + x + 2])
                    if show[row + x] > below + 4:
                        show[row + x] = below + 4
            g = Image.frombytes("L", (gw, gh - 2), bytes(show[:gw * (gh - 2)]))
            glow = Image.blend(bed[0], bed[1], 0.5 - 0.5 * math.cos(TAU * (step - warm) / n))
            out.append(_colorize(Image.composite(glow, g.resize((w, h), Image.Resampling.BICUBIC), mound), lut))
    return out


@scene(320, 240, 80, 25)
def donut(w, h, n, seed):
    """A frosted donut with sprinkles, spinning and rocking in light. Small flat-shaded quads drawn back
    to front (painter's algorithm), with diffuse and specular light, so the brightness alone shows its
    shape. Pink icing with drips sits on top, so the golden dough shows on the sides and underneath."""
    rng = random.Random(seed)
    big, small, nu, nv = 1.0, 0.48, 192, 72
    dist = 4.2
    f = 0.45 * h * SS * dist / (big + small)
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
    inks = [(255, 255, 255), (60, 80, 230), (255, 230, 40), (40, 170, 80), (130, 50, 190), (255, 255, 255)]
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
        t = k / n
        # Spin once around the donut's own axis, then tilt it toward the camera: seen from above,
        # rocking between three-quarter and nearly side-on.
        spin = _rot(0, 0, TAU * t)
        view = _rot(math.pi + 1.15 + 0.3 * math.sin(TAU * t), 0.35 * math.sin(TAU * t + 1.2), 0.25 * math.cos(TAU * t))
        m = tuple(zip(*[_apply(view, col) for col in zip(*spin)]))
        pts = []
        for p in verts:
            x, y, z = _apply(m, p)
            d = f / (z + dist)
            pts.append((w * SS / 2 + x * d, h * SS / 2 - y * d))
        faces = []
        for idx, ctr, nrm, col, bias in quads:
            c, nn = _apply(m, ctr), _apply(m, nrm)
            facing = (c[0] * nn[0] + c[1] * nn[1] + (c[2] + dist) * nn[2]) / math.dist(c, (0, 0, -dist))
            if facing >= (-0.3 if bias else 0):  # faces away from the camera; sprinkles also hide edge-on
                continue
            dif = nn[0] * light[0] + nn[1] * light[1] + nn[2] * light[2]
            spec = max(0.0, nn[0] * half[0] + nn[1] * half[1] + nn[2] * half[2]) ** 30
            s = 0.4 + 0.6 * (0.5 + 0.5 * dif) ** 2  # never too dark, so braille dots still show the back
            faces.append((c[2] - bias, [pts[q] for q in idx],
                          tuple(min(255, round(v * s + 255 * 0.5 * spec)) for v in col)))
        im = Image.new("RGB", (w * SS, h * SS))
        draw = ImageDraw.Draw(im)
        for _z, poly, col in sorted(faces, key=lambda fc: -fc[0]):
            draw.polygon(poly, fill=col, outline=col)
        out.append(_shrink(im, w, h))
    return out


@scene(320, 240, 80, 25)
def cube(w, h, n, seed):
    """A tumbling cube with lit faces and bright edges. It is convex, so hiding the back faces is enough."""
    dist = 5.0
    f = 0.36 * h * SS * dist / math.sqrt(3)
    light = _unit((-0.4, 0.7, -1))
    faces = []
    for ax in range(3):
        for s in (-1, 1):
            o = [(ax + 1) % 3, (ax + 2) % 3]
            corners = []
            for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                p = [0, 0, 0]
                p[ax], p[o[0]], p[o[1]] = s, u, v
                corners.append(tuple(p))
            nrm = [0, 0, 0]
            nrm[ax] = s
            faces.append((corners, tuple(nrm), [(255, 90, 70), (80, 200, 110), (70, 140, 255)][ax]))
    out = []
    for k in range(n):
        t = k / n
        m = _rot(TAU * t + 0.6, TAU * t, 0.3)
        im = Image.new("RGB", (w * SS, h * SS))
        draw = ImageDraw.Draw(im)
        for corners, nrm, col in faces:
            nn = _apply(m, nrm)
            c = _apply(m, nrm)  # a face center sits at its normal on a unit cube
            if c[0] * nn[0] + c[1] * nn[1] + (c[2] + dist) * nn[2] >= 0:
                continue
            poly = []
            for p in corners:
                x, y, z = _apply(m, p)
                d = f / (z + dist)
                poly.append((w * SS / 2 + x * d, h * SS / 2 - y * d))
            s = 0.45 + 0.55 * max(0.0, nn[0] * light[0] + nn[1] * light[1] + nn[2] * light[2])
            draw.polygon(poly, fill=tuple(round(v * s) for v in col))
            draw.line(poly + poly[:1], fill=(255, 255, 255), width=3 * SS, joint="curve")
        out.append(_shrink(im, w, h))
    return out


@scene(320, 240, 64, 20)
def waves(w, h, n, seed):
    """Ocean swell under the moon: layers of sine waves, far ones small and slow, near ones big.
    Each wave body fades from a lit top to dark, with a foam line on its crest and a moon glint.
    Every layer shifts by one whole wave per loop, so it loops."""
    rng = random.Random(seed)
    W, H = w * SS, h * SS
    horizon, layers = 0.4 * H, 7
    mx, my, mr = 0.72 * W, 0.17 * H, 0.075 * H
    sky = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(sky)
    for _ in range(40):
        x, y, r = rng.uniform(0, W), rng.uniform(0, horizon * 0.9), rng.choice((1, 1, 2)) * SS
        if math.hypot(x - mx, y - my) > 2 * mr:
            draw.ellipse((x - r, y - r, x + r, y + r), fill=(150, 160, 190))
    draw.ellipse((mx - mr, my - mr, mx + mr, my + mr), fill=(255, 250, 225))
    bodies, phases = [], [rng.uniform(0, TAU) for _ in range(2 * layers)]
    for li in range(layers):
        d = li / (layers - 1)  # 0 far, 1 near
        base = horizon + (H - horizon) * (0.03 + 0.85 * d ** 1.3)
        amp, deep = H * (0.006 + 0.045 * d), H * (0.04 + 0.12 * d)
        top = tuple(round(c * (0.45 + 0.4 * d)) for c in (60, 140, 200))
        ramp = _lut([(0, top), (1, (0, 0, 0))])
        grad = Image.new("L", (1, H))  # lit at the crest, dark one `deep` below it
        grad.putdata([max(0, min(255, round((y - base + amp) / deep * 255))) for y in range(H)])
        bodies.append((base, amp, w * SS * (0.12 + 0.5 * d), d, _colorize(grad.resize((W, H)), ramp)))
    out = []
    for k in range(n):
        t = k / n
        im = sky.copy()
        draw = ImageDraw.Draw(im)
        for li, (base, amp, lam, d, body) in enumerate(bodies):
            crest = []
            for x in range(-4 * SS, W + 8 * SS, 3 * SS):
                y = base - amp * math.sin(TAU * (x / lam - t) + phases[li]) \
                    - 0.35 * amp * math.sin(TAU * (2.3 * x / lam + t) + phases[layers + li])
                crest.append((x, y))
            mask = Image.new("L", (W, H))
            ImageDraw.Draw(mask).polygon(crest + [(W + 8 * SS, H), (-4 * SS, H)], fill=255)
            im.paste(body, mask=mask)
            foam = tuple(round(c * (0.55 + 0.45 * d)) for c in (200, 230, 255))
            width = max(1, round((1 + 2.5 * d) * SS))
            draw.line(crest, fill=foam, width=width, joint="curve")
            glint = [p for p in crest if abs(p[0] - mx) < (0.3 + 0.7 * d) * 2.2 * mr]
            if len(glint) > 1:  # the moon's path on the water
                draw.line(glint, fill=(255, 245, 210), width=width + SS, joint="curve")
        out.append(_shrink(im, w, h))
    return out


@scene(320, 240, 80, 25)
def stars(w, h, n, seed):
    """Flying through a starfield. Each star moves from far to near once per loop and then starts far
    again, so the loop has no seam; streaks grow as stars get close."""
    rng = random.Random(seed)
    f = 0.5 * h * SS
    span = (w / h, 1.0)
    pts = [(rng.uniform(-1, 1) * span[0] * 1.1, rng.uniform(-1, 1) * span[1] * 1.1, rng.random(),
            rng.choice([(255, 255, 255), (190, 215, 255), (255, 235, 190)])) for _ in range(420)]
    cx, cy = w * SS / 2, h * SS / 2
    out = []
    for k in range(n):
        t = k / n
        im = Image.new("RGB", (w * SS, h * SS))
        draw = ImageDraw.Draw(im)
        for x, y, z0, col in pts:
            z = (z0 - t) % 1.0
            if z < 0.04:
                continue
            near = 1 - z
            tail = z + 0.03 + 0.1 * near
            a = (cx + x * f / z, cy + y * f / z)
            b = (cx + x * f / tail, cy + y * f / tail)
            lum = 0.25 + 0.75 * near ** 2
            ink = tuple(round(v * lum) for v in col)
            r = SS * (0.8 + 2.6 * near ** 3)
            draw.line([b, a], fill=ink, width=max(1, round(r * 1.6)))
            draw.ellipse((a[0] - r, a[1] - r, a[0] + r, a[1] + r), fill=ink)
        out.append(_shrink(im, w, h))
    return out


def _gait(phase, unit):
    """Joint points of one side of a running stick figure, relative to the hip (y points down).
    Angles are from straight down, positive toward the front (right)."""
    s, c = math.sin(phase), math.cos(phase)
    thigh = math.radians(10 + 42 * s)
    knee = math.radians(12 + 95 * max(0.0, c) ** 1.5 + 18 * max(0.0, -c))  # tucks while the leg swings forward
    shin = thigh - knee
    kx, ky = 1.05 * unit * math.sin(thigh), 1.05 * unit * math.cos(thigh)
    ax, ay = kx + unit * math.sin(shin), ky + unit * math.cos(shin)
    foot = shin + math.radians(95)
    return [(0, 0), (kx, ky), (ax, ay), (ax + 0.35 * unit * math.sin(foot), ay + 0.35 * unit * math.cos(foot))]


def _arm(phase, unit):
    s = math.sin(phase)
    upper = math.radians(-8 - 45 * s)  # swings against the leg on the same side
    fore = upper + math.radians(95 + 15 * s)
    ex, ey = 0.8 * unit * math.sin(upper), 0.8 * unit * math.cos(upper)
    return [(0, 0), (ex, ey), (ex + 0.75 * unit * math.sin(fore), ey + 0.75 * unit * math.cos(fore))]


@scene(320, 240, 80, 25)
def walker(w, h, n, seed):
    """A stick figure running in place: sine-driven hip, knee and arm angles, the body set so the lowest
    foot touches the ground (that gives the bounce), and ground marks that slide back at foot speed."""
    strides = 4
    u = h * SS * 0.16  # shin length; the figure is about 4.5 units tall
    ground = h * SS * 0.86
    lean = math.radians(12)
    lw = max(2, round(h * SS / 28))
    # Ground speed: how far a planted foot slides back per stride, measured from the gait itself.
    xs = [_gait(TAU * i / 64, u)[2][0] for i in range(64)]
    slide = 2 * (max(xs) - min(xs))
    gap = w * SS / 5
    shift = max(1, round(slide * strides / gap)) * gap  # whole mark spacings per loop, so the loop is seamless
    out = []
    for k in range(n):
        t = k / n
        ph = TAU * strides * t
        legs = [_gait(ph + math.pi, u), _gait(ph, u)]  # far leg first, near leg drawn on top
        hip_y = ground - max(max(y for _x, y in leg) for leg in legs) - lw / 2
        hip = (w * SS * 0.5, hip_y)
        bob = 0.04 * u * math.cos(2 * ph)
        neck = (hip[0] + 1.6 * u * math.sin(lean), hip_y - 1.6 * u * math.cos(lean) + bob)
        shoulder = (neck[0] - 0.05 * u, neck[1] + 0.15 * u)
        arms = [_arm(ph, u), _arm(ph + math.pi, u)]
        im = Image.new("RGB", (w * SS, h * SS))
        draw = ImageDraw.Draw(im)
        draw.line([(0, ground), (w * SS, ground)], fill=(150, 145, 175), width=2 * SS)
        off = (shift * t) % gap
        for g in range(7):
            x0 = g * gap - off
            draw.line([(x0, ground + lw), (x0 + gap * 0.45, ground + lw)], fill=(120, 115, 135), width=lw // 2)
            draw.line([(x0 + gap * 0.5, ground + 3.2 * lw), (x0 + gap * 0.7, ground + 3.2 * lw)],
                      fill=(80, 76, 95), width=lw // 2)

        def limb(points, origin, col):
            pts = [(origin[0] + x, origin[1] + y) for x, y in points]
            draw.line(pts, fill=col, width=lw, joint="curve")
            for x, y in (pts[0], pts[-1]):
                draw.ellipse((x - lw / 2, y - lw / 2, x + lw / 2, y + lw / 2), fill=col)

        far, near = (120, 130, 160), (255, 255, 255)
        limb(arms[0], shoulder, far)
        limb(legs[0], hip, far)
        limb([(0, 0), (neck[0] - hip[0], neck[1] - hip[1])], hip, near)
        limb(legs[1], hip, near)
        limb(arms[1], shoulder, near)
        hr = 0.36 * u
        hx, hy = neck[0] + 0.2 * u, neck[1] - hr - 0.1 * u
        draw.ellipse((hx - hr, hy - hr, hx + hr, hy + hr), fill=near)
        out.append(_shrink(im, w, h))
    return out


@scene(320, 240, 60, 25)
def rain(w, h, n, seed):
    """Rain at night: slanted streaks fall a whole number of times per loop and splash where they land."""
    rng = random.Random(seed)
    W, H = w * SS, h * SS
    ground, wind = 0.84 * H, -0.18
    drops = []
    for _ in range(80):
        d = rng.random() ** 0.6  # depth: 0 far, 1 near
        drops.append((rng.uniform(0, 1.15) * W, rng.random(), 1 + round(d), d))
    out = []
    for k in range(n):
        t = k / n
        im = Image.new("RGB", (W, H))
        draw = ImageDraw.Draw(im)
        draw.line([(0, ground), (W, ground)], fill=(70, 80, 100), width=SS)
        for x0, p0, speed, d in drops:
            length = (14 + 30 * d) * SS
            land = ground + (d - 0.4) * 0.5 * (H - ground)  # near drops land lower
            pos = (p0 + speed * t) % 1.0
            bottom = pos * (land + length)  # fully above the frame at pos 0, on the ground at pos 1
            ink = tuple(round(c * (0.35 + 0.65 * d)) for c in (180, 210, 255))
            draw.line([(x0 + wind * (bottom - length), bottom - length), (x0 + wind * bottom, bottom)],
                      fill=ink, width=round((1.2 + 1.3 * d) * SS))
            age = pos * n / speed  # frames since this drop last landed
            if age < 5:
                sx, r, fade = x0 + wind * (land + length), (5 + 12 * d) * SS * (0.4 + age / 5), 1 - age / 5
                draw.ellipse((sx - r, land - r * 0.3, sx + r, land + r * 0.3),
                             outline=tuple(round(c * fade) for c in ink), width=SS)
        out.append(_shrink(im, w, h))
    return out


@scene(320, 240, 50, 25)
def bounce(w, h, n, seed):
    """A shaded ball bouncing in place in a room: parabolic height, squash at the floor, stretch at
    speed, and a soft shadow on a tiled floor that gets darker and sharper as the ball comes down."""
    W, H = w * SS, h * SS
    bounces = 2
    r0 = 0.2 * H
    horizon, ground = 0.58 * H, 0.9 * H
    jump = ground - 2 * r0 - 0.06 * H
    cx = W / 2
    # The room: a wall that darkens upward, a floor that lightens toward us, and floor tiles in
    # perspective that fade out before the horizon, where they would get too fine to read.
    grad = Image.new("L", (1, H))
    grad.putdata([round(255 * (y / horizon if y < horizon else (y - horizon) / (H - horizon))) for y in range(H)])
    grad = grad.resize((W, H))
    floor = Image.new("L", (W, H))
    ImageDraw.Draw(floor).rectangle((0, horizon, W, H), fill=255)
    room = Image.composite(_colorize(grad, _lut([(0, (26, 24, 42)), (1, (58, 53, 82))])),
                           _colorize(grad, _lut([(0, (2, 2, 6)), (1, (34, 30, 52))])), floor)
    tiles = Image.new("L", (W, H))
    draw = ImageDraw.Draw(tiles)
    for i in range(-8, 9):
        draw.line([(cx, horizon), (cx + (i + 0.5) * 0.36 * W, H)], fill=255, width=2 * SS)
    for i in range(1, 12):
        y = horizon + (H - horizon) / (1 + 0.55 * i)
        draw.line([(0, y), (W, y)], fill=255, width=2 * SS)
    draw.rectangle((0, 0, W, horizon), fill=0)  # no line ends poking up into the wall
    tiles = Image.composite(tiles, Image.new("L", (W, H)), grad.point(lambda v: round(170 * (v / 255) ** 1.5)))
    room = Image.composite(Image.new("RGB", (W, H), (165, 155, 215)), room, tiles)
    out = []
    for k in range(n):
        t = k / n
        u = (bounces * t) % 1.0
        height = 4 * u * (1 - u)
        contact = max(0.0, 1 - min(u, 1 - u) / 0.06)  # 1 at the floor, 0 a little above it
        sy = 1 - 0.22 * contact + 0.1 * abs(1 - 2 * u) * (1 - contact)
        sx = 1 / sy
        bottom = ground - height * jump
        rx, ry = r0 * sx, r0 * sy
        cy = bottom - ry
        im = room.copy()
        shadow = Image.new("L", (W, H))
        sw = r0 * (0.85 + 0.5 * height)
        ImageDraw.Draw(shadow).ellipse((cx - sw, ground - 0.2 * sw, cx + sw, ground + 0.2 * sw),
                                       fill=round(235 * (1 - 0.55 * height)))
        im.paste((0, 0, 0), mask=shadow.filter(ImageFilter.GaussianBlur(SS * (1.5 + 10 * height))))
        draw = ImageDraw.Draw(im)
        for i in range(40):  # concentric ellipses toward the highlight make a lit sphere
            q = i / 39
            ex, ey = cx - 0.35 * rx * q, cy - 0.4 * ry * q
            a, b = rx * (1 - 0.85 * q), ry * (1 - 0.85 * q)
            lum = 0.45 + 0.55 * q
            col = tuple(min(255, round(c * lum + 140 * q ** 6)) for c in (255, 95, 60))
            draw.ellipse((ex - a, ey - b, ex + a, ey + b), fill=col)
        out.append(_shrink(im, w, h))
    return out


@scene(320, 240, 64, 25)
def text(w, h, n, seed, word="ASCII"):
    """A word whose letters ride a sine wave, each in a hue that cycles once per loop."""
    size = round(SS * min(0.36 * h, 0.85 * w / (0.75 * len(word))))  # fits the frame with room to spare
    ft = font(size)
    widths = [ft.getlength(c) for c in word]
    gap = 0.12 * size
    total = sum(widths) + gap * (len(word) - 1)
    out = []
    for k in range(n):
        t = k / n
        im = Image.new("RGB", (w * SS, h * SS))
        draw = ImageDraw.Draw(im)
        x = (w * SS - total) / 2
        for i, (ch, cw) in enumerate(zip(word, widths)):
            y = h * SS / 2 - 0.16 * h * SS * math.sin(TAU * t - 0.9 * i)
            col = tuple(round(v * 255) for v in colorsys.hsv_to_rgb((t + i / len(word)) % 1.0, 0.75, 1.0))
            draw.text((x + cw / 2, y), ch, font=ft, fill=col, anchor="mm", stroke_width=round(size / 20), stroke_fill=col)
            x += cw + gap
        out.append(_shrink(im, w, h))
    return out
