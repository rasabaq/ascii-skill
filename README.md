# ascii-skill

A free, open-source agent skill that turns images, GIFs and video into ASCII art and ASCII animation. Inspired by [ASCII Magic](https://www.ascii-magic.com/).

- **Eight modes:** `ramp` (classic), `shape` (outlines drawn with `/ \ | _`), `braille` (8 dots per character), `halfblock` (two true colors per character), `words` (a typographic word poster), `tiles` (a square-tile poster), `led` (an LED board with glowing lamps) and `dots` (a halftone print). The last two still give round-glyph text
- **Moving ASCII:** GIF, WebP, APNG or any video in; GIF, WebP, MP4, an HTML player or terminal playback out. `--subject` keeps only what moves (still camera), and still areas do not flicker
- **From a description:** `fetch.py "running horse"` finds a freely licensed clip on Wikimedia Commons and prints its attribution
- **Scenes drawn in code:** `fire`, `donut`, `cube`, `waves`, `stars`, `walker`, `rain`, `bounce`, `text`, `city`, `tree`, `planet`, `gears`, all looping
- **Effects for still images:** `matrix`, `decode`, `scan`, `glitch`, `wave`
- **Post effects:** `--post crt,bloom,chroma,scan,vignette,grain` for PNG, GIF, WebP and MP4, steady from frame to frame
- **Outputs:** plain text, truecolor terminal, HTML, PNG, JPG, WebP, GIF, MP4
- **Looks:** 7 character ramps or your own, photo colors or one ink color, black, white or transparent background, dithering, sharpening

Python 3.9+ and Pillow. ffmpeg only for video.

## Install as a skill

Copy or clone this folder into your agent's skills folder:

```bash
git clone https://github.com/rasabaq/ascii-skill ~/.claude/skills/ascii-art
```

Then ask your agent something like "make ASCII art of cat.jpg" or "turn this GIF into an ASCII animation".

## Use from the command line

```bash
uv run scripts/ascii.py cat.jpg                                  # text in the terminal
uv run scripts/ascii.py cat.jpg --mode halfblock --color         # best color photo in a terminal
uv run scripts/ascii.py cat.jpg --mode braille --dither -o x.png # fine dot drawing
uv run scripts/ascii.py cat.jpg --mode tiles -w 32 -o poster.png
uv run scripts/ascii.py cat.jpg --mode words --accent "#f28c28" -o poster.png
uv run scripts/ascii.py cat.jpg --mode dots --bg white -o print.png
uv run scripts/animate.py --scene planet --mode led -w 64 -o board.gif

uv run scripts/animate.py cat.gif -o out.mp4                     # GIF or video to ASCII
uv run scripts/animate.py cat.jpg --effect matrix -o intro.gif   # animate a still image
uv run scripts/animate.py --scene walker --mode braille -o run.gif
uv run scripts/fetch.py "running horse"                          # then animate.py the printed path
```

`uv run` installs Pillow on its own. Without `uv`, run `pip install pillow` and then `python3 scripts/ascii.py`.

See [SKILL.md](SKILL.md) for every option.

## Test

```bash
uv run scripts/test_ascii.py
uv run scripts/test_animate.py
uv run scripts/test_scenes.py
uv run scripts/test_fetch.py
uv run scripts/test_post.py
uv run scripts/test_modes.py
uv run --with pillow python scripts/test_effects.py
```

## License

MIT
