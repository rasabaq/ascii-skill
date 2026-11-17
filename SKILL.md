---
name: ascii-art
description: Turn any image, GIF or video into ASCII art or ASCII animation, as plain text, truecolor terminal output, HTML, PNG, GIF, WebP or MP4. Also draws a photo as small glowing glyphs over the photo itself (characters, lines, diagonal strokes, diamonds, dots, crosses), or as a mosaic. Also animates still images with matrix-rain, decode, scan, glitch, wave, shimmer and dust effects. Also makes ASCII art or animation from a short description with no image at all, such as "seaweed" or "a running horse", by drawing it in code or using a freely licensed clip from Wikimedia Commons. Use when the user asks for ASCII art, an ASCII animation or video, a text-art version of an image, a terminal banner from a logo, a "matrix" / retro text look, or art that crumbles, decays or blows away as dust.
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
| `-w 100` | Width in characters (1–1000). Use 60–80 for chat, 120–200 for PNG/HTML, 120+ for screenshots of text. |
| `-c standard` | Character ramp: `standard`, `detailed`, `blocks`, `terminal`, `minimal`, `binary`, `dots`, the six style ramps (`characters`, `lines`, `diagonal`, `diamond`, `dot`, `cross`), or your own string from dense to empty, like `-c "#*. "`. |
| `--style characters` | The photo look in one step: `characters`, `lines`, `diagonal`, `diamond`, `dot` or `cross`. See "Photo styles". |
| `--under 0.9` | PNG, JPG, WebP and HTML: draws the original photo behind the glyphs, untouched. The number (0–1) is how strongly it shows: `1` is the photo as it is, lower dims it toward the page. `--style` sets it to 0.9. |
| `-o out.png` | Output by extension: `.txt`, `.html`, `.png`, `.jpg`, `.webp`. No `-o` prints plain text to stdout. |
| `--bg black` | Background: `black` (default), `white`, `none` (transparent PNG/HTML), or any color. On a dark background bright pixels get dense glyphs. On a light one dark pixels do. |
| `--fg matrix` | One ink color: `matrix`, `amber`, `cyan`, `magenta`, `mint`, or any CSS color or hex. Without it, PNG/HTML use the photo's own colors. |
| `--color` | Truecolor ANSI escape codes in text output (stdout or `.txt`). Uses `--fg` if given, else photo colors. |
| `--invert` | Swap light and dark. |
| `--contrast 1.0` `--brightness 1.0` | Factors on top of the automatic contrast stretch. `1.0` means no change. |
| `--dither` | Floyd-Steinberg dithering. Good for smooth gradients and short ramps such as `blocks` or `minimal`. |
| `--mode ramp` | `ramp` (default): one glyph per pixel, picked by brightness. `shape`: like ramp, but edges are drawn with symbols of the same shape (`/ \ | _`), so outlines are sharp. `braille`: each char holds 2x4 dots, so 8 pixels per char and much finer lines. `halfblock`: each char is `▀` with two true colors (top and bottom pixel), the sharpest color photo for terminals, HTML and PNG. `words`: a word poster (see "Word poster"). `tiles`: a tile poster (see "Tile poster"). |
| `--sharpen` | Sharpens edges before shrinking. Helps faces and fine detail, most of all in `braille` mode. |
| `--aspect 0.5` | Character width divided by height. Raise it if the art looks squashed. |
| `--font-size 12` | Glyph size in px for PNG/HTML. |
| `--glow 0.8` | Soft bloom around the glyphs (0-1) in PNG, HTML and animation, like light on an old screen. Best on a dark background. |
| `--gap 1` | Px of page color around each tile (`tiles`) or between rows of word boxes (`words`). In PNG it also parts the pixels of `halfblock`, which makes a mosaic. |

## Fixing weak results

The script already stretches every image to its full tonal range, so most images look fine with no tuning.

