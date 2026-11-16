---
name: ascii-art
description: Turn any image, GIF or video into ASCII art or ASCII animation, as plain text, truecolor terminal output, HTML, PNG, GIF, WebP or MP4. Also animates still images with matrix-rain, decode, scan, glitch and wave effects. Also makes an ASCII animation from a short description such as "a running horse", using a freely licensed clip from Wikimedia Commons. Use when the user asks for ASCII art, an ASCII animation or video, a text-art version of an image, a terminal banner from a logo, or a "matrix" / retro text look.
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
| `--dither` | Floyd-Steinberg dithering. Good for smooth gradients and short ramps such as `blocks` or `minimal`. Put it after the image path (`--dither photo.jpg` reads the path as a dither name). |
| `--dither bayer` | Ordered dithering with a fixed 8x8 pattern: the classic retro crosshatch. The pattern stays put from frame to frame, so it is safe for animation. With `--colors` it also dithers the colors. |
| `--colors pico8` | Snap every color to a retro palette: `c64`, `pico8`, `gameboy` (4 greens), `cga` (black, cyan, magenta, white), `zx` (ZX Spectrum), `mono` (black and white). See "Retro palettes". |
| `--mode ramp` | `ramp` (default): one glyph per pixel, picked by brightness. `shape`: like ramp, but edges are drawn with symbols of the same shape (`/ \ | _`), so outlines are sharp. `braille`: each char holds 2x4 dots, so 8 pixels per char and much finer lines. `halfblock`: each char is `▀` with two true colors (top and bottom pixel), the sharpest color photo for terminals, HTML and PNG. `words`: a word poster (see "Word poster"). `tiles`: a tile poster (see "Tile poster"). `led`: an LED board (see "LED board"). `dots`: a halftone print (see "Halftone dots"). |
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
- `halfblock` ignores `-c` and `--fg`, because the colors are the picture. It uses `--dither bayer` only with `--colors`. Plain text (no `--color`) has no colors, so each cell becomes a shade block `█▓▒░` by brightness. `--bg none` does not make it transparent: transparent pixels become black.
- Terminals draw braille dots small, so braille looks dimmer there than in a PNG.
- `led` and `dots` draw real round lamps or dots in PNG, GIF, WebP and MP4. Text, terminal and HTML output get the round glyphs `●•·` by size instead. Both ignore `--dither` and `--gap`.

## LED board

`--mode led` draws each cell as one round lamp on a dark board. Lit lamps take the image color (or `--fg`) at a few brightness steps, unlit lamps stay faintly visible, and lit lamps have a soft glow.

```bash
uv run scripts/ascii.py logo.png --mode led -w 64 -o board.png
uv run scripts/animate.py --scene planet --mode led -w 64 -o planet.gif
```

- Defaults: square cells (`--aspect 1`) of 16 px (`--font-size 26`) on black. Text output keeps `--aspect 0.5`.
- `-c` sets the steps: one lit step per glyph before the last one. The default `●•· ` gives 3 steps; `-c "● "` gives plain on/off lamps.
- `--fg amber` (or `matrix`, `cyan`, any color) gives a one-color board.
- Works with `--effect`: `matrix` becomes falling lamps.

## Halftone dots

`--mode dots` is a halftone print: a dot in each cell and one on each cell corner, so the dots sit on a grid turned 45 degrees, as in print. The dot's area matches the ink, so tones stay right when you look from a distance.

```bash
uv run scripts/ascii.py photo.jpg --mode dots -w 90 --bg white -o print.png
uv run scripts/ascii.py photo.jpg --mode dots -w 90 --bg white --fg black -o newspaper.png
```

- Defaults: square cells of 12 px (`--font-size 20`) on black. On black, light parts get big dots. On `--bg white`, dark parts do, as on paper.
- Dot colors come from the image, or all dots are `--fg`.
- An image with a black background (a scene, a logo) on white paper: add `--invert`. It flips light and dark but keeps the colors, so an orange planet prints as dark orange.
- Not the same as `-c dots`, which is a braille ramp.

## Retro palettes

`--colors NAME` makes the art look like an old computer or console. Every color is snapped to that machine's palette. Add `--dither bayer` for the classic crosshatch between palette colors.

