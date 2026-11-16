# /// script
# dependencies = ["pillow>=10.1"]
# ///
"""Offline checks for fetch.py (no network). Run: uv run scripts/test_fetch.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from fetch import attribution, candidate, is_free, rank  # noqa: E402

MB = 2**20


def page(title, mime, size, dur=0, lic="CC BY-SA 4.0", index=1, derivatives=()):
    ext = {"LicenseShortName": {"value": lic}, "Artist": {"value": '<a href="//commons.wikimedia.org/wiki/User:Jo">Jo &amp; Al</a> (cropped by <i>Bo</i> )'}}
    info = {"mime": mime, "size": size, "duration": dur, "url": "https://upload.example/" + title,
            "descriptionurl": "https://commons.wikimedia.org/wiki/File:" + title, "extmetadata": ext,
            "derivatives": list(derivatives)}
    return candidate({"title": "File:" + title, "index": index, "videoinfo": [info]})


# Licenses: free ones pass, NC/ND and unknown ones do not.
for lic in ("CC BY-SA 3.0", "CC BY 4.0", "CC0", "Public domain", "GFDL", "Copyrighted free use", "PD-USGov", "GODL-India"):
    assert is_free({"extmetadata": {"LicenseShortName": {"value": lic}}}), lic
for lic in ("CC BY-NC 4.0", "CC BY-ND 2.0", "CC BY-NC-SA 3.0", "Attribution-NonCommercial", "Fair use", ""):
    assert not is_free({"extmetadata": {"LicenseShortName": {"value": lic}}}), lic
assert not is_free({"extmetadata": {"LicenseShortName": {"value": "CC BY 4.0"}, "NonFree": {"value": "true"}}})

# Ranking: animated GIF beats video, video beats nothing; stills, huge files and non-free files are dropped.
gif = page("Running horse.gif", "image/gif", MB, dur=1.2, index=3)
video = page("Running horse.webm", "video/webm", 3 * MB, dur=12, index=1)
long_video = page("Running horse long.webm", "video/webm", 3 * MB, dur=600, index=2)
still = page("Running horse still.gif", "image/gif", MB, dur=0, index=1)
huge = page("Running horse huge.gif", "image/gif", 80 * MB, dur=2, index=1)
nonfree = page("Running horse nc.gif", "image/gif", MB, dur=1, lic="CC BY-NC 4.0", index=1)
jpeg = page("Running horse.jpg", "image/jpeg", MB, index=1)
other = page("Sunset over hills.gif", "image/gif", MB, dur=1, index=1)
big_gif = page("Running horse big.gif", "image/gif", 30 * MB, dur=1, index=1)
order = rank([still, huge, nonfree, jpeg, long_video, other, big_gif, video, gif], "running horse")
names = [c["title"] for c in order]
assert names[:2] == ["Running horse.gif", "Running horse.webm"], names
assert names.index("Running horse.webm") < names.index("Running horse long.webm"), "short clips first"
assert names.index("Running horse.gif") < names.index("Running horse big.gif"), "small files first"
assert names.index("Running horse.gif") < names.index("Sunset over hills.gif"), "title match counts"
for gone in ("Running horse still.gif", "Running horse huge.gif", "Running horse nc.gif", "Running horse.jpg"):
    assert gone not in names, gone

# Videos download a small webm transcode when Commons has one.
v = page("Big.ogv", "application/ogg", 200 * MB, dur=10, derivatives=[
    {"src": "https://x/Big.ogv.240p.vp9.webm", "type": 'video/webm; codecs="vp9"', "height": 240, "bandwidth": 400000},
    {"src": "https://x/Big.ogv.480p.vp9.webm", "type": 'video/webm; codecs="vp9"', "height": 480, "bandwidth": 1600000},
    {"src": "https://x/Big.ogv.1080p.vp9.webm", "type": 'video/webm; codecs="vp9"', "height": 1080, "bandwidth": 9000000}])
assert v["url"].endswith("480p.vp9.webm") and v["size"] == 2_000_000, v

# Attribution: plain text from the HTML extmetadata, one line.
assert attribution(gif) == ('"Running horse.gif" by Jo & Al (cropped by Bo), CC BY-SA 4.0, '
                            "https://commons.wikimedia.org/wiki/File:Running horse.gif"), attribution(gif)
print("ok")
