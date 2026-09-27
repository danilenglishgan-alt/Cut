"""Montage of the sticker-pack reel in the "aesthetic personal blog" style kit
(template 7): cream/pastel grade, T1-T5 text styles, persistent film-counter
overlay, number stickers, polaroid grid, B/W twist, whip-pan and slide wipe,
karaoke subtitles, synthesized music bed ducked under a cleaned-up voice.

    python3 render_kit07.py                 # full render -> output/montage_kit07.mp4
    python3 render_kit07.py preview 1.0 5   # still frames (output time) -> output/preview/
"""
import json
import math
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "assets", "source.mp4")
OUT = os.path.join(ROOT, "output", "montage_kit07.mp4")
TMP = os.path.join(ROOT, "output", "_tmp")
FONTS = os.path.join(ROOT, "assets", "fonts")
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")

SW, SH = 720, 1280
W, H = 1080, 1920
FPS = 30
SR = 48000

# ---------------------------------------------------------------- palette (kit, block 5)
CREAM = (247, 243, 234)
WHITE = (255, 255, 255)
INK = (26, 26, 26)
PINK = (246, 201, 232)       # #F6C9E8
PINK_D = (240, 184, 216)     # #F0B8D8
BLUE = (175, 200, 234)       # #AFC8EA
BROWN = (43, 23, 16)         # #2B1710 outlines / subtitle plates
BORDO = (74, 20, 38)
YELLOW = (250, 229, 150)
MINT = (190, 234, 212)

# Optional author nick for the top-right counter (kit block 1). Empty = counter only.
AUTHOR = ""
SERIES_NO = 7

# ---------------------------------------------------------------- edit decision list
# (source_in, source_out, kind). Output time is the running sum of durations.
# Trimmed: 3.34-3.45 (pause), 4.44-4.53 (pause), 9.12-9.36 (pause), 10.20-10.48 (pause).
SEGMENTS = [
    (0.00, 3.34, "A"),     # hook, wide
    (3.45, 4.44, "TWIST"), # "я собрала" - B/W twist
    (4.53, 7.07, "B"),     # phone insert (screencast)
    (7.07, 7.90, "C"),     # speaker, "1000+ стикеров"
    (7.90, 9.12, "GRID"),  # 2x2 polaroid grid, "разделила по цветам"
    (9.36, 10.20, "C2"),   # "убрала фон"
    (10.48, 15.066, "D"),  # CTA block
]

# zoom-punch keyframes per segment: (source_time, zoom, focus_x, focus_y) as fractions
ZOOM = {
    "A": [(0.00, 1.00, .30, .55), (1.50, 1.22, .30, .55), (1.78, 1.45, .30, .52),
          (2.24, 1.10, .30, .55)],
    "TWIST": [(3.45, 1.00, .46, .52)],
    "B": [(4.53, 1.00, .47, .50), (6.66, 1.22, .45, .47)],
    "C": [(7.07, 1.22, .44, .47)],
    "C2": [(9.36, 1.35, .48, .45)],
    "D": [(10.48, 1.00, .52, .55), (11.34, 1.14, .52, .55), (12.36, 1.28, .52, .52),
          (13.22, 1.06, .52, .55)],
}


def seg_table():
    out, t = [], 0.0
    for a, b, k in SEGMENTS:
        out.append((a, b, k, t))
        t += b - a
    return out, t


SEGS, DUR = seg_table()
NFRAMES = int(round(DUR * FPS))
CUTS = [s[3] for s in SEGS[1:]]


def src2out(ts):
    for a, b, k, o in SEGS:
        if a - 1e-6 <= ts <= b + 1e-6:
            return o + ts - a
    # time inside a trimmed gap -> next segment start
    for a, b, k, o in SEGS:
        if ts < a:
            return o
    return DUR


def seg_at(t):
    for s in SEGS:
        if s[3] <= t < s[3] + (s[1] - s[0]):
            return s
    return SEGS[-1]


# ---------------------------------------------------------------- speech (whisper word times, text corrected)
WORDS = [
    ("все", 0.00, 0.44), ("ищут,", 0.44, 0.70), ("откуда", 0.72, 1.16), ("эти-", 1.16, 1.50),
    ("эти-", 1.50, 1.78), ("эти", 1.78, 2.24), ("стикеры", 2.24, 2.62), ("на", 2.62, 2.76),
    ("рилсах?", 2.76, 3.32),
    ("я", 3.80, 3.84), ("собрала", 3.84, 4.42),
    ("правда,", 4.72, 5.06), ("у", 5.10, 5.14), ("меня", 5.14, 5.38), ("я", 5.38, 5.58),
    ("собрала", 5.58, 6.04), ("пак", 6.04, 6.32), ("из", 6.32, 6.66), ("1000+", 6.66, 7.30),
    ("стикеров,", 7.30, 7.74),
    ("разделила", 7.94, 8.22), ("их", 8.22, 8.40), ("по", 8.40, 8.54), ("цветам,", 8.54, 9.10),
    ("убрала", 9.38, 9.90), ("фон", 9.90, 10.22),
    ("тебе", 10.52, 10.74), ("всего", 10.74, 10.90), ("лишь", 10.90, 11.06), ("нужно", 11.06, 11.34),
    ("перейти", 11.34, 11.62), ("в", 11.62, 11.76), ("комментарии,", 11.76, 12.20),
    ("написать", 12.36, 12.58), ("слово", 12.58, 12.74), ("«стикер»,", 12.74, 13.22),
    ("и", 13.22, 13.38), ("я", 13.38, 13.48), ("тебе", 13.48, 13.62), ("всё", 13.62, 13.80),
    ("отправлю", 13.80, 14.26),
]
# subtitle phrases (word index ranges, end exclusive), 1-2 lines each
GROUPS = [(0, 3), (3, 6), (6, 9), (9, 11), (11, 14), (14, 17), (17, 20), (20, 24), (24, 26),
          (26, 30), (30, 33), (33, 36), (36, 41)]


