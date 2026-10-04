#!/usr/bin/env python3
"""
Teaser figure for the project page, drawn on the page's own background.

Web copy of the paper's teaser script (teaser_plot/make_teaser.py): same
layout and signals, but one palette per page theme, so the figure sits on the
page instead of on a white card.
  - left  : simplified transformer stack (vision encoder -> layers) + question
  - right : output probabilities (yellow stereotype vs purple true colour)
            and a readiness / evidence signal, both keyed to t = 5
  - bottom: streaming video frames cropped from the two kitchen renders

Usage:  python make_teaser_web.py          -> both themes
        python make_teaser_web.py dark     -> one theme
Writes static/images/teaser-<theme>.png and .webp (2400 px wide).
The kitchen renders here are 2x-downscaled copies of the originals; the
frames are cropped to 440 px, so nothing is lost.
"""

import os
import subprocess
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from matplotlib.path import Path
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from PIL import Image

# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #
HERE = os.path.dirname(os.path.abspath(__file__))
IMG_BEFORE = os.path.join(HERE, "kitchen.jpg")
IMG_AFTER = os.path.join(HERE, "kitchen_purple_bananas.jpg")
OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "static", "images"))
WEB_WIDTH = 2400       # px width of the published images

# --- theme ----------------------------------------------------------------- #
# With no argument, render every theme, each in a fresh interpreter (the
# palette is read at import time by the drawing code below).
THEMES_ORDER = ("light", "dark")
if len(sys.argv) < 2:
    for _theme in THEMES_ORDER:
        subprocess.run([sys.executable, os.path.abspath(__file__), _theme],
                       check=True)
    sys.exit(0)
THEME = sys.argv[1]
if THEME not in THEMES_ORDER:
    sys.exit(f"unknown theme {THEME!r}; use one of {THEMES_ORDER}")
# optional: `--bg HEX` renders the theme on another background (the grid,
# bubble and chip tints follow it), `--out PATH` writes PATH.png / PATH.webp
_opts = dict(zip(sys.argv[2::2], sys.argv[3::2]))
BG_OVERRIDE = _opts.get("--bg")
OUT_OVERRIDE = _opts.get("--out")


