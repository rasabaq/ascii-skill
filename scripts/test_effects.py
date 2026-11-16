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
    assert any(len(c) == 3 for f in fr[:-1] for row in f for c in row), name  # not only the last frame
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