# ---------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def font(name, size, var=None):
    f = ImageFont.truetype(os.path.join(FONTS, name), size)
    if var:
        f.set_variation_by_name(var)
    return f


def paste(frame, im, x, y):
    x, y = int(round(x)), int(round(y))
    l, t = max(0, -x), max(0, -y)
    r, b = min(im.width, frame.width - x), min(im.height, frame.height - y)
    if r > l and b > t:
        frame.alpha_composite(im.crop((l, t, r, b)), (x + l, y + t))


def paste_c(frame, im, cx, cy):
    paste(frame, im, cx - im.width / 2, cy - im.height / 2)


def solid(size, color, mask):
    im = Image.new("RGBA", size, color + (0,))
    im.putalpha(mask)
    return im


def styled_text(text, f, fill, stroke=0, stroke_col=BROWN, glow=None, glow_r=0,
                glow_gain=1.6, pad=None):
    """Text with optional outline and soft bloom around the letters."""
    pad = pad if pad is not None else stroke + glow_r * 3 + 8
    l, t, r, b = f.getbbox(text, stroke_width=stroke)
    size = (r - l + pad * 2, b - t + pad * 2)
    org = (pad - l, pad - t)

    def mask(sw):
        m = Image.new("L", size, 0)
        ImageDraw.Draw(m).text(org, text, font=f, fill=255, stroke_width=sw, stroke_fill=255)
        return m

    fill_m = mask(0)
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    outer = mask(stroke) if stroke else fill_m
    if glow:
        g = outer.filter(ImageFilter.GaussianBlur(glow_r)).point(
            lambda v: min(255, int(v * glow_gain)))
        out.alpha_composite(solid(size, glow, g))
    if stroke:
        out.alpha_composite(solid(size, stroke_col, outer))
    out.alpha_composite(solid(size, fill, fill_m))
    return out


def trim(im):
    return im.crop(im.getbbox())


# ---------------------------------------------------------------- kit elements
def star(size, color, rot):
    """Block 3.1: flat pastel five-point star, no outline, slightly rotated."""
    s = size * 2
    im = Image.new("L", (s, s), 0)
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = s * 0.48 if i % 2 == 0 else s * 0.2
        pts.append((s / 2 + r * math.cos(a), s / 2 + r * math.sin(a)))
    ImageDraw.Draw(im).polygon(pts, fill=255)
    im = im.resize((size, size), Image.LANCZOS)
    return solid((size, size), color, im).rotate(rot, Image.BICUBIC, expand=True)


def t1(top, bottom, top_fill=BLUE, bottom_fill=WHITE, width=940):
    """T1: rounded bold sans top line + bold cursive bottom line, thin dark
    outline and pastel bloom."""
    ft = font("Nunito.ttf", 74, "Black")
    a = trim(styled_text(top, ft, top_fill, stroke=4, stroke_col=BROWN, glow=PINK_D,
                         glow_r=7, glow_gain=1.3))
    size = 150
    while True:
        fb = font("Lobster-Regular.ttf", size)
        l, _, r, _ = fb.getbbox(bottom)
        if r - l <= width or size < 60:
            break
        size -= 6
    b = trim(styled_text(bottom, fb, bottom_fill, stroke=4, stroke_col=BORDO, glow=PINK_D,
                         glow_r=9, glow_gain=1.8))
    return a, b


def t5(text, color):
    """T5: bold black sans on a flat square pastel plate hugging the text."""
    f = font("Nunito.ttf", 60, "Black")
    l, t, r, b = f.getbbox(text)
    px, py = 26, 14
    im = Image.new("RGBA", (r - l + px * 2, b - t + py * 2), color + (255,))
    ImageDraw.Draw(im).text((px - l, py - t), text, font=f, fill=INK + (255,))
    return im


