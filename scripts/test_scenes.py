# /// script
# dependencies = ["pillow>=10.1"]
# ///
"""Run: uv run scripts/test_scenes.py"""
import contextlib
import io
import os
import sys
import tempfile

from PIL import Image, ImageChops, ImageSequence, ImageStat

sys.path.insert(0, os.path.dirname(__file__))
from animate import main  # noqa: E402
from scenes import DEFAULTS, SCENES, frames  # noqa: E402


def diff(a, b):
    """Mean absolute pixel difference, 0-255."""
    return sum(ImageStat.Stat(ImageChops.difference(a.convert("RGB"), b.convert("RGB"))).mean) / 3


assert set(SCENES) == set(DEFAULTS) >= {"fire", "donut", "cube", "waves", "stars", "walker"}
for name, scene in SCENES.items():
    w, h, n, fps = DEFAULTS[name]
    assert 2000 <= n * 1000 / fps <= 4000, (name, "loop is 2-4 s")
    seq = scene(160, 120, 24, 1)
    assert len(seq) == 24 and all(im.size == (160, 120) for im in seq), name
    assert all(a.tobytes() == b.tobytes() for a, b in zip(seq, scene(160, 120, 24, 1))), (name, "same seed, same frames")
    steps = [diff(a, b) for a, b in zip(seq, seq[1:])]
    assert min(steps) > 0.05, (name, "every frame moves", min(steps))
    # Loops: the jump from the last frame back to the first is a normal step, not a cut and not a repeat.
    assert 0.05 < diff(seq[-1], seq[0]) <= 1.5 * max(steps), (name, diff(seq[-1], seq[0]), max(steps))

# frames() keeps the loop length when the fps changes.
assert len(frames("cube", fps=50)) == 2 * DEFAULTS["cube"][2]

# CLI: --scene needs no input file and writes a looping GIF; a bad name lists the scenes.
tmp = tempfile.mkdtemp()
out = os.path.join(tmp, "cube.gif")
main(["--scene", "cube", "-w", "30", "--mode", "braille", "-o", out])
gif = Image.open(out)
assert gif.n_frames > 40 and gif.info.get("loop") == 0
assert len({f.convert("RGB").tobytes() for f in ImageSequence.Iterator(gif)}) > 10, "frames differ"
# A scene file drawn on request: --scene takes its path. A file with no @scene, or broken code, is a usage error.
good, empty, broken = (os.path.join(tmp, f) for f in ("blob.py", "empty.py", "broken.py"))
with open(good, "w") as f:
    f.write("""import math
from PIL import Image, ImageDraw
from scenes import TAU, scene

@scene(80, 60, 20, 10)
def blob(w, h, n, seed):
    out = []
    for k in range(n):
        im = Image.new("RGB", (w, h))
        x = w / 2 + math.sin(TAU * k / n) * w / 4
        ImageDraw.Draw(im).ellipse((x - 10, h / 2 - 10, x + 10, h / 2 + 10), fill=(255, 255, 255))
        out.append(im)
    return out
""")
open(empty, "w").write("x = 1\n")
open(broken, "w").write("def (\n")
out = os.path.join(tmp, "blob.gif")
main(["--scene", good, "-w", "20", "-o", out])
assert Image.open(out).n_frames > 10 and "blob" in SCENES
for argv in (["--scene", "nope"], [], ["x.gif", "--scene", "cube"], ["--scene", empty], ["--scene", broken],
             ["--scene", os.path.join(tmp, "missing.py")]):
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            main(argv)
    except SystemExit as e:
        assert e.code == 2, argv
    else:
        raise AssertionError(argv)
print("ok")
