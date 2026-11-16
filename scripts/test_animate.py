# /// script
# dependencies = ["pillow>=10.1"]
# ///
"""Run: uv run scripts/test_animate.py"""
import contextlib
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from argparse import Namespace

from PIL import Image, ImageDraw, ImageSequence

sys.path.insert(0, os.path.dirname(__file__))
from animate import (MARK2, background, html_frame, main, shared_lut, snap, steady, subject_masks,  # noqa: E402
                     timeline, to_html_player, video_frames)
from ascii import convert  # noqa: E402

# A 3-frame GIF: a white box moving over a dim gradient, with uneven delays.
frames = []
for k in range(3):
    im = Image.linear_gradient("L").rotate(90).resize((80, 40)).point(lambda v: v // 2).convert("RGB")
    ImageDraw.Draw(im).rectangle((10 + 20 * k, 10, 25 + 20 * k, 25), fill="white")
    frames.append(im)
tmp = tempfile.mkdtemp()
src = os.path.join(tmp, "in.gif")
frames[0].save(src, save_all=True, append_images=frames[1:], duration=[100, 200, 300], loop=0)

main([src, "-o", os.path.join(tmp, "out.gif"), "-w", "20"])
out = Image.open(os.path.join(tmp, "out.gif"))
assert [f.info["duration"] for f in ImageSequence.Iterator(out)] == [100, 200, 300]
assert out.info["loop"] == 0, "loops forever"

main([src, "-o", os.path.join(tmp, "out.html"), "-w", "20"])
page = open(os.path.join(tmp, "out.html"), encoding="utf-8").read()
F, I, D = json.loads(re.search(r"const \[F, I, D\] = (.*), a =", page).group(1))
assert len(I) == 3 and D == [100, 200, 300], (I, D)

# --fps resamples, --start/--duration cut, the cap truncates.
ten = [(None, 100)] * 10
assert len(timeline(ten, 0, 0, 20, 300)[0]) == 20
assert len(timeline(ten, 200, 300, None, 300)[0]) == 3
assert timeline(ten, 0, 0, None, 4) == ([[None, 100]] * 4, True)
# 60 fps in GIF: no frame under 20 ms and the total length is kept.
keep, durs = snap(list(range(60)), [1000 / 60] * 60, 10, 2)
assert min(durs) >= 20 and sum(durs) == 1000, durs

# One shared tonal range: a blinking bright box must not change the dim background.
blink = [frames[0], frames[0].copy()]
ImageDraw.Draw(blink[0]).rectangle((0, 0, 79, 39), fill=(60, 60, 60))
ImageDraw.Draw(blink[0]).rectangle((0, 0, 10, 10), fill="white")
blink[1].paste((60, 60, 60), (0, 0, 80, 40))
sky = Image.new("RGB", (40, 40), (20, 20, 30))
sky.paste((200, 200, 200), (0, 20, 40, 40))
r, g, b = sky.point(shared_lut([sky])).getpixel((0, 39))
assert r == g == b, "the shared stretch keeps hues: gray stays gray"
lut = shared_lut(blink)
rows = [convert(b.point(lut), 20, autocontrast=False)[3] for b in blink]
assert rows[0][-5:] == rows[1][-5:], "background stays the same"

# Halfblock rows keep their colored spaces, and the player's JS has no raw newline inside a regex.
hb = [[("▀", (255, 0, 0), (0, 0, 255))] * 3, [("▀", (0, 255, 0), (0, 0, 0))] * 3]
assert html_frame(hb, None).split("\n")[0] == MARK2 + "f0000f   "
page = to_html_player([hb], [100], "black", None, 12, 0.5)
assert re.search(r"replace\(/\\n/g", page) and not re.search(r"replace\(/\n", page)

# Tiles: square tiles in GIF and HTML, and each cell keeps its random glyph from frame to frame.
main([src, "--mode", "tiles", "-w", "8", "-o", os.path.join(tmp, "tiles.gif")])
assert Image.open(os.path.join(tmp, "tiles.gif")).size == (8 * 48, 4 * 48)
main([src, "--mode", "tiles", "-w", "8", "-o", os.path.join(tmp, "tiles.html")])
g1, g2 = (convert(f, 8, mode="tiles") for f in frames[:2])
assert g1 != g2 and [c[0] for r in g1 for c in r] == [c[0] for r in g2 for c in r], "tile glyphs do not flicker"

# A still image plus --effect makes a looping intro that ends on the art.
still = os.path.join(tmp, "still.png")
Image.new("RGB", (40, 30), (200, 120, 40)).save(still)
main([still, "--effect", "decode", "--mode", "halfblock", "-w", "10", "-o", os.path.join(tmp, "fx.gif")])
fx = Image.open(os.path.join(tmp, "fx.gif"))
assert fx.n_frames > 10 and fx.info.get("loop") == 0


def player_rows(args, path):
    """Run main to an HTML player; return each shown frame as text rows without color marks."""
    main(args + ["-o", path])
    F, I, D = json.loads(re.search(r"const \[F, I, D\] = (.*), a =", open(path, encoding="utf-8").read()).group(1))
    return [re.sub("\ue000...", "", F[i]).split("\n") for i in I]


# Noisy still camera: grey wall with grain, and a white square that moves 6 px per frame.
rng = random.Random(1)
clip = []
for k in range(12):
    im = Image.new("L", (80, 40))
    im.putdata([100 + rng.randint(-4, 4) for _ in range(80 * 40)])
    im = im.convert("RGB")
    ImageDraw.Draw(im).rectangle((4 + 6 * k, 12, 15 + 6 * k, 27), fill="white")
    clip.append(im)
held = steady(clip, 6)
wall = (0, 33, 79, 39)  # never touched by the square
assert all(h.crop(wall).tobytes() == held[0].crop(wall).tobytes() for h in held), "grain no longer flickers"
assert all(h.getpixel((9 + 6 * k, 20)) == (255, 255, 255) for k, h in enumerate(held)), "the square is followed"
assert held[5].getpixel((9, 20))[0] < 110, "and leaves no trail"
blue = steady([Image.new("RGB", (4, 4)), Image.new("RGB", (4, 4), (0, 0, 60))], 6)
assert blue[1].getpixel((1, 1)) == (0, 0, 60), "a change in blue alone counts"

# --subject: the median background has no square, so the mask keeps the square and blanks the grainy wall.
masks = subject_masks(clip, background(clip, 30), 30)
assert masks[3].getpixel((27, 20)) == 255 and masks[3].crop(wall).getextrema()[1] < 16
noisy = os.path.join(tmp, "noisy.gif")
clip[0].save(noisy, save_all=True, append_images=clip[1:], duration=100, loop=0)
rows = player_rows([noisy, "--subject", "--mode", "braille", "-w", "40"], os.path.join(tmp, "subj.html"))
assert all(not "".join(r[-2:]).strip() for r in rows), "the wall is blank"
assert all("".join(r).strip() for r in rows), "the square is drawn"

# Braille: one dot threshold for the clip, so a big bright box blinking on the left leaves the right side's dots alone.
blinky = os.path.join(tmp, "blink.gif")
on = frames[0].copy()
ImageDraw.Draw(on).rectangle((0, 0, 39, 39), fill="white")
frames[0].save(blinky, save_all=True, append_images=[on, frames[0], on], duration=100, loop=0)
rows = player_rows([blinky, "--mode", "braille", "-w", "20"], os.path.join(tmp, "blink.html"))
assert len({tuple(line.ljust(20)[12:] for line in r) for r in rows}) == 1, rows

# Video: non-square pixels are shown at their display shape.
if shutil.which("ffmpeg") and shutil.which("ffprobe"):
    vid = os.path.join(tmp, "anamorphic.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=360x270:rate=10:duration=0.3",
                    "-vf", "setsar=4/3", "-c:v", "libx264", "-pix_fmt", "yuv420p", vid], check=True)
    img, _ = next(video_frames(vid, Namespace(fps=None, start=0, duration=None), 480, 5))
    assert abs(img.width / img.height - 16 / 9) < 0.02, img.size
# Bad option mixes stop with one clear line, never a traceback or a silent ignore.
svg = os.path.join(tmp, "logo.svg")
with open(svg, "w") as f:
    f.write('<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="8" height="8"/></svg>')
for argv, says in (([src, "--subject", "--subject-cut", "0"], "--subject-cut > 0"),
                   (["--scene", "fire", "--duration", "1"], "--scene is one short loop"),
                   ([svg], "convert it to PNG")):
    with contextlib.redirect_stderr(io.StringIO()) as err:
        try:
            main(argv + ["-o", os.path.join(tmp, "bad.gif")])
        except SystemExit as e:
            assert e.code == 2, argv
        else:
            raise AssertionError(argv)
    assert says in err.getvalue(), (argv, err.getvalue())
print("ok")
