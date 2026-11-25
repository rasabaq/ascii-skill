# Van Gogh examples

Four Van Gogh works run through the skill. In each film a white line sweeps across: left of it is the painting, right of it is the skill's version. Each film is 12 s and loops with no jump. Open `index.html` to see all four side by side.

| Film | Work | Command |
|---|---|---|
| `self-portrait-stipple-dust.mp4` | *Self-Portrait*, 1887 | `animate.py portrait.jpg --mode stipple -w 110 --effect dust --wind right` |
| `almond-blossom-diamond-shimmer.mp4` | *Almond Blossom*, 1890 | `animate.py almond.jpg --style diamond --effect shimmer` |
| `irises-characters-shimmer.mp4` | *Irises*, 1889 | `animate.py irises.jpg --style characters -w 90 --font-size 18 --effect shimmer` |
| `straw-hat-braille-shimmer.mp4` | *Self-Portrait with Straw Hat*, 1887 | `animate.py strawhat.jpg --mode braille -w 110 --effect shimmer` |

The sweep is added afterwards with ffmpeg: the ASCII clip is looped to 12 s, and a moving mask (`maskedmerge`) shows the painting on one side of the line and the ASCII art on the other.

Each film also has a GIF preview of the same name for the main README, because GitHub does not play MP4 files inline. The GIF is the film at 1.5x speed (8 s), 10 fps and 480 px wide (420 px for the portraits), made with ffmpeg's `palettegen` and `paletteuse=dither=bayer:bayer_scale=4` (128 colors for the almond and straw hat films, to stay under 3 MB).

Paintings: Vincent van Gogh, public domain. Images from Wikimedia Commons (Google Art Project and others).
