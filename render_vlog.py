"""Universal aesthetic vlog-kit montage (template 7) for the sticker-pack reel.

Same source footage as render.py, restyled with the vlog-kit catalog:
T1-T5 text styles, whip-pan / grid-multiview / slide-wipe transitions,
a black-and-white grain twist at the "1000+" reveal, and a no-handle
CTA profile mockup near the end. Writes output/vlog_kit.mp4.
"""
import math
import os
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import render as base
from render import (ROOT, SRC, FONTS, SW, SH, W, H, FPS, DUR, FFMPEG,
                     clamp, ease_out, ease_in_out, ease_out_back,
                     font, fit_font, text_mask, vgradient,
                     emoji_sticker, sparkle, _paste_clip, _inside)

OUT = os.path.join(ROOT, "output", "vlog_kit.mp4")

# ---------------------------------------------------------------- palette
CREAM = (247, 243, 234)
PINK = (240, 184, 216)
PINK_LIGHT = (246, 201, 232)
BLUE = (175, 200, 234)
WHITE = (255, 255, 255)
BLACK = (26, 26, 26)
INK = (30, 15, 10)
PLATE_DARK = (43, 23, 16)
FLAT_PINK = (246, 201, 232)
FLAT_YELLOW = (255, 224, 150)
FLAT_MINT = (185, 232, 210)

# same cut points as the original edit (unchanged source footage)
CUT_B, CUT_C, CUT_D = 4.53, 7.03, 10.2
NFRAMES = int(DUR * FPS)


# ---------------------------------------------------------------- fonts
def bubble_font(text, max_w, size):
    return fit_font("RubikBubbles-Regular.ttf", text, max_w, size)


def script_font(text, max_w, size):
    return fit_font("MarckScript-Regular.ttf", text, max_w, size)


def sans_font(text, max_w, size, variation=None):
    return fit_font("Unbounded.ttf", text, max_w, size, variation)


# ---------------------------------------------------------------- generic glow text
def glow_text(text, f, fill, glow, sw=3, blur=6, glow_boost=2.0, pad=50):
    """Flat fill + thin dark outline + soft colour bloom. Backbone of T1/twist."""
    m = text_mask(text, f, stroke=0, pad=pad)
    ms = text_mask(text, f, stroke=sw, pad=pad)
    if ms.size != m.size:
        ms = ms.crop((0, 0, m.width, m.height))
    out = Image.new("RGBA", m.size, (0, 0, 0, 0))
    if glow is not None:
        g = Image.new("RGBA", m.size, glow + (0,))
        g.putalpha(ms.filter(ImageFilter.GaussianBlur(blur))
                   .point(lambda v: min(255, int(v * glow_boost))))
        out.alpha_composite(g)
    o = Image.new("RGBA", m.size, INK + (0,))
    o.putalpha(ms)
    out.alpha_composite(o)
    t = Image.new("RGBA", m.size, fill + (0,))
    t.putalpha(m)
    out.alpha_composite(t)
    return out.crop(out.getbbox())


def t1_top(text, size=110, max_w=880):
    f = bubble_font(text, max_w, size)
    return glow_text(text, f, fill=BLUE, glow=PINK_LIGHT, sw=3, blur=5, glow_boost=1.6)


def t1_bottom(text, size=150, max_w=920, twist=False):
    f = script_font(text, max_w, size)
    if twist:
        return glow_text(text, f, fill=PINK_LIGHT, glow=PINK, sw=3, blur=14, glow_boost=2.6)
    return glow_text(text, f, fill=WHITE, glow=PINK, sw=3, blur=8, glow_boost=1.8)


def t3_caption(text, size=64, max_w=880):
    f = sans_font(text, max_w, size, "Bold")
    return glow_text(text, f, fill=BLUE, glow=None, sw=3, blur=0)


def t4_caption(text, size=58, max_w=780, fill=BLACK):
    f = sans_font(text, max_w, size, "Medium")
    m = text_mask(text, f, stroke=0, pad=20)
    out = Image.new("RGBA", m.size, fill + (0,))
    out.putalpha(m)
    return out.crop(out.getbbox())