def mix(a, b, t):
    """Blend hex colour a toward hex colour b by fraction t."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))

# The strip, the time axis of both plots and the legend all derive from
# N_FRAMES: 11 shows t = 0 .. 10, matching the paper's figure.
N_FRAMES = 11          # t = 0 .. N_FRAMES - 1
T_APPEAR = N_FRAMES // 2
FRAME_AR = 0.86        # width / height of each video frame

# --- palettes -------------------------------------------------------------- #
# BG / FG are the page's own background and ink for that theme, so the figure
# reads as part of the page.  Readiness uses the page's accent family.
#   light: the paper palette, retuned for the warm off-white page.
#   dark : the slide palette of the reference (neon yellow / magenta / cyan,
#          violet blocks with a soft glow), on the page's dark navy.
THEMES = {
    "light": dict(
        BG="#fbfaf7", FG="#16181d",
        YELLOW="#D97D00",        # stereotype answer  (deep amber)
        MAGENTA="#6A1FA0",       # true answer        (deep violet)
        GREEN="#0b8468",         # readiness / evidence (page accent)
        CYAN="#0B62C4",          # "object appears" accent
        BOX_FILL="#E7D9F8", BOX_EDGE="#5B2C8D",
        VIT_FILL="#D3E6FA", VIT_EDGE="#155E9E",
        DASH="#7A55B4", DOT="#5B2C8D", SCAN="#A9A9B6",
        GRID="#dcd8cf", CHIP="#E4EFFB", SHADOW="#4A3A66", BUBBLE="#F5F0FC",
        THUMB_BORDER=(22, 24, 29),
        FILL_A=0.09, FILL_A1=0.16, GLOW=False,
    ),
    "dark": dict(
        BG="#0a172c", FG="#eef2f8",
        YELLOW="#f2e205", MAGENTA="#e879d8", GREEN="#3ddc97", CYAN="#22d3ee",
        BOX_FILL="#2e1f4d", BOX_EDGE="#b9a8e8",
        VIT_FILL="#122a4a", VIT_EDGE="#7fb2e5",
        DASH="#cfc6ea", DOT="#b9a2e8", SCAN="#5d5f69",
        GRID=None, CHIP=None, SHADOW="#000000", BUBBLE=None,   # from BG
        THUMB_BORDER=(200, 200, 210),
        FILL_A=0.035, FILL_A1=0.08, GLOW=True,
    ),
}
_C = dict(THEMES[THEME])
if BG_OVERRIDE:
    _C["BG"] = BG_OVERRIDE
# dark tints are derived from the background so any dark page colour works
if _C["GRID"] is None:
    _C["GRID"] = mix(_C["BG"], "#ffffff", 0.14)
if _C["BUBBLE"] is None:
    _C["BUBBLE"] = mix(_C["BG"], "#ffffff", 0.03)
if _C["CHIP"] is None:
    _C["CHIP"] = mix(_C["BG"], _C["CYAN"], 0.12)
GLOW = _C["GLOW"]
BG, FG = _C["BG"], _C["FG"]
YELLOW, MAGENTA, GREEN, CYAN = _C["YELLOW"], _C["MAGENTA"], _C["GREEN"], _C["CYAN"]
BOX_FILL, BOX_EDGE = _C["BOX_FILL"], _C["BOX_EDGE"]
VIT_FILL, VIT_EDGE = _C["VIT_FILL"], _C["VIT_EDGE"]
DASH, DOT, SCAN, THUMB_BORDER = _C["DASH"], _C["DOT"], _C["SCAN"], _C["THUMB_BORDER"]
GRID, CHIP, SHADOW, BUBBLE = _C["GRID"], _C["CHIP"], _C["SHADOW"], _C["BUBBLE"]

# --- ink weights ----------------------------------------------------------- #
# On a white page the figure has to earn its contrast from stroke weight and
# saturation rather than from a glowing background, so every rule is heavier
# than the slide version and the traces carry a light fill underneath.
LW_TRACE = 2.8          # signal curves
LW_AXIS = 2.2           # arrow-tipped axes
LW_BOX = 2.6            # block outlines
LW_ARROW = 2.3          # data-flow arrows
LW_WIRE = 1.9           # frame taps / bus
FILL_A = _C["FILL_A"]   # area under a curve that shares its panel
FILL_A1 = _C["FILL_A1"] # area under a curve that owns its panel

# --- signal levels --------------------------------------------------------- #
# plateau (HI) and floor (LO) of each answer's probability.  The stereotype
# keeps a visible residual after the evidence arrives - it is suppressed, not
# ruled out - while the true colour starts from near zero, below that residual.
Y_HI, Y_LO = 0.94, 0.10          # "yellow": confident, then residual
P_HI, P_LO = 0.72, 0.02          # "purple": near zero, then confident

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "text.color": FG,
    "axes.labelcolor": FG,
    "xtick.color": FG,
    "ytick.color": FG,
    "savefig.facecolor": BG,
    "axes.linewidth": LW_AXIS,
    "lines.solid_capstyle": "round",
})


# --------------------------------------------------------------------------- #
# signals
# --------------------------------------------------------------------------- #
def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def make_signals(n=1400, seed=0):
    """Time axis in frame units plus the three traces shown on the right."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, N_FRAMES - 0.5, n)

    # stereotype ("yellow") collapses right after the object becomes visible;
    # the true colour ("purple") takes over with a slight lag.  The stereotype
    # settles on a residual well above where the true colour started.
    s_down = sigmoid(-(t - (T_APPEAR + 0.55)) * 6.0)
    s_up = sigmoid((t - (T_APPEAR + 0.95)) * 4.0)

    yellow = Y_LO + (Y_HI - Y_LO) * s_down
    purple = P_LO + (P_HI - P_LO) * s_up
    ready = 0.07 + 0.92 * sigmoid((t - (T_APPEAR + 0.75)) * 3.6)

    noise = lambda a: a * rng.standard_normal(n)
    return t, yellow + noise(0.008), purple + noise(0.008), ready + noise(0.006)


