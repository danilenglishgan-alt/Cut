"""Girly-style montage for the sticker-pack reel.

Reads assets/source.mp4, adds zooms, animated titles, emoji stickers,
sparkles, flashes and pop sounds, writes output/montage.mp4 (1080x1920).
"""
import math
import os
import random
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "assets", "source.mp4")
OUT = os.path.join(ROOT, "output", "montage.mp4")
FONTS = os.path.join(ROOT, "assets", "fonts")
EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")

SW, SH = 720, 1280          # source size
W, H = 1080, 1920           # output size
FPS = 30
DUR = 15.066
NFRAMES = int(DUR * FPS)

PINK = (255, 143, 199)
PINK_LIGHT = (255, 214, 234)
PINK_HOT = (255, 72, 158)
PLUM = (150, 30, 92)
WHITE = (255, 255, 255)

random.seed(7)


# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out_back(x, s=1.9):
    x = clamp(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def ease_in_out(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


# ---------------------------------------------------------------- fonts
def font(name, size, variation=None):
    f = ImageFont.truetype(os.path.join(FONTS, name), size)
    if variation:
        f.set_variation_by_name(variation)
    return f


def fit_font(name, text, max_w, size, variation=None):
    while size > 20:
        f = font(name, size, variation)
        l, t, r, b = f.getbbox(text)
        if r - l <= max_w:
            return f
        size -= 4
    return font(name, size, variation)


def text_mask(text, f, stroke=0, pad=40):
    l, t, r, b = f.getbbox(text, stroke_width=stroke)
    img = Image.new("L", (r - l + pad * 2, b - t + pad * 2), 0)
    ImageDraw.Draw(img).text((pad - l, pad - t), text, font=f, fill=255,
                             stroke_width=stroke, stroke_fill=255)
    return img


def vgradient(size, top, bottom):
    w, h = size
    g = np.linspace(0, 1, h)[:, None]
    arr = np.zeros((h, w, 3), np.float32)
    for i in range(3):
        arr[..., i] = top[i] * (1 - g) + bottom[i] * g
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def bubble_text(text, size=150, max_w=880, top=PINK_LIGHT, bottom=PINK_HOT,
                stroke=WHITE, sw=12, shadow=PLUM, fname="RubikBubbles-Regular.ttf",
                variation=None):
    """Glossy gradient letters with white outline and plum drop shadow."""
    f = fit_font(fname, text, max_w, size, variation)
    outer = text_mask(text, f, stroke=sw)
    inner = text_mask(text, f, stroke=0)
    # both masks share the same padding origin shifted by the stroke width
    inner_full = Image.new("L", outer.size, 0)
    inner_full.paste(inner, (sw, sw) if inner.size != outer.size else (0, 0))
    inner = inner_full if inner.size != outer.size else inner
    out = Image.new("RGBA", (outer.width + 16, outer.height + 16), (0, 0, 0, 0))
    sh = Image.new("RGBA", outer.size, shadow + (0,))
    sh.putalpha(outer.point(lambda v: int(v * 0.75)))
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(3)), (8, 12))
    st = Image.new("RGBA", outer.size, stroke + (0,))
    st.putalpha(outer)
    out.alpha_composite(st, (0, 0))
    grad = vgradient(outer.size, top, bottom).convert("RGBA")
    grad.putalpha(inner)
    out.alpha_composite(grad, (0, 0))
    # gloss: light streak on the upper part of each letter
    gloss_mask = np.array(inner, np.float32)
    h = gloss_mask.shape[0]
    fade = np.clip(1.4 - np.linspace(0, 2.6, h), 0, 1)[:, None]
    shifted = np.roll(np.array(inner, np.float32), 10, axis=0)
    gm = (gloss_mask / 255) * (shifted / 255) * fade * 0.55 * 255
    gl = Image.new("RGBA", outer.size, WHITE + (0,))
    gl.putalpha(Image.fromarray(gm.astype(np.uint8)))
    out.alpha_composite(gl, (0, 0))
    return out.crop(out.getbbox())


