"""H10 video layered pipeline — анимация без артефактов на тексте.

Шаги:
  1. Inpaint: gpt-5.4-image-2 убирает текст и графические элементы → clean.png
  2. Animate: Kling v3.0 Pro анимирует clean.png → bg.mp4 (5 сек 1:1)
  3. Composite: PIL делает text_alpha.png (разность с alpha по яркости),
     ffmpeg накладывает его поверх bg.mp4 → final.mp4

Запуск: python _kling_video_layered.py [имя_баннера_без_расширения]
По умолчанию: openclaw_brief1
"""
import json, base64, sys, time, subprocess, urllib.request, urllib.error
from pathlib import Path
from PIL import Image, ImageChops
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ENV = Path("I:/neuro/GENERAL CLAUDE CODE/Zerocoder/dragonslayer/goliath_daily/.env")
OR_KEY = next(l.split("=",1)[1].strip() for l in ENV.read_text(encoding="utf-8").splitlines() if l.startswith("OPENROUTER_API_KEY="))

NAME = sys.argv[1] if len(sys.argv) > 1 else "openclaw_brief1"
SRC = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/banners/H08_2026-05-06") / f"{NAME}.png"
OUT = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/videos/H10_test_2026-05-07")
OUT.mkdir(parents=True, exist_ok=True)
clean_png = OUT / f"{NAME}__clean.png"
text_alpha_png = OUT / f"{NAME}__text_alpha.png"
bg_mp4 = OUT / f"{NAME}__bg.mp4"
final_mp4 = OUT / f"{NAME}__final.mp4"

def http(method, url, body=None, raw=False, timeout=300, extra_headers=None):
    headers = {"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"}
    if extra_headers: headers.update(extra_headers)
    req = urllib.request.Request(url, method=method, headers=headers)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
            c = r.read()
            return r.status, c if raw else json.loads(c.decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")

# ============ STEP 1: Inpaint (remove text) ============
cost1 = 0.0
if clean_png.exists():
    print(f"[1/3] Inpaint: SKIP — {clean_png.name} уже есть")
else:
    print(f"[1/3] Inpaint: {SRC.name} → clean.png")
    b64_src = base64.b64encode(SRC.read_bytes()).decode("ascii")
    src_data_uri = f"data:image/png;base64,{b64_src}"

    inpaint_prompt = (
        "Take this advertising banner image. Remove all text, letters, numbers, logos, "
        "and graphic icon elements completely. Keep the background, illustration, photo, "
        "lighting, color palette, mood, and overall composition pixel-identical to the input. "
        "Output a clean version with NO text and NO graphic UI elements — only the underlying "
        "scene and decorative background. Same exact dimensions, same style."
    )

    s, r = http("POST", "https://openrouter.ai/api/v1/chat/completions", body={
        "model": "openai/gpt-5.4-image-2",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": inpaint_prompt},
            {"type": "image_url", "image_url": {"url": src_data_uri}},
        ]}],
        "modalities": ["image", "text"],
        "max_tokens": 16000,
    }, extra_headers={"HTTP-Referer": "https://kurzemnek.ru", "X-Title": "Goliath H10 layered"})

    if s != 200 or not isinstance(r, dict):
        print(f"  inpaint FAIL {s}: {r}"); sys.exit(1)

    clean_bytes = None
    for choice in r.get("choices", []):
        for img in (choice.get("message") or {}).get("images") or []:
            url = (img.get("image_url") or {}).get("url") or img.get("url")
            if url and url.startswith("data:image"):
                clean_bytes = base64.b64decode(url.split(",", 1)[1])
            elif url and url.startswith("http"):
                with urllib.request.urlopen(url, timeout=60) as ir:
                    clean_bytes = ir.read()
            if clean_bytes: break
        if clean_bytes: break

    if not clean_bytes:
        print(f"  inpaint: no image in response: {r}"); sys.exit(1)
    clean_png.write_bytes(clean_bytes)
    cost1 = (r.get("usage") or {}).get("cost", 0)
    print(f"  ok: {clean_png.name} (${cost1:.3f})")

