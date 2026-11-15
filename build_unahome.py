#!/usr/bin/env python3

"""UnaHome Lab - r/homelab-style network diagram.

Adapted from build.py in this repo (MIT): same palette, card language and
SVG -> PNG pipeline. Two changes: the content comes from unahome.yaml, and the
layout is computed (cursor based) instead of hand-placed, so cards cannot
overlap when the inventory changes.

    python3 build_unahome.py [--inventory FILE]
                                    -> out/unahome.svg + out/unahome.png
"""
from __future__ import annotations

import base64
import html
import pathlib
import shutil
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent

# Inventory: --inventory FILE wins, then an untracked unahome.local.yaml (where the
# real values live), then the redacted unahome.yaml committed in this repo.
_ARGS = sys.argv[1:]
if "--inventory" in _ARGS:
    INV_PATH = pathlib.Path(_ARGS[_ARGS.index("--inventory") + 1]).resolve()
elif (ROOT / "unahome.local.yaml").exists():
    INV_PATH = ROOT / "unahome.local.yaml"
else:
    INV_PATH = ROOT / "unahome.yaml"

INV = yaml.safe_load(INV_PATH.read_text(encoding="utf-8"))
ICONS = ROOT / "icons"
OUT = ROOT / "out"

W = 2400
M = 40
SCALE = "1.6"

# ---------------------------------------------------------------- palette
BG = "#0b0f15"
GRID = "#151c26"
PANEL = "#111821"
PANEL2 = "#161f2b"
CHIP = "#19222e"
BORDER = "#253042"
TEXT = "#e6edf3"
MUTED = "#8d9aab"
FAINT = "#5d6a7c"
TRUNK = "#d5dde6"
LINK = "#79c0ff"
REDDIT = "#ff5722"
DISK = "#1d2734"
DISK_EDGE = "#5a6b82"
HWC = "#c08a5c"
TAB = 34

NET = {n["key"]: n for n in INV["networks"]}
NC = {k: v["color"] for k, v in NET.items()}
DOMAIN = INV["meta"]["domain"]

# ---------------------------------------------------------------- fonts
def _find(*names):
    for name in names:
        for d in ("/usr/share/fonts/truetype/fira", "/usr/share/fonts/truetype/dejavu",
                  "/usr/share/fonts/truetype/firacode", str(ROOT / "fonts")):
            p = pathlib.Path(d) / name
            if p.exists():
                return str(p)
    return None


_FIRA = _find("FiraSans-Regular.ttf")
SANS = "Fira Sans" if _FIRA else "DejaVu Sans"
MONO = "Fira Code" if _find("FiraCode-Regular.ttf") else "DejaVu Sans Mono"
_WF = {
    400: _find("FiraSans-Regular.ttf", "DejaVuSans.ttf"),
    500: _find("FiraSans-Medium.ttf", "FiraSans-Regular.ttf", "DejaVuSans.ttf"),
    600: _find("FiraSans-SemiBold.ttf", "FiraSans-Bold.ttf", "DejaVuSans-Bold.ttf"),
    700: _find("FiraSans-Bold.ttf", "DejaVuSans-Bold.ttf"),
}
_MF = _find("FiraCode-Regular.ttf", "DejaVuSansMono.ttf")

try:
    from PIL import ImageFont
except Exception:                                    # Pillow optional
    ImageFont = None

_CACHE = {}


def m(s, size, weight=400, mono=False):
    """Width of s in px at `size`, measured from the real font file."""
    s = str(s)
    f = _MF if mono else _WF.get(weight, _WF[400])
    if ImageFont and f:
        key = (f, round(size, 2))
        if key not in _CACHE:
            _CACHE[key] = ImageFont.truetype(f, size=max(int(round(size * 8)), 8))
        return _CACHE[key].getlength(s) / 8.0
    return len(s) * size * (0.6 if mono else 0.53)


def fit(s, size, maxw, weight=400, mono=False, minimum=8.5):
    """Size to use so s fits maxw (never below minimum)."""
    w = m(s, size, weight, mono)
    return size if w <= maxw else max(minimum, size * maxw / max(w, 1))


