"""Демо-overlay на экран монитора в анимированном видео — заполняем пустой экран
после inpaint статичным UI-плейсхолдером (имитация чата OpenClaw).

Берёт final.mp4 → накладывает PNG с UI на координаты экрана → final_v2.mp4
"""
import sys, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")

NAME = sys.argv[1] if len(sys.argv) > 1 else "openclaw_brief1"
OUT = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/videos/H10_test_2026-05-07")
final_in = OUT / f"{NAME}__final.mp4"
screen_png = OUT / f"{NAME}__screen.png"
final_out = OUT / f"{NAME}__final_v2.mp4"

# Координаты экрана монитора на 1024x1024 баннере (подобраны по композиции)
SCREEN_X, SCREEN_Y = 240, 320
SCREEN_W, SCREEN_H = 360, 270

W, H = 1024, 1024
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

def font(size):
    for path in ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"):
        try: return ImageFont.truetype(path, size)
        except: pass
    return ImageFont.load_default()

# Header bar (тёмная полоса сверху экрана)
header_h = 32
draw.rectangle(
    [SCREEN_X, SCREEN_Y, SCREEN_X+SCREEN_W, SCREEN_Y+header_h],
    fill=(35, 38, 50, 230)
)
# 3 dots слева
for i, c in enumerate([(255,95,86), (255,189,46), (39,201,63)]):
    cx = SCREEN_X + 14 + i*18
    cy = SCREEN_Y + header_h//2
    draw.ellipse([cx-5, cy-5, cx+5, cy+5], fill=(*c, 255))
# Title в шапке
draw.text((SCREEN_X + 90, SCREEN_Y + 8), "OpenClaw  ·  AI Agent", fill=(220,220,230,255), font=font(15))

# Body — два чат-блока
body_y0 = SCREEN_Y + header_h + 10
gap = 8
block_w = SCREEN_W - 24
block_h = 80
pad = 12

# Левый/верхний блок (запрос пользователя)
b1 = [SCREEN_X+12, body_y0, SCREEN_X+12+block_w, body_y0+block_h]
draw.rounded_rectangle(b1, radius=10, fill=(45, 50, 65, 220))
draw.text((b1[0]+pad, b1[1]+pad),     "you", fill=(140,160,200,255), font=font(11))
draw.text((b1[0]+pad, b1[1]+pad+18),  "Собери отчёт по продажам", fill=(230,235,245,255), font=font(14))
draw.text((b1[0]+pad, b1[1]+pad+38),  "за апрель и пришли в 9:00", fill=(230,235,245,255), font=font(14))

# Нижний блок (ответ агента)
b2 = [SCREEN_X+12, b1[3]+gap, SCREEN_X+12+block_w, b1[3]+gap+block_h]
draw.rounded_rectangle(b2, radius=10, fill=(40, 70, 90, 220))
draw.text((b2[0]+pad, b2[1]+pad),     "OpenClaw", fill=(120,200,255,255), font=font(11))
draw.text((b2[0]+pad, b2[1]+pad+18),  "Готово. Подключился к CRM,", fill=(230,235,245,255), font=font(14))
draw.text((b2[0]+pad, b2[1]+pad+38),  "собрал отчёт и отправил.",   fill=(230,235,245,255), font=font(14))

img.save(screen_png)
print(f"saved: {screen_png.name}")

# Накладываем на final.mp4
cmd = [
    "ffmpeg", "-y",
    "-i", str(final_in),
    "-i", str(screen_png),
    "-filter_complex", "[0:v][1:v]overlay=0:0[out]",
    "-map", "[out]",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
    str(final_out),
]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(f"ffmpeg FAIL:\n{r.stderr[-1500:]}"); sys.exit(1)
print(f"saved: {final_out}  ({final_out.stat().st_size/1024:.1f} KB)")