```bash
uv run scripts/ascii.py photo.jpg --mode halfblock --colors pico8 --dither bayer -w 120 -o out.png
uv run scripts/ascii.py photo.jpg --mode halfblock --colors gameboy --dither bayer -o out.png
uv run scripts/ascii.py photo.jpg -c blocks --colors c64 --dither bayer -o out.png
uv run scripts/animate.py --scene planet --mode halfblock --colors pico8 --dither bayer -o planet.gif
```

- `--mode halfblock` gives the most retro look: each half cell is one palette pixel.
- Without `--dither bayer`, each color goes to the nearest palette color. Plain `--dither` only spreads brightness, not color.
- The page defaults to the palette's darkest color, such as the Game Boy's dark green. Set `--bg` to change it.
- PNG, GIF and WebP output add no other colors: glyph edges are not smoothed, and `░▒▓` are drawn as dot patterns.
- `--fg` is snapped to the palette too. Tiles take their tile colors from the palette. Words mode ignores `--colors`.

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
- PICO-8 look: `--mode halfblock --colors pico8 --dither bayer -o out.png`
- Print-friendly: `--bg white -o out.png`
- Tile poster: `--mode tiles -w 36 -o poster.png`
- LED board: `--mode led -w 64 -o board.png`
- Newspaper print: `--mode dots -w 90 --bg white --fg black -o print.png`

### Post effects

`--post LIST` adds screen effects to PNG, JPG and WebP from `ascii.py`, and to GIF, WebP and MP4 from `animate.py`. LIST is comma separated:

- `crt`: a curved screen with rounded dark corners, plus scan lines, a soft vignette and a light glow. The full retro monitor.
- `scan`: thin dark lines between scan lines. They line up with the text rows, so they never beat against the glyphs.
- `bloom`: bright glyphs glow. The glyphs stay sharp.
- `chroma`: red and blue fringes that grow toward the edges. The centre stays clean.
- `vignette`: darker corners.
- `grain`: fine film grain, strongest in mid tones. Pure black stays black.

The order you type does not matter. Every effect is the same in each frame, so still areas never flicker; the grain does not move. Transparency becomes black. Effects show best on bright art and colour photos (`--mode halfblock`); on a black page, scan lines and vignette only show on the glyphs.

Preset: `--mode halfblock -w 120 --post crt -o tv.png`

## Animation

`scripts/animate.py` makes ASCII animation. It takes the same look options as `ascii.py` (`-w`, `-c`, `--mode`, `--sharpen`, `--bg`, `--fg`, `--invert`, `--contrast`, `--brightness`, `--font-size`, `--aspect`, `--gap`, `--colors`, `--dither`, and the word and tile poster options). Video input and `.mp4` output need ffmpeg. GIF and WebP do not.

```bash
uv run scripts/animate.py cat.gif                          # play in the terminal, Ctrl-C stops
uv run scripts/animate.py cat.gif -o out.gif               # also .webp, .mp4, or .html (one file with a play/pause player)
uv run scripts/animate.py clip.mp4 -o out.html --start 2 --duration 4 --fps 12
uv run scripts/animate.py photo.jpg --effect matrix -o intro.gif   # animate a still image
```

- Input: animated GIF, WebP or APNG, any video ffmpeg reads, or a still image with `--effect`.
- Frame timing comes from the source. `--fps` resamples. `--start` and `--duration` pick a slice in seconds.
- It stops at 300 frames by default and says so. Raise `--max-frames`, or lower `--fps`, for longer clips.
- One tonal range (and in braille one dot threshold) is used for all frames, so brightness does not pump.
- Still areas do not flicker: a pixel keeps its value until it changes by more than `--steady` (default 6, out of 255). Raise it to 16 or more for grainy film. `--steady 0` turns it off.
- Interlaced video is deinterlaced, and video with non-square pixels keeps its real shape.
- Avoid plain `--dither` for animation: it makes the glyphs crawl from frame to frame. `--dither bayer` holds still.
- GIF cannot play faster than about 50 fps, so fast video drops some frames in `.gif`. Use `.mp4` or `.webp` for smooth 60 fps.

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

`--effect NAME` turns one image into a 2–3 second intro at 25 fps that ends on the finished art and holds it for 1.5 seconds. Every effect works with every mode.

- `matrix`: falling columns of glyphs with a bright head, leaving the art behind them.
- `decode`: cells scramble through random glyphs and lock in, sweeping left to right.
- `scan`: a bright CRT line sweeps down and types each row in, with a short glow.
- `glitch`: short bursts of torn rows, glyph swaps and red/cyan bands. Loops well.
- `wave`: rows sway sideways on a sine wave that swells and calms. Loops well.

