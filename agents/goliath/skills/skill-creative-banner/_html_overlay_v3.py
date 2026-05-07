"""HTML overlay v3 для n8n_brief3 — production-grade типографика + сильный копирайт.

Изменения от v2:
  - Решение проблемы дублирования: убран отдельный CTA-бейдж top-right,
    оставлена единая нижняя CTA-полоса (она и тег + кнопка одновременно).
    Top-right остался только маленький временной маркер «90 МИН» как accent.
  - Шрифты: Unbounded (display H1) + Inter (текст). Mix display+grotesk = дороже.
  - Иерархия: kicker (лейбл-каплет) → H1 (display, чёрный, оранжевый акцент) →
    subtitle (Inter 500) → нижняя CTA-плашка с цифрой и кнопкой.
  - Композиция учитывает кадр видео: верх = свободная стена,
    низ = тёмная зона (стол) → плашка должна быть solid и иметь tint.
    Правый-центр = лицо мужчины — НЕ накрываем.
  - Glass через ffmpeg pre-blur зон под верхней карточкой и нижней полосой.

КОПИ-ВАРИАНТЫ (рассмотрено 3):
  A) «Контент-завод на n8n. Соцсети, рассылки, отчёты — пока вы спите...»
     - сильный образ, но «пока вы спите» = нейрослоп-окраска.
  B) «Свой ИИ-агент за вечер. Без кода.» + «Маркетологи 45+ собирают на n8n
     то, за что раньше платили разработчикам по 200К»
     - бьёт по 3 триггерам сразу (свой ИИ-агент / без кода / 200К) + ЦА явно.
     - тропа захвата: «собирают» (мультипликатор), не «учатся выживать».
  C) «Вторая профессия после 45. Соберите ИИ-агентов на n8n без кода»
     - сильно, но «вторая профессия» = слишком про переучивание (спасение).
     - наша рамка — «уже руководитель, наращивает», не «начинает заново».
  → ВЫБРАН B. Цифра 200К + конкретика «разработчикам» = anchor цены.
"""
import sys, subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
NAME = "n8n_brief3"
OUT = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/videos/H10_test_2026-05-07")
bg = OUT / f"{NAME}__bg.mp4"
overlay_html = OUT / f"{NAME}__overlay_v3.html"
overlay_png = OUT / f"{NAME}__overlay_v3.png"
final = OUT / f"{NAME}__final_v3.mp4"

ORANGE = "#FF6E33"
ORANGE_DARK = "#E5572220"
INK = "#0B0B10"
INK_SUB = "#2B2B33"
INK_MUT = "#6B6B75"

# Композиция:
#  Верх (y=24..360): card на «стене» (светлая зона видео)
#    - kicker «n8n × ИИ» оранжевый
#    - H1 в 3 строки, акцент «Без кода»
#    - subtitle Inter 500
#  Низ (y=820..1000): тёмная плашка с CTA + цифра + tag
#    Лицо мужчины (560..820, 280..540) свободно