def clip(s, size, maxw, weight=400, mono=False):
    s = str(s)
    if m(s, size, weight, mono) <= maxw:
        return s
    while s and m(s + "…", size, weight, mono) > maxw:
        s = s[:-1]
    return (s + "…") if s else ""


def esc(s):
    return html.escape(str(s), quote=True)


class SVG:
    def __init__(self):
        self.p = []
        self._cache = {}

    def add(self, s):
        self.p.append(s)

    def rect(self, x, y, w, h, rx=10, fill=PANEL, stroke=BORDER, sw=1.2, op=1, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{op}"{d}/>')

    def text(self, x, y, s, size=14, fill=TEXT, weight=400, anchor="start", mono=False, ls=0, op=1):
        fam = MONO if mono else SANS
        lsa = f' letter-spacing="{ls}"' if ls else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam}" font-size="{size}" fill="{fill}" '
                 f'font-weight="{weight}" text-anchor="{anchor}" opacity="{op}"{lsa}>{esc(s)}</text>')

    def icon(self, name, x, y, size):
        path, mime = None, None
        for ext, mt in (("svg", "image/svg+xml"), ("png", "image/png")):
            p = ICONS / f"{name}.{ext}"
            if p.exists():
                path, mime = p, mt
                break
        if path:
            key = str(path)
            if key not in self._cache:
                self._cache[key] = base64.b64encode(path.read_bytes()).decode()
            self.add(f'<image x="{x:.1f}" y="{y:.1f}" width="{size}" height="{size}" '
                     f'href="data:{mime};base64,{self._cache[key]}"/>')
        else:                                        # graceful placeholder
            r = size * 0.28
            self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{size}" height="{size}" rx="{r}" '
                     f'fill="{CHIP}" stroke="{BORDER}" stroke-width="1"/>')
            self.add(f'<text x="{x+size/2:.1f}" y="{y+size*0.68:.1f}" font-family="{SANS}" '
                     f'font-size="{size*0.5:.1f}" fill="{MUTED}" text-anchor="middle" '
                     f'font-weight="700">{esc(name[:1].upper())}</text>')

    def line(self, pts, color, sw=3, dash=None, r=10, op=1, cap="round"):
        self.add(f'<path d="{rounded(pts, r)}" fill="none" stroke="{color}" stroke-width="{sw}" '
                 f'stroke-linecap="{cap}" stroke-linejoin="round" opacity="{op}"'
                 + (f' stroke-dasharray="{dash}"' if dash else "") + "/>")

    def trunk(self, pts, r=12, sw=7):
        self.line(pts, TRUNK, sw=sw, r=r)
        self.line(pts, BG, sw=sw - 4.4, r=r)

    def pill(self, x, y, s, color, size=11, mono=False, anchor="start", h=None, pad=7):
        w = m(s, size, 600, mono) + pad * 2
        h = h or size + 10
        if anchor == "middle":
            x -= w / 2
        elif anchor == "end":
            x -= w
        self.rect(x, y, w, h, rx=h / 2, fill=color + "22", stroke=color + "88", sw=1)
        self.text(x + w / 2, y + h / 2 + size * 0.36, s, size, color, 600, "middle", mono)
        return w

    def label(self, x, y, s, color=MUTED, size=11.5, anchor="middle", mono=False, bg=BG):
        w = m(s, size, 600, mono) + 14
        bx = x - w / 2 if anchor == "middle" else (x if anchor == "start" else x - w)
        self.rect(bx, y - size - 3, w, size + 10, rx=5, fill=bg, stroke=bg, sw=0)
        self.text(bx + w / 2, y + 1, s, size, color, 600, "middle", mono)

    def render(self):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
                f'viewBox="0 0 {W} {H}">' + "".join(self.p) + "</svg>")


