"""Animated ASCII effects: turn one grid into a list of grids that settles on the art.

    from effects import frames, EFFECTS, FPS
    seq = frames(grid, "matrix", seed=1)   # list of grids, seq[-1] == grid

A grid is rows of (char, (r, g, b)) cells, as made by ascii.convert(). Every frame has the
same size, and the last frame equals the input, so each effect works as an intro or a reveal.
Writers (GIF, MP4, terminal) live in animate.py. Pass colors baked into the grid: a single
`fg` ink at render time would hide the bright heads and glows.
"""
import math
import random

FPS = 25  # all default frame counts are timed for this rate
GLYPHS = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ$#%&*+=<>?/\\|!:;~^"
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


def mix(c, t, k):
    """Blend color c toward t by k (0 = c, 1 = t)."""
    return (round(c[0] + (t[0] - c[0]) * k), round(c[1] + (t[1] - c[1]) * k), round(c[2] + (t[2] - c[2]) * k))


def _dark(bg):
    return sum(bg) < 384  # same split as ascii.convert()


def _pop(bg):
    """The color that stands out on the page: white on a dark page, black on a light one."""
    return WHITE if _dark(bg) else BLACK


def _lit(c, bg=BLACK):  # cells close to the page get gray ink, so rain over them shows
    if _dark(bg):
        return c if max(c) > 60 else (150, 150, 150)
    return c if min(c) < 195 else (105, 105, 105)


def matrix(grid, n=65, rng=None, bg=(0, 0, 0), trail=10, **_):
    """Falling columns of glyphs with a bright head; the art is left behind the trail.
    On a light page (`bg`) the head is dark instead, so it still shows."""
    rows, cols = len(grid), len(grid[0])
    active = max(1, n - 1)  # the art is complete on the last frame; animate.py --hold keeps it on screen
    drops = []
    for _x in range(cols):
        delay = rng.uniform(0, active * 0.45)
        speed = (rows + trail) / max(1.0, active - delay) * rng.uniform(1.0, 1.5)
        drops.append((delay, speed))
    out = []
    for f in range(n):
        frame = [[(" ", c) for _ch, c in row] for row in grid]
        for x, (delay, speed) in enumerate(drops):
            head = (f - delay) * speed
            if head < 0:
                continue
            hy = int(head)
            for y in range(max(0, hy - trail), min(rows, hy + 1)):
                ch, c = grid[y][x]
                d = hy - y
                if d == 0:
                    frame[y][x] = (rng.choice(GLYPHS), mix(_lit(c, bg), _pop(bg), 0.75))
                elif ch != " " and rng.random() < d / trail:  # the art shows through, more so up the trail
                    frame[y][x] = (ch, mix(c, bg, 0.5 * (1 - d / trail)))
                else:
                    frame[y][x] = (rng.choice(GLYPHS), mix(_lit(c, bg), bg, 0.15 + 0.75 * d / trail))
            for y in range(0, min(rows, hy - trail + 1)):
                frame[y][x] = grid[y][x]
        out.append(frame)
    return out


def decode(grid, n=50, rng=None, **_):
    """Cells scramble through random glyphs and lock in, sweeping left to right."""
    rows, cols = len(grid), len(grid[0])
    active = max(1, n - 2)  # the last cells lock and stop flashing on the last frame
    scramble = max(2, round(active * 0.3))
    span = active - scramble - 1
    lock = [[scramble + (0.75 * x / max(1, cols - 1) + rng.uniform(0, 0.25)) * span for x in range(cols)]
            for _y in range(rows)]
    out = []
    for f in range(n):
        frame = []
        for y, row in enumerate(grid):
            line = []
            for x, (ch, c) in enumerate(row):
                t = lock[y][x]
                if ch == " " or f >= t + 2:
                    line.append((ch, c) if ch == " " or f >= t else (" ", c))
                elif f >= t:  # just locked: flash
                    line.append((ch, mix(c, WHITE, 0.6 if f < t + 1 else 0.3)))
                elif f >= t - scramble:
                    line.append((rng.choice(GLYPHS), mix(c, (0, 0, 0), 0.55)))
                else:
                    line.append((" ", c))
            frame.append(line)
        out.append(frame)
    return out


def scan(grid, n=52, rng=None, glow=4, bg=BLACK, **_):
    """A bright CRT line sweeps down and types each row in, leaving a short glow.
    On a light page (`bg`) the line and glow are dark instead, so they still show."""
    rows, cols, hi = len(grid), len(grid[0]), _pop(bg)
    active = max(1, n - 1)
    out = []
    for f in range(n):
        pos = min(1.0, f / active) * (rows + glow)  # beam row, fractional part is typing progress
        beam, typed = int(pos), int((pos % 1) * cols)
        frame = []
        for y, row in enumerate(grid):
            d = beam - y
            if d < 0 or (d == 0 and f >= active):
                frame.append([(" ", c) for _ch, c in row] if d < 0 else list(row))
            elif d == 0:
                line = [(ch, mix(c, hi, 0.85)) if x < typed else (" ", c) for x, (ch, c) in enumerate(row)]
                if typed < cols:
                    line[typed] = ("█", hi)
                frame.append(line)
            elif d <= glow:
                k = 0.7 * (1 - d / (glow + 1))
                frame.append([(ch, mix(c, hi, k)) for ch, c in row])
            else:
                frame.append(list(row))
        out.append(frame)
    return out


