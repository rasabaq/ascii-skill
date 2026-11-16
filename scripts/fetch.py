#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow>=10.1"]
# ///
"""Find a freely licensed animated GIF or short video on Wikimedia Commons and download it.

    uv run scripts/fetch.py "running horse"                 # saves the best match, prints path + attribution
    uv run scripts/fetch.py "running horse" --list          # show the top results
    uv run scripts/fetch.py "running horse" --pick 3 -o /tmp/clip
"""
import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://commons.wikimedia.org/w/api.php"
AGENT = "ascii-skill-agent/1.0 (open-source ASCII art tool)"  # generic on purpose: no personal data
TIMEOUT = 30
MAX_MB = 50
MIMES = ("image/gif", "video/webm", "video/ogg", "application/ogg", "video/mp4")
FREE = re.compile(r"public domain|^pd\b|cc0|cc[- ]by|gfdl|gpl|free art|copyrighted free use|godl|ogl|open government|fal\b|attribution|no restrictions")
NOT_FREE = re.compile(r"\bnc\b|-nc|\bnd\b|-nd|non-?free|fair use|all rights|noncommercial|noderiv")


def get(url, limit=None, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = r.read(limit + 1) if limit else r.read()
    except urllib.error.HTTPError as e:
        if e.code != 429 or tries <= 1:
            raise
        wait = e.headers.get("Retry-After", "")
        time.sleep(min(int(wait) if wait.isdigit() else 5, 30))  # Commons rate limit: wait, then retry
        return get(url, limit, tries - 1)
    if limit and len(data) > limit:
        raise ValueError("file is larger than %d MB" % (limit // 2**20))
    return data


def search(query, n=20):
    """Return Commons file pages for the query: animated GIFs and videos, with video derivatives."""
    pages = {}
    for kind in ("filemime:image/gif", "filetype:video"):
        params = {"action": "query", "format": "json", "formatversion": 2, "generator": "search",
                  "gsrnamespace": 6, "gsrsearch": "%s %s" % (query, kind), "gsrlimit": n,
                  "prop": "videoinfo", "viprop": "url|size|mime|extmetadata|derivatives",
                  "viextmetadatafilter": "LicenseShortName|Artist|Credit|ObjectName|NonFree"}
        for p in json.loads(get(API + "?" + urllib.parse.urlencode(params))).get("query", {}).get("pages", []):
            if p.get("videoinfo"):
                pages.setdefault(p["title"], p)
    return list(pages.values())


def meta(info, key):
    """Plain text of one extmetadata field (Commons gives HTML)."""
    v = str(info.get("extmetadata", {}).get(key, {}).get("value", ""))
    v = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", v)).split())
    return re.sub(r" ([),.;:])", r"\1", v)


def is_free(info):
    lic = meta(info, "LicenseShortName").lower()
    return bool(FREE.search(lic)) and not NOT_FREE.search(lic) and meta(info, "NonFree").lower() != "true"


def candidate(page):
    """Flatten a page into what we rank and download. Videos use a small transcode when there is one."""
    i = page["videoinfo"][0]
    c = {"title": page["title"].split(":", 1)[-1], "mime": i.get("mime", ""), "dur": i.get("duration") or 0,
         "url": i["url"], "size": i.get("size", 0), "page": i.get("descriptionurl", ""), "index": page.get("index", 99),
         "free": is_free(i), "license": meta(i, "LicenseShortName") or "unknown license",
         "author": meta(i, "Artist") or meta(i, "Credit") or "unknown author"}
    webm = [d for d in i.get("derivatives", []) if "webm" in d.get("type", "") and d.get("height", 0) <= 480]
    if c["mime"] != "image/gif" and webm:
        d = max(webm, key=lambda d: d["height"])
        c["url"], c["size"] = d["src"], min(c["size"], int(d.get("bandwidth", 0) * c["dur"] / 8) or c["size"])
    return c


def score(c, query):
    """Higher is better. Moving media only; title match, short clips and small files win."""
    if c["mime"] not in MIMES or c["dur"] < 0.5 or c["size"] > MAX_MB * 2**20:
        return None  # still image, odd format, or too big
    words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2] or [query.lower()]
    title = c["title"].lower()
    s = 3.0 * sum(w[:-1] in title for w in words) / len(words)  # w[:-1]: "horses" matches "horse"
    s += 2.0 if c["mime"] == "image/gif" else 1.0
    s += 1.0 if c["dur"] <= 30 else 0.3 if c["dur"] <= 90 else -1.0
    s -= 0.1 * c["size"] / 2**20  # smaller is faster and plenty for ASCII
    return s - 0.05 * c["index"]  # keep a little of the search engine's own relevance


def rank(cands, query):
    scored = [(score(c, query), c) for c in cands if c["free"]]
    return [c for s, c in sorted((x for x in scored if x[0] is not None), key=lambda x: -x[0])]


def attribution(c):
    return '"%s" by %s, %s, %s' % (c["title"], c["author"], c["license"], c["page"])


def save(c, out):
    ext = os.path.splitext(urllib.parse.urlparse(c["url"]).path)[1] or ".bin"
    if out and os.path.isdir(out):
        out = os.path.join(out, re.sub(r"[^\w.-]+", "_", os.path.splitext(c["title"])[0]) + ext)
    elif out:
        out = out if os.path.splitext(out)[1] else out + ext
    else:
        out = re.sub(r"[^\w.-]+", "_", os.path.splitext(c["title"])[0]) + ext
    data = get(c["url"], MAX_MB * 2**20)
    with open(out, "wb") as f:
        f.write(data)
    if ext == ".gif":
        from PIL import Image
        with Image.open(out) as im:
            frames = getattr(im, "n_frames", 1)
        if frames < 2:
            os.remove(out)
            raise ValueError("%s is a still GIF" % c["title"])
    return out


def fmt_row(n, c):
    kind = "gif" if c["mime"] == "image/gif" else "video"
    return "%2d. %-5s %6.1f MB %6.1f s  %-14s %s" % (n, kind, c["size"] / 2**20, c["dur"], c["license"], c["title"])


def main(argv=None):
    p = argparse.ArgumentParser(description="Download a freely licensed animated GIF or video from Wikimedia Commons.")
    p.add_argument("query", help='what to look for, like "running horse"')
    p.add_argument("-o", "--out", help="file or folder to save to (default: current folder, Commons file name)")
    p.add_argument("--list", action="store_true", help="show the top results and stop")
    p.add_argument("--pick", type=int, help="download result N from --list instead of the best one")
    p.add_argument("-n", type=int, default=10, help="how many results --list shows (default 10)")
    a = p.parse_args(argv)
    try:
        cands = [candidate(pg) for pg in search(a.query)]
        dropped = sum(not c["free"] for c in cands)
        ranked = rank(cands, a.query)
        if dropped:
            print("note: skipped %d result(s) without a free license" % dropped, file=sys.stderr)
        if not ranked:
            raise ValueError('no freely licensed animated GIF or short video found for "%s"' % a.query)
        if a.list:
            for n, c in enumerate(ranked[:a.n], 1):
                print(fmt_row(n, c))
            return 0
        if a.pick:
            if not 1 <= a.pick <= len(ranked):
                raise ValueError("--pick must be between 1 and %d" % len(ranked))
            todo = [ranked[a.pick - 1]]
        else:
            todo = ranked[:5]
        for c in todo:
            try:
                path = save(c, a.out)
            except ValueError as e:  # still GIF or too big: try the next one
                print("note: skipped %s" % e, file=sys.stderr)
                continue
            print(path)
            print("Attribution: " + attribution(c))
            return 0
        raise ValueError("none of the top results could be used")
    except KeyboardInterrupt:
        return 130
    except Exception as e:  # network, HTTP, JSON, disk: one clean line, no traceback
        print("fetch: error: %s" % (getattr(e, "reason", None) or e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
