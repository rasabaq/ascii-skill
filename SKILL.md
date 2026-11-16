---
name: ascii-art
description: Turn any image, GIF or video into ASCII art or ASCII animation, as plain text, truecolor terminal output, HTML, PNG, GIF, WebP or MP4. Also animates still images with matrix-rain, decode, scan, glitch and wave effects. Use when the user asks for ASCII art, an ASCII animation or video, a text-art version of an image, a terminal banner from a logo, or a "matrix" / retro text look.
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
3. Run it, then read the result. For a PNG, open the image and look at it.
4. If the subject is hard to see, tune and run again (see "Fixing weak results").

## Options

| Option | What it does |
|---|---|
| `-w 100` | Width in characters (1–1000). Use 60–80 for chat, 120–200 for PNG/HTML, 120+ for screenshots of text. |
| `-c standard` | Character ramp: `standard`, `detailed`, `blocks`, `terminal`, `minimal`, `binary`, `dots`, or your own string from dense to empty, like `-c "#*. "`. |
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

## Fixing weak results

The script already stretches every image to its full tonal range, so most images look fine with no tuning.

- Photos: `-c blocks --dither` gives the most recognizable faces and animals.
- Dark subject (black dog, night scene) disappears on the black background: use `--bg white`. Raising `--brightness 1.5` also helps. Raising contrast makes dark scenes worse.
- Dark logo on a white background shows as a solid block: add `--bg white` (or `--invert` for terminal output).
- Want more detail at the same width: `--mode braille --dither --sharpen` for line-art style, `--mode halfblock` for a color photo.
- Too much noise: use fewer columns or a shorter ramp (`-c minimal`).
- Banding in gradients: add `--dither`.
- Chat output: never use `--color`, because escape codes show up as junk. Wrap the text in a code block.
- SVG is not supported. Convert it to PNG first (`rsvg-convert -w 800 logo.svg -o logo.png`).

## Modes in short

- `braille` ignores `-c`. Use it with `--dither` for photos and without it for logos. Colors follow the photo, or `--fg`.
- `halfblock` ignores `-c`, `--dither` and `--fg`, because the colors are the picture. Plain text (no `--color`) has no colors, so each cell becomes a shade block `█▓▒░` by brightness. `--bg none` does not make it transparent: transparent pixels become black.
- Terminals draw braille dots small, so braille looks dimmer there than in a PNG.

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

- Matrix: `-c binary --fg matrix -o out.png`
- Retro amber terminal: `-c terminal --fg amber -o out.png`
- Photo mosaic in color: `-c detailed -w 160 -o out.html`
- Best color photo in a terminal: `--mode halfblock --color`
- Fine dot drawing: `--mode braille --dither --sharpen -o out.png`
- Print-friendly: `--bg white -o out.png`
- Tile poster: `--mode tiles -w 36 -o poster.png`

## Animation

`scripts/animate.py` makes ASCII animation. It takes the same look options as `ascii.py` (`-w`, `-c`, `--mode`, `--sharpen`, `--bg`, `--fg`, `--invert`, `--contrast`, `--brightness`, `--font-size`, `--aspect`, `--gap`, and the word and tile poster options). Video input and `.mp4` output need ffmpeg. GIF and WebP do not.

```bash
uv run scripts/animate.py cat.gif                          # play in the terminal, Ctrl-C stops
uv run scripts/animate.py cat.gif -o out.gif               # also .webp, .mp4, or .html (one file with a play/pause player)
uv run scripts/animate.py clip.mp4 -o out.html --start 2 --duration 4 --fps 12
uv run scripts/animate.py photo.jpg --effect matrix -o intro.gif   # animate a still image
```

- Input: animated GIF, WebP or APNG, any video ffmpeg reads, or a still image with `--effect`.
- Frame timing comes from the source. `--fps` resamples. `--start` and `--duration` pick a slice in seconds.
- It stops at 300 frames by default and says so. Raise `--max-frames`, or lower `--fps`, for longer clips.
- One tonal range is used for all frames, so brightness does not pump.
- Avoid `--dither` for animation: it makes the glyphs crawl from frame to frame.
- GIF cannot play faster than about 50 fps, so fast video drops some frames in `.gif`. Use `.mp4` or `.webp` for smooth 60 fps.
- Light subject on a light background shows as a solid block: add `--bg white`.

### Effects for still images

`--effect NAME` turns one image into a 2–3 second intro at 25 fps that ends on the finished art and holds it for 1.5 seconds. Every effect works with every mode.

- `matrix`: falling columns of glyphs with a bright head, leaving the art behind them.
- `decode`: cells scramble through random glyphs and lock in, sweeping left to right.
- `scan`: a bright CRT line sweeps down and types each row in, with a short glow.
- `glitch`: short bursts of torn rows, glyph swaps and red/cyan bands. Loops well.
- `wave`: rows sway sideways on a sine wave that swells and calms. Loops well.

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
```