- Photos: `-c blocks --dither` gives the most recognizable faces and animals.
- Dark subject (black dog, night scene) disappears on the black background: use `--bg white`. Raising `--brightness 1.5` also helps. Raising contrast makes dark scenes worse.
- Dark logo on a white background shows as a solid block: add `--bg white` (or `--invert` for terminal output).
- Light picture with a darker subject (a print, a painting, a drawing on paper): use the "Print or light page" preset below. Braille with one dark `--fg` ink on a light `--bg` looks like a woodblock print. Leave out `--dither` here: it fills the paper with stray dots.
- A light `--bg` (like `white`) keeps the photo's colors, so pale parts of the picture almost vanish into the page. Add a dark `--fg` too.
- In braille mode, small `--brightness` steps like `1.2` barely change the result. Try `1.5` or more.
- `-c detailed` turns busy pictures into letter soup. Use it for simple subjects and `--mode braille` for busy ones.
- Want more detail at the same width: `--mode braille --dither --sharpen` for line-art style, `--mode halfblock` for a color photo.
- Too much noise: use fewer columns or a shorter ramp (`-c minimal`).
- Banding in gradients: add `--dither`.
- Chat output: never use `--color`, because escape codes show up as junk. Wrap the text in a code block.
- With `--style`, a dark photo gets only a few glyphs: add `--brightness 1.5`. For more glyphs everywhere, give your own ramp with no spaces at the end, like `-c "◆◆◇◇"`.
- With `--style`, the photo is too faint or too strong: change `--under` (0.5 is dimmer and makes the glyphs stand out, 1 is the photo as it is).
- SVG is not supported. Convert it to PNG first (`rsvg-convert -w 800 logo.svg -o logo.png`).

## Modes in short

- `braille` ignores `-c`. Use it with `--dither` for photos and without it for logos. Colors follow the photo, or `--fg`.
- `halfblock` ignores `-c`, `--dither` and `--fg`, because the colors are the picture. Plain text (no `--color`) has no colors, so each cell becomes a shade block `█▓▒░` by brightness. `--bg none` does not make it transparent: transparent pixels become black.
- Terminals draw braille dots small, so braille looks dimmer there than in a PNG.

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
| `--style dot` | `● • ·` | Dots on a square grid that grow with brightness, like a halftone print. |
| `--style cross` | `✖ ✕ ×` | Crosses on a square grid, like cross-stitch. |

- Use it with `-o out.png`, `.jpg`, `.webp` or `.html`. The HTML keeps the photo inside the file.
- A style sets `-c`, `-w` (120 or 160), `--aspect`, `--font-size` and `--under 0.9` for you. Any of these that you give yourself wins. For finer glyphs raise `-w` (200–250). For a bigger picture raise `--font-size`.
- `--under 0` turns the photo off: the glyphs sit on the flat page and get brighter ink.
- `--under` also works without a style, with any ramp and with `--mode shape` or `--mode braille`: `-c detailed --under 0.5 -o out.png`.
- `--fg` gives all glyphs one color. Without it they take the photo's colors.
- For text output (stdout or `.txt`) a style only picks the ramp. There is no photo under text.
- In `animate.py` a style works the same for `.gif`, `.webp` and `.mp4` (see "Animation").

### Mosaic and pixel art

These two use `--mode halfblock`, which keeps the photo's true colors. They do not use `--style`.

```bash
uv run scripts/ascii.py photo.jpg --mode halfblock -w 120 -o pixels.png                            # pixel art
uv run scripts/ascii.py photo.jpg --mode halfblock --gap 1 --font-size 24 -w 96 -o mosaic.png     # mosaic
```

`--gap 1` puts a thin line of page color around every pixel, so each one becomes a small square tile. It works in PNG, JPG, WebP and in animations (GIF, WebP, MP4). HTML and the terminal ignore it.

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
- It works best on a bright, simple subject on a dark background. For a dark subject on a light photo, add `--invert`.
- In `animate.py` the layout stays the same in every frame; only the brightness changes.

Preset: `--mode words -w 110 --font-size 16 --accent "#f28c28" -o poster.png`

## Presets

