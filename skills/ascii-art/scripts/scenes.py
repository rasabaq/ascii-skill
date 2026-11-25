"""Looping animations drawn in code, so animate.py can make ASCII motion with no footage.

    uv run scripts/animate.py --scene seaweed.py -o seaweed.gif

A scene is `scene(w, h, n, seed) -> list of n images`. It draws one full loop: frame i is time t = i / n,
so frame n would be frame 0 again and the last frame flows into the first.

A scene lives in its own file, written for a subject drawn on request (see load()). The file does
`from scenes import SS, TAU, _shrink, scene` and puts `@scene(w, h, frames, fps)` on its drawing function.
"""
import importlib.util
import math

from PIL import Image

SCENES = {}  # name -> scene function
DEFAULTS = {}  # name -> (width, height, frames, fps)
TAU = 2 * math.pi
SS = 2  # vector scenes draw at 2x and shrink, for smooth edges


def scene(w, h, n, fps):
    def add(fn):
        SCENES[fn.__name__], DEFAULTS[fn.__name__] = fn, (w, h, n, fps)
        return fn
    return add


def load(path):
    """Run a scene file and return the name of the scene it adds. The file does `from scenes import scene`
    and puts `@scene(w, h, frames, fps)` on one function."""
    before = dict(SCENES)
    spec = importlib.util.spec_from_file_location("scene_file", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    new = [k for k, fn in SCENES.items() if before.get(k) is not fn]
    if not new:
        raise ValueError("it adds no scene: put @scene(w, h, frames, fps) on its drawing function")
    return new[-1]


def frames(name, seed=0, fps=None):
    """(RGB image, ms) pairs for animate.py. Another fps keeps the loop length and changes the frame count."""
    w, h, n, rate = DEFAULTS[name]
    fps = fps or rate
    n = max(2, round(n * fps / rate))
    return [(im.convert("RGB"), 1000 / fps) for im in SCENES[name](w, h, n, seed)]


def _shrink(im, w, h):
    return im.resize((w, h), Image.Resampling.LANCZOS)
