"""Финальный composite: анимированный фон (bg.mp4) + оригинальный UI экрана (вырезка)
+ заголовок/кнопка (text_alpha из diff). Без выдуманных надписей.

Координаты экрана подобраны для openclaw_brief1.png (1024×1024).
"""
import sys, subprocess
from pathlib import Path
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")
NAME = sys.argv[1] if len(sys.argv) > 1 else "openclaw_brief1"
SRC = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/banners/H08_2026-05-06") / f"{NAME}.png"
OUT = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/videos/H10_test_2026-05-07")

bg_mp4 = OUT / f"{NAME}__bg.mp4"
text_alpha_png = OUT / f"{NAME}__text_alpha.png"
ui_screen_png = OUT / f"{NAME}__ui_screen.png"
final_v3 = OUT / f"{NAME}__final_v3.mp4"

# Зона экрана монитора на 1024×1024
SX, SY, SW, SH = 240, 315, 365, 250

# 1. Вырезаем UI экрана из оригинала, кладём в RGBA 1024×1024 на ту же позицию
src = Image.open(SRC).convert("RGBA")
ui = Image.new("RGBA", src.size, (0, 0, 0, 0))
crop = src.crop((SX, SY, SX+SW, SY+SH))
ui.paste(crop, (SX, SY))
ui.save(ui_screen_png)
print(f"saved: {ui_screen_png.name}")

# 2. ffmpeg: bg.mp4 → scale → overlay ui_screen → overlay text_alpha → final
cmd = [
    "ffmpeg", "-y",
    "-i", str(bg_mp4),
    "-i", str(ui_screen_png),
    "-i", str(text_alpha_png),
    "-filter_complex",
    "[0:v]scale=1024:1024[bg];"
    "[bg][1:v]overlay=0:0[bg2];"
    "[bg2][2:v]overlay=0:0[out]",
    "-map", "[out]",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
    str(final_v3),
]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(f"ffmpeg FAIL:\n{r.stderr[-1500:]}"); sys.exit(1)
print(f"saved: {final_v3}  ({final_v3.stat().st_size/1024:.1f} KB)")