def t2_caption(text, size=60, max_w=780):
    f = sans_font(text, max_w, size, "Bold")
    m = text_mask(text, f, stroke=0, pad=34)
    txt = Image.new("RGBA", m.size, WHITE + (0,))
    txt.putalpha(m)
    tw, th = txt.width - 20, 96
    plate = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    ImageDraw.Draw(plate).rounded_rectangle((0, 0, tw - 1, th - 1), radius=18,
                                            fill=PLATE_DARK + (204,))
    out = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    out.alpha_composite(plate)
    out.alpha_composite(txt, (10, (th - txt.height) // 2))
    return out


def t5_plate(text, size=64, max_w=760, plate=FLAT_PINK):
    f = sans_font(text, max_w, size, "Bold")
    m = text_mask(text, f, stroke=0, pad=28)
    txt = Image.new("RGBA", m.size, BLACK + (0,))
    txt.putalpha(m)
    out = Image.new("RGBA", m.size, plate + (255,))
    out.alpha_composite(txt)
    return out


# ---------------------------------------------------------------- decor
def flat_star(size, color=PINK_LIGHT, rot=0):
    s = size * 2
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = s / 2
    pts = []
    for i in range(10):
        ang = i * math.pi / 5 - math.pi / 2
        r = size if i % 2 == 0 else size * 0.4
        pts.append((c + r * math.cos(ang), c + r * math.sin(ang)))
    d.polygon(pts, fill=color + (255,))
    img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
    return img.crop(img.getbbox())


def polaroid(img, border=10, radius=22, shadow_color=(80, 40, 60)):
    w, h = img.width + border * 2, img.height + border * 2
    card = Image.new("RGBA", (w + 14, h + 14), (0, 0, 0, 0))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
    sh = Image.new("RGBA", (w, h), shadow_color + (0,))
    sh.putalpha(mask.filter(ImageFilter.GaussianBlur(6)).point(lambda v: int(v * 0.5)))
    card.alpha_composite(sh, (7, 10))
    white = Image.new("RGBA", (w, h), WHITE + (255,))
    white.putalpha(mask)
    card.alpha_composite(white, (0, 0))
    cmask = Image.new("L", (img.width, img.height), 0)
    ImageDraw.Draw(cmask).rounded_rectangle((0, 0, img.width - 1, img.height - 1),
                                            radius=max(2, radius - border), fill=255)
    tile = img.convert("RGBA")
    tile.putalpha(cmask)
    card.alpha_composite(tile, (border, border))
    return card


def profile_mockup(w=560, h=190):
    card = Image.new("RGBA", (w + 30, h + 30), (0, 0, 0, 0))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=32, fill=255)
    sh = Image.new("RGBA", (w, h), (40, 20, 30, 0))
    sh.putalpha(mask.filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * 0.5)))
    card.alpha_composite(sh, (15, 18))
    body = Image.new("RGBA", (w, h), (255, 255, 255, 240))
    body.putalpha(mask)
    card.alpha_composite(body, (15, 15))
    d = ImageDraw.Draw(card)
    # generic avatar: soft gradient circle, no face / no handle
    av = 108
    ax, ay = 45, 15 + (h - av) // 2
    grad = vgradient((av, av), PINK_LIGHT, BLUE).convert("RGBA")
    amask = Image.new("L", (av, av), 0)
    ImageDraw.Draw(amask).ellipse((0, 0, av - 1, av - 1), fill=255)
    grad.putalpha(amask)
    card.alpha_composite(grad, (ax, ay))
    d.ellipse((ax, ay, ax + av, ay + av), outline=WHITE + (255,), width=5)
    tx = ax + av + 28
    f_name = sans_font("мой профиль", 260, 34, "Bold")
    d.text((tx, ay + 6), "мой профиль", font=f_name, fill=BLACK + (255,))
    f_stat = sans_font("• • •", 200, 30, "Medium")
    d.text((tx, ay + 52), "•  •  •", font=f_stat, fill=(150, 130, 140, 255))
    return card


# ---------------------------------------------------------------- twist grade
def twist_grade(img, grain):
    a = np.asarray(img.convert("L"), np.float32)
    a = 255 * (a / 255) ** 1.05
    a = a + grain
    rgb = np.stack([a, a, a], axis=-1)
    d = np.abs(rgb - 128)
    rgb = np.clip(128 + (rgb - 128) * (1 - 0.08 * (d / 128)), 0, 255)
    return Image.fromarray(rgb.astype(np.uint8), "RGB").convert("RGBA")