HTML = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Unbounded:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing:border-box; }}
  html, body {{ margin:0; padding:0; width:1024px; height:1024px; background:transparent;
                font-family:'Inter','Segoe UI',sans-serif;
                -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility; }}
  body {{ position:relative; }}

  /* ВЕРХНЯЯ КАРТОЧКА — заголовок */
  .card {{
    position:absolute; left:32px; top:28px;
    width:600px;
    background:rgba(255,255,255,0.94);
    padding:22px 30px 24px;
    border-radius:24px;
    border:1px solid rgba(20,20,30,0.06);
    box-shadow:
      0 1px 0 rgba(255,255,255,0.9) inset,
      0 24px 56px rgba(15,20,40,0.18),
      0 4px 12px rgba(15,20,40,0.08);
  }}

  .kicker {{
    display:inline-flex; align-items:center; gap:8px;
    font-family:'Inter',sans-serif;
    font-weight:700; font-size:13px; letter-spacing:1.6px;
    color:{ORANGE}; text-transform:uppercase;
    margin:0 0 14px;
  }}
  .kicker .dot {{
    width:7px; height:7px; border-radius:50%;
    background:{ORANGE};
    box-shadow:0 0 0 4px rgba(255,110,51,0.18);
  }}
  .kicker .sep {{ color:rgba(11,11,16,0.25); font-weight:500; }}
  .kicker .tag {{ color:#0B0B10; letter-spacing:1.4px; }}

  .h1 {{
    font-family:'Unbounded',sans-serif;
    font-weight:800;
    font-size:64px;
    line-height:0.98;
    letter-spacing:-2.2px;
    color:{INK};
    margin:0;
  }}
  .h1 .row {{ display:block; }}
  .h1 .accent {{
    color:{ORANGE};
    /* мягкая «подпись» под акцентом */
    background:linear-gradient(180deg, transparent 78%, rgba(255,110,51,0.18) 78%);
    padding:0 4px; margin:0 -4px;
    border-radius:4px;
  }}

  .subtitle {{
    font-family:'Inter',sans-serif;
    font-weight:500; font-size:22px;
    line-height:1.32; letter-spacing:-0.2px;
    color:{INK_SUB};
    margin:18px 0 0;
    max-width:540px;
  }}
  .subtitle b {{
    font-weight:700; color:{INK};
    /* числовой anchor */
    white-space:nowrap;
  }}

  /* ПРАВЫЙ ВЕРХ — маленький time-pill (не дублирует CTA, а дополняет) */
  .pill {{
    position:absolute; right:30px; top:38px;
    display:inline-flex; align-items:center; gap:9px;
    background:rgba(11,11,16,0.86);
    color:#fff;
    font-family:'Inter',sans-serif; font-weight:600;
    font-size:14px; letter-spacing:1.4px; text-transform:uppercase;
    padding:11px 16px;
    border-radius:999px;
    border:1px solid rgba(255,255,255,0.08);
    box-shadow:0 8px 24px rgba(0,0,0,0.28);
  }}
  .pill .live {{
    width:8px; height:8px; border-radius:50%;
    background:{ORANGE};
    box-shadow:0 0 0 3px rgba(255,110,51,0.25);
  }}

  /* НИЖНЯЯ ПЛАШКА — единый CTA + tag */
  .footer {{
    position:absolute; left:32px; right:32px; bottom:30px;
    display:grid;
    grid-template-columns: 1fr auto;
    gap:16px;
    align-items:center;
    background:rgba(11,11,16,0.92);
    padding:18px 18px 18px 26px;
    border-radius:22px;
    border:1px solid rgba(255,255,255,0.06);
    box-shadow:0 16px 48px rgba(0,0,0,0.40);
  }}
  .foot-text {{
    color:#fff;
    font-family:'Inter',sans-serif;
  }}
  .foot-text .label {{
    display:block;
    font-size:12px; font-weight:600; letter-spacing:1.8px;
    color:rgba(255,255,255,0.55);
    text-transform:uppercase;
    margin-bottom:4px;
  }}
  .foot-text .title {{
    display:block;
    font-size:22px; font-weight:600; letter-spacing:-0.2px;
    line-height:1.18;
  }}
  .foot-text .title b {{ color:{ORANGE}; font-weight:700; }}

  .cta-btn {{
    display:inline-flex; align-items:center; gap:10px;
    background:{ORANGE}; color:#fff;
    font-family:'Inter',sans-serif;
    font-weight:700; font-size:18px; letter-spacing:-0.1px;
    padding:16px 22px;
    border-radius:14px;
    box-shadow:
      0 1px 0 rgba(255,255,255,0.25) inset,
      0 8px 22px rgba(255,110,51,0.45);
  }}
  .cta-btn .arrow {{
    width:22px; height:22px;
    display:inline-flex; align-items:center; justify-content:center;
    background:rgba(255,255,255,0.18);
    border-radius:50%;
    font-size:14px; line-height:1;
    transform:translateX(0);
  }}
</style></head>
<body>

  <!-- top-right: live time-pill (НЕ CTA, чтобы не дублировать с нижней) -->
  <div class="pill"><span class="live"></span>90 минут · онлайн</div>

  <div class="card">
    <div class="kicker">
      <span class="dot"></span>
      <span class="tag">n8n × ИИ</span>
      <span class="sep">/</span>
      <span class="tag" style="color:{INK_SUB};">для маркетологов 45+</span>
    </div>

    <h1 class="h1">
      <span class="row">Свой <span class="accent">ИИ-агент</span></span>
      <span class="row">за вечер.</span>
      <span class="row" style="color:{ORANGE};">Без кода.</span>
    </h1>

    <p class="subtitle">
      Соберите на n8n то, за что раньше платили разработчикам
      <b>по 200&nbsp;000 ₽</b> — на бесплатном практикуме.
    </p>
  </div>

  <div class="footer">
    <div class="foot-text">
      <span class="label">Бесплатный практикум · вторник, 19:00 МСК</span>
      <span class="title">Контент-завод на n8n: <b>соцсети, рассылки, отчёты</b> на автомате</span>
    </div>
    <div class="cta-btn">
      Занять место
      <span class="arrow">→</span>
    </div>
  </div>

</body></html>
"""
overlay_html.write_text(HTML, encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width":1024,"height":1024}, device_scale_factor=1)
    page = ctx.new_page()
    page.goto(f"file:///{overlay_html.as_posix()}")
    # ждём шрифты
    page.evaluate("async () => { await document.fonts.ready; }")
    page.wait_for_timeout(800)
    page.screenshot(path=str(overlay_png), omit_background=True, full_page=False,
                    clip={"x":0,"y":0,"width":1024,"height":1024})
    browser.close()
print(f"saved: {overlay_png.name}  ({overlay_png.stat().st_size/1024:.1f} KB)")

# Composite — без pre-blur (карточки уже solid 0.92-0.94),
# но добавим лёгкий unsharp на bg для микроконтраста.
cmd = [
    "ffmpeg","-y",
    "-i", str(bg),
    "-i", str(overlay_png),
    "-filter_complex",
    "[0:v]scale=1024:1024,unsharp=5:5:0.6:5:5:0.0[v];[v][1:v]overlay=0:0[out]",
    "-map","[out]","-map","0:a?",
    "-c:v","libx264","-pix_fmt","yuv420p","-crf","18","-preset","medium",
    "-c:a","aac","-b:a","128k",
    str(final),
]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(f"ffmpeg FAIL:\n{r.stderr[-1500:]}"); sys.exit(1)
print(f"saved: {final.name}  ({final.stat().st_size/1024:.1f} KB)")