def t4(text, size=50, fill=INK):
    """T4: plain rounded bold sans, no outline/shadow/plate."""
    f = font("Nunito.ttf", size, "ExtraBold")
    l, t, r, b = f.getbbox(text)
    im = Image.new("RGBA", (r - l + 4, b - t + 4), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((2 - l, 2 - t), text, font=f, fill=fill + (255,))
    return im


def number_sticker(text, size=210, rot=-6):
    """Block 3.2: hand-drawn marker number, white fill, thick black outline,
    no colour or glow. Slightly wobbly double stroke for the 'by hand' feel."""
    f = font("Caveat.ttf", size, "Bold")
    base = styled_text(text, f, WHITE, stroke=13, stroke_col=INK, pad=40)
    wob = styled_text(text, f, WHITE, stroke=11, stroke_col=INK, pad=40)
    out = Image.new("RGBA", base.size, (0, 0, 0, 0))
    out.alpha_composite(wob, (4, -3))
    out.alpha_composite(base)
    return trim(out.rotate(rot, Image.BICUBIC, expand=True))


def twist_text(text):
    """Block 3.5: cursive, pastel pink, thin bordo outline, bloom halo."""
    f = font("Lobster-Regular.ttf", 132)
    return trim(styled_text(text, f, PINK, stroke=3, stroke_col=BORDO, glow=PINK_D,
                            glow_r=16, glow_gain=2.4))


def glitter(w, h, n, seed):
    """Block 3.4: barely visible field of twinkling dots."""
    rng = np.random.default_rng(seed)
    return [(rng.uniform(0, w), rng.uniform(0, h), rng.uniform(2, 5), rng.uniform(0, 6.28),
             rng.uniform(5, 11)) for _ in range(n)]


def draw_glitter(frame, pts, ox, oy, t, alpha=0.8):
    d = ImageDraw.Draw(frame)
    for x, y, r, ph, sp in pts:
        v = 0.5 + 0.5 * math.sin(t * sp + ph)
        if v < 0.35:
            continue
        a = int(255 * alpha * v)
        rr = r * (0.6 + 0.4 * v)
        d.ellipse((ox + x - rr, oy + y - rr, ox + x + rr, oy + y + rr), fill=(255, 255, 255, a))


# ---------------------------------------------------------------- block 1 overlay
OV_FONT_1 = font("CormorantGaramond-Italic.ttf", 50, "Italic")
OV_FONT_2 = font("CormorantGaramond-Italic.ttf", 38, "Light Italic")


def overlay_img(shot_no):
    im = Image.new("RGBA", (W, 260), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((64, 150), "стикер-дневник", font=OV_FONT_1, fill=WHITE + (255,), anchor="ls")
    d.text((66, 196), "sticker diary", font=OV_FONT_2, fill=WHITE + (255,), anchor="ls")
    d.text((W - 64, 150), f"({SERIES_NO})", font=OV_FONT_1, fill=WHITE + (255,), anchor="rs")
    d.text((W - 64, 196), AUTHOR or f"кадр {shot_no:02d}", font=OV_FONT_2,
           fill=WHITE + (255,), anchor="rs")
    return im


OVERLAYS = {i + 1: overlay_img(i + 1) for i in range(len(SEGMENTS))}


# ---------------------------------------------------------------- subtitles (T2, karaoke)
SUB_F = font("Nunito.ttf", 64, "Black")
SUB_Y = 1440
SUB_MAXW = 820
PLATE = BROWN + (204,)       # ~80% opacity


def join_words(idx):
    out = ""
    for i in idx:
        out += WORDS[i][0] if WORDS[i][0].endswith("-") else WORDS[i][0] + " "
    return out.strip()


def layout_group(gi):
    """Split a phrase into <=2 lines that fit SUB_MAXW."""
    a, b = GROUPS[gi]
    words = [WORDS[i][0] for i in range(a, b)]
    lines, cur = [], []
    for i, w in zip(range(a, b), words):
        test = join_words(cur + [i])
        if cur and SUB_F.getlength(test) > SUB_MAXW:
            lines.append(cur)
            cur = []
        cur.append(i)
    lines.append(cur)
    return lines


SUB_CACHE = {}


def subtitle_img(gi, active):
    key = (gi, active)
    if key in SUB_CACHE:
        return SUB_CACHE[key]
    lines = layout_group(gi)
    asc, desc = SUB_F.getmetrics()
    lh = asc + desc - 8
    px, py = 22, 6
    widths = [SUB_F.getlength(join_words(ln)) for ln in lines]
    im = Image.new("RGBA", (W, len(lines) * (lh + py * 2)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for li, (ln, lw) in enumerate(zip(lines, widths)):
        y0 = li * (lh + py * 2)
        x0 = (W - lw) / 2
        d.rounded_rectangle((x0 - px, y0, x0 + lw + px, y0 + lh + py * 2), radius=14, fill=PLATE)
        x = x0
        for i in ln:
            w = WORDS[i][0]
            col = PINK if i == active else WHITE
            d.text((x, y0 + py - 4), w, font=SUB_F, fill=col + (255,))
            x += SUB_F.getlength(w if w.endswith("-") else w + " ")
    SUB_CACHE[key] = im
    return im


def draw_subs(frame, t):
    # word times in output timeline
    for gi, (a, b) in enumerate(GROUPS):
        g0 = src2out(WORDS[a][1]) - 0.04
        nxt = src2out(WORDS[GROUPS[gi + 1][0]][1]) - 0.04 if gi + 1 < len(GROUPS) else DUR
        g1 = min(nxt, src2out(WORDS[b - 1][2]) + 0.45)
        if g0 <= t < g1:
            active = None
            for i in range(a, b):
                if src2out(WORDS[i][1]) - 0.02 <= t:
                    active = i
            im = subtitle_img(gi, active)
            paste(frame, im, 0, SUB_Y - im.height / 2)
            return


# ---------------------------------------------------------------- accent elements (output-time)
def ow(i):
    """Output time of word i start."""
    return src2out(WORDS[i][1])


class Static:
    def __init__(self, img, t0, t1, cx, cy):
        self.img, self.t0, self.t1, self.cx, self.cy = img, t0, t1, cx, cy

    def draw(self, frame, t):
        if self.t0 <= t < self.t1:
            paste_c(frame, self.img, self.cx, self.cy)


def build_elements():
    E, sfx = [], []
    # hook T1 (0 .. end of "эти"), top line on "все", bottom on "откуда"
    top, bot = t1("те самые", "стикеры из рилс")
    E.append(Static(star(300, PINK_D, 14), ow(2), ow(6), 830, 520))
    E.append(Static(top, ow(0), ow(6), 540, 410))
    E.append(Static(bot, ow(2), ow(6), 540, 545))
    sfx += [(ow(2), "pop")]

    # twist (whole TWIST segment): cursive pink with bloom
    tw0 = SEGS[1][3]
    E.append(Static(twist_text("всё — сама"), tw0 + 0.12, SEGS[2][3], 540, 560))
    sfx += [(tw0, "shutter")]

    # phone insert: T5 accent before showing the object
    b0 = SEGS[2][3]
    E.append(Static(t5("смотри, что внутри", PINK), b0, ow(17), 400, 330))

    # 1000+ number sticker on "тысячи", held through the grid (≈2.3 s)
    E.append(Static(number_sticker("1000+", 220, -6), ow(18), SEGS[4][3] + 1.22, 540, 1150))
    sfx += [(ow(18), "pop")]

    # grid
    sfx += [(SEGS[4][3], "shutter")]

    # CTA block
    d0 = SEGS[6][3]
    top, bot = t1("как забрать", "весь пак", top_fill=WHITE, bottom_fill=PINK)
    E.append(Static(star(260, YELLOW, -12), d0, ow(30), 250, 540))
    E.append(Static(top, d0, ow(30), 540, 410))
    E.append(Static(bot, d0 + 0.2, ow(30), 540, 545))
    # step 1 / step 2 number stickers at the chest + T5 labels
    E.append(Static(number_sticker("1", 230, -8), ow(30), ow(33), 250, 1170))
    E.append(Static(t5("комменты", YELLOW), ow(30), ow(33), 560, 1180))
    E.append(Static(number_sticker("2", 230, 6), ow(33), ow(36), 250, 1170))
    E.append(Static(t5("пиши «стикер»", MINT), ow(33), ow(36), 600, 1180))
    sfx += [(ow(30), "pop"), (ow(33), "pop"), (ow(36), "chime")]
    return E, sfx


# ---------------------------------------------------------------- profile card (block 3.6)
def profile_card(avatar_src):
    w, h = 820, 330
    card = Image.new("RGBA", (w + 60, h + 60), (0, 0, 0, 0))
    sh = Image.new("L", card.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle((30, 40, w + 30, h + 40), radius=44, fill=90)
    card.alpha_composite(solid(card.size, BROWN, sh.filter(ImageFilter.GaussianBlur(14))))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((30, 30, w + 30, h + 30), radius=44, fill=CREAM + (255,))
    # avatar: face crop from the footage in a round pastel ring
    av = avatar_src.resize((170, 170), Image.LANCZOS)
    m = Image.new("L", (170, 170), 0)
    ImageDraw.Draw(m).ellipse((0, 0, 169, 169), fill=255)
    d.ellipse((62, 62, 62 + 186, 62 + 186), fill=PINK_D + (255,))
    ring = Image.new("RGBA", (170, 170))
    ring.paste(av, (0, 0))
    ring.putalpha(m)
    card.alpha_composite(ring, (70, 70))
    fn = font("Nunito.ttf", 50, "Black")
    fs = font("Nunito.ttf", 40, "Black")
    fl = font("Nunito.ttf", 28, "SemiBold")
    d.text((290, 78), "стикер-дневник", font=fn, fill=INK + (255,))
    for i, (num, lab) in enumerate([("1000+", "стикеров"), ("0", "фона"), ("1", "пак")]):
        x = 290 + i * 180
        d.text((x, 150), num, font=fs, fill=INK + (255,))
        d.text((x, 198), lab, font=fl, fill=(110, 95, 90, 255))
    d.rounded_rectangle((290, 262, w - 10, 330), radius=20, fill=PINK_D + (255,))
    d.text(((290 + w - 10) / 2, 296), "подписаться", font=font("Nunito.ttf", 36, "Black"),
           fill=INK + (255,), anchor="mm")
    return card


# ---------------------------------------------------------------- camera / grade
def fetch(frames, ts):
    return frames[int(clamp(round(ts * FPS), 0, len(frames) - 1))]


def zoom_state(kind, ts):
    keys = ZOOM[kind]
    cur = keys[0]
    for k in keys:
        if ts >= k[0] - 1e-6:
            cur = k
    return cur[1:]


def crop(src, z, fx, fy, out=(W, H)):
    cw, ch = SW / z, SH / z
    x0 = clamp(fx * SW - cw / 2, 0, SW - cw)
    y0 = clamp(fy * SH - ch / 2, 0, SH - ch)
    return src.resize(out, Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


def normalize_insert(a):
    """Bring the saturated cyan/hot-pink insert into the kit palette before the
    common grade (shot matching): desaturate, pull cyan to pastel blue."""
    lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
    a = lum[..., None] + (a - lum[..., None]) * 0.52
    a = a @ np.array([[0.96, 0.0, 0.04], [0.0, 0.82, 0.0], [0.04, 0.18, 0.96]], np.float32)
    return a * 0.9 + np.array(CREAM, np.float32) * 0.1


TOP_SHADE = (1 - 0.22 * np.clip(1 - np.arange(H) / 380, 0, 1) ** 1.5)[:, None, None] \
    .astype(np.float32)
GRAIN = np.random.default_rng(1).normal(0, 1, (4, H // 2, W // 2)).astype(np.float32)


def grade(img, n, insert=False):
    """One look for the whole reel: warm cream highlights, softened sage greens,
    lifted warm-brown blacks, a hint of pink in the mids, gentle bloom, grain."""
    a = np.asarray(img, np.float32)
    if insert:
        a = normalize_insert(a)
    lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
    # soften saturated yellow-greens of the foliage
    g_excess = np.clip(a[..., 1] - np.maximum(a[..., 0], a[..., 2]), 0, None)
    a[..., 1] -= g_excess * 0.25
    a[..., 0] += g_excess * 0.08
    a = lum[..., None] + (a - lum[..., None]) * 0.84
    x = a / 255.0
    x = x * x * (3 - 2 * x) * 0.35 + x * 0.65                     # soft S-curve
    hl = np.clip((lum / 255 - 0.55) / 0.45, 0, 1)[..., None]
    mid = (1 - np.abs(lum / 255 - 0.5) * 2)[..., None]
    x = x * (1 - hl * 0.25) + np.array(CREAM, np.float32) / 255 * hl * 0.25
    x = x + mid * np.array([0.018, -0.004, 0.012], np.float32)   # pink in mids
    x = np.array(BROWN, np.float32) / 255 * 0.55 + x * (1 - 0.055)  # warm matte lift
    x = np.clip(x, 0, 1)
    # bloom from the highlights
    small = Image.fromarray((x * 255).astype(np.uint8)).resize((W // 8, H // 8), Image.BILINEAR)
    sa = np.asarray(small, np.float32) / 255
    sa = np.clip(sa - 0.72, 0, 1) / 0.28
    bl = Image.fromarray((sa * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6))
    bl = np.asarray(bl.resize((W, H), Image.BILINEAR), np.float32) / 255
    x = 1 - (1 - x) * (1 - bl * 0.18)
    # gentle darkening of the top band so the thin white overlay reads on bright sky
    x = x * TOP_SHADE
    # fine grain
    g = GRAIN[n % 4]
    g = np.repeat(np.repeat(g, 2, 0), 2, 1)[..., None]
    x = x + g * 0.012
    return Image.fromarray(np.clip(x * 255, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


# halftone cell map for the twist
_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
CELL = 9
HT_DIST = np.sqrt(((_xx % CELL) - CELL / 2) ** 2 + ((_yy % CELL) - CELL / 2) ** 2) / (CELL / 2)
del _yy, _xx


def bw_twist(img, n):
    """Block 4.5: hard switch to B/W with grain and a light halftone."""
    a = np.asarray(img.convert("RGB"), np.float32)
    l = a @ np.array([0.299, 0.587, 0.114], np.float32)
    l = np.clip((l - 20) * 1.12, 0, 255)
    small = np.asarray(Image.fromarray(l.astype(np.uint8)).resize(
        (W // CELL + 1, H // CELL + 1), Image.BILINEAR), np.float32)[:H // CELL + 1, :W // CELL + 1]
    cellv = np.repeat(np.repeat(small, CELL, 0), CELL, 1)[:H, :W] / 255
    dots = (HT_DIST < 1.15 * np.sqrt(1 - cellv)).astype(np.float32)
    ht = 245 - dots * 215
    l = l * 0.78 + ht * 0.22
    rng = np.random.default_rng(n)
    l = l + rng.normal(0, 11, l.shape).astype(np.float32)
    l = np.clip(l, 0, 255).astype(np.uint8)
    return Image.fromarray(np.stack([l] * 3, -1), "RGB").convert("RGBA")


def motion_blur_x(img, width):
    """Horizontal smear for the whip-pan (computed at half resolution)."""
    if width < 2:
        return img
    sm = np.asarray(img.convert("RGB").resize((W // 2, H // 2), Image.BILINEAR), np.float32)
    k = max(1, int(width / 2))
    c = np.cumsum(np.pad(sm, ((0, 0), (k, k), (0, 0)), mode="edge"), axis=1)
    bl = (c[:, 2 * k:] - c[:, :-2 * k]) / (2 * k)
    bl = bl[:, : W // 2]
    return Image.fromarray(np.clip(bl, 0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR) \
        .convert("RGBA")


def shift_x(img, dx):
    out = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    dx = int(dx) % W
    out.paste(img.crop((dx, 0, W, H)), (0, 0))
    out.paste(img.crop((0, 0, dx, H)), (W - dx, 0))
    return out


# ---------------------------------------------------------------- grid (block 4.3 + polaroid 3.3)
GRID_TIMES = [4.62, 5.20, 5.80, 6.40]
GRID_TINTS = [PINK_D, YELLOW, MINT, BLUE]
TILE_W, TILE_H = 470, 520
GRID_POS = [(55 + 0, 300), (55 + 500, 300), (55 + 0, 850), (55 + 500, 850)]


def polaroid(content):
    b = 12
    w, h = content.width + 2 * b, content.height + 2 * b
    out = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    sh = Image.new("L", out.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle((20, 26, w + 20, h + 26), radius=22, fill=110)
    out.alpha_composite(solid(out.size, BROWN, sh.filter(ImageFilter.GaussianBlur(10))))
    fr = Image.new("L", out.size, 0)
    ImageDraw.Draw(fr).rounded_rectangle((20, 20, w + 20, h + 20), radius=22, fill=255)
    out.alpha_composite(solid(out.size, WHITE, fr))
    cm = Image.new("L", content.size, 0)
    ImageDraw.Draw(cm).rounded_rectangle((0, 0, content.width - 1, content.height - 1),
                                         radius=12, fill=255)
    c = content.copy()
    c.putalpha(cm)
    out.alpha_composite(c, (20 + b, 20 + b))
    return out


def grid_frame(frames, dt, n):
    base = Image.new("RGBA", (W, H), CREAM + (255,))
    for (gx, gy), ts, tint in zip(GRID_POS, GRID_TIMES, GRID_TINTS):
        src = fetch(frames, ts + dt)
        # crop around the phone, keep tile aspect
        z = 1.55
        cw, ch = SW / z, SW / z * TILE_H / TILE_W
        x0, y0 = SW * 0.46 - cw / 2, SH * 0.48 - ch / 2
        tile = src.resize((TILE_W, TILE_H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
        a = np.asarray(tile, np.float32)
        a = normalize_insert(a)
        a = a * (1 - 0.32) + a * np.array(tint, np.float32) / 255 * 0.32 + \
            np.array(tint, np.float32) * 0.12
        tile = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")
        base.alpha_composite(polaroid(tile), (gx - 20, gy - 20))
    g = grade(base.convert("RGB"), n)
    return g


# ---------------------------------------------------------------- frame composer
def load_frames():
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", SRC, "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-"], capture_output=True, check=True).stdout
    n = len(raw) // (SW * SH * 3)
    return [Image.frombuffer("RGB", (SW, SH), raw[i * SW * SH * 3:(i + 1) * SW * SH * 3])
            for i in range(n)]


def shot_frame(frames, seg, t, n):
    a, b, kind, o = seg
    if kind == "GRID":
        return grid_frame(frames, t - o, n)
    ts = a + (t - o)
    src = fetch(frames, ts)
    z, fx, fy = zoom_state(kind, ts)
    img = crop(src, z, fx, fy)
    if kind == "TWIST":
        return bw_twist(img, n)
    return grade(img.convert("RGB"), n, insert=(kind == "B"))


WHIP_AT = SEGS[3][3]    # B (screen) -> C (park): location change
SLIDE_AT = SEGS[6][3]   # C2 -> D: story -> CTA block
WHIP_N = 4              # frames on each side of the cut
SLIDE_DUR = 0.32


def compose(frames, n, elements, card, glit):
    t = n / FPS
    seg = seg_at(t)
    frame = shot_frame(frames, seg, t, n)

    # whip-pan: smear + pan into the cut, out of the cut on the other side
    fi = n - int(round(WHIP_AT * FPS))
    if -WHIP_N <= fi < WHIP_N:
        k = (WHIP_N - abs(fi + 0.5)) / WHIP_N          # 0 -> 1 at the cut
        frame = motion_blur_x(shift_x(frame, (k ** 2) * 380 * (1 if fi < 0 else -1)),
                              int(40 + 260 * k))

    # slide wipe: screen split in half, old frame left, new frame right
    if SLIDE_AT <= t < SLIDE_AT + SLIDE_DUR:
        u = (t - SLIDE_AT) / SLIDE_DUR
        old = shot_frame(frames, SEGS[5], SLIDE_AT - 1 / FPS, n)
        if u < 0.25:
            edge = W - (W / 2) * (1 - (1 - u / 0.25) ** 3)
        elif u < 0.75:
            edge = W / 2
        else:
            edge = W / 2 * (1 - ((u - 0.75) / 0.25) ** 2)
        comp = Image.new("RGBA", (W, H))
        comp.paste(old.crop((0, 0, int(edge), H)), (0, 0))
        comp.paste(frame.crop((0, 0, W - int(edge), H)), (int(edge), 0))
        frame = comp

    # glitter texture: one "breath" between blocks (C2) and behind the CTA
    if seg[2] == "C2":
        draw_glitter(frame, glit, 0, 250, t, 0.55)

    for el in elements:
        el.draw(frame, t)

    # profile card + CTA (last seconds)
    c0 = src2out(13.22)
    if t >= c0:
        paste_c(frame, card, 540, 1000)
        draw_glitter(frame, CTA_GLIT, 180, 1170, t, 0.9)
        paste_c(frame, CTA_TXT, 540, 1245)

    draw_subs(frame, t)
    paste(frame, OVERLAYS[SEGS.index(seg) + 1], 0, 0)
    return frame.convert("RGB")


CTA_TXT = t4("[не забудь подписаться!]", 48, WHITE)
CTA_GLIT = glitter(720, 150, 26, 5)


# ---------------------------------------------------------------- audio
def read_wav(path):
    with wave.open(path) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        return x.reshape(-1, w.getnchannels())


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    if x.ndim == 1:
        x = x[:, None]
    with wave.open(path, "wb") as w:
        w.setnchannels(x.shape[1])
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def build_voice():
    """Cut the voice along the EDL (short crossfades), then clean it up:
    rumble high-pass, FFT denoise, de-mud, presence, de-ess, compression."""
    raw = os.path.join(TMP, "voice_raw.wav")
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", SRC, "-ac", "1", "-ar", str(SR), raw],
                   check=True)
    x = read_wav(raw)[:, 0]
    fade = int(0.006 * SR)
    parts = []
    for a, b, k, o in SEGS:
        p = x[int(a * SR):int(b * SR)].copy()
        p[:fade] *= np.linspace(0, 1, fade)
        p[-fade:] *= np.linspace(1, 0, fade)
        parts.append(p)
    v = np.concatenate(parts)
    cut = os.path.join(TMP, "voice_cut.wav")
    write_wav(cut, v)
    clean = os.path.join(TMP, "voice_clean.wav")
    af = ("highpass=f=85:poles=2,afftdn=nr=14:nf=-38:tn=1,"
          "equalizer=f=260:t=q:w=1.2:g=-2.5,equalizer=f=3400:t=q:w=1.0:g=2.5,"
          "equalizer=f=11000:t=h:w=0.7:g=1.5,deesser=i=0.35,"
          "acompressor=threshold=-20dB:ratio=3:attack=5:release=90:makeup=2")
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", cut, "-af", af, "-ar", str(SR), clean],
                   check=True)
    return read_wav(clean)[:, 0]


# music: 117 bpm, eighth-note grid aligned with the edit's cut points
BPM = 117.0
PHASE = 0.235
BEAT = 60 / BPM
BAR0 = PHASE + 2 * BEAT   # a bar downbeat lands on the twist cut


def midi(m):
    return 440 * 2 ** ((m - 69) / 12)


def adsr(n, a, d, s, r_len, sus_len):
    env = np.concatenate([np.linspace(0, 1, max(1, int(a * SR))),
                          np.linspace(1, s, max(1, int(d * SR))),
                          np.full(max(1, int(sus_len * SR)), s),
                          np.linspace(s, 0, max(1, int(r_len * SR)))])
    out = np.zeros(n, np.float32)
    out[:min(n, len(env))] = env[:n]
    return out


def ep_note(f, dur, vel):
    """Soft electric-piano: FM tine + warm body, slight detune chorus."""
    n = int((dur + 1.2) * SR)
    t = np.arange(n) / SR
    env = np.exp(-t * 2.2) * np.clip(t / 0.004, 0, 1)
    env *= np.clip(1 - (t - dur) / 0.6, 0, 1)
    idx = 1.6 * np.exp(-t * 9)
    s = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * t))
    s += 0.5 * np.sin(2 * np.pi * f * 1.003 * t) + 0.25 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-t * 4)
    return (s * env * vel).astype(np.float32)


def synth_music(dur):
    n = int(dur * SR) + SR
    L = np.zeros(n, np.float32)
    R = np.zeros(n, np.float32)
    rng = np.random.default_rng(11)

    def add(sig, t0, pan=0.0):
        i = int(t0 * SR)
        if i >= n:
            return
        j0 = max(0, -i)
        sig = sig[j0:]
        i = max(0, i)
        m = min(len(sig), n - i)
        L[i:i + m] += sig[:m] * (1 - pan) * 0.9
        R[i:i + m] += sig[:m] * (1 + pan) * 0.9

    # Fmaj9 - Am7 - Dm9 - Bbmaj7
    chords = [[53, 57, 60, 64, 67], [57, 60, 64, 67, 71], [50, 57, 60, 64, 65], [46, 57, 62, 65, 69]]
    roots = [41, 45, 38, 46]
    melody = {1: [(0, 76), (1.5, 74), (2, 72)], 3: [(0, 77), (1, 76), (2.5, 72)],
              5: [(0, 76), (1.5, 79), (2, 76)], 7: [(0, 74), (1, 72)]}
    twist0, twist1 = SEGS[1][3], SEGS[2][3]
    bar = 4 * BEAT
    first = -int(math.ceil(BAR0 / bar))
    last = int(dur / bar) + 2
    for bi in range(first, last):
        t0 = BAR0 + bi * bar
        ch = chords[bi % 4]
        for m in ch:
            add(ep_note(midi(m), BEAT * 1.4, 0.055), t0, pan=rng.uniform(-0.3, 0.3))
            add(ep_note(midi(m), BEAT * 1.2, 0.04), t0 + 2.5 * BEAT, pan=rng.uniform(-0.3, 0.3))
        # sub bass
        for off, ln in ((0, 1.4), (2.5, 1.3)):
            nb = int(ln * BEAT * SR)
            tt = np.arange(nb) / SR
            sb = np.sin(2 * np.pi * midi(roots[bi % 4]) * tt) * np.minimum(1, tt / 0.01) \
                * np.clip(1 - (tt - ln * BEAT + 0.08) / 0.08, 0, 1) * 0.2
            add(sb.astype(np.float32), t0 + off * BEAT)
        for (off, m) in melody.get(bi % 8, []):
            add(ep_note(midi(m + 12), BEAT * 0.8, 0.028), t0 + off * BEAT, pan=0.35)
        for q in range(4):
            tq = t0 + q * BEAT
            in_twist = twist0 <= tq < twist1
            if q in (0, 2) and not in_twist:                       # kick
                nk = int(0.3 * SR)
                tt = np.arange(nk) / SR
                f = 45 + 80 * np.exp(-tt * 28)
                k = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 11) * 0.5
                add(k.astype(np.float32), tq)
            if q in (1, 3) and not in_twist:                       # soft clap
                nc = int(0.18 * SR)
                tt = np.arange(nc) / SR
                noise = rng.standard_normal(nc).astype(np.float32)
                noise = noise - np.convolve(noise, np.ones(6) / 6, "same")
                env = np.exp(-tt * 26) * (1 + 0.6 * (tt < 0.012))
                add(noise * env * 0.10, tq)
            for e in (0, 1):                                        # hats, light swing
                th = tq + e * BEAT * 0.54
                nh = int(0.04 * SR)
                noise = rng.standard_normal(nh).astype(np.float32)
                noise = noise - np.convolve(noise, np.ones(3) / 3, "same")
                add(noise * np.exp(-np.arange(nh) / SR * 90) * (0.035 if e else 0.05), th,
                    pan=0.25)
    mus = np.stack([L, R], 1)[: int(dur * SR)]
    # twist: muffle the bed (one-pole low-pass) - "held breath" under the B/W moment
    a0, a1 = int(twist0 * SR), int(twist1 * SR)
    seg = mus[a0:a1].copy()
    y = np.zeros_like(seg)
    acc = np.zeros(2, np.float32)
    alpha = 0.06
    for i in range(len(seg)):
        acc += alpha * (seg[i] - acc)
        y[i] = acc
    mus[a0:a1] = y * 1.6
    # tail: fade after the last word
    tail = int((DUR - 0.5) * SR)
    mus[tail:] *= np.linspace(1, 0, len(mus) - tail)[:, None]
    return mus


def sfx(kind, rng):
    if kind == "whoosh":
        n = int(0.45 * SR)
        t = np.arange(n) / SR
        noise = rng.standard_normal(n).astype(np.float32)
        out = np.zeros(n, np.float32)
        acc = 0.0
        for i in range(n):            # sweeping low-pass
            a = 0.02 + 0.5 * math.sin(math.pi * i / n) ** 2
            acc += a * (noise[i] - acc)
            out[i] = acc
        return out * np.sin(np.pi * t / t[-1]) ** 2 * 0.9, -0.22
    if kind == "swish":
        n = int(0.3 * SR)
        t = np.arange(n) / SR
        noise = rng.standard_normal(n).astype(np.float32)
        hp = noise - np.convolve(noise, np.ones(8) / 8, "same")
        return hp * np.sin(np.pi * t / t[-1]) ** 3 * 0.5, -0.05
    if kind == "shutter":
        n = int(0.16 * SR)
        t = np.arange(n) / SR
        noise = rng.standard_normal(n).astype(np.float32)
        hp = noise - np.convolve(noise, np.ones(4) / 4, "same")
        env = np.exp(-t * 160) + 0.7 * np.exp(-np.clip(t - 0.07, 0, None) * 170) * (t > 0.07)
        return hp * env * 0.6, 0.0
    if kind == "pop":
        n = int(0.09 * SR)
        t = np.arange(n) / SR
        f = 700 * np.exp(-t * 35) + 220
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 50) * 0.35, 0.0
    if kind == "chime":
        n = int(0.9 * SR)
        t = np.arange(n) / SR
        s = np.sin(2 * np.pi * 1318.5 * t) * np.exp(-t * 6) + \
            (t > 0.11) * np.sin(2 * np.pi * 1760 * t) * np.exp(-np.clip(t - 0.11, 0, None) * 5)
        return s * 0.16, 0.0
    raise ValueError(kind)


def build_audio(sfx_events, path):
    voice = build_voice()
    n = int(DUR * SR)
    voice = np.pad(voice, (0, max(0, n - len(voice))))[:n]
    music = synth_music(DUR)[:n]
    music = np.pad(music, ((0, n - len(music)), (0, 0)))
    # sidechain: duck the bed ~9 dB while the voice is present
    env = np.abs(voice)
    k = int(0.03 * SR)
    env = np.convolve(env, np.ones(k) / k, "same")
    env = np.maximum.accumulate(env[::-1])[::-1] * 0 + env      # keep plain envelope
    on = np.clip((20 * np.log10(env + 1e-6) + 42) / 12, 0, 1)
    sm = np.convolve(on, np.ones(int(0.12 * SR)) / int(0.12 * SR), "same")
    duck = 1 - 0.65 * sm
    mix = np.stack([voice, voice], 1) + music * 0.55 * duck[:, None]
    rng = np.random.default_rng(4)
    for t, kind in sfx_events:
        s, off = sfx(kind, rng)
        i = int((t + off) * SR)
        i0 = max(0, i)
        s = s[i0 - i:]
        m = min(len(s), n - i0)
        if m > 0:
            mix[i0:i0 + m] += s[:m, None] * 0.5
    pre = os.path.join(TMP, "mix_pre.wav")
    write_wav(pre, mix * 0.5)
    # two-pass loudness normalisation to -14 LUFS / -1.5 dBTP (Reels/TikTok/Shorts)
    r = subprocess.run([FFMPEG, "-v", "info", "-i", pre, "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=9:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    js = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    af = ("loudnorm=I=-14:TP=-1.5:LRA=9:linear=true:"
          f"measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
          f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:"
          f"offset={js['target_offset']}")
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", pre, "-af", af, "-ar", str(SR), path],
                   check=True)


# ---------------------------------------------------------------- main
def main(preview=None):
    os.makedirs(TMP, exist_ok=True)
    frames = load_frames()
    elements, sfx_events = build_elements()
    sfx_events += [(WHIP_AT, "whoosh"), (SLIDE_AT, "swish")]
    face = fetch(frames, 11.0)
    card = profile_card(face.crop((290, 640, 470, 820)))
    glit = glitter(W, 900, 40, 3)

    if preview:
        pdir = os.path.join(ROOT, "output", "preview")
        os.makedirs(pdir, exist_ok=True)
        for t in preview:
            n = int(round(t * FPS))
            compose(frames, n, elements, card, glit).save(
                os.path.join(pdir, f"k{t:05.2f}.jpg"), quality=88)
        return

    audio = os.path.join(TMP, "audio.wav")
    build_audio(sfx_events, audio)
    enc = subprocess.Popen([
        FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
        "-r", str(FPS), "-i", "-", "-i", audio,
        "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high",
        "-level", "4.2", "-maxrate", "20M", "-bufsize", "40M", "-g", "60",
        "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
        "-color_trc", "bt709", "-c:a", "aac", "-b:a", "320k", "-ar", str(SR),
        "-movflags", "+faststart", "-shortest", OUT], stdin=subprocess.PIPE)
    for n in range(NFRAMES):
        enc.stdin.write(compose(frames, n, elements, card, glit).tobytes())
        if n % 60 == 0:
            print(f"frame {n}/{NFRAMES}", flush=True)
    enc.stdin.close()
    enc.wait()
    for f in os.listdir(TMP):
        os.remove(os.path.join(TMP, f))
    os.rmdir(TMP)
    print("done:", OUT, f"{DUR:.2f}s")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        main([float(x) for x in sys.argv[2:]])
    else:
        main()