def rounded(pts, r):
    if len(pts) == 2:
        return f"M{pts[0][0]},{pts[0][1]} L{pts[1][0]},{pts[1][1]}"
    d = f"M{pts[0][0]},{pts[0][1]}"
    for i in range(1, len(pts) - 1):
        (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[i + 1]
        l1 = max(abs(x1 - x0), abs(y1 - y0)) or 1
        l2 = max(abs(x2 - x1), abs(y2 - y1)) or 1
        rr = min(r, l1 / 2, l2 / 2)
        ax, ay = x1 - (x1 - x0) / l1 * rr, y1 - (y1 - y0) / l1 * rr
        bx, by = x1 + (x2 - x1) / l2 * rr, y1 + (y2 - y1) / l2 * rr
        d += f" L{ax:.1f},{ay:.1f} Q{x1},{y1} {bx:.1f},{by:.1f}"
    return d + f" L{pts[-1][0]},{pts[-1][1]}"


S = SVG()
H = 0

# ---------------------------------------------------------------- shared pieces
def hostname(g):
    if g.get("host"):
        return f"{g['host']}.{DOMAIN}", LINK
    if g.get("internal"):
        return f"{g['internal']}.internal", None
    return None, None


def addr(x, y, ip, g, color, size=12):
    S.text(x, y, ip, size, color, 500, mono=True)
    name, ncol = hostname(g)
    if name:
        dx = x + m(ip, size, 500, True) + 9
        S.text(dx, y, "·", size, MUTED, 400, mono=True)
        S.text(dx + m("·", size, 400, True) + 6, y, name, size, ncol or color, 400, mono=True,
               op=1 if ncol else 0.85)


def tab_width(g):
    return 16 + m(g["name"], 20, 700) + 7 + m("·", 20, 700) + 7 + m(g["type"], 14, 600) + 18


def folder(x, y, w, h, tw, fill, stroke, sw=1.6):
    t = y - TAB
    r, rt, sl = 12, 9, 16
    d = (f"M{x},{y+h-r} L{x},{t+rt} Q{x},{t} {x+rt},{t} L{x+tw-sl:.1f},{t} "
         f"C{x+tw-sl/3:.1f},{t} {x+tw-sl/3:.1f},{y} {x+tw+sl/2:.1f},{y} "
         f"L{x+w-r},{y} Q{x+w},{y} {x+w},{y+r} L{x+w},{y+h-r} Q{x+w},{y+h} {x+w-r},{y+h} "
         f"L{x+r},{y+h} Q{x},{y+h} {x},{y+h-r} Z")
    S.add(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def device_card(x, y, w, h, icons, g, color, fill=PANEL, stroke=None, sw=1.6, isz=48):
    folder(x, y, w, h, tab_width(g), fill, stroke or color + "aa", sw)
    S.add(f'<text x="{x+16}" y="{y-10}" font-family="{SANS}" fill="{TEXT}">'
          f'<tspan font-size="20" font-weight="700">{esc(g["name"])}</tspan>'
          f'<tspan dx="7" font-size="20" font-weight="700" fill-opacity="0.6">·</tspan>'
          f'<tspan dx="7" font-size="14" font-weight="600">{esc(g["type"])}</tspan></text>')
    ix = x + 16
    for ic in icons:
        S.icon(ic, ix, y + 16, isz)
        ix += isz + 6
    tx = ix + 10
    S.text(tx, y + 30, g.get("model") or "custom build", 14, TEXT, 500)
    addr(tx, y + 50, g["ip"], g, color)
    if g.get("os"):
        S.text(tx, y + 68, g["os"], 12, MUTED, 400)
    if g.get("config"):
        S.text(tx, y + 86, g["config"], 12, FAINT, 400)


def panel(x, y, w, h, title=None, note=None, stroke=BORDER, fill=PANEL):
    S.rect(x, y, w, h, rx=14, fill=fill, stroke=stroke, sw=1.4)
    if title:
        S.text(x + 20, y + 34, title, 19, TEXT, 600)
    if note:
        S.text(x + 20, y + 56, clip(note, 12, w - 40), 12, MUTED, 400)


def chip_row(x, y, w, items, h=40, size=12.5):
    gap = 10
    cw = (w - gap * (len(items) - 1)) / len(items)
    for i, t in enumerate(items):
        cx = x + i * (cw + gap)
        S.rect(cx, y, cw, h, rx=9, fill=CHIP, stroke=BORDER, sw=1)
        S.text(cx + 12, y + h / 2 + 4.5, t, fit(t, size, cw - 24, 500), TEXT, 500)


# ---------------------------------------------------------------- header
meta = INV["meta"]
S.text(M, 92, meta["title"], 46, TEXT, 700, ls=-0.5)
S.text(M, 122, meta["subtitle"], 15, MUTED, 400)
S.text(W - M, 74, meta["watermark"], 21, REDDIT, 700, "end")
S.text(W - M, 100, meta["date"], 16, MUTED, 400, "end")

BG_IDX = len(S.p)
S.add("")
S.add("")

TOP = 150

# ---------------------------------------------------------------- left column
def networks_card(x, y, w):
    nets = INV["networks"]
    h = 70 + len(nets) * 60
    panel(x, y, w, h, "Networks", "one flat /24 per role · the UDR7 routes between them")
    for i, n in enumerate(nets):
        ry = y + 56 + i * 60
        S.rect(x + 14, ry, w - 28, 52, rx=9, fill=CHIP, stroke=n["color"] + "55", sw=1)
        S.add(f'<rect x="{x+14}" y="{ry}" width="6" height="52" rx="3" fill="{n["color"]}"/>')
        S.text(x + 32, ry + 22, n["tag"], 13, n["color"], 600, mono=True)
        S.text(x + 140, ry + 22, n["name"], 15.5, TEXT, 600)
        S.text(x + w - 28, ry + 22, n["subnet"], 13.5, TEXT, 500, "end", mono=True)
        S.text(x + 32, ry + 42, clip(n["note"], 12, w - 64), 12, MUTED, 400)
    return y + h


def legend_card(x, y, w):
    items = INV["legend"]
    h = 62 + len(items) * 30
    panel(x, y, w, h, "Legend")
    SX, TX = x + 26, x + 150
    for i, it in enumerate(items):
        ry = y + 78 + i * 30
        k = it["kind"]
        if k == "netcolor":
            for j, key in enumerate(["30", "220", "210", "wan"]):
                S.line([(SX + j * 12, ry), (SX + j * 12 + 8, ry)], NC[key], 4.4, r=0, cap="butt")
        elif k == "public":
            S.text(SX, ry + 4, "app.domain", 11.5, LINK, 600, mono=True)
        elif k == "internal":
            S.text(SX, ry + 4, "name.internal", 11, NC["30"], 400, mono=True, op=0.8)
        elif k == "tunnel":
            S.line([(SX, ry), (SX + 46, ry)], MUTED, 1.8, dash="2 5", r=0)
        elif k == "guest":
            S.text(SX, ry + 4, "CT 117", 11.5, FAINT, 600, mono=True)
        elif k == "docker":
            S.icon("docker", SX, ry - 9, 18)
        S.text(TX, ry + 4, it["text"], 12.5, MUTED, 400)
    return y + h


def public_card(x, y, w):
    pub = INV["public"]
    hosts = pub["hosts"]
    h = 76 + len(hosts) * 46 + 6
    panel(x, y, w, h, "Public hostnames", None)
    S.text(x + 20, y + 56, clip(pub["note"], 12, w - 40), 12, MUTED, 400)
    for i, hst in enumerate(hosts):
        ry = y + 70 + i * 46
        S.rect(x + 14, ry, w - 28, 40, rx=8, fill=CHIP, stroke=BORDER, sw=1)
        S.text(x + 26, ry + 17, hst["host"], 12.5, LINK, 600, mono=True)
        S.text(x + w - 26, ry + 17, hst["to"], 12.5, TEXT, 600, "end")
        S.text(x + 26, ry + 32, clip(hst["note"], 10.5, w - 150), 10.5, MUTED, 400)
        S.text(x + w - 26, ry + 32, hst["ct"], 10.5, FAINT, 500, "end", mono=True)
    return y + h


LX, LW = M, 520
y = TOP
y = networks_card(LX, y, LW) + 16
y = legend_card(LX, y, LW) + 16
y = public_card(LX, y, LW)
LEFT_BOTTOM = y

# ---------------------------------------------------------------- centre: internet, gateway, workstation
CX = 1175
cy = 200
S.add("")
blob_idx = len(S.p) - 1

RX, RW = 700, 320
rx_, ry_ = 580, 150
S.rect(rx_, ry_, RW, 84, rx=12, fill=PANEL, stroke=NC["220"] + "aa", sw=1.6)
S.icon("tailscale", rx_ + 16, ry_ + 22, 38)
S.text(rx_ + 66, ry_ + 38, INV["remote"]["name"], 17, TEXT, 600)
S.text(rx_ + 66, ry_ + 60, clip(INV["remote"]["note"], 12, RW - 80), 12, MUTED, 400)
S.line([(rx_ + RW, ry_ + 42), (CX - 160, ry_ + 42)], MUTED, 1.7, dash="2 5", r=0)
S.label((rx_ + RW + CX - 160) / 2, ry_ + 42 - 10, "phone · laptop", MUTED, 11)

UD = INV["udr7"]
ux, uy, uw, uh = 795, 330, 760, 168
WS = INV["workstation"]
wx, wy, ww, wh = 580, 560, 560, 124

S.line([(CX, cy + 62), (CX, uy)], NC["wan"], 3.4)
for i, (dx, dy, r) in enumerate([(-95, 18, 42), (-45, -8, 56), (25, -18, 62), (90, 6, 48),
                                 (130, 26, 30), (-130, 30, 28)]):
    S.add(f'<circle cx="{CX+dx}" cy="{cy+dy}" r="{r+2.5}" fill="#3a4a60"/>')
S.add(f'<rect x="{CX-150}" y="{cy+12}" width="300" height="46" rx="23" fill="#3a4a60"/>')
for dx, dy, r in [(-95, 18, 42), (-45, -8, 56), (25, -18, 62), (90, 6, 48), (130, 26, 30), (-130, 30, 28)]:
    S.add(f'<circle cx="{CX+dx}" cy="{cy+dy}" r="{r}" fill="#1a2433"/>')
S.add(f'<rect x="{CX-147.5}" y="{cy+14.5}" width="295" height="41" rx="20.5" fill="#1a2433"/>')
S.text(CX, cy + 16, INV["internet"]["title"], 26, TEXT, 600, "middle")
S.text(CX, cy + 42, INV["internet"]["note"], 12, MUTED, 400, "middle")
S.p[blob_idx] = ""

device_card(ux, uy, uw, uh, ["unifi"], UD, NC["30"], stroke=TRUNK)
chip_row(ux + 18, uy + 98, uw - 36, UD["roles"], h=42)
S.label(CX, (cy + 62 + uy) / 2, "WAN", NC["wan"], 11, mono=True)

device_card(wx, wy, ww, wh, ["windows"], WS, NC["220"])
S.line([(wx + 320, uy + uh), (wx + 320, wy)], NC["220"], 3.2)
S.label(wx + 320 + 52, (uy + uh + wy) / 2, "net .220", NC["220"], 11, mono=True)

# ---------------------------------------------------------------- right column: cloud + entry path + remote
RX = 1790
RW = 570
cloud = INV["cloud"]
ch = 70 + len(cloud) * 54
panel(RX, TOP, RW, ch, "Cloud", "what the world sees")
for i, c in enumerate(cloud):
    ry2 = TOP + 58 + i * 54
    S.rect(RX + 14, ry2, RW - 28, 46, rx=10, fill=PANEL2, stroke=BORDER, sw=1)
    S.icon(c["icon"], RX + 24, ry2 + 10, 26)
    S.text(RX + 60, ry2 + 20, c["name"], 14, TEXT, 600)
    S.text(RX + 60, ry2 + 36, clip(c["note"], 11.5, RW - 90), 11.5, MUTED, 400)

ey = TOP + ch + 16
entry = INV["entry"]
eh = 66 + len(entry) * 62
panel(RX, ey, RW, eh, "Inbound path", "public web names arrive through the tunnel")
for i, e in enumerate(entry):
    ry2 = ey + 58 + i * 62
    S.rect(RX + 14, ry2, RW - 28, 48, rx=9, fill=CHIP, stroke=BORDER, sw=1)
    S.text(RX + 26, ry2 + 20, e["name"], 13.5, TEXT, 600)
    S.text(RX + 26, ry2 + 36, clip(e["note"], 11, RW - 60), 11, MUTED, 400)
    if i < len(entry) - 1:
        S.line([(RX + 40, ry2 + 48), (RX + 40, ry2 + 62)], MUTED, 1.4, dash="3 3", r=0)

RIGHT_BOTTOM = ey + eh

S.line([(ux + uw, uy + 84), (RX, uy + 84)], MUTED, 1.6, dash="2 5", r=0)
S.label(ux + uw + 60, uy + 84 - 9, "tunnel out", MUTED, 11)

# ---------------------------------------------------------------- cluster
TOP_Y = max(RIGHT_BOTTOM, wy + wh, LEFT_BOTTOM if False else 0) + 20
CL = INV["cluster"]
cx0, cw_all = 580, W - M - 580


def guest_row_h(g):
    return 34 + (14 if g.get("host") else 0)


def node_h(node):
    return 46 + sum(guest_row_h(g) for g in node["guests"]) + 8


def node_card(x, y, w, node):
    h = node_h(node)
    S.rect(x, y, w, h, rx=11, fill=PANEL2, stroke=NC["30"] + "77", sw=1.2)
    S.text(x + 12, y + 21, node["name"], 15.5, TEXT, 700)
    nx = x + 12 + m(node["name"], 15.5, 700) + 9
    S.text(nx, y + 21, clip("· " + node["model"], 10.5, w - (nx - x) - 92), 10.5, MUTED, 400)
    S.text(x + w - 12, y + 21, f'{node["threads"]}t · {node["mem"]}', 10.5, FAINT, 600, "end", mono=True)
    S.text(x + 12, y + 37, f'{node["ip"]} · {node["cpu"]}', 10.5, NC["30"], 500, mono=True)
    gy = y + 44
    for g in node["guests"]:
        S.icon(g["icon"], x + 12, gy + 5, 18)
        S.text(x + 38, gy + 18, clip(g["name"], 12.5, w - 38 - 66, 600), 12.5, TEXT, 600)
        S.text(x + w - 12, gy + 18, f'{g["kind"]} {g["id"]}', 10, FAINT, 600, "end", mono=True)
        S.text(x + 38, gy + 31, clip(g["role"], 10, w - 38 - 56), 10, MUTED, 400)
        S.text(x + w - 12, gy + 31, g["ip"], 10, FAINT, 500, "end", mono=True)
        if g.get("host"):
            S.text(x + 38, gy + 44, f'{g["host"]}.{DOMAIN}', 9.5, LINK, 500, mono=True)
        gy += guest_row_h(g)
    return y + h


NCOL = len(CL["columns"])
GAP = 16
PAD = 20
colw = (cw_all - 2 * PAD - GAP * (NCOL - 1)) / NCOL
nodes = {n["name"]: n for n in CL["nodes"]}
colh = max(sum(node_h(nodes[n]) for n in col) + 14 * (len(col) - 1) for col in CL["columns"])
GY, FACTS_H = 92, 58
body_h = GY + FACTS_H + 16 + colh + PAD

device_card(cx0, TOP_Y, cw_all, body_h, ["proxmox"], CL, NC["30"],
            fill="#0f151e", stroke=NC["30"] + "88", sw=2)
S.trunk([(1400, uy + uh), (1400, TOP_Y)], sw=6)
S.label(1400 + 42, (uy + uh + TOP_Y) / 2, "VLAN 30", TRUNK, 11, mono=True)

ftw = (cw_all - 2 * PAD - 3 * 10) / 4
fy = TOP_Y + GY
for i, f in enumerate(CL["facts"]):
    tx = cx0 + PAD + i * (ftw + 10)
    S.rect(tx, fy, ftw, FACTS_H, rx=11, fill="#151d29", stroke="#2e3a4c", sw=1.2)
    S.add(f'<rect x="{tx+1}" y="{fy+12}" width="4" height="{FACTS_H-24}" rx="2" fill="{HWC}"/>')
    S.icon(f["icon"], tx + 12, fy + 15, 28)
    S.text(tx + 50, fy + 17, f["label"], 10, HWC, 700, ls=1.3)
    S.text(tx + 50, fy + 35, f["value"], 15.5, TEXT, 700)
    S.text(tx + 50, fy + 50, clip(f["sub"], 10.5, ftw - 60), 10.5, MUTED, 400)

cy0 = fy + FACTS_H + 16
for ci, col in enumerate(CL["columns"]):
    cx = cx0 + PAD + ci * (colw + GAP)
    cyv = cy0
    for nm in col:
        cyv = node_card(cx, cyv, colw, nodes[nm]) + 14
CLUSTER_BOTTOM = TOP_Y + body_h

# ---------------------------------------------------------------- bottom: storage + docker host
BY = CLUSTER_BOTTOM + 32


def disk_glyph(kind, x, y):
    if kind == "hdd":
        S.rect(x, y, 30, 40, rx=4, fill=DISK, stroke=DISK_EDGE, sw=1.2)
        S.add(f'<circle cx="{x+15}" cy="{y+16}" r="9" fill="none" stroke="{NC["30"]}" stroke-width="1.6"/>'
              f'<circle cx="{x+15}" cy="{y+16}" r="2" fill="{NC["30"]}"/>')
        S.rect(x + 8, y + 31, 14, 3, rx=1, fill=DISK_EDGE, stroke="none", sw=0)
        return 30
    if kind == "ssd":
        S.rect(x, y + 6, 44, 28, rx=3, fill=DISK, stroke=DISK_EDGE, sw=1.2)
        return 44
    S.rect(x, y + 10, 96, 20, rx=2, fill=DISK, stroke=DISK_EDGE, sw=1.2)
    return 96


def pool_box(p, x, y, w, h):
    S.rect(x, y, w, h, rx=10, fill=CHIP, stroke=BORDER, sw=1)
    S.text(x + 14, y + 24, p["name"], 15.5, TEXT, 700)
    S.text(x + 14 + m(p["name"], 15.5, 700) + 12, y + 24, p["layout"], 12.5, MUTED, 400)
    S.text(x + w - 14, y + 24, p["used"], 12, MUTED, 400, "end")
    bw = w - 28
    S.rect(x + 14, y + 34, bw, 8, rx=4, fill="#253042", stroke="none", sw=0)
    S.rect(x + 14, y + 34, max(bw * p["pct"] / 100, 8), 8, rx=4, fill=NC["30"], stroke="none", sw=0)
    gx = x + 14
    for grp in p["groups"]:
        dx = gx
        for _ in range(grp["count"]):
            dx += disk_glyph(grp["kind"], dx, y + 56) + 7
        gw = dx - 7 - gx
        S.line([(gx, y + 104), (gx, y + 108), (gx + gw, y + 108), (gx + gw, y + 104)],
               DISK_EDGE, 1.2, r=0, cap="butt")
        S.text(gx, y + 126, grp["label"], 12.5, TEXT, 500)
        S.text(gx, y + 141, grp["sub"], 11, MUTED, 400)
        S.text(gx, y + 155, grp["sub2"], 11, MUTED, 400)


st = INV["storage"]
POOL_H = 168
sx, sw = M, 1120
sh = 96 + POOL_H + 34
S.rect(sx, BY, sw, sh, rx=14, fill=PANEL, stroke=NC["30"] + "aa", sw=1.6)
S.icon("truenas", sx + 16, BY + 16, 34)
S.text(sx + 60, BY + 34, st["name"], 17, TEXT, 600)
S.pill(sx + sw - 14, BY + 16, st["type"], FAINT, 10.5, mono=True, h=20, anchor="end")
addr(sx + 60, BY + 54, st["ip"], st, NC["30"])
S.text(sx + 60, BY + 74, clip(st["note"], 12.5, sw - 80), 12.5, MUTED, 400)
pw = (sw - 28 - 16) / 2
for i, p in enumerate(st["pools"]):
    pool_box(p, sx + 14 + i * (pw + 16), BY + 90, pw, POOL_H)
S.text(sx + 18, BY + 90 + POOL_H + 24, clip(st["footer"], 11.5, sw - 40), 11.5, MUTED, 400)
STORAGE_BOTTOM = BY + sh

dk = INV["docker"]
dx0 = sx + sw + 20
dw = W - M - dx0
apps = dk["apps"]
nrow = (len(apps) + 1) // 2
ROWH = 44
dh = 92 + nrow * ROWH + 14
S.rect(dx0, BY, dw, dh, rx=14, fill=PANEL, stroke=NC["30"] + "aa", sw=1.6)
S.icon("docker", dx0 + 16, BY + 16, 34)
S.text(dx0 + 60, BY + 34, dk["name"], 17, TEXT, 600)
S.pill(dx0 + dw - 14, BY + 16, dk["type"], FAINT, 10.5, mono=True, h=20, anchor="end")
addr(dx0 + 60, BY + 54, dk["ip"], dk, NC["30"])
S.text(dx0 + 60, BY + 74, clip(dk["note"], 12.5, dw - 80), 12.5, MUTED, 400)
colw2 = (dw - 28 - 16) / 2
for i, a in enumerate(apps):
    r, c = i // 2, i % 2
    ax = dx0 + 14 + c * (colw2 + 16)
    ay = BY + 88 + r * ROWH
    S.rect(ax, ay, colw2, ROWH - 6, rx=8, fill=CHIP, stroke=BORDER, sw=1)
    S.icon(a["icon"], ax + 10, ay + 8, 20)
    S.text(ax + 38, ay + 16, a["name"], 12.5, TEXT, 600)
    S.text(ax + colw2 - 10, ay + 16, a["port"], 10.5, FAINT, 500, "end", mono=True)
    note = a["note"] if not a.get("host") else f'{a["note"]} · {a["host"]}.{DOMAIN}'
    S.text(ax + 38, ay + 30, clip(note, 10.5, colw2 - 70), 10.5, MUTED, 400)
DOCKER_BOTTOM = BY + dh

# ---------------------------------------------------------------- canvas height + background
H = int(max(STORAGE_BOTTOM, DOCKER_BOTTOM) + 40)
S.rect(0, 0, W, H, rx=0, fill=BG, stroke=BG, sw=0)
S.rect(0, 0, W, H, rx=0, fill="url(#dots)", stroke="none", sw=0)
dots = S.p.pop()
S.p[BG_IDX], S.p[BG_IDX + 1] = S.p.pop(), dots
S.p.insert(0, f'<defs><pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse">'
              f'<circle cx="1.5" cy="1.5" r="1.3" fill="{GRID}"/></pattern></defs>')

OUT.mkdir(exist_ok=True)
svg_path = OUT / "unahome.svg"
svg_path.write_text(S.render())
print(f"inv  {INV_PATH.name}")
print(f"svg  {svg_path}  {W}x{H}  font={SANS} mono={MONO}")
png = OUT / "unahome.png"
if shutil.which("rsvg-convert"):
    subprocess.run(["rsvg-convert", "-z", SCALE, "-o", str(png), str(svg_path)], check=True)
    print(f"png  {png}")
else:
    print("rsvg-convert not found - SVG only")
