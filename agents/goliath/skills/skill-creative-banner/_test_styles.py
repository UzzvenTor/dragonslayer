"""Тест 2 разных стилей через gpt-5.4-image-2:
  - law (legal — sober, dark navy + cream, no futurism)
  - openclaw (tech — clean, dark workspace, blue accents)

Цель: убедиться, что стиль реально меняется per продукт, а не уезжает в один и тот же business-look.
"""
import os, json, urllib.request, urllib.error, base64, sys, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ENV = Path("I:/neuro/GENERAL CLAUDE CODE/Zerocoder/dragonslayer/goliath_daily/.env")
for line in ENV.read_text(encoding="utf-8").splitlines():
    if line.startswith("OPENROUTER_API_KEY="):
        OR_KEY = line.split("=", 1)[1].strip()
        break

OUT_DIR = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/banners/H08_test_2026-05-06")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPTS = {
    "law_v1_test": (
        "Banner ad image, vertical 4:5 aspect ratio, for online practical course about AI assistants for lawyers. "
        "Photo-realistic, sober and professional. A serious lawyer in his mid-40s wearing a dark navy suit with a light shirt, "
        "sitting at an organized wooden desk with neat stacks of legal documents and a sleek modern laptop. "
        "Neutral confident expression, NOT smiling. Warm lamp lighting, traditional law-office aesthetic with subtle wood tones. "
        "Color palette: deep navy + cream + warm wood. NO neon, NO AI-futurism, NO chaos. "
        "Bold Russian text in top-left corner, white serif font: «Как юристу создать ИИ-ассистента». "
        "Smaller subtitle below: «Пошаговая инструкция». "
        "Subtle gold-accented badge in top-right: «Бесплатный практикум». "
        "Premium legal-tech aesthetic, not flashy."
    ),
    "openclaw_v1_test": (
        "Banner ad image, vertical 4:5 aspect ratio, for online course about installing autonomous AI agent OpenClaw on PC. "
        "Photo-realistic, clean tech aesthetic. A modern minimalist desktop workspace at evening — sleek monitor displaying "
        "an AI agent chat interface with code and tasks running, mechanical keyboard, soft warm desk lamp creating ambient light, "
        "person silhouette barely visible in chair (back to camera, focused on screen). "
        "Color palette: deep blue + black + warm white accents from lamp. Calm, focused, NOT chaotic. "
        "NO neon, NO cyberpunk, NO sci-fi 'brain with wires' cliches. Just a real tech workspace. "
        "Bold Russian text in top area, white sans-serif font: «OpenClaw — ИИ-агент». "
        "Smaller subtitle below: «Работает 24/7 пока вы спите». "
        "Small green badge in bottom-right: «Бесплатный практикум». "
        "Premium clean tech aesthetic."
    ),
}

def call_image(prompt: str, retry: int = 2):
    body = {
        "model": "openai/gpt-5.4-image-2",
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image", "text"],
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OR_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://kurzemnek.ru",
            "X-Title": "Goliath skill-creative-banner test",
        },
    )
    last_err = None
    for attempt in range(retry):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:300]}"
            time.sleep(3)
    raise RuntimeError(last_err)


def extract_image(resp):
    for choice in resp.get("choices", []):
        msg = choice.get("message", {})
        for img in msg.get("images") or []:
            url = (img.get("image_url") or {}).get("url") or img.get("url")
            if url and url.startswith("data:image"):
                _, b64 = url.split(",", 1)
                return base64.b64decode(b64)
            if url and url.startswith("http"):
                with urllib.request.urlopen(url, timeout=60) as ir:
                    return ir.read()
    return None


total_cost = 0.0
for name, prompt in PROMPTS.items():
    print(f"\n=== {name} ===")
    print(f"Sending request...")
    t0 = time.time()
    resp = call_image(prompt)
    img = extract_image(resp)
    if not img:
        print(f"  ⚠️  no image in response — see raw_response_{name}.json")
        (OUT_DIR / f"raw_response_{name}.json").write_text(
            json.dumps(resp, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        continue
    out_path = OUT_DIR / f"{name}.png"
    out_path.write_bytes(img)
    cost = (resp.get("usage") or {}).get("cost", 0)
    total_cost += cost
    print(f"  ✓ saved → {out_path}")
    print(f"  cost ${cost:.3f}, took {time.time()-t0:.1f}s")

print(f"\nTotal cost: ${total_cost:.3f}")