def script_text(text, size=110, max_w=940, fill=WHITE, glow=PINK_HOT,
                fname="MarckScript-Regular.ttf", sw=3, variation=None):
    """Handwritten words with soft pink glow."""
    f = fit_font(fname, text, max_w, size, variation)
    pad = 50
    m = text_mask(text, f, stroke=0, pad=pad)
    ms = text_mask(text, f, stroke=sw, pad=pad)
    ms = ms.crop((sw, sw, sw + m.width, sw + m.height)) if ms.size != m.size else ms
    out = Image.new("RGBA", m.size, (0, 0, 0, 0))
    g = Image.new("RGBA", m.size, glow + (0,))
    g.putalpha(ms.filter(ImageFilter.GaussianBlur(14)).point(lambda v: min(255, int(v * 2.2))))
    out.alpha_composite(g)
    s = Image.new("RGBA", m.size, glow + (0,))
    s.putalpha(ms)
    out.alpha_composite(s)
    t = Image.new("RGBA", m.size, fill + (0,))
    t.putalpha(m)
    out.alpha_composite(t)
    return out.crop(out.getbbox())


def emoji_sticker(ch, size=230, border=14, rot=0):
    """Render an emoji as a die-cut sticker with white border and shadow."""
    f = ImageFont.truetype(EMOJI_FONT, 109)
    base = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(base).text((80, 80), ch, font=f, embedded_color=True, anchor="mm")
    base = base.crop(base.getbbox())
    k = size / max(base.size)
    base = base.resize((int(base.width * k), int(base.height * k)), Image.LANCZOS)
    pad = border * 2 + 10
    canvas = Image.new("RGBA", (base.width + pad * 2, base.height + pad * 2), (0, 0, 0, 0))
    canvas.alpha_composite(base, (pad, pad))
    a = canvas.getchannel("A").point(lambda v: 255 if v > 40 else 0)
    outline = a.filter(ImageFilter.MaxFilter(border * 2 + 1)) if border else a
    outline = outline.filter(ImageFilter.GaussianBlur(1.2))
    out = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sh = Image.new("RGBA", canvas.size, (120, 20, 70, 0))
    sh.putalpha(outline.point(lambda v: int(v * 0.45)).filter(ImageFilter.GaussianBlur(8)))
    out.alpha_composite(sh, (6, 10))
    wh = Image.new("RGBA", canvas.size, WHITE + (0,))
    wh.putalpha(outline)
    out.alpha_composite(wh)
    out.alpha_composite(canvas)
    out = out.crop(out.getbbox())
    if rot:
        out = out.rotate(rot, resample=Image.BICUBIC, expand=True)
    return out


def sparkle(size, color=WHITE):
    """Four-point star with glow."""
    s = size * 3
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = s / 2
    r, q = size * 1.0, size * 0.22
    pts = []
    for i in range(8):
        ang = i * math.pi / 4 - math.pi / 2
        rad = r if i % 2 == 0 else q
        pts.append((c + rad * math.cos(ang), c + rad * math.sin(ang)))
    d.polygon(pts, fill=color + (255,))
    glow = img.getchannel("A").filter(ImageFilter.GaussianBlur(size * 0.35))
    out = Image.new("RGBA", img.size, PINK + (0,))
    out.putalpha(glow)
    out.alpha_composite(img)
    return out


def heart(size, color=PINK_HOT, outline=WHITE):
    s = 400
    img = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(img)
    pts = []
    for i in range(200):
        t = i / 200 * 2 * math.pi
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((s / 2 + x * 10, s / 2 - y * 10 + 10))
    d.polygon(pts, fill=255)
    big = img.filter(ImageFilter.MaxFilter(25))
    out = Image.new("RGBA", (s, s), outline + (0,))
    out.putalpha(big)
    fill = vgradient((s, s), PINK_LIGHT, color).convert("RGBA")
    fill.putalpha(img)
    out.alpha_composite(fill)
    out = out.crop(out.getbbox())
    return out.resize((size, int(size * out.height / out.width)), Image.LANCZOS)


