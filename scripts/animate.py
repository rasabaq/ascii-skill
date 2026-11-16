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

from PIL import Image, ImageSequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ascii import (CELL_W, CHARSETS, HALF, COLORS, MAX_SIDE, SUBPIXELS, _corner, add_poster_args, convert,  # noqa: E402
                   POSTER_BG, poster_defaults, rgb, to_ansi, to_png)
import effects  # noqa: E402
import scenes  # noqa: E402

MARK = "\ue000"  # private-use char: never in a ramp, 3 bytes in UTF-8. MARK + 3 hex = new ink color.
MARK2 = "\ue001"  # MARK2 + 6 hex = two-color (halfblock) cells: top and bottom color.
MARK3 = "\ue002"  # MARK3 + 6 hex = glyph on its own background: ink and background color.
HOLD_MS = 1500  # an effect holds the finished art this long before it loops
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
    vf = ("fps=%g," % a.fps if a.fps else "") + "scale='min(iw,%d)':-1:flags=area" % px
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
    p.add_argument("--aspect", type=float, help="char width / height (default 0.5; tiles: 1 for files)")
    p.add_argument("--contrast", type=float, default=1.0, help="1.0 = unchanged")
    p.add_argument("--brightness", type=float, default=1.0, help="1.0 = unchanged")
    p.add_argument("--invert", action="store_true", help="swap light and dark")
    p.add_argument("--dither", action="store_true", help="Floyd-Steinberg dithering (crawls between frames)")
    p.add_argument("--bg", help="black (default; %s in words and tiles mode), white, none (WebP/HTML only), or any color" % POSTER_BG)
    p.add_argument("--fg", help="one ink color: %s, or any color" % ", ".join(COLORS))
    p.add_argument("--font-size", type=int, help="glyph size in px for GIF/WebP/MP4/HTML (default 12; tiles: 80)")
    p.add_argument("--fps", type=float, help="resample to this frame rate (default: keep source timing)")
    p.add_argument("--start", type=float, default=0, help="start at this second")
    p.add_argument("--duration", type=float, help="stop after this many seconds")
    p.add_argument("--max-frames", type=int, default=300, help="frame cap (default 300)")
    p.add_argument("--mode", choices=SUBPIXELS, default="ramp", help="ramp (default), shape, braille, halfblock or words")
    p.add_argument("--sharpen", action="store_true", help="unsharp mask before shrinking, for crisper edges")
    p.add_argument("--effect", choices=effects.EFFECTS, help="animate a still image: %s" % ", ".join(effects.EFFECTS))
    p.add_argument("--gap", type=int, help="px of background around each tile (tiles: default 1); "
                   "words mode: px between boxes in stacked rows (default font size / 8)")
    p.add_argument("--scene", choices=scenes.SCENES, help="draw a looping animation instead of reading input: %s"
                   % ", ".join(scenes.SCENES))
    add_poster_args(p)
    a = p.parse_args(argv)
    if bool(a.input) == bool(a.scene):
        p.error("give an input file or --scene NAME (one of: %s)" % ", ".join(scenes.SCENES))
    ext = os.path.splitext(a.output or "")[1].lower()
    poster_defaults(a, bool(ext))
    if ext not in ("", ".gif", ".webp", ".mp4", ".html", ".htm"):
        p.error("unknown output extension %r: use .gif, .webp, .mp4 or .html" % ext)
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
        lut = list(range(256)) * 3 if a.scene else shared_lut(images)  # scenes are drawn in their own colors

        def look(im, palette):
            return convert(im.point(lut), width, a.charset, a.aspect, a.contrast, a.brightness, a.invert, a.dither,
                           bg, mode=a.mode, sharpen=a.sharpen, autocontrast=False, palette=palette, seed=a.seed,
                           words=a.words, accent=a.accent, accent_level=a.accent_level)  # same seed: same layout

        pal = a.palette
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
            if fg:  # bake the ink into the cells, so the effect's bright heads and glows still show
                grids, fg = [[[(c[0], fg) + tuple(c[2:]) for c in row] for row in grids[0]]], None
            grids = effects.frames(grids[0], a.effect)
            durs = [1000 / effects.FPS] * (len(grids) - 1) + [HOLD_MS]
        if ext in (".gif", ".webp", ".mp4"):
            cw = max(1, round(a.font_size * CELL_W))
            size = len(grids[0][0]) * cw * len(grids) * max(1, round(cw / a.aspect)) * len(grids[0]) * 4
            if size > MAX_BYTES:
                raise ValueError("too big (%d frames of %d columns); lower -w, --font-size or --max-frames"
                                 % (len(grids), len(grids[0][0])))
            out = [to_png(g, a.bg if ext == ".webp" else bg, fg, a.font_size, a.aspect, a.gap) for g in grids]
            if ext == ".mp4":
                to_mp4(out, durs, a.output, a.fps)
            else:
                # GIF ticks are 10 ms and browsers slow frames under 20 ms, so 60 fps becomes ~40 fps.
                out, durs = snap(out, durs, 10, 2) if ext == ".gif" else snap(out, durs, 1, 1)
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
