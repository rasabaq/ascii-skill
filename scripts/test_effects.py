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
