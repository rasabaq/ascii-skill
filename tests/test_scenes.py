# /// script
# dependencies = ["pillow>=10.1"]
# ///
"""Run: uv run tests/test_scenes.py"""
import contextlib
import io
import os
import sys
import tempfile

from PIL import Image, ImageChops, ImageStat

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "ascii-art", "scripts")
sys.path.insert(0, SCRIPTS)
import scenes  # noqa: E402
from animate import main  # noqa: E402
from scenes import DEFAULTS, SCENES, frames  # noqa: E402


def diff(a, b):
    """Mean absolute pixel difference, 0-255."""
    return sum(ImageStat.Stat(ImageChops.difference(a.convert("RGB"), b.convert("RGB"))).mean) / 3


# A scene file drawn on request: --scene takes its path. A file with no @scene, or broken code, is a usage error.
tmp = tempfile.mkdtemp()
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
gif = Image.open(out)
assert gif.n_frames > 10 and gif.info.get("loop") == 0 and "blob" in SCENES and set(SCENES) == set(DEFAULTS)
# The scene draws one loop: same seed, same frames; it moves; the last frame flows into the first.
seq = SCENES["blob"](80, 60, 20, 1)
assert all(a.tobytes() == b.tobytes() for a, b in zip(seq, SCENES["blob"](80, 60, 20, 1)))
steps = [diff(a, b) for a, b in zip(seq, seq[1:])]
assert max(steps) > 0.05 and 0.05 < diff(seq[-1], seq[0]) <= 1.5 * max(steps), steps
# frames() keeps the loop length when the fps changes.
assert len(frames("blob", fps=20)) == 2 * DEFAULTS["blob"][2]
for argv in (["--scene", "nope"], ["--scene", "fire"], [], ["x.gif", "--scene", good], ["--scene", empty], ["--scene", broken],
             ["--scene", os.path.join(tmp, "missing.py")]):
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            main(argv)
    except SystemExit as e:
        assert e.code == 2, argv
    else:
        raise AssertionError(argv)
# The donut example loads like any scene file and draws frames of the size it declares.
name = scenes.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "examples", "donut.py"))
w, h = DEFAULTS[name][:2]
donut = SCENES[name](w, h, 3, 0)
assert name == "donut" and len(donut) == 3 and all(im.size == (w, h) for im in donut)
print("ok")