### Scenes

`--scene NAME` draws a looping animation in code, so no input file is needed. Each loop is 2 to 3.2 seconds, and the last frame flows into the first. Every mode, color option and output works. `--seed N` gives another variant (fire, waves, stars, rain, city, tree, planet), and `--fps` changes smoothness but keeps the loop length.

```bash
uv run scripts/animate.py --scene fire -o fire.gif                       # rising flames, warm colors
uv run scripts/animate.py --scene donut -o donut.gif                     # a frosted donut with sprinkles, spinning
uv run scripts/animate.py --scene cube --mode braille -o cube.gif        # a tumbling cube with bright edges
uv run scripts/animate.py --scene waves --mode halfblock -o waves.gif    # ocean swell under the moon
uv run scripts/animate.py --scene stars -o stars.gif                     # flying through a starfield
uv run scripts/animate.py --scene walker --mode braille -o run.gif       # a stick figure running in place
uv run scripts/animate.py --scene rain --mode braille -o rain.gif        # rain with splashes
uv run scripts/animate.py --scene bounce --mode halfblock -o ball.gif    # a ball that squashes as it bounces
uv run scripts/animate.py --scene text --mode halfblock -o text.gif      # the word ASCII riding a rainbow wave
uv run scripts/animate.py --scene city --mode halfblock -o city.gif      # night skyline in parallax, a train on a bridge
uv run scripts/animate.py --scene tree --mode halfblock -o tree.gif      # an autumn tree swaying, leaves falling
uv run scripts/animate.py --scene planet --mode halfblock -o planet.gif  # a ringed planet with turning bands and two moons
uv run scripts/animate.py --scene gears --mode braille -o gears.gif      # a clockwork: meshing gears, pendulum, escapement
```

- Use `-w 60` to `-w 100`. `--mode halfblock` gives the best color; `--mode braille` gives the crispest lines.
- Without `-o` the scene plays in the terminal.
- A scene is a plain function in `scripts/scenes.py`: `scene(w, h, n, seed)` returns `n` images that loop. To add one, write the function and give it the `@scene(width, height, frames, fps)` line.

### From a description

When the user describes a moving thing ("a running horse") instead of giving a file, find a free clip first. `scripts/fetch.py` searches Wikimedia Commons for animated GIFs and short videos with a free license and downloads the best match.

1. Fetch a clip: `uv run scripts/fetch.py "running horse" -o /tmp/clip`. It adds the right extension (`.gif`, `.webm`), then prints the saved path and an attribution line. To choose yourself, run with `--list` first, then `--pick N`.
2. Convert the printed path: `uv run scripts/animate.py /tmp/clip.gif --mode braille -w 80 --bg white -o out.gif`. Any preset works. For long videos add `--duration 5`.
3. Look at a frame of the result. If the subject is hard to see, try `--pick` with another result.
4. Give the user the attribution line with the result. Most licenses (CC BY, CC BY-SA) require it.

Search with short plain English words for the subject and the motion. Line drawings, silhouettes and clips on a plain background read best as ASCII. Busy real-world video often does not.

If nothing suitable is found, use a code-drawn scene instead: `animate.py --scene NAME` (see "Scenes").

## Python use

```python
import sys; sys.path.insert(0, "scripts")
from PIL import Image
from ascii import convert, to_text, to_png
grid = convert(Image.open("cat.jpg"), width=80, charset="blocks", dither=True)
# Cells are (char, (r, g, b)). With mode="halfblock" they are (char, top_rgb, bottom_rgb).
# With mode="tiles", tile cells are (char, ink_rgb, tile_rgb).
# With mode="led" or "dots", pass the same mode to to_png to draw lamps or dots.
print(to_text(grid))
to_png(grid).save("cat_ascii.png")

from ascii import snap_grid  # retro palette, as --colors c64 --dither bayer
retro = snap_grid(convert(Image.open("cat.jpg"), width=80, dither="bayer"), "c64", ordered=True)
to_png(retro, pure=True).save("cat_c64.png")  # pure: no blended edges, so only palette colors

from effects import frames  # list of grids; the last one is `grid`
intro = [to_png(g) for g in frames(grid, "decode")]
```