# --------------------------------------------------------------------------- #
# drawing helpers
# --------------------------------------------------------------------------- #
def rbox(ax, x, y, w, h, label, fill, edge, fs=17, lw=LW_BOX, r=0.016,
         shadow=True):
    """Rounded box with centred label; (x, y) is the lower-left corner.

    A hard offset copy underneath stands in for a drop shadow: it survives the
    vector (PDF) backend, unlike matplotlib's blur-based shadow filter.
    """
    if GLOW:
        # dark theme: a soft halo in the outline colour, as in the slide
        # reference, instead of a drop shadow nobody can see on near-black
        for extra, a in ((14, 0.05), (9, 0.08), (5, 0.12)):
            ax.add_patch(FancyBboxPatch(
                (x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                facecolor="none", edgecolor=edge, linewidth=lw + extra,
                alpha=a, zorder=2))
    elif shadow:
        ax.add_patch(FancyBboxPatch(
            (x + 0.0022, y - 0.0034), w, h,
            boxstyle=f"round,pad=0,rounding_size={r}",
            facecolor=SHADOW, edgecolor="none", alpha=0.16, zorder=2))
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0,rounding_size={r}",
        facecolor=fill, edgecolor=edge, linewidth=lw, zorder=3))
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
            fontsize=fs, color=FG, fontweight="bold", zorder=4)


def arrow(ax, p0, p1, color=FG, lw=LW_ARROW, style="-|>", rad=0.0, ms=15):
    ax.add_patch(FancyArrowPatch(
        p0, p1, arrowstyle=style, mutation_scale=ms, linewidth=lw,
        color=color, connectionstyle=f"arc3,rad={rad}",
        shrinkA=0, shrinkB=0, zorder=5))


def axis_arrows(ax, x0, x1, y0, y1):
    """Replace spines with arrow-tipped axes in data coordinates."""
    for s in ax.spines.values():
        s.set_visible(False)
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y0), arrowstyle="-|>",
                                 mutation_scale=16, lw=LW_AXIS, color=FG,
                                 shrinkA=0, shrinkB=0, clip_on=False, zorder=5))
    ax.add_patch(FancyArrowPatch((x0, y0), (x0, y1), arrowstyle="-|>",
                                 mutation_scale=16, lw=LW_AXIS, color=FG,
                                 shrinkA=0, shrinkB=0, clip_on=False, zorder=5))


def speech_bubble(ax, x, y, w, h, text, fs=15, lw=2.4, fc=None):
    """Speech bubble drawn as ONE closed outline (body + tail).

    Building the tail into the bottom edge avoids the seam that appears if the
    body and the tail are drawn as two overlapping patches.
    """
    fc = BUBBLE if fc is None else fc
    tx0, tx1 = x + 0.018, x + 0.048          # where the tail meets the body
    tip = (x + 0.012, y - 0.038)             # tail tip
    verts = [(x, y + h), (x + w, y + h), (x + w, y), (tx1, y), tip,
             (tx0, y), (x, y)]
    ax.add_patch(Polygon([(vx + 0.0022, vy - 0.0034) for vx, vy in verts],
                         closed=True, facecolor=SHADOW, edgecolor="none",
                         alpha=0.16, joinstyle="round", zorder=2))
    ax.add_patch(Polygon(verts, closed=True, facecolor=fc, edgecolor=FG,
                         linewidth=lw, joinstyle="round", zorder=3))
    ax.text(x + w / 2, y + h * 0.52, text, ha="center", va="center",
            fontsize=fs, color=FG, fontweight="bold", linespacing=1.35,
            zorder=6)


