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

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

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
    the cells under it, minus a little cooling, so heat rises and fades into flame tongues.
    The embers repeat every n steps and a cell only remembers one grid height of history, so after a
    warm-up the flames repeat every n frames: a seamless loop."""
    gw, gh = max(8, w // 3), max(8, h // 3) + 2  # the 2 bottom rows (raw embers) are cut off
    rng = random.Random(seed)
    edge = max(1, gw // 4)  # embers fade out at the sides, so the fire has a shape
    reach = [min(1, (x + 1) / edge, (gw - x) / edge) for x in range(gw)]
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
    lut = _lut([(0, (0, 0, 0)), (0.1, (90, 0, 0)), (0.3, (220, 45, 0)), (0.5, (255, 125, 0)),
                (0.7, (255, 205, 50)), (0.9, (255, 250, 200)), (1, (255, 255, 255))])
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
                     + heat[b2 + x]) // 4 - cool[c + x]
                new[row + x] = v if v > 0 else 0
        heat = new
        if step >= warm:
            g = Image.frombytes("L", (gw, gh - 2), bytes(heat[:gw * (gh - 2)]))
            out.append(_colorize(g.resize((w, h), Image.Resampling.BICUBIC), lut))
    return out


@scene(320, 240, 80, 25)
def donut(w, h, n, seed):
    """A frosted torus tumbling in light. Small flat-shaded quads drawn back to front (painter's
    algorithm), with diffuse and specular light, so the brightness alone shows its shape."""
    big, small, nu, nv = 1.0, 0.48, 80, 40
    dist = 4.2
    f = 0.4 * h * SS * dist / (big + small)
    light = _unit((-0.5, 0.8, -1))
    half = _unit((light[0], light[1], light[2] - 1))
    verts, quads = [], []
    for i in range(nu):
        for j in range(nv):
            a, b = TAU * i / nu, TAU * j / nv
            verts.append(((big + small * math.cos(b)) * math.cos(a), (big + small * math.cos(b)) * math.sin(a),
                          small * math.sin(b)))
            a, b = TAU * (i + 0.5) / nu, TAU * (j + 0.5) / nv  # quad center and its normal
            nrm = (math.cos(a) * math.cos(b), math.sin(a) * math.cos(b), math.sin(b))
            icing = nrm[2] > 0.1 * math.sin(7 * a) - 0.15  # frosting on the top side, with a wavy edge
            idx = [i * nv + j, ((i + 1) % nu) * nv + j, ((i + 1) % nu) * nv + (j + 1) % nv, i * nv + (j + 1) % nv]
            ctr = ((big + small * math.cos(b)) * math.cos(a), (big + small * math.cos(b)) * math.sin(a), small * nrm[2])
            quads.append((idx, ctr, nrm, (250, 125, 180) if icing else (220, 150, 75)))
    out = []
    for k in range(n):
        t = k / n
        m = _rot(TAU * t + 0.9, 0.35, TAU * t)
        pts = []
        for p in verts:
            x, y, z = _apply(m, p)
            d = f / (z + dist)
            pts.append((w * SS / 2 + x * d, h * SS / 2 - y * d))
        faces = []
        for idx, ctr, nrm, col in quads:
            c, nn = _apply(m, ctr), _apply(m, nrm)
            if c[0] * nn[0] + c[1] * nn[1] + (c[2] + dist) * nn[2] >= 0:  # faces away from the camera
                continue
            dif = nn[0] * light[0] + nn[1] * light[1] + nn[2] * light[2]
            spec = max(0.0, nn[0] * half[0] + nn[1] * half[1] + nn[2] * half[2]) ** 30
            s = 0.4 + 0.6 * (0.5 + 0.5 * dif) ** 2  # never too dark, so braille dots still show the back
            faces.append((c[2], [pts[q] for q in idx], tuple(min(255, round(v * s + 255 * 0.6 * spec)) for v in col)))
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
    """A shaded ball bouncing in place: parabolic height, squash at the floor, stretch at speed."""
    bounces = 2
    r0 = 0.15 * h * SS
    ground = 0.86 * h * SS
    jump = 0.58 * h * SS
    cx = w * SS / 2
    out = []
    for k in range(n):
        t = k / n
        u = (bounces * t) % 1.0
        height = 4 * u * (1 - u)
        contact = max(0.0, 1 - min(u, 1 - u) / 0.06)  # 1 at the floor, 0 a little above it
        sy = 1 - 0.22 * contact + 0.15 * abs(1 - 2 * u) * (1 - contact)
        sx = 1 / sy
        bottom = ground - height * jump
        rx, ry = r0 * sx, r0 * sy
        cy = bottom - ry
        im = Image.new("RGB", (w * SS, h * SS))
        draw = ImageDraw.Draw(im)
        draw.line([(0, ground), (w * SS, ground)], fill=(150, 140, 175), width=2 * SS)
        sw = r0 * (1.3 - 0.6 * height)
        shade = round(30 + 40 * (1 - height))
        draw.ellipse((cx - sw, ground - 0.18 * sw, cx + sw, ground + 0.18 * sw), fill=(shade, shade, shade + 6))
        for i in range(24):  # concentric ellipses toward the highlight make a lit sphere
            q = i / 23
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


def _city_layer(rng, W, H, u, P, top, width, body, win, pitch, lit, bright, flick=0.0, tallest=None):
    """One strip of buildings, P wide. Buildings never cross the strip's edges, so tiling it has no seam.
    Returns the strip (RGBA) and the lights that switch on and off: (shape, box, color, times per loop, phase, duty)."""
    strip = Image.new("RGBA", (P, H))
    draw = ImageDraw.Draw(strip)
    rim = tuple(min(255, round(c * 1.6 + 30)) for c in body) + (255,)
    dark = tuple(round(c * 1.5 + 4) for c in body) + (255,)
    warm = [(255, 214, 140), (255, 190, 100), (255, 236, 190), (200, 220, 255)]
    flips = []
    x = rng.uniform(0, 4 * u)
    while P - x > width[0] * u:
        bw = min(rng.uniform(*width) * u, P - x - u)
        tall = tallest is not None and x <= tallest * P < x + bw + 10 * u
        y = (0.3 if tall else rng.uniform(*top)) * H
        if tall:
            bw = max(bw, 34 * u)
        x0, x1 = round(x), round(x + bw)
        draw.rectangle((x0, y, x1, H), fill=body + (255,))
        roof = "spire" if tall else rng.choice(("flat", "step", "antenna", "tank", "flat"))
        cx = (x0 + x1) / 2
        if roof == "step" or roof == "spire":  # setbacks: narrower blocks on top
            for i, s in enumerate((0.7, 0.42)):
                hw, ty = bw * s / 2, y - (i + 1) * 9 * u
                draw.rectangle((cx - hw, ty, cx + hw, ty + 9 * u), fill=body + (255,))
                draw.rectangle((cx - hw, ty, cx + hw, ty + u), fill=rim)
            if roof == "spire":
                tip = y - 18 * u - 34 * u
                draw.polygon([(cx - 5 * u, y - 18 * u), (cx + 5 * u, y - 18 * u), (cx, tip)], fill=body + (255,))
                draw.line([(cx, tip), (cx, tip - 8 * u)], fill=rim, width=max(1, round(u)))
                r, ly = 2 * u, tip - 8 * u  # aviation light: a red glow that blinks 4 times a loop
                draw.ellipse((cx - r, ly - r, cx + r, ly + r), fill=(80, 12, 14, 255))
                flips.append(("ellipse", (cx - 2.4 * r, ly - 2.4 * r, cx + 2.4 * r, ly + 2.4 * r), (190, 28, 30), 4, 0, 0.3))
                flips.append(("ellipse", (cx - r, ly - r, cx + r, ly + r), (255, 50, 45), 4, 0, 0.3))
        elif roof == "antenna":
            ax = rng.uniform(x0 + 0.25 * bw, x1 - 0.25 * bw)
            ah = rng.uniform(12, 26) * u
            draw.line([(ax, y), (ax, y - ah)], fill=rim, width=max(1, round(u)))
            draw.line([(ax - 3 * u, y - 0.6 * ah), (ax + 3 * u, y - 0.6 * ah)], fill=rim, width=max(1, round(u)))
        elif roof == "tank" and bw > 14 * u:  # a water tank on legs with a cone lid
            tx = rng.uniform(x0 + 2 * u, x1 - 12 * u)
            draw.line([(tx + 2 * u, y), (tx + 2 * u, y - 5 * u)], fill=body + (255,), width=max(1, round(u)))
            draw.line([(tx + 8 * u, y), (tx + 8 * u, y - 5 * u)], fill=body + (255,), width=max(1, round(u)))
            draw.rectangle((tx, y - 13 * u, tx + 10 * u, y - 5 * u), fill=body + (255,))
            draw.polygon([(tx - u, y - 13 * u), (tx + 11 * u, y - 13 * u), (tx + 5 * u, y - 18 * u)], fill=rim)
        else:  # flat roof with a small stair house
            sx = rng.uniform(x0 + 2 * u, max(x0 + 2 * u, x1 - 10 * u))
            draw.rectangle((sx, y - 5 * u, sx + 8 * u, y), fill=body + (255,))
        draw.rectangle((x0, y, x1, y + u), fill=rim)  # a moonlit roof edge keeps the outline readable
        ww, wh = win[0] * u, win[1] * u
        px, py = pitch[0] * u, pitch[1] * u
        cols = max(1, int((bw - 2 * u - ww) // px) + 1)
        left = cx - ((cols - 1) * px + ww) / 2
        p = lit * rng.uniform(0.3, 1.7)  # some buildings are busy offices, some are asleep
        tint = rng.choice(warm[:3] if rng.random() < 0.8 else warm[3:])
        row = y + 4 * u
        while row + wh < H:
            for c in range(cols):
                box = (round(left + c * px), round(row), round(left + c * px + ww) - 1, round(row + wh) - 1)
                col = tuple(round(v * bright * rng.uniform(0.8, 1)) for v in tint)
                if rng.random() < flick:
                    draw.rectangle(box, fill=dark)
                    flips.append(("rectangle", box, col, rng.choice((1, 1, 2)), rng.random(), rng.uniform(0.35, 0.65)))
                else:
                    draw.rectangle(box, fill=col + (255,) if rng.random() < p else dark)
            row += py
        x += bw + rng.uniform(1, 9) * u
    return strip, flips


@scene(320, 240, 64, 20)
def city(w, h, n, seed):
    """A night skyline sliding past. Three building strips (far, middle, near) each move one strip width
    per loop, and the strips are 1/2, 1 and 1.5 screens wide, so the near ones move 3x as fast as the far
    ones and every layer is back where it started. Windows blink and the train crosses whole times per loop."""
    rng = random.Random(seed)
    W, H, u = w * SS, h * SS, h * SS / 240  # u: one pixel at 320x240
    grad = Image.new("L", (1, H))
    grad.putdata([min(255, round(255 * y / (0.8 * H))) for y in range(H)])
    sky = _colorize(grad.resize((W, H)), _lut([(0, (3, 5, 18)), (0.6, (16, 18, 46)), (1, (62, 40, 80))]))
    draw = ImageDraw.Draw(sky)
    mx, my, mr = 0.8 * W, 0.17 * H, 0.06 * H
    for _ in range(70):
        x, y = rng.uniform(0, W), rng.uniform(0, 0.5 * H)
        if math.hypot(x - mx, y - my) > 3 * mr:
            r, v = rng.choice((0.6, 0.6, 1.0)) * u, rng.randint(90, 200)
            draw.ellipse((x - r, y - r, x + r, y + r), fill=(v, v, min(255, v + 25)))
    for i in range(14):  # moon halo: rings from wide and dim to tight and bright
        q, r = i / 13, mr * (2.8 - 1.7 * i / 13)
        draw.ellipse((mx - r, my - r, mx + r, my + r), fill=tuple(round(a + (b - a) * q * q) for a, b in zip((8, 10, 30), (70, 70, 100))))
    draw.ellipse((mx - mr, my - mr, mx + mr, my + mr), fill=(250, 246, 222))
    for dx, dy, cr in ((-0.3, -0.2, 0.22), (0.25, 0.25, 0.16), (0.1, -0.35, 0.1)):
        draw.ellipse((mx + (dx - cr) * mr, my + (dy - cr) * mr, mx + (dx + cr) * mr, my + (dy + cr) * mr), fill=(222, 218, 198))
    layers = [  # strip width, layer, then: tops (share of H), widths, body, window size, pitch, lit, brightness, flicker
        (W // 2, _city_layer(rng, W, H, u, W // 2, (0.36, 0.6), (14, 30), (80, 90, 138), (2, 2), (4, 5), 0.25, 0.55)),
        (W, _city_layer(rng, W, H, u, W, (0.36, 0.58), (22, 44), (34, 38, 66), (3, 3), (6, 7), 0.3, 0.8, 0.02, 0.3)),
        (3 * W // 2, _city_layer(rng, W, H, u, 3 * W // 2, (0.44, 0.7), (40, 76), (7, 7, 12), (4, 5), (8, 9), 0.35, 1.0, 0.03)),
    ]
    deck, gap = 0.82 * H, W / 4  # elevated track: pillars every quarter screen, moving 2 screens per loop
    cars, cl, ch = 3, 0.3 * W, 17 * u
    train = cars * cl + (cars - 1) * 3 * u
    lit = [[rng.random() < 0.85 for _ in range(int((cl - 10 * u) // (10 * u)))] for _ in range(cars)]
    out = []
    for k in range(n):
        t = k / n
        im = sky.copy()
        draw = ImageDraw.Draw(im)
        for P, (strip, flips) in layers:
            s = round(P * t) % P
            for x in range(-s, W, P):
                im.paste(strip, (x, 0), strip)
                for shape, box, col, times, ph, duty in flips:
                    if (t * times + ph) % 1 < duty and x + box[2] >= 0 and x + box[0] < W:
                        getattr(draw, shape)((box[0] + x, box[1], box[2] + x, box[3]), fill=col)
        left = t * (W + train + 0.3 * W) - train - 0.15 * W  # once across per loop, against the scroll
        for c in range(cars):
            x0, top = left + c * (cl + 3 * u), deck - ch - 2 * u
            draw.rounded_rectangle((x0, top, x0 + cl, deck), radius=3 * u, fill=(104, 112, 134))
            draw.rectangle((x0 + 2 * u, top + u, x0 + cl - 2 * u, top + 2.5 * u), fill=(150, 158, 180))
            if c == cars - 1:  # sloped nose and headlight
                draw.polygon([(x0 + cl - 8 * u, top), (x0 + cl + 6 * u, deck), (x0 + cl - 8 * u, deck)], fill=(104, 112, 134))
                draw.ellipse((x0 + cl - u, deck - 7 * u, x0 + cl + 3 * u, deck - 3 * u), fill=(255, 255, 230))
            for i, on in enumerate(lit[c]):
                wx = x0 + 6 * u + i * 10 * u
                draw.rectangle((wx, top + 5 * u, wx + 6 * u, top + 10 * u), fill=(255, 238, 185) if on else (40, 44, 58))
        draw.rectangle((0, deck - 3 * u, W, deck + 3 * u), fill=(62, 66, 86))
        draw.rectangle((0, deck - 3 * u, W, deck - 2 * u), fill=(118, 122, 142))
        draw.rectangle((0, deck + 3 * u, W, deck + 11 * u), fill=(34, 37, 52))
        s = 2 * W * t
        step = W / 32
        for i in range(34):  # truss diagonals
            x = i * step - s % step
            draw.line([(x, deck + 3 * u), (x + step / 2, deck + 11 * u), (x + step, deck + 3 * u)], fill=(66, 70, 90), width=max(1, round(u)))
        for i in range(6):
            x = i * gap - s % gap
            draw.rectangle((x, deck + 11 * u, x + 10 * u, H), fill=(30, 33, 46))
            draw.rectangle((x, deck + 11 * u, x + 2 * u, H), fill=(52, 56, 74))
        out.append(_shrink(im, w, h))
    return out


@scene(320, 240, 75, 25)
def tree(w, h, n, seed):
    """An autumn tree on a hill, swaying in the wind, losing leaves. The tree is a seeded list of branches,
    each stored as an angle relative to its parent, so every frame rebuilds it from the root (forward
    kinematics) and branches can never come apart. Wind adds to each angle a bend that grows with depth and
    lags by depth, so a gust travels up from the trunk to the twigs. It has one slow and one fast harmonic,
    each a whole number of cycles per loop. Falling leaves grow in at a twig and leave below the frame."""
    rng = random.Random(seed)
    W, H = w * SS, h * SS
    u = H / 240  # one pixel at the default size
    cx, top = 0.5 * W, 0.8 * H  # tree root, on top of the hill

    def ground(x):
        return top + 0.09 * H * ((x - cx) / (0.5 * W)) ** 2

    # Branches: (parent, angle to parent, length, start width, end width, depth, wind phase). Each child
    # leans back toward upright a little, so the crown grows up and out instead of drooping.
    nodes = []

    def grow(parent, rel, absolute, length, width, depth):
        end = max(1.6 * u, width * 0.72)
        nodes.append((parent, rel, length, width, end, depth, rng.uniform(-0.5, 0.5)))
        i = len(nodes) - 1
        if depth == 9 or (depth >= 4 and rng.random() < 0.15):
            return
        offsets = (-1, 0, 1) if 1 <= depth <= 2 and rng.random() < 0.35 else (-1, 1)
        spread = rng.uniform(0.35, 0.55)
        for o in offsets:
            a = spread * o + rng.uniform(-0.15, 0.15) - 0.12 * absolute
            grow(i, a, absolute + a, length * rng.uniform(0.7, 0.84), max(1.6 * u, end * rng.uniform(0.78, 0.92)),
                 depth + 1)

    grow(-1, rng.uniform(-0.05, 0.05), 0, 1.0, 26 * u, 0)
    bend = [0.008 + 0.009 * d for d in range(10)]  # radians of wind per level: twigs bend most

    def pose(t, gust=1.0):
        """Each branch as (start x, start y, angle, end x, end y); angle 0 points up, positive leans right."""
        out = []
        for parent, rel, length, _w0, _w1, d, ph in nodes:
            x, y, a = (cx, top, 0) if parent < 0 else (out[parent][3], out[parent][4], out[parent][2])
            wind = 0.5 + math.sin(TAU * (t - 0.035 * d) + ph) + 0.35 * math.sin(TAU * (2 * t - 0.07 * d) + 2 * ph + 1)
            a += rel + gust * bend[d] * wind
            out.append((x, y, a, x + length * scale * math.sin(a), y - length * scale * math.cos(a)))
        return out

    scale = 1.0
    rest = pose(0, 0)
    scale = min((top - 0.1 * H) / (top - min(p[4] for p in rest)), 0.4 * W / max(abs(p[3] - cx) for p in rest))
    rest = pose(0, 0)
    tips = [i for i in range(len(nodes)) if i == len(nodes) - 1 or nodes[i + 1][0] != i]
    # Leaf clusters: two or three blobs on each twig, in the twig's own frame so they sway with it. A blob
    # is lit by where it sits in the crown (upper left is bright) plus noise. All shadows are drawn first,
    # then the leaves, then the highlights, so the crown breaks into lit clumps over dark gaps.
    ccx, ccy = sum(rest[i][3] for i in tips) / len(tips), sum(rest[i][4] for i in tips) / len(tips)
    span = max(math.hypot(rest[i][3] - ccx, rest[i][4] - ccy) for i in tips)
    autumn = _lut([(0, (70, 20, 12)), (0.3, (150, 45, 20)), (0.55, (205, 90, 28)), (0.8, (240, 160, 45)),
                   (1, (255, 215, 110))])

    def ink(v):
        return autumn[max(0, min(255, round(255 * v)))]

    # Leaves grow on every branch from depth 5 out, so the crown is full and not a thin shell. Branches
    # that share a depth-6 branch form one clump: lit on its upper left, dark on its lower right, and
    # darker deeper inside the crown.
    clumps = {}
    for i, nd in enumerate(nodes):
        if nd[5] >= 5:
            j = i
            while nodes[j][5] > 6:
                j = nodes[j][0]
            clumps.setdefault(j, []).append(i)
    blobs = []
    for group in clumps.values():
        gx, gy = sum(rest[i][3] for i in group) / len(group), sum(rest[i][4] for i in group) / len(group) - 4 * u
        size = max(10 * u, max(math.hypot(rest[i][3] - gx, rest[i][4] - gy) for i in group))
        tone = 0.42 + 0.22 * ((ccx - gx) * 0.6 + (ccy - gy) * 0.8) / span + rng.uniform(-0.15, 0.15)
        for i in group:
            d = nodes[i][5]
            for _ in range(rng.choice((2, 3)) if i in tips else 1):
                dx, dy, r = rng.uniform(-6, 6) * u, rng.uniform(-8, 2) * u, rng.uniform(5, 8) * u
                px, py = rest[i][3] + dx, rest[i][4] + dy
                lit = tone + 0.3 * ((gx - px) * 0.6 + (gy - py) * 0.8) / size - 0.04 * (9 - d) + rng.uniform(-0.05, 0.05)
                blobs.append((d, i, dx, dy, r, max(0.12, min(0.95, lit))))
    blobs.sort(key=lambda b: b[0])  # inner leaves first, twig tips on top
    # Shaded foliage deep in the crown, drawn behind the branches, so the inside is not an empty hole.
    back = [(i, rng.uniform(-10, 10) * u, rng.uniform(-18, 0) * u, rng.uniform(12, 18) * u, rng.uniform(0.14, 0.26))
            for i, nd in enumerate(nodes) if nd[5] in (3, 4) for _ in range(2)]

    def at(p, i, dx, dy):
        """A point fixed to branch i's end, turning with it."""
        a, x, y = p[i][2:]
        return x + dx * math.cos(a) - dy * math.sin(a), y + dx * math.sin(a) + dy * math.cos(a)
    # Falling leaves: (twig, start, falls per loop, drift right, wobble, flutter, spin, phase, shade).
    leaves = [(rng.choice(tips), rng.random(), rng.choice((1, 1, 2)), rng.uniform(0.15, 0.45) * W, rng.uniform(4, 12) * u,
               rng.uniform(1.5, 3), rng.uniform(2, 5), rng.uniform(0, TAU), rng.uniform(0.5, 0.9)) for _ in range(12)]
    # Still background: night sky, the hill with a lit rim, and fallen leaves.
    grad = Image.new("L", (1, H))
    grad.putdata([round(255 * y / H) for y in range(H)])
    bg = _colorize(grad.resize((W, H)), _lut([(0, (3, 4, 12)), (0.8, (16, 11, 24)), (1, (16, 11, 24))]))
    draw = ImageDraw.Draw(bg)
    hill = [(x, ground(x) - 2 * u) for x in range(-W // 10, W + W // 10, 4)]
    draw.polygon(hill + [(W + W // 10, H), (-W // 10, H)], fill=(32, 31, 17))
    draw.line(hill, fill=(92, 88, 40), width=round(3 * u))
    for _ in range(18):  # fallen leaves gather under the crown
        x = cx + rng.gauss(0, 0.2) * W
        y, r = ground(x) + rng.uniform(5 * u, 0.12 * H), rng.uniform(2.5, 3.5) * u
        draw.ellipse((x - r, y - 0.55 * r, x + r, y + 0.55 * r), fill=ink(rng.uniform(0.2, 0.45)))
    tufts = [rng.uniform(0, W) for _ in range(26)]
    poses = [pose(k / n) for k in range(n)]
    base = (105, 74, 52)
    out = []
    for k in range(n):
        t = k / n
        im = bg.copy()
        draw = ImageDraw.Draw(im)
        for x in tufts:  # grass bends with the same wind, a little later the further right it is
            y = ground(x)
            sway = 0.25 + 0.25 * math.sin(TAU * (t - 0.3 * x / W)) + 0.1 * math.sin(TAU * (2 * t - 0.6 * x / W))
            for j, a in enumerate((-0.45, 0.0, 0.4)):
                ln = (7 + 3 * (j == 1)) * u
                draw.line([(x + 2 * (j - 1) * u, y), (x + ln * math.sin(a + sway), y - ln * math.cos(a + sway))],
                          fill=(120, 124, 52), width=round(2 * u))
        p = poses[k]
        rw = nodes[0][3] / 2
        draw.polygon([(cx - 1.8 * rw, top + 2 * u), (cx - rw, top - 10 * u), (cx + rw, top - 10 * u),
                      (cx + 1.8 * rw, top + 2 * u)], fill=base)  # root flare
        for i, dx, dy, r, v in back:
            bx, by = at(p, i, dx, dy)
            draw.ellipse((bx - r, by - r, bx + r, by + r), fill=ink(v))
        for (par, _rel, _len, w0, w1, d, _ph), (x0, y0, a, x1, y1) in zip(nodes, p):
            ca, sa = math.cos(a), math.sin(a)
            bark = tuple(round(c0 + (c1 - c0) * min(1, d / 5)) for c0, c1 in zip(base, (165, 125, 90)))
            draw.polygon([(x0 - ca * w0 / 2, y0 - sa * w0 / 2), (x1 - ca * w1 / 2, y1 - sa * w1 / 2),
                          (x1 + ca * w1 / 2, y1 + sa * w1 / 2), (x0 + ca * w0 / 2, y0 + sa * w0 / 2)], fill=bark)
            if par >= 0:  # round joints hide the seams between a branch and its children
                draw.ellipse((x0 - w0 / 2, y0 - w0 / 2, x0 + w0 / 2, y0 + w0 / 2), fill=bark)
            if w0 > 6 * u:  # a lit stripe on the left side of thick limbs makes them look round
                o0, o1 = 0.22 * w0, 0.22 * w1
                draw.line([(x0 - ca * o0, y0 - sa * o0), (x1 - ca * o1, y1 - sa * o1)],
                          fill=tuple(c + 45 for c in bark), width=max(1, round(0.2 * w1)))
        for layer in range(3):
            for _d, i, dx, dy, r, lit in blobs:
                if layer == 2 and lit < 0.6:
                    continue
                bx, by = at(p, i, dx, dy)
                if layer == 0:
                    bx, by, r, v = bx + 2 * u, by + 3 * u, r * 1.15, lit * 0.35
                elif layer == 1:
                    v = lit
                else:
                    bx, by, r, v = bx - 0.25 * r, by - 0.3 * r, r * 0.55, lit + 0.25
                draw.ellipse((bx - r, by - r, bx + r, by + r), fill=ink(v))
        for tip, p0, times, drift, wob, flutter, spin, ph, lit in leaves:
            s = (p0 + times * t) % 1.0
            x0, y0 = poses[round((t - s / times) * n) % n][tip][3:]  # where its twig was when it let go
            x = x0 + drift * s + wob * math.sin(TAU * flutter * s + ph)
            y = y0 + (H + 12 * u - y0) * s ** 1.4
            size = 5.5 * u * min(1, s / 0.1)  # grows in at the twig instead of popping up
            ang = TAU * spin * s + ph
            c, sn = size * math.cos(ang), size * math.sin(ang)
            f = 0.6 * (0.3 + 0.7 * abs(math.cos(TAU * flutter * s * 0.7 + ph)))  # flips as it tumbles
            draw.polygon([(x + c, y + sn), (x - f * sn, y + f * c), (x - c, y - sn), (x + f * sn, y - f * c)],
                         fill=ink(lit))
        out.append(_shrink(im, w, h))
    return out


@scene(320, 240, 80, 25)
def planet(w, h, n, seed):
    """A ringed gas giant with two moons. The light, rings and shadows never change, so one pass over
    the pixels works them out once: where the view ray meets the sphere and the ring plane, which is
    nearer, the light on the disc, the ring's shadow on the disc and the planet's shadow on the ring.
    Each frame then only shifts the longitude of the cloud texture (it repeats twice around the
    planet and turns half a turn per loop) and moves the moons, which hide pixel by pixel behind
    whatever is nearer."""
    rng = random.Random(seed)
    W, H = w * SS, h * SS
    R = 0.22 * min(h, 0.75 * w) * SS  # planet radius in pixels; the rest is in planet radii
    cx, cy = W / 2, H / 2
    m = _rot(math.radians(22), 0, math.radians(-14))  # pole tipped 22 deg toward us, then rolled
    mt = tuple(zip(*m))  # camera -> planet frame
    pole = (m[0][1], m[1][1], m[2][1])
    light = _unit((-0.85, 0.35, 0.35))
    nl = sum(a * b for a, b in zip(pole, light))  # > 0: we see the lit face of the rings
    r0, r1 = 1.24, 2.3
    ring = [v / 255 for (v,) in _lut([(0, (0,)), (0.03, (60,)), (0.24, (90,)), (0.26, (200,)), (0.4, (250,)),
                                     (0.47, (205,)), (0.56, (255,)), (0.62, (235,)), (0.64, (0,)),
                                     (0.76, (0,)), (0.78, (190,)), (0.97, (165,)), (1, (0,))])]

    def dens(rho):
        return ring[int((rho - r0) / (r1 - r0) * 255)] if r0 < rho < r1 else 0.0

    # Cloud texture over one period of longitude (half the planet): belts, wavy edges, a storm.
    tw, th = 320, 160
    belts = [(c, hw, d + rng.uniform(-0.06, 0.06)) for c, hw, d in
             ((12, 6, 0.5), (-12, 6, 0.55), (31, 5, 0.42), (-34, 6, 0.45), (50, 5, 0.38), (-53, 5, 0.38),
              (68, 6, 0.3), (-70, 6, 0.3))]
    ph = [rng.uniform(0, TAU) for _ in range(3)]
    su, sl = rng.random(), 21.0  # the north faces us; the rings hide the south
    tex = bytearray(2 * tw * th)
    for i in range(th):
        lat = (i + 0.5) / th * 180 - 90
        for j in range(tw):
            u = j / tw  # whole harmonics of u keep the texture periodic
            lw = lat + 0.7 * math.sin(TAU * 4 * u + 0.2 * lat + ph[0]) + 0.4 * math.sin(TAU * 9 * u - 0.3 * lat + ph[1])
            v = 0.9
            for c, hw, d in belts:
                x = min(1.0, max(0.0, (1 - abs(lw - c) / hw) * 3))
                v -= d * x * x * (3 - 2 * x) * (1 + 0.15 * math.sin(TAU * 5 * u + 0.5 * lat + ph[2]))
            v *= 1 - 0.35 * (abs(lat) / 90) ** 3
            du = (u - su + 0.5) % 1 - 0.5
            e = (du / 0.078) ** 2 + ((lat - sl) / 5.5) ** 2
            if e < 1:
                v = 0.15 + 0.15 * e
            elif e < 2.5:  # a light collar, wide enough to survive as ASCII
                v = max(v, 0.95)
            tex[i * 2 * tw + j] = tex[i * 2 * tw + tw + j] = max(0, min(255, round(255 * v)))
    tex = bytes(tex)
    lut = _lut([(0, (75, 30, 20)), (0.4, (160, 95, 55)), (0.7, (215, 170, 115)), (1, (252, 236, 196))])

    # Stars, then one pass over the pixels for everything that never moves.
    bg = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(bg)
    for _ in range(round(w * h / 1600)):
        x, y, r, g = rng.uniform(0, W), rng.uniform(0, H), SS * rng.uniform(0.8, 1.6), rng.randint(90, 230)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(g, g, min(255, g + 20)))
    bx, by, B = int(cx - R) - 1, int(cy - R) - 1, int(2 * R) + 3  # planet box
    idx, shade, pmask = [0] * (B * B), bytearray(B * B), bytearray(B * B)
    zs, zr = [-9.0] * (W * H), [9.0] * (W * H)  # sphere and ring depth (toward us), for the moons
    ra, rcol = bytearray(W * H), bytearray(3 * W * H)  # visible ring: alpha and color
    ring_a = bytearray(W * H)  # ring over the background; 255 where it covers the disc
    for py in range(H):
        Y = (cy - py - 0.5) / R
        for px in range(W):
            X = (px + 0.5 - cx) / R
            i, d2 = py * W + px, X * X + Y * Y
            if d2 < 1:
                z = zs[i] = math.sqrt(1 - d2)
                lam = X * light[0] + Y * light[1] + z * light[2]
                k = min(1.0, max(0.0, (lam + 0.1) / 0.35))
                lit = k * k * (3 - 2 * k) * (0.35 + 0.65 * max(0.0, lam)) * (0.6 + 0.4 * z)
                t = -(X * pole[0] + Y * pole[1] + z * pole[2]) / nl  # toward the light, to the ring plane
                if t > 0:
                    lit *= 1 - 0.6 * dens(math.dist((0, 0, 0), (X + t * light[0], Y + t * light[1], z + t * light[2])))
                q = (py - by) * B + px - bx
                shade[q] = round(255 * (0.4 + 0.6 * lit))  # the night side stays visible as ASCII
                pmask[q] = 255
                p = _apply(mt, (X, Y, z))
                row = min(th - 1, int((math.asin(max(-1.0, min(1.0, p[1]))) / math.pi + 0.5) * th))
                idx[q] = row * 2 * tw + int((math.atan2(p[0], p[2]) / math.pi) % 1 * tw)
            z = -(X * pole[0] + Y * pole[1]) / pole[2]
            rho2 = d2 + z * z
            if r0 * r0 < rho2 < r1 * r1 and not (d2 < 1 and z < zs[i]):
                a = dens(math.sqrt(rho2))
                if not a:
                    continue
                pl = X * light[0] + Y * light[1] + z * light[2]
                sh = 1.0 if pl > 0 else min(1.0, max(0.0, (math.sqrt(rho2 - pl * pl) - 0.97) / 0.06))
                lum = (0.75 + 0.25 * a) * (0.35 + 0.65 * sh)
                zr[i], ra[i] = z, round(255 * a)
                rcol[3 * i:3 * i + 3] = bytes(round(c * lum) for c in (232, 214, 180))
                if d2 < 1:
                    ring_a[i] = 255
                    pmask[(py - by) * B + px - bx] = round(255 * (1 - a))
                else:
                    ring_a[i] = ra[i]
    base = Image.composite(Image.frombytes("RGB", (W, H), bytes(rcol)), bg, Image.frombytes("L", (W, H), bytes(ring_a)))
    shade = Image.frombytes("L", (B, B), bytes(shade)).convert("RGB")
    pmask = Image.frombytes("L", (B, B), bytes(pmask))

    # Moons: (orbit radius, size, tilt of the orbit from the rings, start, color). One orbit per loop.
    start = rng.random()
    moons = [(2.6, 0.13, 8, start, (200, 195, 185)), (2.75, 0.09, -20, start + 0.45, (175, 180, 200))]
    out = []
    for f in range(n):
        t = f / n
        s = f * tw // n
        alb = Image.frombytes("L", (B, B), bytes([tex[j + s] for j in idx]))
        im = base.copy()
        im.paste(ImageChops.multiply(_colorize(alb, lut), shade), (bx, by), pmask)
        pix = im.load()
        for orbit, size, tilt, start, col in moons:
            a, ti = TAU * (t + start), math.radians(tilt)
            c = _apply(m, (orbit * math.cos(a), orbit * math.sin(a) * math.sin(ti), orbit * math.sin(a) * math.cos(ti)))
            cl = sum(p * q for p, q in zip(c, light))
            eclipse = 1.0 if cl > 0 else min(1.0, max(0.0, (math.sqrt(orbit * orbit - cl * cl) - 1 + size) / (2 * size)))
            mx, my, mr = cx + c[0] * R, cy - c[1] * R, size * R
            for py in range(max(0, int(my - mr)), min(H, int(my + mr) + 2)):
                for px in range(max(0, int(mx - mr)), min(W, int(mx + mr) + 2)):
                    dx, dy = (px + 0.5 - mx) / mr, (my - py - 0.5) / mr
                    q = dx * dx + dy * dy
                    i = py * W + px
                    if q >= 1 or zs[i] > c[2] + size:
                        continue
                    dz = math.sqrt(1 - q)
                    lam = dx * light[0] + dy * light[1] + dz * light[2]
                    lum = 0.12 + 0.88 * max(0.0, lam) * eclipse
                    rgb = [v * lum for v in col]
                    if ra[i] and zr[i] > c[2] + size * dz:  # ring in front of the moon
                        k = ra[i] / 255
                        rgb = [rcol[3 * i + j] * k + rgb[j] * (1 - k) for j in range(3)]
                    pix[px, py] = tuple(round(v) for v in rgb)
        out.append(_shrink(im, w, h))
    return out