- Matrix: `-c binary --fg matrix --glow 0.8 -o out.png`
- Retro amber terminal: `-c terminal --fg amber -o out.png`
- Photo mosaic in color (simple subjects): `-c detailed -w 160 -o out.html`
- Best color photo in a terminal: `--mode halfblock --color`
- Fine dot drawing: `--mode braille --dither --sharpen -o out.png`
- Film noir: `--fg "#e8e6df" --contrast 1.35 --bg "#050505" --glow 0.7 -o out.png`
- Print-friendly: `--bg white --fg black -o out.png`
- Print or light page (prints, paintings, line art on paper): `--mode braille --sharpen --brightness 1.6 -w 200 --bg "#f3ead8" --fg "#1d3557" -o out.png`. No `--dither`.
- Tile poster: `--mode tiles -w 36 -o poster.png`
- Glyphs over the photo: `--style characters -o out.png` (also `lines`, `diagonal`, `diamond`, `dot`, `cross`)
- Mosaic: `--mode halfblock --gap 1 --font-size 24 -w 96 -o out.png`
- Pixel art: `--mode halfblock -w 120 -o out.png`
- Moving glyphs over a photo: `uv run scripts/animate.py photo.jpg --style characters --effect shimmer -o out.mp4`

## Animation

`scripts/animate.py` makes ASCII animation. It takes the same look options as `ascii.py` (`-w`, `-c`, `--mode`, `--sharpen`, `--bg`, `--fg`, `--invert`, `--contrast`, `--brightness`, `--font-size`, `--aspect`, `--gap`, `--glow`, `--style`, `--under`, and the word and tile poster options). Video input and `.mp4` output need ffmpeg. GIF and WebP do not.

```bash
uv run scripts/animate.py cat.gif                          # play in the terminal, Ctrl-C stops
uv run scripts/animate.py cat.gif -o out.gif               # also .webp, .mp4, or .html (one file with a play/pause player)
uv run scripts/animate.py clip.mp4 -o out.html --start 2 --duration 4 --fps 12
uv run scripts/animate.py photo.jpg --effect matrix -o intro.gif   # animate a still image
uv run scripts/animate.py photo.jpg --effect decode --hold 0 -o intro.mp4   # no pause at the end
```

- Input: animated GIF, WebP or APNG, any video ffmpeg reads, or a still image with `--effect`.
- Frame timing comes from the source. `--fps` resamples. `--start` and `--duration` pick a slice in seconds.
- It stops at 300 frames by default and says so. Raise `--max-frames`, or lower `--fps`, for longer clips.
- One tonal range (and in braille one dot threshold) is used for all frames, so brightness does not pump.
- Still areas do not flicker: a pixel keeps its value until it changes by more than `--steady` (default 6, out of 255). Raise it to 16 or more for grainy film. `--steady 0` turns it off.
- Interlaced video is deinterlaced, and video with non-square pixels keeps its real shape.
- Avoid `--dither` for animation: it makes the glyphs crawl from frame to frame.
- GIF cannot play faster than about 50 fps, so fast video drops some frames in `.gif`. Use `.mp4` or `.webp` for smooth 60 fps.
- `--hold SECONDS` keeps the last frame on screen that long before the loop starts again (default 0, or 1.5 for the `matrix`, `decode` and `scan` effects).
- `.mp4` is tagged as BT.709, so browsers show the exact `--bg` color and the video blends into a page of the same color. `--crf` sets the quality (default 23; lower is sharper and bigger). With `--font-size` 16 or more, 28 still looks clean and is about 30% smaller.
- When it writes a file, it prints the path, size and length.

### Figures on a plain background

For a dark figure on a light background, like the Muybridge running horse, use `--bg white`. Then the figure gets the ink and the page stays clean. `--mode braille` gives the sharpest moving figure, and `--mode halfblock` keeps the photo's tones.

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

`--effect NAME` turns one image into a 2–4 second animation at 25 fps that ends on the finished art. `matrix`, `decode` and `scan` then hold the art for 1.5 seconds; `glitch`, `wave`, `shimmer` and `dust` loop with no pause. `--hold SECONDS` changes the pause (`--hold 0` for none). Every effect works with every mode.

