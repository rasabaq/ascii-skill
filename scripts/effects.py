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


def matrix(grid, n=80, rng=None, bg=(0, 0, 0), trail=10, **_):
    """Falling columns of glyphs with a bright head; the art is left behind the trail.
    On a light page (`bg`) the head is dark instead, so it still shows."""
    rows, cols = len(grid), len(grid[0])
    active = max(1, round(n * 0.8))  # last 20% holds the clean art
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


def decode(grid, n=60, rng=None, **_):
    """Cells scramble through random glyphs and lock in, sweeping left to right."""
    rows, cols = len(grid), len(grid[0])
    active = max(1, round(n * 0.8))
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


def scan(grid, n=60, rng=None, glow=4, bg=BLACK, **_):
    """A bright CRT line sweeps down and types each row in, leaving a short glow.
    On a light page (`bg`) the line and glow are dark instead, so they still show."""
    rows, cols, hi = len(grid), len(grid[0]), _pop(bg)
    active = max(1, round(n * 0.85))
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
        env = math.sin(math.pi * f / max(1, n - 1)) ** 2 * amp
        frame = []
        for y, row in enumerate(grid):
            dx = round(env * math.sin(2 * math.pi * (2 * f / n - y / 12)))
            frame.append(list(row) if dx == 0 else
                         [row[x - dx] if 0 <= x - dx < cols else (" ", row[x][1]) for x in range(cols)])
        out.append(frame)
    out[-1] = [list(row) for row in grid]
    return out


EFFECTS = {"matrix": matrix, "decode": decode, "scan": scan, "glitch": glitch, "wave": wave}


def frames(grid, effect, n=None, seed=0, **opts):
    """Return a list of grids for `effect`. The last one equals `grid`. Same seed, same frames.
    `n` is the frame count (default per effect, timed for FPS); extra opts go to the effect."""
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
    out[-1] = [list(row) for row in grid]  # settle exactly on the art, even for tiny n
    return out