def glitch(grid, n=50, rng=None, **_):
    """The art with short bursts of row shifts, glyph swaps and color splits. Starts and ends clean: loops."""
    rows, cols = len(grid), len(grid[0])
    hot = set()
    f = rng.randint(3, 8)
    while f < n - 4:  # bursts of 2-4 frames, quiet gaps between, last frames clean
        hot.update(range(f, min(n - 4, f + rng.randint(2, 4))))
        f += rng.randint(8, 16)
    out = []
    for f in range(n):
        frame = [list(row) for row in grid]
        if f in hot:
            power = rng.uniform(0.5, 1.0)
            reach = max(1, int(cols * 0.15 * power))
            for _ in range(rng.randint(2, 4)):  # bands slide sideways, tinted red or cyan, with torn glyphs
                y0, dx = rng.randrange(rows), rng.choice((-1, 1)) * rng.randint(1, reach)
                tint = rng.choice(((255, 40, 70), (40, 230, 255), None))
                for y in range(y0, min(rows, y0 + rng.randint(1, max(2, rows // 6)))):
                    line = []
                    for x in range(cols):
                        ch, c = grid[y][(x - dx) % cols]
                        if rng.random() < 0.12 * power:
                            ch, c = rng.choice(GLYPHS + "▓▒░"), _lit(c)
                        line.append((ch, mix(c, tint, 0.55) if tint and ch != " " else c))
                    frame[y] = line
        out.append(frame)
    out[-1] = [list(row) for row in grid]
    return out


def wave(grid, n=50, rng=None, amp=3, **_):
    """Rows sway sideways on a sine wave that swells and calms. Starts and ends clean: loops."""
    rows, cols = len(grid), len(grid[0])
    out = []
    for f in range(n):
        env = math.sin(math.pi * f / max(1, n - 1)) * amp  # not squared: only ~3 still frames at each end
        frame = []
        for y, row in enumerate(grid):
            dx = round(env * math.sin(2 * math.pi * (2 * f / n - y / 12)))
            frame.append(list(row) if dx == 0 else
                         [row[x - dx] if 0 <= x - dx < cols else (" ", row[x][1]) for x in range(cols)])
        out.append(frame)
    out[-1] = [list(row) for row in grid]
    return out


SIMILAR = ("@#%&$B8", "0SXZ96", "x+=*", "-:~;", ".,'`")  # glyphs of about the same weight


def _twin(ch, rng):
    """Another glyph of about the same weight: a letter or number from ch's family, or a braille cell
    with one dot moved. Anything else (blocks, words) stays as it is."""
    for fam in SIMILAR:
        if ch in fam:
            return rng.choice(fam.replace(ch, ""))
    if "\u2801" <= ch <= "\u28ff":
        dots = [b for b in range(8) if ord(ch) >> b & 1]
        free = [b for b in range(8) if not ord(ch) >> b & 1]
        if dots and free:
            return chr(ord(ch) ^ (1 << rng.choice(dots)) ^ (1 << rng.choice(free)))
    return ch


def shimmer(grid, n=75, rng=None, rate=0.02, **_):
    """The art holds still while its glyphs keep swapping for others of the same weight (S for #,
    0 for @), a few at a time, so it looks alive. Pairs with animate.py --under, which keeps the photo
    under them. `rate` is swaps per cell per frame. Starts and ends clean: loops."""
    out = [[list(row) for row in grid] for _ in range(n)]
    for y, row in enumerate(grid):
        for x, (ch, c) in enumerate(row):
            if ch == " ":
                continue
            t = rng.expovariate(rate)
            while True:
                dur = rng.randint(2, 6)  # frames the other glyph stays
                if t + dur >= n - 1:  # nothing still swapped on the last frame
                    break
                g = _twin(ch, rng)
                for f in range(int(t), int(t) + dur):
                    out[f][y][x] = (g, c)
                t += dur + rng.expovariate(rate)
    return out


def dust(grid, n=100, rng=None, bg=BLACK, wind="left", reach=0.45, red=0.035, seq=None, **_):
    """The art comes apart into wind-blown dust and grows back. Cells near the edge the wind blows
    toward go first and come back last; each leaves as a grain that rides a swirling wind and fades.
    `reach` is how far into the art it eats (share of the width); about `red` of the grains are
    crimson. Starts and ends clean: loops. `seq` is a moving picture (a list of grids the size of
    `grid`) that keeps playing under the dust; `n` then rounds to whole runs of it, so both loop."""
    rows, cols = len(grid), len(grid[0])
    if seq:
        n = len(seq) * max(1, round(n / len(seq)))
    base = (lambda f: seq[f % len(seq)]) if seq else (lambda f: grid)
    sx = -1 if wind == "left" else 1
    a, b, c3 = (rng.uniform(0, 2 * math.pi) for _ in range(3))

    def flow(x, y):
        # Steady wind plus the curl of psi = sin(v+a) + 0.6 sin(1.7v-u+b) + 0.8 sin(1.3u+c): eddies
        # that swirl without clumping. Cells are about twice as tall as wide, so rows move half as far.
        u, v = 6 * x / max(8, cols), 6 * y / max(8, rows)
        dv = math.cos(v + a) + 1.02 * math.cos(1.7 * v - u + b)
        du = -0.6 * math.cos(1.7 * v - u + b) + 1.04 * math.cos(1.3 * u + c3)
        return sx + 0.55 * dv, 0.5 * (-0.3 - 0.6 * du)

    span = max(1.0, cols * reach)
    grains = []  # (x, y, t0, t1, life, path, ch, color)
    for y, row in enumerate(grid):
        filled = [x for x, (ch, _c) in enumerate(row) if ch != " "]
        if not filled:
            continue
        edge = filled[0] if sx < 0 else filled[-1]
        for x in filled:
            s = abs(x - edge) / span + rng.uniform(0, 0.15)  # 0 at the edge, 1 at full reach
            if s >= 1 or rng.random() > (1 - s) ** 1.2:
                continue
            # The edge tends to go first. Each cell is gone for a while, so the art keeps shedding and
            # re-forming through the loop, and all is back and still by the last frames.
            t0 = 2 + (0.7 * s + 0.3 * rng.random()) * 0.55 * n
            t1 = min(n - 3, t0 + rng.uniform(0.15, 0.3) * n)
            life = max(1.0, min(rng.uniform(0.22, 0.38) * n, n - 2 - t0))
            step = rng.uniform(0.15, 0.4) * cols / life
            path, px, py = [], float(x), float(y)
            for _ in range(int(life) + 1):  # the field is static, so each path is worked out once
                path.append((round(px), round(py)))
                vx, vy = flow(px, py)
                px, py = px + vx * step, py + vy * step
            ch, c = base(int(t0))[y][x][:2]  # what the cell shows as it lifts off
            if ch == " ":
                ch, c = row[x]
            grains.append((x, y, t0, t1, life, path, ch, (220, 20, 60) if rng.random() < red else c))
    out = []
    for f in range(n):
        now = base(f)
        frame = [list(row) for row in now]
        fade = {}  # cell -> how faded the grain drawn there is; the freshest wins
        for x, y, t0, t1, life, path, ch, c in grains:
            if t0 <= f < t1:  # the cell is gone; its last 3 frames grow back as small marks
                k = (f - t1 + 3) / 3
                frame[y][x] = (" ", now[y][x][1]) if k < 0 else (".+"[int(k * 2)], mix(now[y][x][1], bg, 0.5))
            u = (f - t0) / life
            if not 0 <= u < 1:
                continue
            gx, gy = path[int(life * u ** 1.15)]  # eased: grains lift off slowly, then the wind takes them
            if 0 <= gx < cols and 0 <= gy < rows and u < fade.get((gx, gy), 2):
                fade[gx, gy] = u
                g = ch if u < 0.12 else "*+:.."[min(4, int((u - 0.12) / 0.88 * 5))]
                frame[gy][gx] = (g, mix(c, bg, 1 - (1 - u) ** 0.9))
        out.append(frame)
    return out


LOOPS = ("glitch", "wave", "shimmer", "dust")  # start and end on the art, so they loop with no hold
EFFECTS = {"matrix": matrix, "decode": decode, "scan": scan, "glitch": glitch, "wave": wave, "shimmer": shimmer,
           "dust": dust}


def frames(grid, effect, n=None, seed=0, **opts):
    """Return a list of grids for `effect`. The last one equals `grid` (or, with a moving `seq`, its
    matching frame). Same seed, same frames. `n` is the frame count (default per effect, timed for FPS);
    extra opts go to the effect."""
    if effect not in EFFECTS:
        raise ValueError("unknown effect %r: use %s" % (effect, ", ".join(EFFECTS)))
    if not grid or not grid[0]:
        raise ValueError("grid is empty")
    if n is not None and n < 1:
        raise ValueError("n must be at least 1")
    kw = dict(opts, rng=random.Random(seed))
    if n is not None:
        kw["n"] = n
    # Effects work on (char, color) cells. Two-color cells (halfblock) get their second color back
    # wherever an effect shows the original cell: same object (moved cells) or same value in place.
    flat = [[cell[:2] for cell in row] for row in grid]
    orig = {id(f): g for frow, grow in zip(flat, grid) for f, g in zip(frow, grow) if len(g) > 2}
    out = EFFECTS[effect](flat, **kw)
    if orig:
        out = [[[orig.get(id(c), grid[y][x] if c == flat[y][x] else c) for x, c in enumerate(row)]
                for y, row in enumerate(fr)] for fr in out]
    last = opts.get("seq") or [grid]
    out[-1] = [list(row) for row in last[(len(out) - 1) % len(last)]]  # settle exactly on the art, even for tiny n
    return out