# Resize clean to match source dims (image-2 может вернуть другой размер)
src_img = Image.open(SRC).convert("RGBA")
clean_img = Image.open(clean_png).convert("RGBA")
if clean_img.size != src_img.size:
    print(f"  resize clean {clean_img.size} → {src_img.size}")
    clean_img = clean_img.resize(src_img.size, Image.LANCZOS)
    clean_img.save(clean_png)

# ============ STEP 2: Animate clean ============
cost2 = 0.0
if bg_mp4.exists():
    print(f"\n[2/3] Animate: SKIP — {bg_mp4.name} уже есть")
else:
    print(f"\n[2/3] Animate clean → bg.mp4 (Kling v3.0 Pro, 5sec)")
    b64_clean = base64.b64encode(clean_png.read_bytes()).decode("ascii")

    anim_prompt = (
        "Cinematic ambient motion. Slow gentle camera push-in. "
        "Soft floating particles drifting through the scene. "
        "Subtle parallax depth movement on background elements. "
        "Brand-clean professional aesthetic. No abrupt cuts, smooth flowing motion."
    )
    s, r = http("POST", "https://openrouter.ai/api/v1/videos", body={
        "model": "kwaivgi/kling-v3.0-pro",
        "prompt": anim_prompt,
        "frame_images": [{"type":"image_url","image_url":{"url":f"data:image/png;base64,{b64_clean}"},"frame_type":"first_frame"}],
        "duration": 5,
        "aspect_ratio": "1:1",
    })
    if s not in (200, 202) or not isinstance(r, dict):
        print(f"  animate submit FAIL {s}: {r}"); sys.exit(1)
    job = r["id"]; print(f"  job {job}, polling...")
    last = None
    for i in range(120):
        time.sleep(5)
        s2, j = http("GET", f"https://openrouter.ai/api/v1/videos/{job}")
        if isinstance(j, dict):
            st = j.get("status")
            if st != last: print(f"    [{i*5+5:>4}s] {st}"); last = st
            if st in ("completed","succeeded","success"):
                cost2 = (j.get("usage") or {}).get("cost", 0)
                break
            if st in ("failed","error","cancelled"):
                print(f"  animate FAIL: {j}"); sys.exit(1)
    else:
        print("  TIMEOUT"); sys.exit(1)

    s2, content = http("GET", f"https://openrouter.ai/api/v1/videos/{job}/content?index=0", raw=True)
    bg_mp4.write_bytes(content)
    print(f"  ok: {bg_mp4.name} ({len(content)/1024:.1f} KB, ${cost2:.3f})")

# ============ STEP 3: Build text alpha + composite ============
print(f"\n[3/3] Build text_alpha.png + ffmpeg composite")

orig = np.array(src_img.convert("RGB")).astype(np.int32)
clean_arr = np.array(clean_img.convert("RGB")).astype(np.int32)
diff = np.abs(orig - clean_arr).max(axis=-1)  # max channel diff per pixel, 0..255
# Soft threshold: 0 при разнице <15, 255 при разнице >50, плавно между
alpha = np.clip((diff - 15) * 8, 0, 255).astype(np.uint8)

text_alpha_arr = np.array(src_img)  # RGBA
text_alpha_arr[..., 3] = alpha
Image.fromarray(text_alpha_arr).save(text_alpha_png)
print(f"  ok: {text_alpha_png.name} (alpha by diff)")

# ffmpeg overlay
cmd = [
    "ffmpeg", "-y",
    "-i", str(bg_mp4),
    "-i", str(text_alpha_png),
    "-filter_complex", "[0:v]scale=1024:1024[bg];[bg][1:v]overlay=0:0[out]",
    "-map", "[out]",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
    str(final_mp4),
]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(f"  ffmpeg FAIL:\n{r.stderr[-1500:]}"); sys.exit(1)
print(f"  ok: {final_mp4.name} ({final_mp4.stat().st_size/1024:.1f} KB)")

print(f"\n{'='*60}")
print(f"DONE. Final: {final_mp4}")
print(f"Total cost: inpaint ${cost1:.3f} + animate ${cost2:.3f} = ${cost1+cost2:.2f}")
print(f"Layers: {clean_png.name}, {text_alpha_png.name}, {bg_mp4.name}")
