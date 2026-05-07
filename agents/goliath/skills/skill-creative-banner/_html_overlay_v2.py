"""HTML overlay v2 для n8n_brief3 — apgrade типографики и контраста.

Изменения от v1:
  - Light glass card (rgba 0.88 white + blur 14px) под заголовок → читаемо всегда
  - Акцент: «маркетологи» оранжевым (#FF6E33), matches CTA
  - Доп тег: «90 минут · бесплатно · без кода» под subtitle
  - Тюн: tighter letter-spacing, weight 800 для h1, weight 500 для tag
  - CTA бейджик top-right остаётся

Не пере-анимируем bg.mp4 — только re-render PNG + re-composite. Стоимость $0.
"""
import sys, subprocess, json
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
NAME = "n8n_brief3"
OUT = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/videos/H10_test_2026-05-07")
bg = OUT / f"{NAME}__bg.mp4"
overlay_html = OUT / f"{NAME}__overlay_v2.html"
overlay_png = OUT / f"{NAME}__overlay_v2.png"
final = OUT / f"{NAME}__final_v2.mp4"

ORANGE = "#FF6E33"  # n8n accent
HTML = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&display=swap" rel="stylesheet">
<style>
  html, body {{ margin:0; padding:0; width:1024px; height:1024px; background:transparent;
                font-family:'Manrope','Segoe UI',sans-serif; -webkit-font-smoothing:antialiased; }}
  body {{ position:relative; }}

  .card {{
    position:absolute; left:36px; top:36px;
    max-width:640px;
    background:rgba(255,255,255,0.86);
    -webkit-backdrop-filter: blur(14px) saturate(140%);
    backdrop-filter: blur(14px) saturate(140%);
    padding:28px 34px 22px;
    border-radius:22px;
    border:1px solid rgba(255,255,255,0.55);
    box-shadow:0 16px 48px rgba(20,30,60,0.16);
  }}
  .h1 {{
    color:#0E0E12; font-weight:800; font-size:60px; line-height:1.02;
    letter-spacing:-1.6px; margin:0;
  }}
  .h1 b {{ color:{ORANGE}; font-weight:800; }}
  .subtitle {{
    color:#2A2A30; font-weight:600; font-size:26px; letter-spacing:-0.3px;
    margin:10px 0 0; line-height:1.18;
  }}
  .tag {{
    color:#5A5A66; font-weight:500; font-size:17px; letter-spacing:0.2px;
    margin:14px 0 0; text-transform:uppercase;
  }}
  .tag span {{ color:{ORANGE}; font-weight:700; margin:0 6px; }}

  .cta {{
    position:absolute; right:32px; top:32px;
    background:{ORANGE}; color:#fff;
    padding:14px 22px; border-radius:14px;
    font-weight:800; font-size:22px; line-height:1.05; letter-spacing:-0.3px;
    box-shadow:0 8px 24px rgba(255,110,51,0.4);
    text-align:center;
  }}
</style></head>
<body>
  <div class="card">
    <div class="h1">Как <b>маркетологи</b><br>автоматизируют контент</div>
    <div class="subtitle">на n8n за один вечер — без кода</div>
    <div class="tag">90 минут <span>·</span> бесплатно <span>·</span> практикум</div>
  </div>
  <div class="cta">Бесплатный<br>практикум</div>
</body></html>
"""
overlay_html.write_text(HTML, encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width":1024,"height":1024}, device_scale_factor=1)
    page = ctx.new_page()
    page.goto(f"file:///{overlay_html.as_posix()}")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(600)
    page.screenshot(path=str(overlay_png), omit_background=True, full_page=False,
                    clip={"x":0,"y":0,"width":1024,"height":1024})
    browser.close()
print(f"saved: {overlay_png.name}")

cmd = [
    "ffmpeg","-y",
    "-i", str(bg),
    "-i", str(overlay_png),
    "-filter_complex",
    "[0:v]scale=1024:1024,unsharp=5:5:0.8:5:5:0.0[v];[v][1:v]overlay=0:0[out]",
    "-map","[out]","-map","0:a?",
    "-c:v","libx264","-pix_fmt","yuv420p","-crf","18","-preset","medium",
    "-c:a","aac","-b:a","128k",
    str(final),
]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(f"ffmpeg FAIL:\n{r.stderr[-1500:]}"); sys.exit(1)
print(f"saved: {final}  ({final.stat().st_size/1024:.1f} KB)")
