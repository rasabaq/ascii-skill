#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow>=10.1"]
# ///
"""Turn a GIF, animated WebP/APNG or video into ASCII animation.

    uv run scripts/animate.py cat.gif                     # play in the terminal (Ctrl-C stops)
    uv run scripts/animate.py cat.gif -o out.gif          # also .webp, .mp4 (needs ffmpeg), .html
    uv run scripts/animate.py clip.mp4 -o out.html --start 2 --duration 5 --fps 12
    uv run scripts/animate.py photo.jpg --effect matrix -o intro.gif   # animate a still image
    uv run scripts/animate.py --scene donut -o donut.gif           # a looping animation drawn in code
"""
import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import time

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageSequence, ImageStat

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ascii import (CELL_W, CHARSETS, HALF, COLORS, MAX_SIDE, SUBPIXELS, _corner, add_poster_args, convert,  # noqa: E402
                   POSTER_BG, RETRO, parse_look, poster_defaults, rgb, snap, snap_grid, to_ansi, to_png)
import effects  # noqa: E402
import post  # noqa: E402
import scenes  # noqa: E402

MARK = "\ue000"  # private-use char: never in a ramp, 3 bytes in UTF-8. MARK + 3 hex = new ink color.
MARK2 = "\ue001"  # MARK2 + 6 hex = two-color (halfblock) cells: top and bottom color.
MARK3 = "\ue002"  # MARK3 + 6 hex = glyph on its own background: ink and background color.
HOLD_MS = 1500  # an effect holds the finished art this long before it loops
MAX_MOVING = 0.4  # --subject gives up when more than this share of the picture's edges changes: the camera moves
MAX_BYTES = 3_000_000_000  # ponytail: GIF/WebP encoders keep every rendered frame in RAM; refuse past ~3 GB


def pil_frames(path, back, px):
    """Yield (image, ms) for every frame Pillow can read (GIF, WebP, APNG, or a still image)."""
    for f in ImageSequence.Iterator(Image.open(path)):
        img = prepare(f, back, px)  # loads the frame; WebP sets its duration only then
        d = f.info.get("duration") or 0
        yield img, d if d > 10 else 100  # browsers show GIF delays of 0-10 ms as 100 ms