_rng = np.random.default_rng(11)
GRAIN = _rng.normal(0, 14, (H, W)).astype(np.float32)


# ---------------------------------------------------------------- elements (hard in/out)
class Static:
    """A decor/text layer that appears and disappears on a hard cut (no fade/scale)."""
    def __init__(self, img, t0, t1, cx, cy, rot=0):
        self.img, self.t0, self.t1, self.cx, self.cy, self.rot = img, t0, t1, cx, cy, rot
        self._r = None

    def draw(self, frame, t):
        if not (self.t0 <= t <= self.t1):
            return
        im = self.img
        if self.rot:
            if self._r is None:
                self._r = im.rotate(self.rot, resample=Image.BICUBIC, expand=True)
            im = self._r
        _paste_clip(frame, im, int(self.cx - im.width / 2), int(self.cy - im.height / 2))


def build_elements():
    E = []

    def add(img, t0, t1, cx, cy, rot=0):
        E.append(Static(img, t0, t1, cx, cy, rot))

    # --- A: hook ---------------------------------------------------------
    add(flat_star(150, PINK_LIGHT, rot=-10), 0.00, 1.55, 560, 560)
    add(t1_top("все ищут"), 0.00, 1.55, 540, 340)
    add(t1_bottom("стикеры в рилсах?"), 0.00, 1.55, 540, 500)
    add(t3_caption("откуда же эти..."), 1.55, 3.30, 540, 360)
    add(t5_plate("я собрала", plate=FLAT_PINK), 3.36, 4.50, 540, 340)

    # --- B: phone insert ---------------------------------------------------
    add(t2_caption("все свои стикеры"), 5.00, 6.30, 540, 300)
    add(t1_top("у меня их"), 6.55, 8.50, 540, 300)
    add(t1_bottom("1000+", twist=True), 6.55, 8.50, 540, 470)

    # --- C: sorted, no background -------------------------------------------
    add(t3_caption("разделила по цветам"), 8.50, 9.00, 540, 1500)
    add(t4_caption("убрала фон"), 9.00, 10.15, 540, 1500)

    # --- D: CTA --------------------------------------------------------------
    add(t3_caption("всего лишь зайди в"), 10.50, 11.55, 540, 330)
    add(t5_plate("комменты", plate=FLAT_MINT), 11.55, 12.55, 540, 340)
    add(flat_star(130, PINK_LIGHT, rot=8), 12.55, 15.07, 700, 590)
    add(t1_top("напиши"), 12.55, 15.07, 540, 420)
    add(t1_bottom("«стикер»", twist=False), 12.55, 15.07, 540, 590)
    add(t3_caption("и я всё отправлю"), 13.30, 15.07, 540, 750)
    return E


# ---------------------------------------------------------------- product card
NOBG_STICKER = emoji_sticker("🧸", 190)


def sticker_card(sticker, pad=28, radius=28, shadow_color=(80, 40, 60)):
    """White rounded backing behind a transparent die-cut sticker (keeps the
    sticker's own alpha instead of the rectangular polaroid mask)."""
    w, h = sticker.width + pad * 2, sticker.height + pad * 2
    card = Image.new("RGBA", (w + 14, h + 14), (0, 0, 0, 0))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
    sh = Image.new("RGBA", (w, h), shadow_color + (0,))
    sh.putalpha(mask.filter(ImageFilter.GaussianBlur(6)).point(lambda v: int(v * 0.5)))
    card.alpha_composite(sh, (7, 10))
    white = Image.new("RGBA", (w, h), WHITE + (255,))
    white.putalpha(mask)
    card.alpha_composite(white, (0, 0))
    card.alpha_composite(sticker, (pad, pad))
    return card


def draw_product_card(frame, t):
    """Rounded white card showing the die-cut sticker -- nearest catalog stand-in
    for a plain product reveal (no exact 'no-background' item in the kit)."""
    t0, t1 = 9.00, 10.15
    if not t0 <= t <= t1:
        return
    card = sticker_card(NOBG_STICKER)
    _paste_clip(frame, card, int(760 - card.width / 2), int(1150 - card.height / 2))