- `matrix`: falling columns of glyphs with a bright head, leaving the art behind them.
- `decode`: cells scramble through random glyphs and lock in, sweeping left to right.
- `scan`: a bright CRT line sweeps down and types each row in, with a short glow.
- `glitch`: short bursts of torn rows, glyph swaps and red/cyan bands. Loops well.
- `wave`: rows sway sideways on a sine wave that swells and calms. Loops well.
- `shimmer`: the art holds still while its glyphs keep swapping for others of the same weight (`S` for `#`, `0` for `@`; in braille a dot moves), a few at a time, so it looks alive. Loops well. Best with `--under`.
- `dust`: the art comes apart into wind-blown dust and grows back, over 4 seconds. The edge the wind blows toward (the left) crumbles first; its glyphs wear down to `* + : .` as they swirl away and fade, and a few grains are red. Loops well. Best on a subject with dark space beside it, so the dust has room to fly. To blow right instead, call `effects.frames(grid, "dust", wind="right")` from Python.

`dust` also works on a moving input (a GIF, a video or a `--scene`): the animation keeps playing while it crumbles, and the clip is whole runs of it, so it still loops. Every other effect needs a still image.

```bash
uv run scripts/animate.py --scene donut --effect dust -o donut.mp4   # a spinning donut blowing away
```

`--under 0.4` (GIF, WebP and MP4) draws the original photo behind the glyphs instead of a flat page. The number is how strongly it shows, from 0 to 1. Each glyph then keeps the color of its own pixel, a little brighter. It suits photos with photo colors on a dark page:

```bash
uv run scripts/animate.py sky.jpg --effect shimmer --under 0.45 -w 110 -o sky.mp4
```

`--style NAME` (see "Photo styles") sets the ramp, the cell shape and `--under 0.9` in one step. It works on stills with an effect, on GIFs, on video and on scenes:

```bash
uv run scripts/animate.py photo.jpg --style characters --effect shimmer -o out.mp4   # letters that keep changing over the photo
uv run scripts/animate.py photo.jpg --style diamond --effect decode -o out.mp4       # diamonds sweep in over the photo
uv run scripts/animate.py clip.mp4 --style lines -o out.mp4                          # a video as moving dashes
```

- `shimmer` only swaps letters and braille dots. With `lines`, `diagonal`, `diamond`, `dot` and `cross` nothing moves, so use another effect there.
- The HTML player and the terminal cannot show the photo under the glyphs. There a style only sets the ramp and the cell shape. Use `.mp4`, `.gif` or `.webp` for the full look.

### Scenes

`--scene NAME` draws a looping animation in code, so no input file is needed. Each loop is 2 to 3.2 seconds, and the last frame flows into the first. Every mode, color option and output works. `--seed N` gives another variant (fire, waves, stars, rain), and `--fps` changes smoothness but keeps the loop length.

```bash
uv run scripts/animate.py --scene fire -o fire.gif                       # rising flames, warm colors
uv run scripts/animate.py --scene donut -o donut.gif                     # a spinning, lit, frosted donut
uv run scripts/animate.py --scene cube --mode braille -o cube.gif        # a tumbling cube with bright edges
uv run scripts/animate.py --scene waves --mode halfblock -o waves.gif    # ocean swell under the moon
uv run scripts/animate.py --scene stars -o stars.gif                     # flying through a starfield
uv run scripts/animate.py --scene walker --mode braille -o run.gif       # a stick figure running in place
uv run scripts/animate.py --scene rain --mode braille -o rain.gif        # rain with splashes
uv run scripts/animate.py --scene bounce --mode halfblock -o ball.gif    # a ball that squashes as it bounces
uv run scripts/animate.py --scene text --mode halfblock -o text.gif      # the word ASCII riding a rainbow wave
uv run scripts/animate.py --scene flower -o flower.gif                    # a flower breathing open and closed
```

- Use `-w 60` to `-w 100`. `--mode halfblock` gives the best color; `--mode braille` gives the crispest lines.
- Without `-o` the scene plays in the terminal.
- A scene is a plain function in `scripts/scenes.py`: `scene(w, h, n, seed)` returns `n` images that loop. To add one, write the function and give it the `@scene(width, height, frames, fps)` line.

### From a description

When the user describes a thing ("seaweed", "a running horse") instead of giving a file, pick one path:

