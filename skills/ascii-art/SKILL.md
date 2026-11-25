---
name: ascii-art
description: Turn any image, GIF or video into ASCII art or ASCII animation, as plain text, truecolor terminal output, HTML, PNG, GIF, WebP or MP4. Also draws a photo as small glowing glyphs over the photo itself (characters, lines, diagonal strokes, diamonds, crosses), as a mosaic, as a tile poster or as a word poster. Also animates still images with glitch, shimmer and dust effects. Also makes ASCII animation from a short description with no image at all, such as "seaweed" or "a running horse", by drawing it in code or using a freely licensed clip from Wikimedia Commons. Use when the user asks for ASCII art, an ASCII animation or video, a text-art version of an image, a terminal banner from a logo, a mosaic, or art that glitches, shimmers, crumbles or blows away as dust.
---

# ASCII art

`scripts/ascii.py` makes still images and `scripts/animate.py` makes animations (see "Animation"). Both need only Python 3.9+ and Pillow (plus ffmpeg for video). With `uv` installed, `uv run` fetches Pillow by itself.

```bash
uv run scripts/ascii.py IMAGE [options]          # or: python3 scripts/ascii.py (needs pillow)
```

Paths below are relative to this skill's folder.

## Steps

1. Get the image path. For a URL, download it first with `curl -L -o /tmp/in.img URL`.
2. Pick the output. Use stdout text to show the art in chat. Use `-o file.png` or `-o file.html` when the user wants a file to share.
   For a photo that should still look like the photo, use a photo style: `--style characters -o out.png` (see "Photo styles").
3. Run it, then read the result. For a PNG, open the image and look at it.
4. If the subject is hard to see, tune and run again (see "Fixing weak results").

## Options

| Option | What it does |
|---|---|
| `-w 100` | Width in characters (1–1000). Use 60–80 for chat, 120–200 for PNG/HTML. |
| `-o out.png` | Output by extension: `.txt`, `.html`, `.png`, `.jpg`, `.webp`. No `-o` prints plain text to stdout. |
| `--mode ramp` | What one cell is made of: `ramp`, `shape`, `braille`, `mosaic`, `words`, `tiles` or `stipple`. See "Modes". |
| `-c standard` | Character ramp for `ramp` and `shape` mode: `standard`, `detailed`, `terminal`, `minimal`, `binary`, `dots`, or your own string from dense to empty, like `-c "#*. "`. |
| `--style characters` | The photo look in one step: `characters`, `lines`, `diagonal`, `diamond` or `cross`. See "Photo styles". |
| `--bg black` | Background: `black` (default), `white`, `none` (transparent PNG/HTML), or any color. On a dark background bright pixels get dense glyphs. On a light one dark pixels do. |
| `--fg "#00ff41"` | One ink color for all glyphs, as a CSS color name or hex. Without it, PNG/HTML use the photo's own colors. |
| `--color` | Truecolor ANSI escape codes in text output (stdout or `.txt`). Uses `--fg` if given, else photo colors. |
| `--contrast 1.0` `--brightness 1.0` | Factors on top of the automatic contrast stretch. `1.0` means no change. |
| `--aspect 0.5` | Character width divided by height. Raise it if the art looks squashed. |
| `--font-size 12` | Glyph size in px for PNG/HTML. |
| `--gap 1` | Px of page color around each tile (`tiles`), around each pixel (`mosaic`), or between rows of word boxes (`words`). |

## Modes

| Mode | What it draws |
|---|---|
| `ramp` (default) | One glyph per pixel, picked by brightness from the `-c` ramp. |
| `shape` | Like ramp, but edges are drawn with symbols of the same shape (`/ \ | _`), so outlines are sharp. |
| `braille` | Each character holds 2x4 dots, so 8 pixels per character and much finer detail. Ignores `-c`. |
| `mosaic` | Small color tiles in the photo's true colors, two per character, with a thin gap between them. |
| `words` | A word poster. See "Word poster". |
| `tiles` | A tile poster. See "Tile poster". |
| `stipple` | Same-size dots on a square grid. Tone is how many dots are on. |

