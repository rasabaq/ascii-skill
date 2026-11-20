# /// script
# dependencies = ["pillow>=10.1"]
# ///
"""Run: uv run scripts/test_effects.py"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from effects import EFFECTS, frames  # noqa: E402

# 100x50 grid with some blank cells, like real art.
grid = [[(" " if (x * y) % 7 == 0 else "#@%*+"[x % 5], (x * 2, y * 5, 128)) for x in range(100)] for y in range(50)]
for name in EFFECTS:
    for n in (None, 1, 2, 80):
        seq = frames(grid, name, n=n, seed=3)
        assert n is None or len(seq) == n, (name, n)
        assert all(len(f) == 50 and all(len(r) == 100 for r in f) for f in seq), name
        assert all(isinstance(ch, str) and len(ch) == 1 and len(c) == 3 for f in seq for r in f for ch, c in r), name
        assert seq[-1] == grid, (name, n)
    assert frames(grid, name, seed=5) == frames(grid, name, seed=5), name
    assert any(f != grid for f in seq[:-1]), name + " should animate"
    t = time.time()
    frames(grid, name, n=80)
    assert time.time() - t < 2, name
# No built-in hold: intros move until the end (animate.py --hold adds the pause), and wave rests only ~3 frames.
for name in ("matrix", "decode", "scan", "wave"):
    assert frames(grid, name)[-4] != grid, name
assert frames(grid, "wave")[3] != grid
try:
    frames(grid, "nope")
except ValueError:
    pass
else:
    raise AssertionError("unknown effect must raise")
print("ok")

# Two-color (halfblock) cells survive every effect and the last frame is exact.
hb = [[("▀", (200, 10, 10), (10, 10, 200)) for _ in range(12)] for _ in range(6)]
for name in EFFECTS:
    fr = frames(hb, name)
    assert fr[-1] == hb, name
    assert all(len(c) == 3 for f in fr[:-1] for row in f for c in row if c[0] != " "), name  # glyphs keep the bottom color
    if name in ("matrix", "scan"):  # art not shown yet is blank, not a block of the bottom color
        assert any(c[0] == " " and len(c) == 2 for f in fr[:-1] for row in f for c in row), name
print("ok halfblock")

# Scan line and matrix heads stand out on the page: light on a dark page (the default), dark on a light one.
ink = [[("#", (29, 53, 87)) for _ in range(30)] for _ in range(20)]
lum = lambda c: sum(c) / 3
for name, f in (("scan", 30), ("matrix", 25)):
    dark, light = frames(ink, name, seed=1)[f], frames(ink, name, seed=1, bg=(243, 234, 216))[f]
    assert frames(ink, name, seed=1, bg=(0, 0, 0))[f] == dark, name  # default is a black page
    assert max(lum(c) for r in dark for _ch, c in r) > 150, name
    assert name == "matrix" or max(lum(c) for r in light for _ch, c in r) <= lum((29, 53, 87))  # no pale glow
    assert min(lum(c) for r in light for _ch, c in r) < 20, name
print("ok light page")

# Shimmer: the art holds still (same cells filled, same colors) while a few glyphs swap for others of the same weight.
art = [[("@S0x8#"[(x + y) % 6] if (x * y) % 5 else " ", (x * 9, y * 20, 90)) for x in range(30)] for y in range(12)]
seq = frames(art, "shimmer", seed=4)
for f in seq:
    assert all((ch == " ") == (a[0] == " ") and c == a[1] for r, ar in zip(f, art) for (ch, c), a in zip(r, ar))
changed = [sum(ch != a[0] for r, ar in zip(f, art) for (ch, _c), a in zip(r, ar)) for f in seq]
cells = sum(ch != " " for r in art for ch, _c in r)
assert 0.02 < sum(changed) / len(seq) / cells < 0.2, sum(changed) / len(seq) / cells  # a few at a time
assert all(changed[len(seq) // 4: -len(seq) // 4])  # always something moving mid-loop
weight = lambda ch: next(i for i, fam in enumerate(("@#%&$B8", "0SXZ96", "x+=*")) if ch in fam)
assert all(weight(ch) == weight(a[0]) for f in seq for r, ar in zip(f, art) for (ch, _c), a in zip(r, ar) if ch != " ")
# Symbol photo styles have one glyph per weight. Shimmer swaps in a twin, so the picture still reads.
symbols = "┃╏╹╲/′◆◇●•·✖✕×"
sym = [[(symbols[(x + y) % len(symbols)], (220, 180, 40)) for x in range(36)] for y in range(10)]
seq = frames(sym, "shimmer", seed=2)
fams = ("┃║", "╏┇┋", "╹╻", "╲\\", "╱/", "′´", "◆♦", "◇◊", "●◉", "•∙", "·⋅", "✖✘", "✕×✗")
fam = lambda ch: next(s for s in fams if ch in s)
changed = [sum(ch != a[0] for r, ar in zip(f, sym) for (ch, _c), a in zip(r, ar)) for f in seq]
cells = sum(ch != " " for r in sym for ch, _c in r)
assert 0.02 < sum(changed) / len(seq) / cells < 0.2, sum(changed) / len(seq) / cells
assert all(changed[len(seq) // 4:-len(seq) // 4])
assert all(fam(ch) == fam(a[0]) for f in seq for r, ar in zip(f, sym) for (ch, _c), a in zip(r, ar))
print("ok shimmer")

# Dust: starts on the art, eats the side the wind blows toward, and grains fly out past the art's edge.
blob = [[("#" if 20 <= x < 40 else " ", (200, 200, 200)) for x in range(60)] for _ in range(20)]
seq = frames(blob, "dust", seed=4)
assert seq[0] == blob
mid = seq[len(seq) // 3]
kept = lambda f, xs: sum(f[y][x][0] == "#" for y in range(20) for x in xs)
assert kept(mid, range(20, 26)) < kept(mid, range(34, 40))  # left edge gone first
assert any(ch != " " for f in seq for r in f for ch, _c in r[:20])  # dust outside the art
right = frames(blob, "dust", seed=4, wind="right")[len(seq) // 3]
assert kept(right, range(34, 40)) < kept(right, range(20, 26))
print("ok dust")

# Dust over a moving picture: the picture keeps playing under the dust, and the clip is whole runs of it.
movie = [[[("#" if 20 <= x < 40 else " ", (200, 200, 200 - 20 * k)) for x in range(60)] for _ in range(20)] for k in range(8)]
seq = frames(movie[0], "dust", seed=4, seq=movie)
assert len(seq) % 8 == 0 and seq[-1] == movie[-1]
assert seq[3][0][39] == movie[3][0][39] and seq[5][0][39] == movie[5][0][39]  # untouched cells play on
print("ok dust moving")