def color_dot(size, color):
    s = size + 16
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, s - 1, s - 1), fill=WHITE + (255,))
    d.ellipse((8, 8, s - 9, s - 9), fill=color + (255,))
    d.ellipse((s * 0.28, s * 0.22, s * 0.48, s * 0.38), fill=(255, 255, 255, 150))
    return img


NOBG_STICKER = emoji_sticker("🧸", 200)


def draw_no_background(frame, t):
    """Checkerboard card that dissolves, leaving a clean die-cut sticker."""
    t0, t1 = 9.14, 10.15
    if not t0 <= t <= t1:
        return
    size, cx, cy = 290, 800, 1180
    k = ease_out_back((t - t0) / 0.25) * clamp((t1 - t) / 0.15)
    card = Image.new("RGBA", (size, size), WHITE + (255,))
    d = ImageDraw.Draw(card)
    n, c = 8, size / 8
    for i in range(n):
        for j in range(n):
            if (i + j) % 2:
                d.rectangle((i * c, j * c, (i + 1) * c, (j + 1) * c), fill=(214, 214, 222, 255))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=40, fill=255)
    fade = 1 - ease_in_out((t - 9.45) / 0.3)
    card.putalpha(mask.point(lambda v: int(v * fade)))
    card.alpha_composite(NOBG_STICKER, ((size - NOBG_STICKER.width) // 2,
                                        (size - NOBG_STICKER.height) // 2))
    card = card.rotate(6 + math.sin(t * 2.3) * 2, resample=Image.BICUBIC, expand=True)
    s = max(1, int(card.width * max(k, 0.02)))
    card = card.resize((s, s), Image.BICUBIC)
    _paste_clip(frame, card, int(cx - s / 2), int(cy - s / 2))


def pill(text_img_w, h=120, color=WHITE):
    img = Image.new("RGBA", (text_img_w, h), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, text_img_w - 1, h - 1), radius=h // 2,
                                          fill=color + (255,))
    return img


# ---------------------------------------------------------------- timeline
# Cuts in the source (seconds): talking A | phone insert B | talking C | talking D
CUT_B, CUT_C, CUT_D = 4.53, 7.03, 10.2


class El:
    def __init__(self, img, t0, t1, cx, cy, rot=0, anim="pop", float_amp=6,
                 float_speed=1.6, wiggle=2.0, exit="pop", pop_dur=0.28):
        self.img, self.t0, self.t1 = img, t0, t1
        self.cx, self.cy, self.rot = cx, cy, rot
        self.anim, self.exit = anim, exit
        self.float_amp, self.float_speed, self.wiggle = float_amp, float_speed, wiggle
        self.pop_dur = pop_dur
        self.phase = random.random() * 6.28
        self._cache = {}

    def state(self, t):
        if t < self.t0 or t > self.t1:
            return None
        a_in = (t - self.t0) / self.pop_dur
        a_out = (self.t1 - t) / 0.16
        scale, alpha, dy = 1.0, 1.0, 0.0
        if self.anim == "pop":
            scale = ease_out_back(a_in) if a_in < 1 else 1.0
            alpha = clamp(a_in * 3)
        elif self.anim == "fade":
            alpha = ease_out(a_in)
            dy = (1 - ease_out(a_in)) * 40
        elif self.anim == "drop":
            scale = ease_out_back(a_in, 2.4) if a_in < 1 else 1.0
            dy = (1 - ease_out(a_in)) * -120
            alpha = clamp(a_in * 3)
        if a_out < 1:
            if self.exit == "pop":
                scale *= 0.4 + 0.6 * ease_out(a_out)
            alpha *= clamp(a_out)
        dy += math.sin(t * self.float_speed * 2 + self.phase) * self.float_amp
        rot = self.rot + math.sin(t * 2.3 + self.phase) * self.wiggle
        return scale, alpha, dy, rot

    def draw(self, frame, t):
        st = self.state(t)
        if st is None:
            return
        scale, alpha, dy, rot = st
        if scale <= 0.02 or alpha <= 0.01:
            return
        img = self.img
        w, h = max(1, int(img.width * scale)), max(1, int(img.height * scale))
        im = img.resize((w, h), Image.BICUBIC)
        if abs(rot) > 0.2:
            im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
        if alpha < 1:
            im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
        frame.alpha_composite(im, (int(self.cx - im.width / 2), int(self.cy + dy - im.height / 2)),
                              ) if _inside(frame, im, self.cx, self.cy + dy) else \
            _paste_clip(frame, im, int(self.cx - im.width / 2), int(self.cy + dy - im.height / 2))


def _inside(frame, im, cx, cy):
    x, y = int(cx - im.width / 2), int(cy - im.height / 2)
    return x >= 0 and y >= 0 and x + im.width <= frame.width and y + im.height <= frame.height


def _paste_clip(frame, im, x, y):
    l, t = max(0, -x), max(0, -y)
    r, b = min(im.width, frame.width - x), min(im.height, frame.height - y)
    if r <= l or b <= t:
        return
    frame.alpha_composite(im.crop((l, t, r, b)), (x + l, y + t))


def build_elements():
    E = []
    sfx = []  # (time, kind)

    def add(el, sound="pop"):
        E.append(el)
        if sound:
            sfx.append((el.t0, sound))
        return el

    # --- A: hook -------------------------------------------------------
    add(El(bubble_text("ВСЕ ИЩУТ", 170), 0.0, 3.30, 540, 330, rot=-3), "pop")
    add(El(script_text("откуда эти", 120), 0.80, 3.30, 540, 500, rot=-2, anim="fade"), None)
    add(El(emoji_sticker("🍞", 230), 1.02, 3.30, 830, 790, rot=10), "pop")
    add(El(emoji_sticker("🥥", 220), 1.40, 3.30, 860, 1080, rot=-8), "pop")
    add(El(emoji_sticker("🌸", 230), 1.92, 3.30, 170, 760, rot=-12), "pop")
    add(El(script_text("стикеры в рилсах?", 96, fill=PINK_LIGHT, glow=PLUM), 2.16, 3.30,
           540, 620, rot=-2, anim="fade"), None)
    add(El(bubble_text("Я СОБРАЛА", 160, top=(255, 250, 252), bottom=PINK), 3.36, 4.50,
           540, 400, rot=3, pop_dur=0.32), "ding")
    add(El(heart(110), 3.50, 4.50, 880, 270, rot=14), "pop")

    # --- B: phone insert -----------------------------------------------
    add(El(bubble_text("1000+", 250), 6.40, 7.03, 540, 1440, rot=-6, pop_dur=0.22), "ding")

    # --- C: 1000+ stickers, by colour, no background --------------------
    add(El(bubble_text("1000+", 210), CUT_C, 10.15, 540, 330, rot=-4), None)
    add(El(script_text("стикеров", 130), CUT_C + 0.08, 10.15, 560, 500, rot=-3, anim="fade"), None)
    add(El(script_text("разделила по цветам", 88, fill=WHITE, glow=PLUM), 7.74, 9.10,
           540, 1500, anim="fade"), None)
    palette = [(255, 160, 200), (255, 196, 150), (255, 233, 140), (170, 232, 190),
               (160, 205, 255), (205, 180, 255)]
    for i, c in enumerate(palette):
        add(El(color_dot(92, c), 7.80 + i * 0.12, 9.10, 540 + (i - 2.5) * 125, 1640,
               float_amp=8, wiggle=0), "pop" if i % 2 == 0 else None)
    sfx.append((9.14, "whoosh"))
    add(El(script_text("убрала фон", 96, fill=WHITE, glow=PLUM), 9.14, 10.15,
           540, 1500, anim="fade"), None)

    # --- D: CTA ------------------------------------------------------------
    add(El(script_text("всего лишь зайди в", 104), 10.50, 12.55, 540, 330, rot=-3,
           anim="fade"), None)
    add(El(bubble_text("КОММЕНТЫ", 180), 11.55, 12.55, 540, 500, rot=-2), "pop")
    add(El(script_text("напиши", 110), 12.24, 15.07, 540, 320, rot=-3, anim="fade"), None)
    add(El(bubble_text("«СТИКЕР»", 190), 12.66, 15.07, 540, 490, rot=-3, pop_dur=0.3), "ding")
    add(El(emoji_sticker("🎀", 170), 12.80, 15.07, 910, 330, rot=16), "pop")
    add(El(script_text("и я всё отправлю", 100, fill=PINK_LIGHT, glow=PLUM), 13.30, 15.07,
           540, 1470, anim="fade"), None)
    add(El(emoji_sticker("💌", 190), 13.74, 15.07, 860, 1330, rot=-10, anim="drop"), "pop")
    for i, (x, y, s, r) in enumerate([(150, 820, 90, -15), (930, 700, 70, 12),
                                      (210, 1180, 60, 8), (880, 980, 80, -6)]):
        add(El(heart(s), 14.05 + i * 0.1, 15.07, x, y, rot=r, float_amp=14), None)
    return E, sfx


# ---------------------------------------------------------------- camera
def zoom_at(t):
    """Returns (zoom, anchor_x, anchor_y) in source pixels."""
    def steps(t, pts):
        z = pts[0][1]
        for (t0, z1), (_, z0) in zip(pts[1:], pts[:-1]):
            k = ease_out((t - t0) / 0.18)
            z = z0 + (z1 - z0) * k if t >= t0 else z
            if t < t0:
                break
        return z

    if t < CUT_B:
        z = steps(t, [(0, 1.0), (1.02, 1.06), (1.40, 1.11), (1.92, 1.16), (3.36, 1.26)])
        z += 0.012 * math.sin(t * 3)
        return z, 200, 690
    if t < CUT_C:
        return 1.0, 360, 640
    if t < CUT_D:
        k = (t - CUT_C) / (CUT_D - CUT_C)
        z = 1.14 - 0.08 * ease_out(min(1, (t - CUT_C) / 0.35)) + 0.08 * ease_in_out(k)
        if t >= 9.14:
            z += 0.05 * ease_out((t - 9.14) / 0.2)
        return z, 340, 560
    z = steps(t, [(CUT_D, 1.16), (10.5, 1.08), (12.66, 1.2), (13.3, 1.12)])
    z = 1.16 - 0.08 * ease_out((t - CUT_D) / 0.4) if t < 10.5 else z
    return z, 380, 640


def camera(src, t):
    z, ax, ay = zoom_at(t)
    cw, ch = SW / z, SH / z
    x0 = clamp(ax - cw * (ax / SW), 0, SW - cw)
    y0 = clamp(ay - ch * (ay / SH), 0, SH - ch)
    return src.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


# ---------------------------------------------------------------- grade
def make_vignette():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((x - W / 2) / (W * 0.62)) ** 2 + ((y - H / 2) / (H * 0.6)) ** 2)
    a = np.clip((d - 0.55) / 0.6, 0, 1) ** 1.6
    return a[..., None]


