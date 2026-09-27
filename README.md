# Cut — монтаж ролика про стикерпак

Два готовых монтажа из одного и того же исходника (`assets/source.mp4`):

- `render.py` → `output/montage.mp4` — girly-стиль с бабблами и эмодзи-стикерами.
- `render_vlog.py` → `output/vlog_kit.mp4` — монтаж по шаблону 7
  ("универсальный эстетичный влог-кит"): стили текста T1–T5, whip-pan /
  grid-мультивью / slide-wipe переходы, ч/б твист-момент на реплике
  "1000+", CTA-плашка профиля без ника в конце.

Оба — 1080×1920, 30 fps.

Пересобрать: `python3 render.py` или `python3 render_vlog.py` (нужны
`ffmpeg`, `pillow`, `numpy`, шрифт Noto Color Emoji).
Превью отдельных кадров: `python3 render_vlog.py preview 1.2 8.3 12.9`.

Шрифты (OFL, Google Fonts): Rubik Bubbles, Marck Script, Unbounded, Cormorant Garamond.
