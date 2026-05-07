"""H10 video probe — анимация одного баннера H08 через Kling v3.0 Pro в OpenRouter.

Шаг 1: пробуем data:image/png;base64 URI напрямую (без внешнего хостинга).
Если OpenRouter примет — генерируем видео и скачиваем.
Если откажет с понятной ошибкой про URL — переключаемся на catbox/YC.

Запуск:  python _test_kling_video.py
"""
import os, json, base64, sys, time, urllib.request, urllib.error
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ENV = Path("I:/neuro/GENERAL CLAUDE CODE/Zerocoder/dragonslayer/goliath_daily/.env")
OR_KEY = next(l.split("=",1)[1].strip() for l in ENV.read_text(encoding="utf-8").splitlines() if l.startswith("OPENROUTER_API_KEY="))

BANNER = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/banners/H08_2026-05-06/openclaw_brief1.png")
OUT_DIR = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/videos/H10_test_2026-05-07")
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "kwaivgi/kling-v3.0-pro"
PROMPT = (
    "Subtle cinematic camera push-in toward the central subject. "
    "Soft floating particles drifting slowly across the frame. "
    "Gentle parallax and breathing motion on the text and graphic elements. "
    "Brand-clean, professional, no abrupt cuts, no harsh motion."
)

# 1. Кодируем баннер в data URI
b64 = base64.b64encode(BANNER.read_bytes()).decode("ascii")
data_uri = f"data:image/png;base64,{b64}"
print(f"banner: {BANNER.name}, size: {BANNER.stat().st_size/1024:.1f} KB, b64 length: {len(b64)/1024:.1f} KB")

# 2. POST /api/v1/videos
def http(method, url, body=None, raw=False, timeout=60):
    req = urllib.request.Request(url, method=method, headers={
        "Authorization": f"Bearer {OR_KEY}",
        "Content-Type": "application/json",
    })
    data = json.dumps(body).encode("utf-8") if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
            content = r.read()
            return r.status, content if raw else json.loads(content.decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, body

payload = {
    "model": MODEL,
    "prompt": PROMPT,
    "frame_images": [
        {"type": "image_url", "image_url": {"url": data_uri}, "frame_type": "first_frame"}
    ],
    "duration": 5,
    "aspect_ratio": "1:1",
}

print(f"\nPOST /api/v1/videos  model={MODEL}")
status, resp = http("POST", "https://openrouter.ai/api/v1/videos", payload)
print(f"status: {status}")
print(f"resp: {json.dumps(resp, indent=2, ensure_ascii=False)[:1500] if isinstance(resp,(dict,list)) else resp[:1500]}")

if status != 200 or not isinstance(resp, dict):
    print("\n[STOP] data URI не принят. Нужен внешний хостинг (catbox/YC OS).")
    sys.exit(1)

job_id = resp.get("id") or resp.get("job_id") or resp.get("jobId")
if not job_id:
    print(f"\n[?] Не нашёл job id в ответе. Ключи: {list(resp.keys())}")
    sys.exit(1)
print(f"\njob_id: {job_id}")

# 3. Polling
print("\npolling...")
for i in range(60):
    time.sleep(5)
    s, j = http("GET", f"https://openrouter.ai/api/v1/videos/{job_id}")
    state = j.get("status") if isinstance(j, dict) else None
    print(f"  [{i*5+5:>3}s] status={state}")
    if state in ("completed", "succeeded", "success"):
        break
    if state in ("failed", "error", "cancelled"):
        print(f"  fail body: {j}")
        sys.exit(1)
else:
    print("[TIMEOUT] >5min")
    sys.exit(1)

# 4. Download
out_mp4 = OUT_DIR / f"{BANNER.stem}__v1.mp4"
s, content = http("GET", f"https://openrouter.ai/api/v1/videos/{job_id}/content?index=0", raw=True)
out_mp4.write_bytes(content)
print(f"\nsaved: {out_mp4}  ({len(content)/1024:.1f} KB)")