# ---------------------------------------------------------------- grid multiview
def build_grid_tiles():
    times = [4.85, 5.35, 5.85, 6.35]
    tiles = []
    for tt in times:
        raw = subprocess.run([FFMPEG, "-v", "error", "-ss", str(tt), "-i", SRC, "-frames:v", "1",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True, check=True).stdout
        img = Image.frombytes("RGB", (SW, SH), raw)
        crop = img.crop((0, 200, SW, 200 + SW))  # square-ish crop of the phone area
        crop = crop.resize((260, 260), Image.LANCZOS)
        tiles.append(polaroid(crop, border=8, radius=16))
    return tiles


GRID_T0, GRID_T1, GRID_COLLAPSE = 4.80, 6.30, 6.60


def draw_grid(frame, t, tiles):
    if not (GRID_T0 <= t <= GRID_COLLAPSE):
        return
    k = 1.0
    if t > GRID_T1:
        k = clamp(1 - (t - GRID_T1) / (GRID_COLLAPSE - GRID_T1))
    positions = [(360, 760), (720, 760), (360, 1080), (720, 1080)]
    dim = Image.new("RGBA", frame.size, (20, 10, 15, int(140 * clamp((t - GRID_T0) / 0.15))))
    frame.alpha_composite(dim)
    for tile, (cx, cy) in zip(tiles, positions):
        s = max(0.05, k)
        im = tile.resize((max(1, int(tile.width * s)), max(1, int(tile.height * s))), Image.BICUBIC)
        _paste_clip(frame, im, int(cx - im.width / 2), int(cy - im.height / 2))


# ---------------------------------------------------------------- CTA mockup
CTA_CARD = profile_mockup()
CTA_TEXT = t4_caption("[не забудь подписаться!]", size=40, max_w=520, fill=BLACK)


def draw_cta_mockup(frame, t):
    t0 = 11.90
    if t < t0:
        return
    cx, cy = 540, 1720
    _paste_clip(frame, CTA_CARD, int(cx - CTA_CARD.width / 2), int(cy - CTA_CARD.height / 2))
    _paste_clip(frame, CTA_TEXT, int(cx - CTA_TEXT.width / 2), int(cy + 70))


# ---------------------------------------------------------------- camera
def zoom_at(t):
    def steps(t, pts):
        z = pts[0][1]
        for (t0, z1), (_, z0) in zip(pts[1:], pts[:-1]):
            k = ease_out((t - t0) / 0.25)
            z = z0 + (z1 - z0) * k if t >= t0 else z
            if t < t0:
                break
        return z

    if t < CUT_B:
        z = steps(t, [(0, 1.0), (0.0, 1.0), (1.55, 1.05), (3.36, 1.12)])
        return z, 200, 690
    if t < CUT_C:
        return 1.0, 360, 640
    if t < CUT_D:
        z = steps(t, [(CUT_C, 1.05), (6.55, 1.10), (8.50, 1.02), (9.00, 1.08)])
        return z, 340, 560
    z = steps(t, [(CUT_D, 1.0), (10.5, 1.04), (12.55, 1.12)])
    return z, 380, 640


def camera(src, t):
    z, ax, ay = zoom_at(t)
    cw, ch = SW / z, SH / z
    x0 = clamp(ax - cw * (ax / SW), 0, SW - cw)
    y0 = clamp(ay - ch * (ay / SH), 0, SH - ch)
    return src.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


# ---------------------------------------------------------------- grade (documentary warm)
def make_vignette():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((x - W / 2) / (W * 0.65)) ** 2 + ((y - H / 2) / (H * 0.62)) ** 2)
    return (np.clip((d - 0.6) / 0.55, 0, 1) ** 1.6)[..., None]


VIG = make_vignette()


def grade(img):
    a = np.asarray(img.convert("RGB"), np.float32)
    a = a * np.array([1.03, 1.0, 0.98]) + np.array([6, 4, 0])
    a = 255 * (a / 255) ** 0.96
    a = a * (1 - VIG * 0.22)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


# ---------------------------------------------------------------- whip-pan
def whip_pan(frame, strength):
    if strength <= 0.01:
        return frame
    a = np.asarray(frame.convert("RGB"), np.float32)
    shift = int(40 * strength)
    if shift:
        a = 0.5 * a + 0.5 * np.roll(a, shift, axis=1)
    out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    return out.filter(ImageFilter.GaussianBlur(2 + 14 * strength))