- `braille` on a still image sharpens the image and dithers the dots, which suits photos. In an animation the dots are not dithered, so they hold still. Colors follow the photo, or `--fg`. Terminals draw braille dots small, so braille looks dimmer there than in a PNG.
- `mosaic` ignores `-c` and `--fg`, because the colors are the picture. For a picture it defaults to `-w 96 --font-size 24 --gap 1`. `--gap 0` gives plain pixel art. HTML and the terminal ignore the gap. Plain text (no `--color`) has no colors, so each cell becomes a shade block `█▓▒░` by brightness. `--bg none` does not make it transparent: transparent pixels become black.
- `stipple` defaults to square cells of about 8 px (`--font-size 14`) on black. Dot color comes from the image, or from `--fg`. Text output gets `●` for each lit cell.

```bash
uv run scripts/ascii.py photo.jpg --mode braille -w 120 -o dots.png
uv run scripts/ascii.py photo.jpg --mode mosaic -o mosaic.png
uv run scripts/ascii.py earth.jpg --mode stipple -w 140 --fg white -o globe.png
```

## Fixing weak results

The script already stretches every image to its full tonal range, so most images look fine with no tuning.

- Dark subject (black dog, night scene) disappears on the black background: use `--bg white`. Raising `--brightness 1.5` also helps. Raising contrast makes dark scenes worse.
- Dark logo on a white background shows as a solid block: add `--bg white`.
- A light `--bg` (like `white`) keeps the photo's colors, so pale parts of the picture almost vanish into the page. Add a dark `--fg` too.
- Bright photo (snow, sky) looks dark and striped in `ramp` mode on black: use `--bg white --fg black`, `--mode braille`, or a photo style.
- `-c detailed` turns busy pictures into letter soup. Use it for simple subjects and `--mode braille` for busy ones.
- Want more detail at the same width: `--mode braille`.
- Logo or line art: use `ramp` or `shape`. Braille dithers a still image, which puts stray dots on flat areas.
- In braille mode, small `--brightness` steps like `1.2` barely change the result. Try `1.5` or more.
- Too much noise: use fewer columns or a shorter ramp (`-c minimal`).
- Chat output: never use `--color`, because escape codes show up as junk. Wrap the text in a code block.
- With `--style`, a dark photo gets only a few glyphs: add `--brightness 1.5`. For more glyphs everywhere, give your own ramp with no spaces at the end, like `-c "◆◆◇◇"`.
- SVG is not supported. Convert it to PNG first (`rsvg-convert -w 800 logo.svg -o logo.png`).

## Photo styles

`--style NAME` draws a photo as small glyphs over the photo itself. The photo stays visible under the glyphs in its original colors and sharpness. Each glyph takes the color of the pixel under it, a little brighter, so it glows. Bright parts get the heaviest glyph. Dark parts get no glyph, so only the photo shows there. One option is enough:

```bash
uv run scripts/ascii.py photo.jpg --style diamond -o out.png
```

| Style | Glyphs | The look |
|---|---|---|
| `--style characters` | `@ # 0 8 S X x + = -` | Letters and signs with room around them. The classic ASCII look. |
| `--style lines` | `┃ ╏ ╹ '` | Vertical dashes. Brighter parts get longer dashes. |
| `--style diagonal` | `╲ / ′` | Slanted strokes, like pencil hatching. The brightest parts lean the other way. |
| `--style diamond` | `◆ ◇` | Diamonds on a square grid: filled on bright parts, hollow on mid tones. |
| `--style cross` | `✖ ✕ ×` | Crosses on a square grid, like cross-stitch. |

- Use it with `-o out.png`, `.jpg`, `.webp` or `.html`. The HTML keeps the photo inside the file.
- A style sets `-c`, `-w` (120 or 160), `--aspect` and `--font-size` for you. Any of these that you give yourself wins. For finer glyphs raise `-w` (200–250). For a bigger picture raise `--font-size`.
- `--fg` gives all glyphs one color. Without it they take the photo's colors.
- For text output (stdout or `.txt`) a style only picks the ramp. There is no photo under text.
- In `animate.py` a style works the same for `.gif`, `.webp` and `.mp4` (see "Animation").

## Tile poster

`--mode tiles` makes a poster: a grid of square tiles in a few calm colors, each with one glyph, on a charcoal page. Where the image is close to the page color, cells are not tiles: they show a faint glyph, so the grid goes on everywhere.

```bash
uv run scripts/ascii.py photo.jpg --mode tiles -w 36 -o poster.png
```