VIG = make_vignette()
VIG_COLOR = np.array([255, 150, 200], np.float32)


def grade(img, strength=1.0):
    a = np.asarray(img.convert("RGB"), np.float32)
    # soft pastel: lift shadows, warm-pink tint, slight desat of greens
    lum = a.mean(axis=2, keepdims=True)
    a = a * 0.9 + lum * 0.1
    a = a * np.array([1.04, 0.97, 1.02]) + np.array([9, 2, 8])
    a = 255 * (a / 255) ** 0.94
    a = a * (1 - VIG * 0.34 * strength) + VIG_COLOR * VIG * 0.34 * strength
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


# ---------------------------------------------------------------- sparkles
SPARKLES = [sparkle(s) for s in (18, 26, 34)]
SPARK_POS = [(random.randint(40, W - 40), random.randint(120, 1450), random.randint(0, 2),
              random.random() * 6.28, 1.5 + random.random() * 2) for _ in range(14)]


def draw_sparkles(frame, t):
    for x, y, k, ph, sp in SPARK_POS:
        v = math.sin(t * sp + ph)
        if v <= 0.15:
            continue
        im = SPARKLES[k]
        s = 0.5 + 0.5 * v
        im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BICUBIC)
        im.putalpha(im.getchannel("A").point(lambda a: int(a * v)))
        _paste_clip(frame, im, int(x - im.width / 2), int(y - im.height / 2))