- A built-in scene matches: use it (see "Scenes").
- A simple or stylized subject (seaweed, a jellyfish, a campfire, a clock, a planet, falling leaves): draw it yourself (see "Draw it yourself"). Shapes and motion are yours to choose, and nothing needs credit.
- Real motion that is hard to draw (a galloping horse, a dancer): fetch a clip, as below. If no clip fits, draw it.

`scripts/fetch.py` searches Wikimedia Commons for animated GIFs and short videos with a free license and downloads the best match.

1. Fetch a clip: `uv run scripts/fetch.py "running horse" -o /tmp/clip`. It adds the right extension (`.gif`, `.webm`), then prints the saved path and an attribution line. To choose yourself, run with `--list` first, then `--pick N`.
2. Convert the printed path: `uv run scripts/animate.py /tmp/clip.gif --mode braille -w 80 --bg white -o out.gif`. Any preset works. For long videos add `--duration 5`.
3. Look at a frame of the result. If the subject is hard to see, try `--pick` with another result.
4. Give the user the attribution line with the result. Most licenses (CC BY, CC BY-SA) require it.

Search with short plain English words for the subject and the motion. Line drawings, silhouettes and clips on a plain background read best as ASCII. Busy real-world video often does not.

If nothing suitable is found, draw it yourself (below).

### Draw it yourself

Write a scene file and pass its path to `--scene`. It works like a built-in scene, so every mode, color and output works.

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
- Draw bright on black. Dim colors turn into sparse, faint glyphs. Fill shapes and use thick lines, because thin detail is lost at 80 columns.
- Look at a frame of the result and fix what reads poorly, then run again. Most subjects need one or two rounds.
- Copy patterns from `scripts/scenes.py`: 3D shading (`donut`, `cube`), particles (`fire`, `rain`), and a walking figure (`walker`).
- Two finished scene files show the level of detail to aim for: `examples/seaweed.py` (kelp and bubbles) and `examples/koi.py` (koi with patterns, fins, eyes and shading, swimming slow 8-second loops). Run either one with `--scene examples/koi.py`. Copy one as a starting point for a similar subject.
- For a still picture, save one frame and convert it: `uv run --with pillow python -c "import sys; sys.path.insert(0, 'scripts'); from scenes import load, SCENES; SCENES[load('/tmp/seaweed.py')](320, 240, 1, 0)[0].save('/tmp/still.png')"`, then `scripts/ascii.py /tmp/still.png`.

### Put it on a web page

There are two ways:

- **HTML player** (`-o art.html`). The art is real text, sharp at any size, and it fills the width of the box you put it in. Open the file, copy everything from the `<!-- To put the animation on your own page ... -->` line to the end, and paste it into your page. Its CSS and JS only touch that block, so your page's styles do not break it and it does not break your page. The Pause button sits in the art's corner, and readers who ask for less motion see the finished art, paused. Best for text-style art (braille, ramp, tiles). A 200-column, 50-frame loop is about 150 KB, or about 20 KB when the server gzips it.
- **MP4 in a `<video>` tag** (`-o art.mp4`). Best for halfblock art, long clips, or a full-width hero. A video does not pause by itself for readers who ask for less motion, so add `controls` or a pause button.

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
grid = convert(Image.open("cat.jpg"), width=80, charset="blocks", dither=True)
# Cells are (char, (r, g, b)). With mode="halfblock" they are (char, top_rgb, bottom_rgb).
# With mode="tiles", tile cells are (char, ink_rgb, tile_rgb).
print(to_text(grid))
to_png(grid).save("cat_ascii.png")

from effects import frames  # list of grids; the last one is `grid`
intro = [to_png(g) for g in frames(grid, "decode")]

# Glyphs over the photo: over_photo=True keeps each pixel's own color, and underlay() gives the photo to draw behind them.
from ascii import underlay
photo = Image.open("cat.jpg")
over = convert(photo, width=120, charset="diamond", aspect=1.0, over_photo=True)
to_png(over, font_size=16, aspect=1.0, under=underlay(photo, "black", 0.9)).save("cat_diamond.png")
```