- Defaults in tiles mode: square cells (`--aspect 1`), `--font-size 80` (48 px tiles), `--gap 1`, `--bg "#1d1f22"`. Text output keeps `--aspect 0.5`.
- `--palette 8`: number of tile colors, picked once from the subject. Use 4–6 for a flatter, calmer look.
- Glyphs are random. `--seed N` picks another set. Give `-c` to use ramp glyphs instead.
- Photo with a light background: use a light page, like `--bg "#ecebe6"`. Then dark parts become tiles.
- Works in `animate.py` too. Glyphs and colors stay the same from frame to frame.

## Word poster

`--mode words` fills the canvas with uppercase words, one space apart. Each row starts at its own offset and runs off both edges. The image shows only through each word's brightness: one level per word, from the mean of the image under it. Dark parts give faint words and the subject gives light words.

- `--words "A B C"` sets the vocabulary (space or comma separated). The default is a short list of type and pixel words.
- `--accent "#f28c28"` puts a solid box behind the most colorful words, with dark text. `--accent-level 0.5` (0-1) is how colorful a word must be. Gray photos get no boxes; a fully colored logo gets many, so raise the level.
- The background defaults to `#1d1f22`. `--gap` sets the px between boxes in stacked rows. `--seed` picks another layout. `--fg` is ignored.
- It works best on a bright, simple subject on a dark background.
- In `animate.py` the layout stays the same in every frame; only the brightness changes.

Preset: `--mode words -w 110 --font-size 16 --accent "#f28c28" -o poster.png`

## Presets

- Fine dot drawing: `--mode braille -w 120 -o out.png`
- Green terminal: `-c binary --fg "#00ff41" -o out.png`
- Amber terminal: `-c terminal --fg "#ffb000" -o out.png`
- Print-friendly: `--bg white --fg black -o out.png`
- Color photo in a terminal: `--mode mosaic --color`
- Mosaic: `--mode mosaic -o out.png`
- Glyphs over the photo: `--style characters -o out.png` (also `lines`, `diagonal`, `diamond`, `cross`)
- Tile poster: `--mode tiles -w 36 -o poster.png`
- Moving glyphs over a photo: `uv run scripts/animate.py photo.jpg --style characters --effect shimmer -o out.mp4`

## Animation

`scripts/animate.py` makes ASCII animation. It takes the same look options as `ascii.py` (`-w`, `-c`, `--mode`, `--style`, `--bg`, `--fg`, `--contrast`, `--brightness`, `--font-size`, `--aspect`, `--gap`, and the word and tile poster options). Video input and `.mp4` output need ffmpeg. GIF and WebP do not.

```bash
uv run scripts/animate.py cat.gif                          # play in the terminal, Ctrl-C stops
uv run scripts/animate.py cat.gif -o out.gif               # also .webp, .mp4, or .html (one file with a play/pause player)
uv run scripts/animate.py clip.mp4 -o out.html --start 2 --duration 4 --fps 12
uv run scripts/animate.py photo.jpg --effect dust -o dust.gif      # animate a still image
```

- Input: animated GIF, WebP or APNG, any video ffmpeg reads, or a still image with `--effect`.
- Frame timing comes from the source. `--fps` resamples. `--start` and `--duration` pick a slice in seconds.
- It stops at 300 frames by default and says so. Raise `--max-frames`, or lower `--fps`, for longer clips.
- One tonal range (and in braille one dot threshold) is used for all frames, so brightness does not pump.
- Still areas do not flicker: a pixel keeps its value until it changes by more than `--steady` (default 6, out of 255). Raise it to 16 or more for grainy film. `--steady 0` turns it off.
- Interlaced video is deinterlaced, and video with non-square pixels keeps its real shape.
- GIF cannot play faster than about 50 fps, so fast video drops some frames in `.gif`. Use `.mp4` or `.webp` for smooth 60 fps.
- `--hold SECONDS` keeps the last frame on screen that long before the loop starts again (default 0).
- `.mp4` is tagged as BT.709, so browsers show the exact `--bg` color and the video blends into a page of the same color. `--crf` sets the quality (default 23; lower is sharper and bigger). With `--font-size` 16 or more, 28 still looks clean and is about 30% smaller.
- When it writes a file, it prints the path, size and length.

### Figures on a plain background