# ---------------------------------------------------------------- typing pill
TYPE_FONT = font("Unbounded.ttf", 50, "Medium")
TYPE_HINT = font("Unbounded.ttf", 34, "Regular")
AVATAR = emoji_sticker("🎀", 60, border=0)
HEART_SMALL = heart(58)


def draw_comment_box(frame, t):
    t0, t1 = 12.18, 15.07
    if t < t0:
        return
    a_in = ease_out_back((t - t0) / 0.3)
    w, h = 820, 128
    box = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(box)
    sh = Image.new("L", box.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle((20, 28, w + 20, h + 28), radius=h // 2, fill=110)
    shl = Image.new("RGBA", box.size, PLUM + (0,))
    shl.putalpha(sh.filter(ImageFilter.GaussianBlur(10)))
    box.alpha_composite(shl)
    d.rounded_rectangle((20, 20, w + 20, h + 20), radius=h // 2, fill=(255, 255, 255, 245),
                        outline=PINK + (255,), width=5)
    box.alpha_composite(AVATAR, (50, 20 + (h - AVATAR.height) // 2))
    word = "стикер"
    n = int(clamp((t - 12.35) / 0.4) * len(word) + 0.001)
    if n == 0:
        d.text((140, 20 + h // 2), "Добавьте комментарий…", font=TYPE_HINT,
               fill=(170, 150, 160), anchor="lm")
    else:
        d.text((140, 20 + h // 2), word[:n], font=TYPE_FONT, fill=(60, 30, 50), anchor="lm")
        if n < len(word) or int(t * 3) % 2 == 0:
            tw = TYPE_FONT.getlength(word[:n])
            d.rectangle((146 + tw, 20 + h // 2 - 30, 150 + tw, 20 + h // 2 + 30), fill=PINK_HOT)
    if t > 12.9:
        k = ease_out_back((t - 12.9) / 0.3)
        hs = HEART_SMALL.resize((max(1, int(HEART_SMALL.width * k)),
                                 max(1, int(HEART_SMALL.height * k))), Image.BICUBIC)
        box.alpha_composite(hs, (w - 50 - hs.width // 2, 20 + h // 2 - hs.height // 2))
    s = max(0.05, a_in)
    bw, bh = int(box.width * s), int(box.height * s)
    box = box.resize((bw, bh), Image.BICUBIC)
    y = 1640 + math.sin(t * 3) * 4
    _paste_clip(frame, box, int(540 - bw / 2), int(y - bh / 2))


# ---------------------------------------------------------------- flashes
def flash_alpha(t):
    a = 0.0
    for tc, strength in ((CUT_B - 0.02, 0.85), (CUT_C, 0.9), (CUT_D, 0.75), (3.36, 0.35),
                         (12.66, 0.3)):
        dt = t - tc
        if 0 <= dt < 0.25:
            a = max(a, strength * (1 - dt / 0.25) ** 2)
    return a


FLASH = Image.new("RGBA", (W, H), (255, 228, 240, 255))


# ---------------------------------------------------------------- audio
def synth_sfx(events, sr=44100):
    n = int(DUR * sr) + sr
    out = np.zeros(n, np.float32)
    rng = np.random.default_rng(3)
    for t, kind in events:
        i = int(t * sr)
        if kind == "pop":
            L = int(0.09 * sr)
            tt = np.arange(L) / sr
            f = 900 * np.exp(-tt * 30) + 250
            s = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-tt * 45) * 0.55
        elif kind == "ding":
            L = int(0.6 * sr)
            tt = np.arange(L) / sr
            s = (np.sin(2 * np.pi * 1568 * tt) + 0.6 * np.sin(2 * np.pi * 2349 * tt)
                 + 0.3 * np.sin(2 * np.pi * 3136 * tt)) * np.exp(-tt * 7) * 0.28
        elif kind == "whoosh":
            L = int(0.35 * sr)
            tt = np.arange(L) / sr
            noise = rng.standard_normal(L).astype(np.float32)
            k = np.ones(40) / 40
            noise = np.convolve(noise, k, mode="same")
            env = np.sin(np.pi * tt / tt[-1]) ** 2
            s = noise * env * 1.6
            i -= L // 2
        else:
            continue
        i = max(0, i)
        out[i:i + len(s)] += s[: n - i]
    return out[: int(DUR * sr)]


def build_audio(sfx_events, path):
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", SRC, "-f", "s16le", "-ac", "2",
                          "-ar", "44100", "-"], capture_output=True, check=True).stdout
    voice = np.frombuffer(raw, np.int16).astype(np.float32).reshape(-1, 2) / 32768
    fx = synth_sfx(sfx_events)
    n = min(len(voice), len(fx))
    mix = voice[:n] + fx[:n, None] * 0.4
    mix = mix * (0.93 / max(0.93, float(np.abs(mix).max())))
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


# ---------------------------------------------------------------- main
def main(preview_times=None):
    elements, sfx = build_elements()
    for tc in (CUT_B, CUT_C, CUT_D):
        sfx.append((tc, "whoosh"))

    def compose(src, t):
        frame = camera(src, t)
        in_insert = CUT_B <= t < CUT_C
        frame = grade(frame, 0.35 if in_insert else 1.0)
        if not in_insert:
            draw_sparkles(frame, t)
        for el in elements:
            el.draw(frame, t)
        draw_no_background(frame, t)
        draw_comment_box(frame, t)
        fa = flash_alpha(t)
        if fa > 0:
            f = FLASH.copy()
            f.putalpha(int(255 * fa))
            frame.alpha_composite(f)
        return frame.convert("RGB")

    if preview_times:
        os.makedirs(os.path.join(ROOT, "output", "preview"), exist_ok=True)
        for t in preview_times:
            raw = subprocess.run([FFMPEG, "-v", "error", "-ss", str(t), "-i", SRC, "-frames:v", "1",
                                  "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                 capture_output=True, check=True).stdout
            src = Image.frombytes("RGB", (SW, SH), raw)
            compose(src, t).save(os.path.join(ROOT, "output", "preview", f"t{t:05.2f}.jpg"),
                                 quality=85)
        return

    audio = os.path.join(ROOT, "output", "_audio.wav")
    build_audio(sfx, audio)
    dec = subprocess.Popen([FFMPEG, "-v", "error", "-i", SRC, "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen([FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", audio,
                            "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                            "-movflags", "+faststart", "-shortest", OUT], stdin=subprocess.PIPE)
    i = 0
    while True:
        raw = dec.stdout.read(SW * SH * 3)
        if len(raw) < SW * SH * 3:
            break
        t = i / FPS
        enc.stdin.write(compose(Image.frombytes("RGB", (SW, SH), raw), t).tobytes())
        i += 1
        if i % 60 == 0:
            print(f"frame {i}/{NFRAMES}", flush=True)
    enc.stdin.close()
    enc.wait()
    dec.wait()
    os.remove(audio)
    print("done:", OUT)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        main([float(x) for x in sys.argv[2:]])
    else:
        main()
