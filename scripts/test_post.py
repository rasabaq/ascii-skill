# /// script
# dependencies = ["pillow>=10.1"]
# ///
"""Run: uv run scripts/test_post.py"""
import argparse
import contextlib
import io
import os
import sys
import tempfile
import time

from PIL import Image, ImageChops, ImageDraw, ImageSequence

sys.path.insert(0, os.path.dirname(__file__))
import ascii  # noqa: E402
import animate  # noqa: E402
from post import EFFECTS, apply, parse  # noqa: E402

assert parse("grain, crt") == ("crt", "grain") == parse("crt,grain"), "fixed order, whatever was typed"
for bad in ("nope", "crt,glow", ","):
    try:
        parse(bad)
    except argparse.ArgumentTypeError as e:
        assert "scan" in str(e) and "grain" in str(e), e  # lists the valid names
    else:
        raise AssertionError(bad)

# Two frames that differ only in a box on the right: the left half must stay exactly the same,
# so post effects never make still areas flicker. Every effect keeps the size and is deterministic.
a = Image.new("RGB", (420, 280), (40, 40, 40))
ImageDraw.Draw(a).text((20, 20), "STILL TEXT", fill="white")
b = a.copy()
ImageDraw.Draw(b).rectangle((330, 100, 380, 150), fill=(255, 200, 0))
everything = tuple(EFFECTS)
for names in [(n,) for n in EFFECTS] + [everything]:
    x, y = apply(a, names, 14), apply(b, names, 14)
    assert x.size == a.size and x.mode == "RGB", names
    assert x.tobytes() == apply(a, names, 14).tobytes(), names
    assert x.crop((0, 0, 200, 280)).tobytes() == y.crop((0, 0, 200, 280)).tobytes(), names
    assert x.tobytes() != a.tobytes(), names + ("does nothing",)
assert apply(a, (), 14) is a
assert apply(Image.new("RGBA", (40, 30)), ("scan",), 10).mode == "RGB", "transparency becomes black"
mid = apply(a, ("chroma",), 14).getpixel((210, 140))
assert mid == a.getpixel((210, 140)), "no fringes in the centre"
t = time.time()
for _ in range(20):
    apply(b, everything, 14)
assert time.time() - t < 2, "fast enough for long animations"

# CLI: ascii.py keeps the image size; bad names and text outputs are usage errors (exit 2).
tmp = tempfile.mkdtemp()
src = os.path.join(tmp, "in.png")
Image.linear_gradient("L").resize((200, 100)).save(src)
ascii.main([src, "-w", "40", "-o", os.path.join(tmp, "plain.png")])
ascii.main([src, "-w", "40", "-o", os.path.join(tmp, "crt.png"), "--post", "crt,grain"])
assert Image.open(os.path.join(tmp, "plain.png")).size == Image.open(os.path.join(tmp, "crt.png")).size
for main, argv in ((ascii.main, ["--post", "crt,nope", "-o", "x.png"]), (ascii.main, ["--post", "crt", "-o", "x.html"]),
                   (animate.main, ["--post", "glow", "-o", "x.gif"]), (animate.main, ["--post", "scan", "-o", "x.html"])):
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            main([src] + argv)
    except SystemExit as e:
        assert e.code == 2, argv
    else:
        raise AssertionError(argv)

# animate.py: a GIF with post effects is byte-for-byte repeatable, and still areas keep their colors.
frames = []
for k in range(4):
    im = Image.new("RGB", (160, 80), (20, 30, 60))
    ImageDraw.Draw(im).ellipse((10, 10, 50, 50), fill=(250, 250, 250))
    ImageDraw.Draw(im).rectangle((100 + 10 * k, 20, 120 + 10 * k, 40), fill=(255, 120, 0))
    frames.append(im)
src = os.path.join(tmp, "in.gif")
frames[0].save(src, save_all=True, append_images=frames[1:], duration=100, loop=0)
outs = []
for n in (1, 2):
    out = os.path.join(tmp, "out%d.gif" % n)
    animate.main([src, "-w", "32", "-o", out, "--post", "crt,bloom,grain"])
    outs.append(open(out, "rb").read())
assert outs[0] == outs[1], "deterministic"
gif = [f.convert("RGB") for f in ImageSequence.Iterator(Image.open(os.path.join(tmp, "out1.gif")))]
assert len(gif) == 4
left = [f.crop((0, 0, gif[0].width // 3, gif[0].height)).tobytes() for f in gif]
assert len(set(left)) == 1, "the still left part does not flicker"
print("ok")