def film_icon(ax, x, y, w, h):
    """Small film-strip / play glyph used as the stream marker."""
    ax.add_patch(mpatches.Rectangle((x, y), w, h, fill=False,
                                    edgecolor=FG, lw=2.0, zorder=4))
    n, ph = 4, h / 9
    for i in range(n):
        yy = y + h * (i + 0.6) / n - ph / 2
        for xx in (x + w * 0.045, x + w * 0.86):
            ax.add_patch(mpatches.Rectangle((xx, yy), w * 0.10, ph,
                                            facecolor=FG, edgecolor="none",
                                            zorder=5))
    cx, cy, s = x + w * 0.5, y + h * 0.5, min(w, h) * 0.26
    ax.add_patch(Polygon([[cx - s * 0.5, cy - s], [cx - s * 0.5, cy + s],
                          [cx + s * 0.9, cy]], closed=True,
                         facecolor=FG, edgecolor="none", zorder=5))


def center_crop(path, aspect, cx=0.53, cy=0.56, scale=1.0):
    """Crop to the target width/height ratio around a chosen centre.

    cx / cy are fractional coordinates of the crop centre; scale < 1 zooms in.
    The default framing keeps the island, cutting board and window in shot.
    """
    im = Image.open(path).convert("RGB")
    w, h = im.size
    ch = int(round(h * scale))
    cw = int(round(ch * aspect))
    if cw > w:
        cw, ch = w, int(round(w / aspect))
    left = int(round(cx * w - cw / 2))
    top = int(round(cy * h - ch / 2))
    left = max(0, min(left, w - cw))
    top = max(0, min(top, h - ch))
    im = im.crop((left, top, left + cw, top + ch))
    im = im.resize((440, int(round(440 / aspect))), Image.LANCZOS)
    # the frames are shown ~2 cm wide, so nudge contrast/colour/edges up a
    # little; without it the strip reads as a row of grey smudges in print.
    from PIL import ImageEnhance
    im = ImageEnhance.Color(im).enhance(1.16)
    im = ImageEnhance.Contrast(im).enhance(1.14)
    return ImageEnhance.Sharpness(im).enhance(1.35)


