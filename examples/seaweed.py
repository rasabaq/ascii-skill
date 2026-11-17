"""Kelp swaying on the sea floor while bubbles rise: an example scene file for --scene.

    uv run scripts/animate.py --scene examples/seaweed.py -w 80 -o seaweed.gif
"""
import math
import random

from PIL import Image, ImageDraw

from scenes import SS, TAU, _shrink, scene


@scene(320, 240, 75, 25)
def seaweed(w, h, n, seed):
    """Kelp strands sway as a wave runs up each stalk; bubbles rise and wobble."""
    rng = random.Random(seed)
    W, H = w * SS, h * SS
    count = 7
    strands = [(((i + 0.5) / count + rng.uniform(-0.04, 0.04)) * W, rng.uniform(0.5, 0.9) * H, rng.random(),
                rng.uniform(0.7, 1)) for i in range(count)]  # spread evenly, so no two stalks hide each other
    bubbles = [(rng.random() * W, rng.random(), rng.uniform(5, 9) * SS, rng.choice((1, 2))) for _ in range(10)]
    out = []
    for k in range(n):
        t = k / n
        im = Image.new("RGB", (W, H))
        draw = ImageDraw.Draw(im)
        for x0, height, phase, lum in strands:
            pts = []
            for i in range(41):
                s = i / 40
                sway = math.sin(TAU * (t - 0.7 * s + phase)) * 0.07 * W * s ** 1.4  # a wave runs up the stalk
                pts.append((x0 + sway, H - s * height))
            for i, (a, b) in enumerate(zip(pts, pts[1:])):
                s = i / 40
                ink = (round((60 + 90 * s) * lum), round((170 + 85 * s) * lum), round(70 * lum))
                draw.line([a, b], fill=ink, width=round((16 - 10 * s) * SS))
                if i % 6 == 3:  # a leaf on alternating sides, trailing the sway
                    side = 1 if i % 12 == 3 else -1
                    lx = b[0] + side * 22 * SS + (b[0] - a[0]) * 3
                    draw.polygon([b, (lx, b[1] - 10 * SS), (b[0] + side * 4 * SS, b[1] - 18 * SS)], fill=ink)
        draw.rectangle((0, H - 10 * SS, W, H), fill=(200, 170, 110))  # sand
        for x, p0, r, speed in bubbles:  # speed is a whole number of trips per loop, so the loop closes
            y = H * (1 - (p0 + speed * t) % 1.0)
            x += math.sin(TAU * (2 * t + p0)) * 4 * SS
            draw.ellipse((x - r, y - r, x + r, y + r), outline=(190, 230, 255), width=2 * SS)
        out.append(_shrink(im, w, h))
    return out