For a dark figure on a light background, like the Muybridge running horse, use `--bg white`. Then the figure gets the ink and the page stays clean. `--mode braille` gives the sharpest moving figure, and `--mode mosaic` keeps the photo's tones.

```bash
uv run scripts/animate.py horse.gif --mode braille --bg white -o horse.gif
uv run scripts/animate.py juggler.webm --start 17 --duration 4 --mode braille --subject -o juggler.gif
```

`--subject` keeps only what moves and paints the rest as an empty page (white when the background is light, unless you set `--bg`). It needs a still camera: it takes the background from the median of up to 25 frames. Notes:

- Parts that hold still for most of the clip, like a head, count as background and fade out.
- If the picture's edges keep changing, the camera moves: it says so and leaves the frames as they are. A slow pan is not always caught and leaves outlines behind.
- In clips where each frame is a different photo (Muybridge's horse and buffalo), use `--bg white` instead.
- `--subject-cut` (default 40, out of 255) is how much a pixel must differ from the background to count. Lower it for a faint figure, raise it for noisy video.

### Effects for still images

`--effect NAME` turns one image into a 2–4 second animation at 25 fps. Every effect starts and ends on the finished art, so it loops with no pause. `--hold SECONDS` adds a pause on the last frame. Every effect works with every mode.

- `glitch`: short bursts of torn rows, glyph swaps and red/cyan bands.
- `shimmer`: the art holds still while its glyphs keep swapping for others of the same weight (`S` for `#`, `0` for `@`; in braille a dot moves; `◆` for `♦`, `┃` for `║`), a few at a time, so it looks alive. Best with a `--style`, which keeps the photo under the glyphs.
- `dust`: the art comes apart into wind-blown dust and grows back, over 4 seconds. The edge the wind blows toward crumbles first (the left, or the right with `--wind right`); its glyphs wear down to `* + : .` as they swirl away and fade, and a few grains are red. Best on a subject with dark space beside it, so the dust has room to fly.

`dust` also works on a moving input (a GIF, a video or a `--scene`): the animation keeps playing while it crumbles, and the clip is whole runs of it, so it still loops. The other effects need a still image.

`--style NAME` (see "Photo styles") sets the ramp and the cell shape and draws the photo behind the glyphs. It works on stills with an effect, on GIFs, on video and on scenes:

```bash
uv run scripts/animate.py photo.jpg --style characters --effect shimmer -o out.mp4   # letters that keep changing over the photo
uv run scripts/animate.py photo.jpg --style diamond --effect glitch -o out.mp4       # diamonds that glitch over the photo
uv run scripts/animate.py clip.mp4 --style lines -o out.mp4                          # a video as moving dashes
```

The HTML player and the terminal cannot show the photo under the glyphs. There a style only sets the ramp and the cell shape. Use `.mp4`, `.gif` or `.webp` for the full look.

### From a description

When the user describes a thing ("seaweed", "a running horse") instead of giving a file, pick one path:

- A simple or stylized subject (seaweed, a jellyfish, a campfire, a clock, a planet, falling leaves): draw it yourself (see "Draw it yourself"). Shapes and motion are yours to choose, and nothing needs credit.
- Real motion that is hard to draw (a galloping horse, a dancer): fetch a clip, as below. If no clip fits, draw it.

`scripts/fetch.py` searches Wikimedia Commons for animated GIFs and short videos with a free license and downloads the best match.

1. Fetch a clip: `uv run scripts/fetch.py "running horse" -o /tmp/clip`. It adds the right extension (`.gif`, `.webm`), then prints the saved path and an attribution line. To choose yourself, run with `--list` first, then `--pick N`.
2. Convert the printed path: `uv run scripts/animate.py /tmp/clip.gif --mode braille -w 80 --bg white -o out.gif`. For long videos add `--duration 5`.
3. Look at a frame of the result. If the subject is hard to see, try `--pick` with another result.
4. Give the user the attribution line with the result. Most licenses (CC BY, CC BY-SA) require it.

Search with short plain English words for the subject and the motion. Line drawings, silhouettes and clips on a plain background read best as ASCII. Busy real-world video often does not.

If nothing suitable is found, draw it yourself (below).

### Draw it yourself

Write a scene file and pass its path to `--scene`. A scene draws one loop in code, so no input file is needed, and every mode, color and output works.

```python
# /tmp/seaweed.py
import math, random
from PIL import Image, ImageDraw
from scenes import SS, TAU, _shrink, scene

@scene(320, 240, 75, 25)                  # canvas width, height, frames per loop, fps
def seaweed(w, h, n, seed):
    rng = random.Random(seed)             # all randomness from the seed, picked once before the loop
    strands = [(rng.uniform(0.05, 0.95) * w * SS, rng.random()) for _ in range(8)]
    out = []
    for k in range(n):
        t = k / n                         # 0 to 1 over one loop
        im = Image.new("RGB", (w * SS, h * SS))
        draw = ImageDraw.Draw(im)
        for x0, phase in strands:
            pts = [(x0 + math.sin(TAU * (t - 0.7 * s + phase)) * 0.09 * w * SS * s, (1 - 0.8 * s) * h * SS)
                   for s in (i / 30 for i in range(31))]
            draw.line(pts, fill=(120, 240, 90), width=8 * SS)
        out.append(_shrink(im, w, h))     # draw at SS x size, shrink for smooth edges
    return out
```

```bash
uv run scripts/animate.py --scene /tmp/seaweed.py -w 80 -o seaweed.gif
```

- Make it loop. Drive every motion with `t`: `sin(TAU * t)`, or `(p0 + speed * t) % 1` with a whole-number `speed` for things that wrap, like bubbles or rain. Frame `n` must equal frame `0`.
- Pick all random values before the frame loop. Random values picked inside the loop change every frame and make the picture flicker.
- Draw bright on black. Dim colors turn into sparse, faint glyphs. Fill shapes and use thick lines, because thin detail is lost at 80 columns.
- Use `-w 60` to `-w 100`. `--mode mosaic` gives the best color; `--mode braille` gives the crispest lines.
- `--seed N` is passed to the scene, and `--fps` changes smoothness but keeps the loop length. Without `-o` the scene plays in the terminal.
- Look at a frame of the result and fix what reads poorly, then run again. Most subjects need one or two rounds.
- For a still picture, save one frame and convert it: `uv run --with pillow python -c "import sys; sys.path.insert(0, 'scripts'); from scenes import load, SCENES; SCENES[load('/tmp/seaweed.py')](320, 240, 1, 0)[0].save('/tmp/still.png')"`, then `scripts/ascii.py /tmp/still.png`.

### Put it on a web page

There are two ways:

- **HTML player** (`-o art.html`). The art is real text, sharp at any size, and it fills the width of the box you put it in. Open the file, copy everything from the `<!-- To put the animation on your own page ... -->` line to the end, and paste it into your page. Its CSS and JS only touch that block, so your page's styles do not break it and it does not break your page. The Pause button sits in the art's corner, and readers who ask for less motion see the finished art, paused. Best for text-style art (braille, ramp, tiles). A 200-column, 50-frame loop is about 150 KB, or about 20 KB when the server gzips it.
- **MP4 in a `<video>` tag** (`-o art.mp4`). Best for mosaic art, long clips, or a full-width hero. A video does not pause by itself for readers who ask for less motion, so add `controls` or a pause button.

```html
<!-- HTML player: set the size on the parent box -->
<div style="max-width: 720px">
  ...the block you copied from art.html...
</div>

<!-- MP4 -->
<video src="art.mp4" autoplay muted loop playsinline controls style="width: 100%"></video>
```

## Python use

```python
import sys; sys.path.insert(0, "scripts")
from PIL import Image
from ascii import convert, to_text, to_png
grid = convert(Image.open("cat.jpg"), width=80, charset="minimal")
# Cells are (char, (r, g, b)). With mode="mosaic" they are (char, top_rgb, bottom_rgb).
# With mode="tiles", tile cells are (char, ink_rgb, tile_rgb).
# With mode="stipple", pass the same mode to to_png to draw the dots.
print(to_text(grid))
to_png(grid).save("cat_ascii.png")

from effects import frames  # list of grids; the last one is `grid`
loop = [to_png(g) for g in frames(grid, "dust")]

# Glyphs over the photo: over_photo=True keeps each pixel's own color, and underlay() gives the photo to draw behind them.
from ascii import underlay
photo = Image.open("cat.jpg")
over = convert(photo, width=120, charset="diamond", aspect=1.0, over_photo=True)
to_png(over, font_size=16, aspect=1.0, under=underlay(photo, "black", 0.9)).save("cat_diamond.png")
```
