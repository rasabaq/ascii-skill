# ascii-skill

A free, open-source agent skill that turns images, GIFs and video into ASCII art and ASCII animation. Inspired by [ASCII Magic](https://www.ascii-magic.com/).

- **Six modes:** `ramp` (classic), `shape` (outlines drawn with `/ \ | _`), `braille` (8 dots per character), `halfblock` (two true colors per character), `words` (a typographic word poster) and `tiles` (a square-tile poster)
- **Photo styles:** `--style characters`, `lines`, `diagonal`, `diamond`, `dot` or `cross` draws small glowing glyphs over the original photo, so the picture stays easy to see. `--mode halfblock --gap 1` makes a mosaic
- **Moving ASCII:** GIF, WebP, APNG or any video in; GIF, WebP, MP4, an HTML player or terminal playback out. `--subject` keeps only what moves (still camera), and still areas do not flicker
- **From a description:** `fetch.py "running horse"` finds a freely licensed clip on Wikimedia Commons and prints its attribution
- **Scenes drawn in code:** `fire`, `donut`, `cube`, `waves`, `stars`, `walker`, `rain`, `bounce`, `text`, `flower`, all looping
- **Effects for still images:** `matrix`, `decode`, `scan`, `glitch`, `wave`, `shimmer` (with `--under` for the photo behind the glyphs), `dust`
- **Outputs:** plain text, truecolor terminal, HTML, PNG, JPG, WebP, GIF, MP4
- **Looks:** 13 character ramps or your own, photo colors or one ink color, black, white or transparent background, glow, dithering, sharpening

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
uv run scripts/ascii.py cat.jpg --style diamond -o x.png         # diamonds glowing over the photo
uv run scripts/ascii.py cat.jpg --mode tiles -w 32 -o poster.png
uv run scripts/ascii.py cat.jpg --mode words --accent "#f28c28" -o poster.png

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
uv run scripts/test_effects.py
```

## License

MIT
