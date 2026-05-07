"""H10 пилот — n8n_brief3.
Новые параметры:
  - длительность 10 сек (вместо 5)
  - native audio в Kling Pro (probe: пробуем флаг)
  - HTML под n8n_brief3 (тёмный текст на светлом фоне, бейдж top-right оранжевый)
  - master 1:1 1024×1024 (ресайзы 16:9/9:16 — отдельным шагом потом)
"""
import json, base64, sys, time, subprocess, urllib.request, urllib.error
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
ENV = Path("I:/neuro/GENERAL CLAUDE CODE/Zerocoder/dragonslayer/goliath_daily/.env")
OR_KEY = next(l.split("=",1)[1].strip() for l in ENV.read_text(encoding="utf-8").splitlines() if l.startswith("OPENROUTER_API_KEY="))

NAME = "n8n_brief3"
SRC = Path(f"I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/banners/H08_2026-05-06/{NAME}.png")
OUT = Path(f"I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/videos/H10_test_2026-05-07")
OUT.mkdir(parents=True, exist_ok=True)
clean = OUT / f"{NAME}__clean.png"
bg = OUT / f"{NAME}__bg.mp4"
overlay_html = OUT / f"{NAME}__overlay.html"
overlay_png = OUT / f"{NAME}__overlay.png"
final = OUT / f"{NAME}__final.mp4"

# ---------- HTML config под n8n_brief3 (светлый фон, тёмный текст, бейдж top-right) ----------
H1 = "Как маркетологи"
SUBTITLE = "Автоматизируют контент на n8n"
CTA_LINE1 = "Бесплатный"
CTA_LINE2 = "практикум"
BADGE_COLOR = "#FF6E33"   # n8n
TEXT_COLOR = "#1A1A1A"    # тёмный (фон светлый)

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
    color:{TEXT_COLOR}; font-weight:800; font-size:62px; line-height:1; letter-spacing:-1.5px;
    white-space:nowrap;
  }}
  .subtitle {{
    position:absolute; left:48px; top:148px;
    color:{TEXT_COLOR}; font-weight:600; font-size:30px; letter-spacing:-0.3px;
  }}
  .cta {{
    position:absolute; right:32px; top:32px;
    background:{BADGE_COLOR}; color:#fff;
    padding:14px 22px; border-radius:14px;
    font-weight:800; font-size:22px; line-height:1.05; letter-spacing:-0.3px;
    box-shadow:0 6px 20px rgba(0,0,0,0.18);
    text-align:center;
  }}
</style></head>
<body>
  <div class="h1">{H1}</div>
  <div class="subtitle">{SUBTITLE}</div>
  <div class="cta">{CTA_LINE1}<br>{CTA_LINE2}</div>