def video_frames(path, a, px, cap):
    """Yield (image, ms) from ffmpeg as a stream of PPM frames, already cut and resampled."""
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not (ffmpeg and ffprobe):
        raise ValueError("cannot read %s as an image; video input needs ffmpeg and ffprobe" % path)
    probe = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=avg_frame_rate", "-of", "csv=p=0", path], capture_output=True, text=True)
    num, _, den = probe.stdout.strip().partition("/")
    if probe.returncode or not num:
        raise ValueError("cannot read %s: not an image or video" % path)
    rate = a.fps or (float(num) / float(den or 1) if num != "0" else 25)
    # Deinterlace only frames flagged as interlaced (old TV and DV footage), and scale by the display shape:
    # some video stores non-square pixels (sample aspect ratio), which would squash the art.
    vf = "yadif=deint=interlaced," + ("fps=%g," % a.fps if a.fps else "") + \
        "scale='min(iw*sar,%d)':'ow/dar':flags=area,setsar=1" % px
    cmd = [ffmpeg, "-v", "error", "-ss", str(a.start), "-i", path] + (["-t", str(a.duration)] if a.duration else [])
    cmd += ["-vf", vf, "-frames:v", str(cap + 1), "-f", "image2pipe", "-c:v", "ppm", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        while True:
            magic = proc.stdout.readline()
            if not magic:
                break
            w, h = map(int, proc.stdout.readline().split())
            proc.stdout.readline()  # max value, always 255
            yield Image.frombytes("RGB", (w, h), proc.stdout.read(w * h * 3)), 1000 / rate  # already small
    finally:
        proc.kill()
        err = proc.communicate()[1].decode(errors="replace").strip()
    if proc.returncode not in (0, -9) and err:
        raise ValueError("ffmpeg: " + err.splitlines()[-1])


def timeline(frames, start_ms, length_ms, fps, cap):
    """Keep frames inside [start, start+length), resample to fps if given. Returns (frames, truncated)."""
    out, t, nxt = [], 0.0, start_ms
    end = start_ms + length_ms if length_ms else float("inf")
    for img, ms in frames:
        a, b = t, t + ms
        t = b
        if b <= start_ms:
            continue
        if a >= end:
            break
        if fps:
            while nxt < min(b, end):
                out.append([img, 1000 / fps])
                nxt += 1000 / fps
        else:
            out.append([img, min(b, end) - max(a, start_ms)])
        if len(out) > cap:
            break
    return out[:cap], len(out) > cap


def shared_lut(images, cutoff=1):
    """One autocontrast lookup table (same math as ImageOps.autocontrast) over all frames, so brightness never pumps."""
    hist = [sum(col) for col in zip(*(im.histogram() for im in images))]
    lut = []
    for c in range(3):
        h = hist[c * 256:(c + 1) * 256]
        cut, acc, lo, hi = sum(h) * cutoff // 100, 0, 0, 255
        for lo in range(256):
            acc += h[lo]
            if acc > cut:
                break
        acc = 0
        for hi in range(255, -1, -1):
            acc += h[hi]
            if acc > cut:
                break
        scale = 255 / (hi - lo) if hi > lo else 1
        lut += [min(255, max(0, int((v - lo) * scale))) if hi > lo else v for v in range(256)]
    return lut


def background(images, cut, n=25):
    """What a still camera sees behind the subject: the per-pixel median of up to `n` frames spread over the clip.
    A second pass hides what the first one found as subject behind black and white in turn, which cancel out in
    the median, so a figure that stays in the same spot in most frames does not end up in the background."""
    s = images[::-(-len(images) // n)]
    return median([Image.composite(Image.new("RGB", im.size, (255 * (i % 2),) * 3), im, m.point(lambda v: 255 * (v > 127)))
                   for i, (im, m) in enumerate(zip(s, subject_masks(s, median(s), cut)))])


def median(s):
    """Per-pixel median: an odd-even transposition sort of lighter/darker, so all the work is in Pillow's C code."""
    s = list(s)
    for r in range(len(s)):
        for i in range(r % 2, len(s) - 1, 2):
            s[i], s[i + 1] = ImageChops.darker(s[i], s[i + 1]), ImageChops.lighter(s[i], s[i + 1])
    return s[len(s) // 2]


def subject_masks(images, bg, cut):
    """One L mask per frame: 255 where the frame differs from `bg` by more than `cut` (0-255), with a soft edge.
    Lone noisy pixels are dropped, the mask grows a little, and holes it encloses are filled, so the figure
    stays solid even where it covers the same spot in most frames (then the median holds part of it)."""
    ramp = [min(255, max(0, round((v - cut / 2) * 510 / cut))) for v in range(256)]
    gray, masks = bg.convert("L"), []
    for im in images:
        # Old film and auto exposure make a whole frame lighter or darker: take that shift out first.
        shift = ImageStat.Stat(ImageChops.subtract(im.convert("L"), gray, 1, 128)).median[0] - 128
        m = change(im.point(lambda v: v - shift), bg)
        m = m.reduce(2).point(ramp).filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.MaxFilter(3))  # cell size
        m = ImageChops.lighter(m, holes(m)).filter(ImageFilter.GaussianBlur(1))
        masks.append(m.resize(im.size, Image.Resampling.BILINEAR))
    return masks


def holes(mask, side=64):
    """Parts of `mask` that the mask encloses: flood the outside from the edges at low resolution (floodfill is Python)."""
    k = min(1, side / max(mask.size))
    small = mask.resize((max(1, round(mask.width * k)), max(1, round(mask.height * k))), Image.Resampling.BOX)
    small = ImageOps.expand(small.point(lambda v: 255 if v > 127 else 0), 1, 0)
    ImageDraw.floodfill(small, (0, 0), 128)
    inside = small.crop((1, 1, small.width - 1, small.height - 1)).point(lambda v: 255 if v == 0 else 0)
    return inside.resize(mask.size, Image.Resampling.BILINEAR)


def change(a, b):
    """Per pixel, the biggest change in any channel (luma would hide a change in blue)."""
    r, g, b = ImageChops.difference(a, b).split()
    return ImageChops.lighter(ImageChops.lighter(r, g), b)


def steady(images, cut):
    """Keep each pixel until it moves more than `cut` (0-255) from the value shown, so video noise does not
    make glyphs flicker in still areas. Real motion changes pixels by much more, so it passes at once."""
    out = images[:1]
    for im in images[1:]:
        moved = change(im, out[-1]).filter(ImageFilter.BoxBlur(1))  # blur: grain averages out
        out.append(Image.composite(im, out[-1], moved.point(lambda v: 255 * (v > cut))))
    return out


def prepare(img, back, px):
    """Flatten transparency onto the background and shrink to `px` wide, so 300 frames stay small in RAM.
    Always returns a new image: ImageSequence reuses one object for every frame."""
    img = img.convert("RGBA")
    img = Image.alpha_composite(Image.new("RGBA", img.size, back + (255,)), img).convert("RGB")
    if img.width > px:
        img = img.resize((px, max(1, round(img.height * px / img.width))), Image.Resampling.BOX)
    return img


def html_frame(grid, fg, boxed=False, tiles=False):
    """One frame as HTML text where MARK + 3 hex digits starts a new color; the player turns marks into spans.
    Colors are rounded to 12 bits so neighbouring cells merge into one run. `boxed` puts each glyph in its
    own <b> box (glyphs narrower than the cell); `tiles` gives every glyph-on-background cell its own span."""
    esc = (lambda t: "".join("<b>%s</b>" % html.escape(c) for c in t)) if boxed else html.escape
    lines = []
    for row in grid:
        parts, run, color = [], "", None
        for cell in row:
            ch = cell[0]
            if len(cell) > 2:  # halfblock: the player paints it as a background, so the text is a space
                pair = "".join("%x%x%x" % tuple((v + 8) // 17 for v in c) for c in cell[1:3])
                ch, col = (" ", MARK2 + pair) if ch == HALF else (ch, MARK3 + pair)
            else:
                col = None if fg else MARK + "%x%x%x" % tuple((v + 8) // 17 for v in cell[1])
            # A box ends with its word (words); every tile is its own span (tiles).
            if (ch != " " or len(cell) > 2 or color and color[0] == MARK3) and (col != color or tiles and col and col[0] == MARK3):
                parts.append(esc(run))
                parts.append(col or "")
                run, color = "", col
            run += ch
        parts.append(esc(run if color and color[0] in (MARK2, MARK3) else run.rstrip()))  # two-color spaces are cells
        lines.append("".join(parts))
    return "\n".join(lines)


def to_html_player(grids, durs, bg, fg, font_size, aspect, gap=0):
    """`gap` (px) parts the boxes of glyph-on-background cells from each other; (0, y) only parts stacked rows (words mode)."""
    cw = font_size * CELL_W
    gx, gy = gap if isinstance(gap, tuple) else (gap, gap)
    size = min(font_size, round(cw / aspect / 1.2))  # glyphs shrink to fit short cells, as in ascii.to_html
    boxed = size < font_size
    uniq, idx = {}, []
    for g in grids:  # identical frames are stored once
        idx.append(uniq.setdefault(html_frame(g, fg, boxed, gx > 0), len(uniq)))
    data = json.dumps([list(uniq), idx, [round(d) for d in durs]], ensure_ascii=False).replace("</", "<\\/")
    back = "transparent" if bg == "none" else "#%02x%02x%02x" % rgb(bg)
    ink = "#%02x%02x%02x" % fg if fg else "inherit"  # without --fg every glyph has its own span color
    shadow = "#000" if bg == "none" else back
    edge = ("i.t{box-shadow:inset 0 0 0 %dpx %s;border-radius:%dpx}" % (gx, shadow, gx + _corner(round(cw), gx)) if gx
            else "i.t{box-shadow:inset 0 %dpx %s,inset 0 -%dpx %s}" % (gy, shadow, gy, shadow) if gy else "")
    box = ("%.3f" % (cw / size), "text-align:center;") if boxed else (CELL_W, "")
    return """<!doctype html><meta charset="utf-8"><title>ASCII animation</title>
<style>body{margin:0;background:%s;color:%s}i{font-style:normal}%s
i.h{display:inline-block;vertical-align:top;height:%.3fem}b{display:inline-block;width:%sem;%sfont-weight:normal}
pre{margin:0;padding:16px;font:%dpx/%.3f Menlo,Consolas,'DejaVu Sans Mono',monospace;cursor:pointer}
button{position:fixed;right:12px;bottom:12px;font:13px system-ui,sans-serif;padding:6px 14px;border-radius:6px;
border:1px solid #8888;background:#222c;color:#eee;cursor:pointer}</style>
<pre id="a" title="Click or press space to play or pause"></pre><button id="b">Pause</button>
<script>
const [F, I, D] = %s, a = document.getElementById("a"), b = document.getElementById("b");
let i = 0, t = null, due = 0;
function step() {
  a.innerHTML = F[I[i]].replace(/\\n/g, "</i>\\n").replace(/[\u2800-\u28ff]/g, "<b>$&</b>").replace(/\ue000(...)/g, '</i><i style="color:#$1">')
    .replace(/\ue001(...)(...)/g, '</i><i class="h" style="background:linear-gradient(#$1 50%%,#$2 50%%)">')
    .replace(/\ue002(...)(...)/g, '</i><i class="h t" style="color:#$1;background:#$2">');
  due += D[i]; i = (i + 1) %% I.length;
  t = setTimeout(step, Math.max(0, due - performance.now()));
}
function toggle() {
  if (t) { clearTimeout(t); t = null; b.textContent = "Play"; }
  else { b.textContent = "Pause"; due = performance.now(); step(); }
}
a.onclick = b.onclick = toggle;
onkeydown = e => { if (e.key === " ") { e.preventDefault(); toggle(); } };
due = performance.now(); step();
</script>
""" % ((back, ink, edge, cw / aspect / size) + box + (size, cw / aspect / size, data))


def snap(images, durs, unit, least):
    """Round frame start times (not each duration) to the format's clock tick, so the total never drifts.
    Frames that would start less than `least` ticks after the previous kept one are dropped."""
    keep, starts, t = [], [], 0
    for img, d in zip(images, durs):
        tick = round(t / unit)
        if not starts or tick - starts[-1] >= least:
            keep.append(img)
            starts.append(tick)
        t += d
    starts.append(max(round(t / unit), starts[-1] + least))
    return keep, [(b - a) * unit for a, b in zip(starts, starts[1:])]


def one_palette(images, budget=4_000_000):
    """GIF: map every frame to one shared 256-color palette, with no dither. A pixel that does not change
    keeps its palette entry, so still areas never flicker (Pillow would pick a new palette per frame).
    The palette comes from a sheet of up to 16 frames, scaled with nearest so it only holds real colors."""
    pick = images[::max(1, len(images) // 16)]
    w, h = pick[0].size
    k = min(1, (budget / (w * h * len(pick))) ** 0.5)
    sw, sh = max(1, round(w * k)), max(1, round(h * k))
    sheet = Image.new("RGB", (sw, sh * len(pick)))
    for i, im in enumerate(pick):
        sheet.paste(im.convert("RGB").resize((sw, sh), Image.Resampling.NEAREST), (0, i * sh))
    pal = sheet.quantize(256)
    return [im.convert("RGB").quantize(palette=pal, dither=Image.Dither.NONE) for im in images]


def to_mp4(images, durs, path, fps):
    """Constant-rate H.264: each frame is repeated to fill its duration on a 1/fps grid."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError(".mp4 output needs ffmpeg")
    fps = fps or min(60, 1000 / min(durs))
    w, h = images[0].size
    proc = subprocess.Popen([ffmpeg, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (w, h),
                             "-r", "%.6g" % fps, "-i", "-", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264",
                             "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", path],
                            stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    t = k = 0
    try:
        for img, d in zip(images, durs):
            t += d
            raw = img.convert("RGB").tobytes()
            while k * 1000 / fps < t - 1e-6:
                proc.stdin.write(raw)
                k += 1
        proc.stdin.close()
    except BrokenPipeError:
        pass
    err = proc.communicate()[1].decode(errors="replace").strip()
    if proc.returncode:
        raise ValueError("ffmpeg: " + (err.splitlines() or ["failed"])[-1])


def play(texts, durs):
    out = sys.stdout
    out.write("\x1b[?25l\x1b[2J")
    try:
        due = time.monotonic()
        while True:
            for s, d in zip(texts, durs):
                out.write("\x1b[H" + s)
                out.flush()
                due += d / 1000
                time.sleep(max(0, due - time.monotonic()))
            if not out.isatty():  # piped: play once
                break
    except KeyboardInterrupt:
        pass
    finally:
        out.write("\x1b[0m\x1b[?25h\n")
        out.flush()


def main(argv=None):
    p = argparse.ArgumentParser(description="Turn a GIF, WebP, APNG or video into ASCII animation.")
    p.add_argument("input", nargs="?", help="animated GIF/WebP/APNG, or any video ffmpeg can read")
    p.add_argument("-o", "--output", help="write .gif, .webp, .mp4 or .html; default plays in the terminal")
    p.add_argument("-w", "--width", type=int, help="columns (default 100; terminal: fit the window)")
    p.add_argument("-c", "--charset", help="%s, or your own ramp (default standard; tiles: random glyphs)" % ", ".join(CHARSETS))
    p.add_argument("--aspect", type=float, help="char width / height (default 0.5; tiles, led, dots: 1 for files)")
    p.add_argument("--contrast", type=float, default=1.0, help="1.0 = unchanged")
    p.add_argument("--brightness", type=float, default=1.0, help="1.0 = unchanged")
    p.add_argument("--invert", action="store_true", help="swap light and dark")
    p.add_argument("--dither", nargs="?", const="fs", choices=("fs", "bayer"),
                   help="Floyd-Steinberg dithering (crawls between frames); --dither bayer holds still")
    p.add_argument("--colors", choices=RETRO, help="snap every color to this retro palette")
    p.add_argument("--bg", help="black (default; %s in words and tiles mode), white, none (WebP/HTML only), or any color" % POSTER_BG)
    p.add_argument("--fg", help="one ink color: %s, or any color" % ", ".join(COLORS))
    p.add_argument("--font-size", type=int, help="glyph size in px for GIF/WebP/MP4/HTML (default 12; tiles: 80; led: 26; dots: 20)")
    p.add_argument("--fps", type=float, help="resample to this frame rate (default: keep source timing)")
    p.add_argument("--start", type=float, default=0, help="start at this second")
    p.add_argument("--duration", type=float, help="stop after this many seconds")
    p.add_argument("--max-frames", type=int, default=300, help="frame cap (default 300)")
    p.add_argument("--mode", choices=SUBPIXELS, default="ramp", help="ramp (default), shape, braille, halfblock, words, tiles, led or dots")
    p.add_argument("--sharpen", action="store_true", help="unsharp mask before shrinking, for crisper edges")
    p.add_argument("--effect", choices=effects.EFFECTS, help="animate a still image: %s" % ", ".join(effects.EFFECTS))
    p.add_argument("--gap", type=int, help="px of background around each tile (tiles: default 1); "
                   "words mode: px between boxes in stacked rows (default font size / 8)")
    p.add_argument("--scene", choices=scenes.SCENES, help="draw a looping animation instead of reading input: %s"
                   % ", ".join(scenes.SCENES))
    p.add_argument("--subject", action="store_true",
                   help="still camera: keep only what moves and draw it on a clean page (white if the background is light)")
    p.add_argument("--subject-cut", type=float, default=40, help="--subject: how much (0-255) a pixel must differ "
                   "from the still background to count as subject (default 40)")
    p.add_argument("--steady", type=float, default=6, help="keep a pixel until it changes by more than this (0-255), "
                   "so video noise does not make still areas flicker (default 6; 0 = off; grainy film: 16)")
    add_poster_args(p)
    p.add_argument("--post", type=post.parse, default=(), metavar="LIST",
                   help="GIF/WebP/MP4: post effects, comma separated: %s" % ", ".join(post.EFFECTS))
    a = parse_look(p, argv, (".gif", ".webp", ".mp4"))
    if bool(a.input) == bool(a.scene):
        p.error("give an input file or --scene NAME (one of: %s)" % ", ".join(scenes.SCENES))
    user_bg = a.bg
    ext = os.path.splitext(a.output or "")[1].lower()
    poster_defaults(a, bool(ext))
    if ext not in ("", ".gif", ".webp", ".mp4", ".html", ".htm"):
        p.error("unknown output extension %r: use .gif, .webp, .mp4 or .html" % ext)
    if a.post and ext not in (".gif", ".webp", ".mp4"):
        p.error("--post needs a .gif, .webp or .mp4 output")
    if a.font_size < 1 or a.max_frames < 1 or a.start < 0 or (a.fps is not None and a.fps <= 0) \
            or (a.duration is not None and a.duration <= 0) or (a.width is not None and not 1 <= a.width <= MAX_SIDE):
        p.error("need --font-size >= 1, --max-frames >= 1, --start >= 0, --fps > 0, --duration > 0, -w 1-%d" % MAX_SIDE)
    try:
        bg = "black" if a.bg == "none" else a.bg
        back = rgb(bg)
        fg = rgb(a.fg) if a.fg and a.mode != "words" else None  # word ink carries the image
        px = 2 * SUBPIXELS[a.mode][0] * (a.width or MAX_SIDE // 2)  # 2x the sampled pixels; convert() does the final resize
        if a.scene:  # frames drawn in code (scenes.py); --seed varies them, --fps keeps the loop length
            src = timeline(scenes.frames(a.scene, a.seed, a.fps), 0, 0, None, a.max_frames)
        else:
            try:
                Image.open(a.input).close()
                src = timeline(pil_frames(a.input, back, px), a.start * 1000, (a.duration or 0) * 1000, a.fps, a.max_frames)
            except Image.UnidentifiedImageError:
                src = timeline(video_frames(a.input, a, px, a.max_frames), 0, 0, None, a.max_frames)
        frames, truncated = src
        if not frames:
            raise ValueError("no frames in the chosen time range")
        images = [img for img, _ in frames]
        durs = [d for _, d in frames]
        if truncated:
            print("note: stopped at %d frames (%.1f s); raise --max-frames or use --start/--duration/--fps"
                  % (len(images), sum(durs) / 1000), file=sys.stderr)
        width = a.width
        if width is None and not ext:  # terminal: fit both columns and rows
            cols, lines = shutil.get_terminal_size()
            w, h = images[0].size
            width = max(1, min(cols - 1, int((lines - 1) * w / (h * a.aspect))))
        width = width or 100
        footage = not a.scene  # scenes are drawn clean, in their own colors: no steadying, stretch or cut-out
        if footage and a.steady and len(images) > 1:
            images = steady(images, a.steady)
        lut = shared_lut(images) if footage else list(range(256)) * 3
        images = [im.point(lut) for im in images]
        if footage and a.subject and len(images) > 1:
            still = background(images, a.subject_cut)
            masks = subject_masks(images, still, a.subject_cut)
            w, h = still.size  # with a still camera the picture's edges are mostly background
            dx, dy = max(1, w // 10), max(1, h // 10)
            ring = Image.new("L", (w, h), 255)
            ImageDraw.Draw(ring).rectangle((dx, dy, max(dx, w - 1 - dx), max(dy, h - 1 - dy)), fill=0)
            moving = sum(ImageStat.Stat(m, ring).mean[0] for m in masks) / len(masks) / 255
            if moving > MAX_MOVING:
                print("note: --subject skipped: %d%% of the picture's edges change, so the camera seems to move"
                      % (100 * moving), file=sys.stderr)
            else:
                if user_bg is None and a.mode not in ("words", "tiles"):  # a page in the background's own tone
                    a.bg = bg = "white" if ImageStat.Stat(still.convert("L")).mean[0] > 128 else "black"
                    back = rgb(bg)
                fill = Image.new("RGB", still.size, tuple(255 - v for v in back) if a.invert else back)
                images = [Image.composite(im, fill, m) for im, m in zip(images, masks)]
        cut = None
        if a.mode == "braille" and not a.dither and len(images) > 1:  # one dot threshold, so dots hold still
            lum = min(1, a.brightness * sum(ImageStat.Stat(im.convert("L")).mean[0] for im in images) / len(images) / 255)
            cut = min(0.75, max(0.25, lum if (sum(back) < 384) != a.invert else 1 - lum))

        def look(im, palette):
            return convert(im, width, a.charset, a.aspect, a.contrast, a.brightness, a.invert, a.dither,
                           bg, mode=a.mode, sharpen=a.sharpen, autocontrast=False, palette=palette, seed=a.seed,
                           words=a.words, accent=a.accent, accent_level=a.accent_level, cut=cut,  # same seed: same layout
                           tone=bool(a.colors), backdrop=a.backdrop)

        pal = RETRO[a.colors] if a.colors else a.palette
        if a.mode == "tiles" and len(images) > 1:  # one palette from a stack of sample frames, so colors never flicker
            pick = images[::max(1, len(images) // 8)]
            sheet = Image.new("RGB", (pick[0].width, pick[0].height * len(pick)))
            for k, im in enumerate(pick):
                sheet.paste(im, (0, k * im.height))
            pal = sorted({c[2] for row in look(sheet, pal) for c in row if len(c) == 3}) or pal
        grids = [look(im, pal) for im in images]
        if a.effect:
            if len(grids) > 1:
                raise ValueError("--effect needs a still image, not an animation")
            if fg and a.mode not in ("led", "dots"):  # bake the ink in, so bright heads still show (led/dots: they do)
                grids, fg = [[[(c[0], fg) + tuple(c[2:]) for c in row] for row in grids[0]]], None
            grids = effects.frames(grids[0], a.effect)
            durs = [1000 / effects.FPS] * (len(grids) - 1) + [HOLD_MS]
        if a.colors:  # after the effect, so its glows land on the palette too
            grids, fg = [snap_grid(g, a.colors, a.dither == "bayer") for g in grids], fg and snap(fg, a.colors)
        if ext in (".gif", ".webp", ".mp4"):
            cw = max(1, round(a.font_size * CELL_W))
            size = len(grids[0][0]) * cw * len(grids) * max(1, round(cw / a.aspect)) * len(grids[0]) * 4
            if size > MAX_BYTES:
                raise ValueError("too big (%d frames of %d columns); lower -w, --font-size or --max-frames"
                                 % (len(grids), len(grids[0][0])))
            out = [post.apply(to_png(g, a.bg if ext == ".webp" else bg, fg, a.font_size, a.aspect, a.gap, a.mode,
                                     pure=bool(a.colors)), a.post, max(1, round(cw / a.aspect))) for g in grids]
            if ext == ".mp4":
                to_mp4(out, durs, a.output, a.fps)
            else:
                # GIF ticks are 10 ms and browsers slow frames under 20 ms, so 60 fps becomes ~40 fps.
                out, durs = snap(one_palette(out), durs, 10, 2) if ext == ".gif" else snap(out, durs, 1, 1)
                out[0].save(a.output, save_all=True, append_images=out[1:], duration=durs, loop=0,
                            **({"lossless": True} if ext == ".webp" else {}))
        elif ext:
            with open(a.output, "w", encoding="utf-8") as f:
                f.write(to_html_player(grids, durs, a.bg, fg, a.font_size, a.aspect, a.gap))
        else:
            play([to_ansi(g, fg).replace("\n", "\x1b[K\n") for g in grids], durs)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:  # one-line error for any bad input, never a traceback
        p.error(str(e) or type(e).__name__)


if __name__ == "__main__":
    main()
