"""H10 video probe v2 — анти-артефакты на тексте.

Тактика:
  1. last_frame = first_frame (одна и та же картинка) — жёстко фиксирует концовку
  2. duration=3 (минимум 3 сек) — меньше времени для дрейфа
  3. Промпт: явный запрет на трансформацию текста, только ambient motion
"""
import json, base64, sys, time, urllib.request, urllib.error
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ENV = Path("I:/neuro/GENERAL CLAUDE CODE/Zerocoder/dragonslayer/goliath_daily/.env")
OR_KEY = next(l.split("=",1)[1].strip() for l in ENV.read_text(encoding="utf-8").splitlines() if l.startswith("OPENROUTER_API_KEY="))

BANNER = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/banners/H08_2026-05-06/openclaw_brief1.png")
OUT = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/videos/H10_test_2026-05-07")

PROMPT = (
    "Static composition. Camera holds in place with extremely slight breathing motion only. "
    "Soft ambient particles drifting slowly in the empty background areas. "
    "CRITICAL: all text, letters, numbers, and graphic elements remain pixel-perfect identical to the input image. "
    "No text morphing, no letter warping, no character changes, no typography distortion. "
    "Only subtle environmental motion in background empty areas."
)

b64 = base64.b64encode(BANNER.read_bytes()).decode("ascii")
img = {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}

def http(method, url, body=None, raw=False):
    req = urllib.request.Request(url, method=method,
        headers={"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"})
    data = json.dumps(body).encode("utf-8") if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=60) as r:
            c = r.read()
            return r.status, c if raw else json.loads(c.decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")

payload = {
    "model": "kwaivgi/kling-v3.0-pro",
    "prompt": PROMPT,
    "frame_images": [
        {**img, "frame_type": "first_frame"},
    ],
    "duration": 3,
    "aspect_ratio": "1:1",
}

print("submit...")
s, r = http("POST", "https://openrouter.ai/api/v1/videos", payload)
print(f"  {s} {r if not isinstance(r,dict) else {k:r[k] for k in ('id','status') if k in r}}")
if s not in (200, 202) or not isinstance(r, dict):
    sys.exit(1)
job = r["id"]

last = None
for i in range(60):
    s, j = http("GET", f"https://openrouter.ai/api/v1/videos/{job}")
    if isinstance(j, dict):
        st = j.get("status")
        if st != last:
            print(f"  [{i*5:>4}s] {st}")
            last = st
        if st in ("completed","succeeded","success"): break
        if st in ("failed","error","cancelled"):
            print(f"FAIL: {j}")
            sys.exit(1)
    time.sleep(5)

s, content = http("GET", f"https://openrouter.ai/api/v1/videos/{job}/content?index=0", raw=True)
out_mp4 = OUT / f"openclaw_brief1__v2_lockedtext__{job}.mp4"
out_mp4.write_bytes(content)
print(f"\nsaved: {out_mp4}  ({len(content)/1024:.1f} KB)")
print(f"cost: {r.get('usage',{})}")
