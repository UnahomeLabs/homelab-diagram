#!/usr/bin/env python3
"""Layout QA for out/unahome.svg - catches what you cannot see in code:

  1. text colliding with text
  2. text running past the right edge of the card it sits in
  3. cards partially overlapping each other (nested cards are fine)
  4. anything drawn outside the canvas

    python3 qa_check.py [--map]
"""
import pathlib
import sys
import xml.etree.ElementTree as ET

from PIL import ImageFont

ROOT = pathlib.Path(__file__).resolve().parent
SVG = ROOT / "out" / "unahome.svg"
NS = "{http://www.w3.org/2000/svg}"

FILES = {
    ("sans", 400): "/usr/share/fonts/truetype/fira/FiraSans-Regular.ttf",
    ("sans", 500): "/usr/share/fonts/truetype/fira/FiraSans-Medium.ttf",
    ("sans", 600): "/usr/share/fonts/truetype/fira/FiraSans-SemiBold.ttf",
    ("sans", 700): "/usr/share/fonts/truetype/fira/FiraSans-Bold.ttf",
    ("mono", 400): "/usr/share/fonts/truetype/firacode/FiraCode-Regular.ttf",
}
CACHE = {}


def measure(s, size, weight, mono):
    path = FILES.get(("mono" if mono else "sans", weight)) or FILES[("sans", 400)]
    ck = (path, round(size, 2))
    if ck not in CACHE:
        CACHE[ck] = ImageFont.truetype(path, max(int(round(size * 8)), 8))
    return CACHE[ck].getlength(s) / 8.0


def load():
    root = ET.parse(SVG).getroot()
    w, h = float(root.get("width")), float(root.get("height"))
    rects, texts = [], []
    for el in root.iter():
        if el.tag == NS + "rect":
            try:
                x, y = float(el.get("x", 0)), float(el.get("y", 0))
                rw, rh = float(el.get("width", 0)), float(el.get("height", 0))
            except (TypeError, ValueError):
                continue
            if rw > 40 and rh > 26:
                rects.append((x, y, x + rw, y + rh))
        elif el.tag == NS + "text":
            content = "".join(el.itertext())
            if not content.strip():
                continue
            try:
                x, y = float(el.get("x", 0)), float(el.get("y", 0))
                size = float(el.get("font-size", 14))
            except (TypeError, ValueError):
                continue
            weight = int(float(el.get("font-weight", 400)))
            mono = "Fira Code" in (el.get("font-family") or "")
            anchor = el.get("text-anchor", "start")
            tw = measure(content, size, weight, mono)
            left = x if anchor == "start" else (x - tw / 2 if anchor == "middle" else x - tw)
            texts.append({"s": content, "l": left, "r": left + tw,
                          "t": y - size * 0.78, "b": y + size * 0.22})
    return (w, h), rects, texts


def main():
    (CW, CH), rects, texts = load()
    print(f"canvas {CW:.0f}x{CH:.0f}  texts={len(texts)} rects={len(rects)}")

    hits = []
    for i, a in enumerate(texts):
        for b in texts[i + 1:]:
            ow = min(a["r"], b["r"]) - max(a["l"], b["l"])
            oh = min(a["b"], b["b"]) - max(a["t"], b["t"])
            if ow > 3 and oh > 3:
                hits.append((ow * oh, a["s"], b["s"], round(a["l"]), round(a["t"])))
    hits.sort(reverse=True)
    print(f"text/text overlaps: {len(hits)}")
    for area, s1, s2, x, y in hits[:20]:
        print(f"  {area:7.0f}  @({x},{y})  {s1[:40]!r} X {s2[:40]!r}")

    over = []
    for t in texts:
        for (rl, rt, rr, rb) in rects:
            if rl - 1 <= t["l"] <= rr and rt - 1 <= t["t"] <= rb and t["r"] > rr + 2:
                over.append((round(t["r"] - rr), t["s"], round(rr), round(t["t"])))
                break
    over.sort(reverse=True)
    print(f"text past its card edge: {len(over)}")
    for d, s, edge, y in over[:20]:
        print(f"  +{d:4d}px edge={edge} y={y}  {s[:56]!r}")

    cards = [r for r in rects if (r[2] - r[0]) > 150 and (r[3] - r[1]) > 55]
    bad = []
    for i, a in enumerate(cards):
        for b in cards[i + 1:]:
            iw = min(a[2], b[2]) - max(a[0], b[0])
            ih = min(a[3], b[3]) - max(a[1], b[1])
            if iw <= 2 or ih <= 2:
                continue
            nested = (a[0] - 2 <= b[0] and a[1] - 2 <= b[1] and a[2] + 2 >= b[2] and a[3] + 2 >= b[3]) or \
                     (b[0] - 2 <= a[0] and b[1] - 2 <= a[1] and b[2] + 2 >= a[2] and b[3] + 2 >= a[3])
            if not nested:
                bad.append((round(iw * ih), tuple(round(v) for v in a), tuple(round(v) for v in b)))
    bad.sort(reverse=True)
    print(f"cards partially overlapping: {len(bad)}")
    for area, a, b in bad[:10]:
        print(f"  {area:8.0f}  {a} X {b}")

    outside = [tuple(round(v) for v in r) for r in rects
               if r[0] < -1 or r[1] < -1 or r[2] > CW + 1 or r[3] > CH + 1]
    print(f"rects outside the canvas: {len(outside)}")
    for r in outside[:10]:
        print(f"  {r}")

    if "--map" in sys.argv:
        print("\nlayout map (x, y, w, h):")
        for r in sorted(rects, key=lambda r: (round(r[1]), round(r[0]))):
            print(f"  {r[0]:6.0f} {r[1]:6.0f} {r[2]-r[0]:6.0f} {r[3]-r[1]:6.0f}")


if __name__ == "__main__":
    main()