def rounded_thumb(im, radius_frac=0.07, border=None, bw=5):
    """Rounded corners + light border, returned as RGBA."""
    from PIL import ImageDraw
    border = THUMB_BORDER if border is None else border
    w, h = im.size
    r = int(min(w, h) * radius_frac)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], r, fill=255)
    out = im.convert("RGBA")
    out.putalpha(mask)
    ImageDraw.Draw(out).rounded_rectangle([bw // 2, bw // 2, w - 1 - bw // 2,
                                           h - 1 - bw // 2], r,
                                          outline=border + (255,), width=bw)
    return out


# --------------------------------------------------------------------------- #
# figure
# --------------------------------------------------------------------------- #
fig = plt.figure(figsize=(16.7, 9.4), dpi=300)
fig.patch.set_facecolor(BG)

# full-figure canvas for the schematic on the left and the frame strip
bg = fig.add_axes([0, 0, 1, 1], zorder=0)
bg.set_xlim(0, 1)
bg.set_ylim(0, 1)
bg.axis("off")
bg.set_facecolor(BG)

t, yellow, purple, ready = make_signals()

# ---------------------------- right: two plots ----------------------------- #
XMAX = N_FRAMES - 0.4
plot_specs = [
    dict(rect=[0.405, 0.672, 0.565, 0.252], ylab="Confidence"),
    dict(rect=[0.405, 0.372, 0.565, 0.212], ylab="Readiness"),
]
axes = []
for spec in plot_specs:
    ax = fig.add_axes(spec["rect"])
    ax.set_facecolor(BG)
    ax.set_xlim(-0.15, XMAX)
    ax.set_ylim(-0.09, 1.18)
    ax.set_yticks([0.0, 0.5, 1.0])
    ax.set_yticklabels(["0.0", "0.5", "1.0"], fontsize=15, fontweight="bold")
    ax.set_xticks([])
    ax.tick_params(axis="y", length=6, width=LW_AXIS, pad=6)
    ax.set_ylabel(spec["ylab"], fontsize=15.5, labelpad=10, fontweight="bold")
    axis_arrows(ax, -0.15, XMAX, -0.09, 1.18)
    # faint rules at the two reference levels, so the plateaus can be read off
    for gy in (0.5, 1.0):
        ax.plot([-0.15, XMAX], [gy, gy], color=GRID, lw=1.1,
                ls=(0, (1, 4)), zorder=0)
    ax.text(XMAX * 0.995, -0.13, "Time (frames)", ha="right", va="top",
            fontsize=15, color=FG, fontweight="bold")
    axes.append(ax)

ax1, ax2 = axes

def trace(ax, y, color, z=4, alpha=FILL_A):
    """Signal curve: tinted area under it, then the line with a background
    halo so the two probability curves stay separable where they cross."""
    ax.fill_between(t, 0.0, y, color=color, alpha=alpha, lw=0, zorder=z - 2)
    ax.plot(t, y, color=color, lw=LW_TRACE, solid_joinstyle="round", zorder=z,
            path_effects=[pe.Stroke(linewidth=LW_TRACE + 2.6, foreground=BG),
                          pe.Normal()])


trace(ax1, yellow, YELLOW, z=4)
trace(ax1, purple, MAGENTA, z=6)
trace(ax2, ready, GREEN, z=4, alpha=FILL_A1)

# legend (drawn by hand so it sits exactly where the reference has it).  Its
# metrics are figure fractions converted to data units, so the card keeps its
# physical size and its right edge whatever the time axis spans.
DPX = (XMAX + 0.15) / plot_specs[0]["rect"][2]   # data units per fig-width
LEG_X1 = -0.15 + (0.992 - plot_specs[0]["rect"][0]) * DPX
LEG_W = 0.215 * DPX
LEG_X0 = LEG_X1 - LEG_W
LEG_H, LEG_PAD = 0.375, 0.04

# The card keeps its physical width, so a shorter time axis lets it reach back
# into the flip: on a short axis the crossover happens under the card instead
# of to its left.  Test for that and go above the plateau when it happens.
LEG_Y = 0.245                                    # mid-right, as in the reference
_span = (t >= LEG_X0) & (t <= LEG_X1)
if any(((sig[_span] > LEG_Y - LEG_PAD) &
        (sig[_span] < LEG_Y + LEG_H + LEG_PAD)).any()
       for sig in (yellow, purple)):
    LEG_Y = 0.78

ax1.add_patch(FancyBboxPatch(
    (LEG_X0, LEG_Y), LEG_W, LEG_H,
    boxstyle=f"round,pad=0,rounding_size={0.0071 * DPX}",
    facecolor=BG, edgecolor=GRID, linewidth=1.5, clip_on=False, zorder=8))
for i, (c, lab) in enumerate([(YELLOW, '"yellow" (stereotype)'),
                              (MAGENTA, '"purple" (true color)')]):
    yy = LEG_Y + 0.255 - 0.155 * i
    ax1.plot([LEG_X0 + 0.011 * DPX, LEG_X0 + 0.0465 * DPX], [yy, yy],
             color=c, lw=LW_TRACE + 1.2, clip_on=False, zorder=9)
    ax1.text(LEG_X0 + 0.0555 * DPX, yy, lab, va="center", fontsize=15,
             color=FG, fontweight="bold", zorder=9)

# titles
bg.text(0.408, 0.955, "OUTPUT PROBABILITIES", fontsize=16.5, color=FG,
        fontweight="bold")
bg.text(0.400, 0.622, "READINESS SIGNAL", fontsize=16, color=FG,
        fontweight="bold")
bg.text(0.400, 0.594, "(EVIDENCE READINESS)", fontsize=12, color=FG)
bg.text(0.200, 0.958, "TRANSFORMER STACK", fontsize=16.5, color=FG,
        ha="center", fontweight="bold")
bg.text(0.200, 0.930, "(Simplified)", fontsize=13.5, color=FG, ha="center")

# "object appears" markers
for ax, ytop in ((ax1, 1.02), (ax2, 1.02)):
    ax.axvline(T_APPEAR, ymin=0.03, ymax=(ytop + 0.09) / 1.27, color=CYAN,
               ls=(0, (5, 4)), lw=2.4, zorder=6)
    ax.text(T_APPEAR, -0.15, f"Object appears (t = {T_APPEAR})", ha="center",
            va="top", fontsize=13.5, color=CYAN, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.34", facecolor=CHIP,
                      edgecolor=CYAN, linewidth=1.6))

