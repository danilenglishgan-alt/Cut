# Cut — монтаж ролика про стикерпак

Готовое видео: `output/montage.mp4` (1080×1920, 30 fps).

Пересобрать: `python3 render.py` (нужны `ffmpeg`, `pillow`, `numpy`, шрифт Noto Color Emoji).
Превью отдельных кадров: `python3 render.py preview 1.2 8.3 12.9`.

Шрифты (OFL, Google Fonts): Rubik Bubbles, Marck Script, Unbounded, Cormorant Garamond.

## Скилл `reels-montage`

`.claude/skills/reels-montage/` — скилл Claude Code для монтажа разговорных reels в стиле maysoulme
(резка пауз, ×1.3, субтитры word-by-word, хук и CTA с рукописным словом, вставки со звуком, музыка).
Срабатывает на «смонтируй ролик». Инструкция: `.claude/skills/reels-montage/USER_GUIDE.md`.