</body></html>
"""

# ---------- HTTP helper ----------
def http(method, url, body=None, raw=False, timeout=300, extra=None):
    h = {"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"}
    if extra: h.update(extra)
    req = urllib.request.Request(url, method=method, headers=h)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
            c = r.read()
            return r.status, c if raw else json.loads(c.decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")

# ============ STEP 1: точечный inpaint ============
cost1 = 0.0
if clean.exists():
    print(f"[1/4] Inpaint: SKIP — {clean.name} есть")
else:
    print(f"[1/4] Inpaint: {NAME}")
    b64 = base64.b64encode(SRC.read_bytes()).decode("ascii")
    prompt = (
        "Edit this advertising banner. Remove ONLY two specific elements: "
        "(1) the bold dark headline text at the top-left ('Как маркетологи' on the first line "
        "and 'Автоматизируют контент на n8n' below it); "
        "(2) the small orange rounded rectangle badge at the top-right with white text "
        "('Бесплатный практикум'). "
        "CRITICAL: keep absolutely everything else pixel-identical to the input — including "
        "the man at the desk, the open laptop with the n8n workflow interface visible on screen, "
        "the desk, mug, plant, room lighting, window. The laptop screen with the workflow nodes "
        "MUST remain in place, do not blank it out. Same exact dimensions, same composition."
    )
    s, r = http("POST", "https://openrouter.ai/api/v1/chat/completions", body={
        "model": "openai/gpt-5.4-image-2",
        "messages": [{"role": "user", "content": [
            {"type":"text","text":prompt},
            {"type":"image_url","image_url":{"url":f"data:image/png;base64,{b64}"}},
        ]}],
        "modalities": ["image", "text"],
        "max_tokens": 16000,
    }, extra={"HTTP-Referer":"https://kurzemnek.ru","X-Title":"Goliath H10 pilot"})
    if s != 200 or not isinstance(r, dict):
        print(f"  inpaint FAIL {s}: {r}"); sys.exit(1)
    img_bytes = None
    for ch in r.get("choices", []):
        for img in (ch.get("message") or {}).get("images") or []:
            url = (img.get("image_url") or {}).get("url") or img.get("url")
            if url and url.startswith("data:image"):
                img_bytes = base64.b64decode(url.split(",", 1)[1])
            elif url and url.startswith("http"):
                with urllib.request.urlopen(url, timeout=60) as ir: img_bytes = ir.read()
            if img_bytes: break
        if img_bytes: break
    if not img_bytes: print(f"  no image: {r}"); sys.exit(1)
    clean.write_bytes(img_bytes)
    cost1 = (r.get("usage") or {}).get("cost", 0)
    print(f"  ok: {clean.name} (${cost1:.3f})")

# Resize clean → 1024×1024 если другой
src_img = Image.open(SRC).convert("RGBA")
ci = Image.open(clean).convert("RGBA")
if ci.size != src_img.size:
    print(f"  resize {ci.size} → {src_img.size}")
    ci = ci.resize(src_img.size, Image.LANCZOS); ci.save(clean)

# ============ STEP 2: animate 10sec + audio (probe) ============
cost2 = 0.0
if bg.exists():
    print(f"\n[2/4] Animate: SKIP — {bg.name} есть")
else:
    print(f"\n[2/4] Animate clean → bg.mp4 (Kling v3.0 Pro, 10sec, audio probe)")
    b64c = base64.b64encode(clean.read_bytes()).decode("ascii")
    anim_prompt = (
        "Static camera, locked tripod, no camera movement, no zoom. "
        "Subtle ambient motion only: tiny dust particles drifting slowly in air, "
        "very gentle breathing motion of the man's posture, soft warm daylight flicker. "
        "Keep all geometry, screen, monitor, furniture pixel-stable. "
        "Sharp focus, preserve fine details and textures. "
        "Audio: soft ambient room tone, distant gentle keyboard typing, calm focused atmosphere, no music."
    )
    payload = {
        "model": "kwaivgi/kling-v3.0-pro",
        "prompt": anim_prompt,
        "frame_images": [{"type":"image_url","image_url":{"url":f"data:image/png;base64,{b64c}"},"frame_type":"first_frame"}],
        "duration": 10,
        "aspect_ratio": "1:1",
        "audio": True,  # probe: вдруг сработает
    }
    s, r = http("POST", "https://openrouter.ai/api/v1/videos", body=payload)
    if s == 400:
        print(f"  audio:true отклонён, пробую generate_audio:true ({r[:200]})")
        del payload["audio"]
        payload["generate_audio"] = True
        s, r = http("POST", "https://openrouter.ai/api/v1/videos", body=payload)
    if s == 400:
        print(f"  generate_audio:true тоже отклонён, без явного флага ({r[:200]})")
        del payload["generate_audio"]
        s, r = http("POST", "https://openrouter.ai/api/v1/videos", body=payload)
    if s not in (200, 202) or not isinstance(r, dict):
        print(f"  submit FAIL {s}: {r}"); sys.exit(1)
    job = r["id"]; print(f"  job {job}, polling...")
    last = None
    for i in range(180):
        time.sleep(5)
        s2, j = http("GET", f"https://openrouter.ai/api/v1/videos/{job}")
        if isinstance(j, dict):
            st = j.get("status")
            if st != last: print(f"    [{i*5+5:>4}s] {st}"); last = st
            if st in ("completed","succeeded","success"):
                cost2 = (j.get("usage") or {}).get("cost", 0); break
            if st in ("failed","error","cancelled"):
                print(f"  FAIL: {j}"); sys.exit(1)
    else:
        print("  TIMEOUT"); sys.exit(1)
    s2, content = http("GET", f"https://openrouter.ai/api/v1/videos/{job}/content?index=0", raw=True)
    bg.write_bytes(content)
    print(f"  ok: {bg.name} ({len(content)/1024:.1f} KB, ${cost2:.3f})")

# ============ STEP 3: HTML → PNG ============
print(f"\n[3/4] HTML render → overlay.png")
overlay_html.write_text(HTML, encoding="utf-8")
with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width":1024,"height":1024}, device_scale_factor=1)
    page = ctx.new_page()
    page.goto(f"file:///{overlay_html.as_posix()}")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(500)
    page.screenshot(path=str(overlay_png), omit_background=True, full_page=False,
                    clip={"x":0,"y":0,"width":1024,"height":1024})
    browser.close()
print(f"  ok: {overlay_png.name}")

# ============ STEP 4: composite ============
print(f"\n[4/4] ffmpeg composite → {final.name}")
cmd = [
    "ffmpeg","-y",
    "-i", str(bg),
    "-i", str(overlay_png),
    "-filter_complex",
    "[0:v]scale=1024:1024,unsharp=5:5:0.8:5:5:0.0[v];"
    "[v][1:v]overlay=0:0[out]",
    "-map","[out]",
    "-map","0:a?",  # подхватим audio с bg.mp4 если есть
    "-c:v","libx264","-pix_fmt","yuv420p","-crf","18","-preset","medium",
    "-c:a","aac","-b:a","128k",
    str(final),
]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(f"  ffmpeg FAIL:\n{r.stderr[-1500:]}"); sys.exit(1)
print(f"  ok: {final}  ({final.stat().st_size/1024:.1f} KB)")

# ffprobe — есть ли audio
probe = subprocess.run(["ffprobe","-v","error","-show_streams","-of","json",str(final)],
                       capture_output=True, text=True)
streams = json.loads(probe.stdout).get("streams", [])
has_audio = any(s.get("codec_type")=="audio" for s in streams)
print(f"  audio in final: {'YES' if has_audio else 'NO'}")

print(f"\n{'='*60}\nDONE. Cost: inpaint ${cost1:.3f} + animate ${cost2:.3f} = ${cost1+cost2:.2f}")