# dashed link between the two panels, so the same t = 6 is obviously shared
x6 = 0.405 + 0.565 * (T_APPEAR + 0.15) / (XMAX + 0.15)
bg.plot([x6, x6], [0.584, 0.593], color=CYAN, ls=(0, (5, 4)), lw=2.4)

# ------------------------- left: transformer stack -------------------------- #
BW, BH, BX = 0.155, 0.058, 0.1225           # box width / height / left edge
CX = BX + BW / 2                            # stack centre line
#   bottom -> top: layer 1, ellipsis, layer 35, layer 36
layers = [(0.495, "Layer 1"), (0.695, "Layer 35"), (0.775, "Layer 36")]
for y, name in layers:
    rbox(bg, BX, y, BW, BH, name, BOX_FILL, BOX_EDGE, fs=16)

# vertical residual path with the "many layers" ellipsis just above layer 1
DOTS_Y = (0.553 + 0.695) / 2
bg.plot([CX, CX], [0.553, 0.695], color=DASH,
        ls=(0, (2.5, 3.2)), lw=2.6, zorder=1)
bg.plot([CX, CX], [0.753, 0.775], color=DASH,
        ls=(0, (2.5, 3.2)), lw=2.6, zorder=1)
for yy in (DOTS_Y + 0.023, DOTS_Y, DOTS_Y - 0.023):
    bg.plot([CX], [yy], marker="o", ms=8.5, color=DOT, zorder=4)

# vision encoder (deliberately narrower than a transformer layer)
VIT_W, VIT_H, VIT_Y = 0.132, 0.055, 0.395
rbox(bg, CX - VIT_W / 2, VIT_Y, VIT_W, VIT_H, "Vision Encoder",
     VIT_FILL, VIT_EDGE, fs=14.5)
arrow(bg, (CX, VIT_Y + VIT_H), (CX, 0.492))

# question bubble -> layer 1
speech_bubble(bg, 0.006, 0.386, 0.110, 0.104, fs=14.5,
              text="What color is\nthe banana in\nthe video?")
bg.plot([0.057, 0.057], [0.490, 0.5235], color=FG, lw=LW_ARROW, zorder=5)
arrow(bg, (0.057, 0.5235), (0.1195, 0.5235), lw=LW_ARROW, ms=14)

# stack -> plots: final layer feeds the probabilities, an intermediate
# (ellipsis) layer feeds the readiness signal
bg.add_patch(FancyArrowPatch((CX, layers[-1][0] + BH), (0.372, 0.918),
                             arrowstyle="-|>", mutation_scale=16,
                             lw=LW_ARROW, color=FG,
                             connectionstyle="arc3,rad=-0.28",
                             shrinkA=0, shrinkB=0, zorder=5))
arrow(bg, (CX + 0.006, DOTS_Y), (0.372, DOTS_Y))

# ------------------------------ frame strip -------------------------------- #
LEFT, RIGHT = 0.098, 0.975
BAND_C = 0.146                               # vertical centre of the strip
FRAME_H_MAX = 0.168                          # keeps the strip clear of the taps
pitch = (RIGHT - LEFT) / N_FRAMES
centers = [LEFT + pitch * (i + 0.5) for i in range(N_FRAMES)]

# a frame is as wide as the pitch allows; its height follows from the aspect
# ratio, capped so a short strip cannot grow up into the tap points
frame_h = min(pitch * 0.985 * fig.get_figwidth()
              / (FRAME_AR * fig.get_figheight()), FRAME_H_MAX)
