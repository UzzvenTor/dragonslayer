"""H10 video layered v2 — точечный inpaint + статичная анимация.

Отличия от v1:
  - Inpaint точечно: убираем ТОЛЬКО заголовок и кнопку, сохраняем UI монитора
  - Анимация: static camera, без push-in (фон не сдвигается, меньше размытия)
  - Composite: только text_alpha (UI монитора уже в кадре)

Запуск: python _kling_video_layered_v2.py [имя_баннера]
"""
import json, base64, sys, time, subprocess, urllib.request, urllib.error
from pathlib import Path
from PIL import Image
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ENV = Path("I:/neuro/GENERAL CLAUDE CODE/Zerocoder/dragonslayer/goliath_daily/.env")
OR_KEY = next(l.split("=",1)[1].strip() for l in ENV.read_text(encoding="utf-8").splitlines() if l.startswith("OPENROUTER_API_KEY="))

NAME = sys.argv[1] if len(sys.argv) > 1 else "openclaw_brief1"
SRC = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/banners/H08_2026-05-06") / f"{NAME}.png"
OUT = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/videos/H10_test_2026-05-07")
OUT.mkdir(parents=True, exist_ok=True)
clean2 = OUT / f"{NAME}__clean_v2.png"
text_alpha2 = OUT / f"{NAME}__text_alpha_v2.png"
bg2 = OUT / f"{NAME}__bg_v2.mp4"
final = OUT / f"{NAME}__final_v4.mp4"

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

# ====== STEP 1: точечный inpaint (только заголовок и кнопка) ======
cost1 = 0.0
if clean2.exists():
    print(f"[1/3] Inpaint v2: SKIP — {clean2.name} уже есть")
else:
    print(f"[1/3] Inpaint v2 (точечный): {SRC.name} → clean_v2.png")
    b64 = base64.b64encode(SRC.read_bytes()).decode("ascii")
    prompt = (
        "Edit this advertising banner. Remove ONLY two specific elements: "
        "(1) the white headline text at the top-left ('OpenClaw — ИИ-агент' and the line "
        "below it 'Работает 24/7 пока вы спите'); "
        "(2) the small orange rounded rectangle button at the bottom-right with white text "
        "('Бесплатный практикум'). "
        "CRITICAL: keep absolutely everything else pixel-identical to the input — including "
        "the laptop monitor with its dark blue chat interface and panels, the desk lamp, "
        "the man at the desk, the window with city lights, the mug, keyboard, the plant. "
        "The monitor screen with its UI panels MUST remain in place, do not turn it black, "
        "do not remove the chat panels on the screen. Same exact dimensions, same composition."
    )
    s, r = http("POST", "https://openrouter.ai/api/v1/chat/completions", body={
        "model": "openai/gpt-5.4-image-2",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]}],
        "modalities": ["image", "text"],
        "max_tokens": 16000,
    }, extra={"HTTP-Referer": "https://kurzemnek.ru", "X-Title": "Goliath H10 v2"})
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
    clean2.write_bytes(img_bytes)
    cost1 = (r.get("usage") or {}).get("cost", 0)
    print(f"  ok: {clean2.name} (${cost1:.3f})")

# Resize to source dims
src_img = Image.open(SRC).convert("RGBA")
ci = Image.open(clean2).convert("RGBA")
if ci.size != src_img.size:
    print(f"  resize {ci.size} → {src_img.size}")
    ci = ci.resize(src_img.size, Image.LANCZOS); ci.save(clean2)

# ====== STEP 2: animate (static camera) ======
cost2 = 0.0
if bg2.exists():
    print(f"\n[2/3] Animate v2: SKIP — {bg2.name} уже есть")
else:
    print(f"\n[2/3] Animate v2 (static camera) → bg_v2.mp4")
    b64c = base64.b64encode(clean2.read_bytes()).decode("ascii")
    prompt = (
        "Static camera, locked tripod, absolutely no camera movement, no push-in, no zoom. "
        "Only subtle ambient motion: tiny dust particles drifting slowly in the air, "
        "extremely gentle flicker of the desk lamp warm light, soft breathing of the man's posture. "
        "Keep all geometry, screen, monitor, furniture, and composition pixel-stable. "
        "Sharp focus, preserve fine details and textures, no blur, no smoothing."
    )
    s, r = http("POST", "https://openrouter.ai/api/v1/videos", body={
        "model": "kwaivgi/kling-v3.0-pro",
        "prompt": prompt,
        "frame_images": [{"type":"image_url","image_url":{"url":f"data:image/png;base64,{b64c}"},"frame_type":"first_frame"}],
        "duration": 5, "aspect_ratio": "1:1",
    })
    if s not in (200, 202) or not isinstance(r, dict):
        print(f"  submit FAIL {s}: {r}"); sys.exit(1)
    job = r["id"]; print(f"  job {job}")
    last = None
    for i in range(120):
        time.sleep(5)
        s2, j = http("GET", f"https://openrouter.ai/api/v1/videos/{job}")
        if isinstance(j, dict):
            st = j.get("status")
            if st != last: print(f"    [{i*5+5:>4}s] {st}"); last = st
            if st in ("completed","succeeded","success"):
                cost2 = (j.get("usage") or {}).get("cost", 0); break
            if st in ("failed","error","cancelled"): print(f"  FAIL: {j}"); sys.exit(1)
    else:
        print("  TIMEOUT"); sys.exit(1)
    s2, content = http("GET", f"https://openrouter.ai/api/v1/videos/{job}/content?index=0", raw=True)
    bg2.write_bytes(content)
    print(f"  ok: {bg2.name} ({len(content)/1024:.1f} KB, ${cost2:.3f})")

# ====== STEP 3: text_alpha + composite ======
print(f"\n[3/3] text_alpha + composite → {final.name}")
orig = np.array(src_img.convert("RGB")).astype(np.int32)
clean_arr = np.array(ci.convert("RGB")).astype(np.int32)
diff = np.abs(orig - clean_arr).max(axis=-1)
alpha = np.clip((diff - 15) * 8, 0, 255).astype(np.uint8)
ta = np.array(src_img); ta[..., 3] = alpha
Image.fromarray(ta).save(text_alpha2)
print(f"  ok: {text_alpha2.name}")

# unsharp slightly чтобы компенсировать Kling-смазывание
cmd = [
    "ffmpeg", "-y",
    "-i", str(bg2),
    "-i", str(text_alpha2),
    "-filter_complex",
    "[0:v]scale=1024:1024,unsharp=5:5:0.8:5:5:0.0[bg];"
    "[bg][1:v]overlay=0:0[out]",
    "-map", "[out]",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
    str(final),
]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(f"  ffmpeg FAIL:\n{r.stderr[-1500:]}"); sys.exit(1)
print(f"  ok: {final}  ({final.stat().st_size/1024:.1f} KB)")

print(f"\n{'='*60}\nDONE. Cost: inpaint ${cost1:.3f} + animate ${cost2:.3f} = ${cost1+cost2:.2f}")