WHIP_T = CUT_B
WHIP_WIN = 0.12


def whip_strength(t):
    dt = t - WHIP_T
    if -WHIP_WIN <= dt <= WHIP_WIN:
        return 1 - abs(dt) / WHIP_WIN
    return 0.0


# ---------------------------------------------------------------- slide/wipe
WIPE_T = CUT_D
WIPE_WIN = 0.28


# ---------------------------------------------------------------- audio (soft whooshes only)
def synth_whoosh(sr=44100):
    L = int(0.30 * sr)
    tt = np.arange(L) / sr
    rng = np.random.default_rng(4)
    noise = rng.standard_normal(L).astype(np.float32)
    k = np.ones(50) / 50
    noise = np.convolve(noise, k, mode="same")
    env = np.sin(np.pi * tt / tt[-1]) ** 2
    return noise * env * 1.1


def build_audio(path):
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", SRC, "-f", "s16le", "-ac", "2",
                          "-ar", "44100", "-"], capture_output=True, check=True).stdout
    voice = np.frombuffer(raw, np.int16).astype(np.float32).reshape(-1, 2) / 32768
    sr = 44100
    fx = synth_whoosh(sr)
    mix = voice.copy()
    n = len(mix)
    for tc in (CUT_B, CUT_C, CUT_D):
        i = max(0, int(tc * sr) - len(fx) // 2)
        end = min(n, i + len(fx))
        mix[i:end, 0] += fx[: end - i] * 0.35
        mix[i:end, 1] += fx[: end - i] * 0.35
    mix = mix * (0.95 / max(0.95, float(np.abs(mix).max())))
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


# ---------------------------------------------------------------- main
def main(preview_times=None):
    elements = build_elements()
    grid_tiles = build_grid_tiles()

    def compose(src, t):
        frame = camera(src, t)
        in_twist = 6.55 <= t < 8.50
        if in_twist:
            col = int(t * FPS) % 997
            grain = np.roll(GRAIN, col, axis=1)
            frame = twist_grade(frame, grain)
        else:
            frame = grade(frame)
        if not in_twist:
            base.draw_sparkles(frame, t)
        draw_grid(frame, t, grid_tiles)
        for el in elements:
            el.draw(frame, t)
        draw_product_card(frame, t)
        draw_cta_mockup(frame, t)
        ws = whip_strength(t)
        if ws > 0.01:
            frame = whip_pan(frame, ws)
        return frame.convert("RGB")

    if preview_times:
        os.makedirs(os.path.join(ROOT, "output", "preview"), exist_ok=True)
        for t in preview_times:
            raw = subprocess.run([FFMPEG, "-v", "error", "-ss", str(t), "-i", SRC, "-frames:v", "1",
                                  "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                 capture_output=True, check=True).stdout
            src = Image.frombytes("RGB", (SW, SH), raw)
            compose(src, t).save(os.path.join(ROOT, "output", "preview", f"v{t:05.2f}.jpg"),
                                 quality=88)
        return

    audio = os.path.join(ROOT, "output", "_audio_vlog.wav")
    build_audio(audio)
    dec = subprocess.Popen([FFMPEG, "-v", "error", "-i", SRC, "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen([FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", audio,
                            "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                            "-movflags", "+faststart", "-shortest", OUT], stdin=subprocess.PIPE)
    i = 0
    # slide/wipe at CUT_D: freeze the last pre-cut frame on the left half
    # while the new block slides in from the right, per the wipe recipe.
    last_before_wipe = None
    while True:
        raw = dec.stdout.read(SW * SH * 3)
        if len(raw) < SW * SH * 3:
            break
        t = i / FPS
        frame = compose(Image.frombytes("RGB", (SW, SH), raw), t)
        if t < WIPE_T:
            last_before_wipe = frame
        elif WIPE_T <= t < WIPE_T + WIPE_WIN and last_before_wipe is not None:
            k = (t - WIPE_T) / WIPE_WIN
            split = int(W * k)
            a = np.asarray(last_before_wipe, np.uint8)
            b = np.asarray(frame, np.uint8)
            mixed = b.copy()
            mixed[:, :split] = a[:, :split]
            frame = Image.fromarray(mixed, "RGB")
        enc.stdin.write(frame.tobytes())
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