Y_TOP, Y_BOT = BAND_C + frame_h / 2, BAND_C - frame_h / 2

_crop_before = center_crop(IMG_BEFORE, FRAME_AR, cx=0.53, cy=0.60)
_crop_after = center_crop(IMG_AFTER, FRAME_AR, cx=0.53, cy=0.60)
im_before = rounded_thumb(_crop_before)
im_after = rounded_thumb(_crop_after)
# the frame where the object enters gets the accent border, tying the strip
# to the dashed t = 6 marker in both plots
_cyan_rgb = tuple(int(CYAN[i:i + 2], 16) for i in (1, 3, 5))
im_appear = rounded_thumb(_crop_after, border=_cyan_rgb, bw=8)

# OffsetImage draws at 72 dpi, so convert the target height in figure
# fraction -> points before dividing by the source pixel height.
zoom = (Y_TOP - Y_BOT) * fig.get_figheight() * 72.0 / im_before.size[1]
for i, cx in enumerate(centers):
    im = im_appear if i == T_APPEAR else (im_after if i > T_APPEAR
                                          else im_before)
    bg.add_artist(AnnotationBbox(
        OffsetImage(np.asarray(im), zoom=zoom),
        (cx, (Y_TOP + Y_BOT) / 2), frameon=False, xycoords="data",
        box_alignment=(0.5, 0.5), zorder=3))
    lab_c = CYAN if i == T_APPEAR else FG
    bg.text(cx, Y_BOT - 0.030, f"t = {i}", ha="center", va="center",
            fontsize=15, color=lab_c,
            fontweight="bold" if i == T_APPEAR else "normal")

# tap points and the bus that feeds the ViT
BUS_Y, TAP_Y = 0.306, 0.240
for cx in centers:
    bg.plot([cx, cx], [TAP_Y, BUS_Y], color=FG, lw=LW_WIRE, zorder=2)
    bg.plot([cx], [TAP_Y], marker="o", ms=7.5, color=CYAN, zorder=4)
bg.plot([centers[0], centers[-1]], [BUS_Y, BUS_Y], color=FG, lw=LW_WIRE,
        zorder=2)
bg.add_patch(FancyArrowPatch(
    (BX + BW / 2, BUS_Y), (BX + BW / 2, VIT_Y - 0.004), arrowstyle="-|>",
    mutation_scale=16, lw=LW_ARROW, color=FG, shrinkA=0, shrinkB=0, zorder=4))

# stream label, film icon and the "continues" ellipses
bg.text(0.001, 0.182, "STREAMING", fontsize=11.8, color=FG, va="center",
        fontweight="bold")
bg.text(0.001, 0.157, "VIDEO FRAMES", fontsize=11.8, color=FG, va="center",
        fontweight="bold")
film_icon(bg, 0.018, 0.088, 0.026, 0.042)
arrow(bg, (0.050, 0.109), (0.088, 0.109), lw=LW_ARROW, ms=14)
bg.text(0.990, 0.146, "···", fontsize=17, color=FG,
        va="center", ha="center", fontweight="bold")
# faint scan line through the strip
bg.plot([LEFT, 0.982], [0.146, 0.146], color=SCAN, lw=1.4,
        ls=(0, (1, 6)), zorder=1)

# render at print resolution, then downsample for the web: sharper edges than
# rendering directly at the target width
import io
_buf = io.BytesIO()
fig.savefig(_buf, format="png", facecolor=BG)
_buf.seek(0)
_im = Image.open(_buf).convert("RGB")
_im = _im.resize((WEB_WIDTH, round(_im.height * WEB_WIDTH / _im.width)),
                 Image.LANCZOS)
_base = OUT_OVERRIDE or os.path.join(OUT_DIR, f"teaser-{THEME}")
_im.save(_base + ".png", optimize=True)
# lossless: lossy WebP shifts the flat background by one level, which shows
# as a faint box against the page
_im.save(_base + ".webp", lossless=True, quality=100, method=6)
print("wrote", _base + ".png / .webp", _im.size)
