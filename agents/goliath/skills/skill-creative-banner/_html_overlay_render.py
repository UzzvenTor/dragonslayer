"""HTML→PNG (transparent) → overlay на bg_v2.mp4 → final_v5.mp4

HTML вёрстка повторяет баннер 1:1 (заголовок + плашка + оранжевая кнопка).
Playwright headless рендерит с прозрачным фоном.
ffmpeg накладывает PNG поверх анимированного фона.
"""
import sys, subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
NAME = sys.argv[1] if len(sys.argv) > 1 else "openclaw_brief1"
OUT = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/videos/H10_test_2026-05-07")

bg_mp4 = OUT / f"{NAME}__bg_v2.mp4"
overlay_html = OUT / f"{NAME}__overlay.html"
overlay_png = OUT / f"{NAME}__overlay.png"
final_v5 = OUT / f"{NAME}__final_v5.mp4"

# Контент. Для других баннеров параметризуем — пока хардкод под openclaw_brief1.
H1 = "OpenClaw — ИИ-агент"
BADGE = "Работает 24/7 пока вы спите"
CTA_LINE1 = "Бесплатный"
CTA_LINE2 = "практикум"

HTML = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@500;700;800&display=swap" rel="stylesheet">
<style>
  html, body {{ margin:0; padding:0; width:1024px; height:1024px; background:transparent;
                font-family:'Manrope','Segoe UI',sans-serif; }}
  body {{ position:relative; }}
  .h1 {{
    position:absolute; left:48px; top:60px;
    color:#fff; font-weight:800; font-size:54px; line-height:1; letter-spacing:-1.5px;
    white-space:nowrap;
    text-shadow:0 2px 18px rgba(0,0,0,0.45);
  }}
  .badge {{
    position:absolute; left:48px; top:140px;
    background:rgba(232,232,232,0.92); color:#1a1a1a;
    padding:12px 20px; border-radius:12px;
    font-weight:600; font-size:26px; letter-spacing:-0.3px;
    backdrop-filter:blur(4px);
  }}
  .cta {{
    position:absolute; right:48px; bottom:56px;
    background:#FF6A1A; color:#fff;
    padding:22px 30px; border-radius:24px;
    font-weight:800; font-size:30px; line-height:1.05; letter-spacing:-0.5px;
    box-shadow:0 10px 32px rgba(0,0,0,0.35);
    text-align:center;
  }}
</style></head>
<body>
  <div class="h1">{H1}</div>
  <div class="badge">{BADGE}</div>
  <div class="cta">{CTA_LINE1}<br>{CTA_LINE2}</div>
</body></html>
"""
overlay_html.write_text(HTML, encoding="utf-8")
print(f"saved: {overlay_html.name}")

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width":1024,"height":1024}, device_scale_factor=1)
    page = ctx.new_page()
    page.goto(f"file:///{overlay_html.as_posix()}")
    # дождёмся подгрузки шрифта Manrope
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(500)
    page.screenshot(path=str(overlay_png), omit_background=True, full_page=False,
                    clip={"x":0,"y":0,"width":1024,"height":1024})
    browser.close()
print(f"saved: {overlay_png.name}")

cmd = [
    "ffmpeg", "-y",
    "-i", str(bg_mp4),
    "-i", str(overlay_png),
    "-filter_complex",
    "[0:v]scale=1024:1024,unsharp=5:5:0.8:5:5:0.0[bg];"
    "[bg][1:v]overlay=0:0[out]",
    "-map", "[out]",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
    str(final_v5),
]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(f"ffmpeg FAIL:\n{r.stderr[-1500:]}"); sys.exit(1)
print(f"saved: {final_v5}  ({final_v5.stat().st_size/1024:.1f} KB)")
