"""Тестовый запрос к OpenRouter gpt-5.4-image-2 — генерация одного баннера.
Цель: проверить формат API, качество русского текста, скорость.

После успеха — переписать как полноценный skill SKILL.md.
"""
import os, json, urllib.request, urllib.error, base64, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ENV = Path("I:/neuro/GENERAL CLAUDE CODE/Zerocoder/dragonslayer/goliath_daily/.env")
for line in ENV.read_text(encoding="utf-8").splitlines():
    if line.startswith("OPENROUTER_API_KEY="):
        OR_KEY = line.split("=", 1)[1].strip()
        break

OUT_DIR = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/banners/H08_test_2026-05-06")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Тестовый промпт — sysai brief #1 (фото-герой)
PROMPT = (
    "Banner ad image, vertical 4:5 aspect ratio, for online business course about AI consulting. "
    "Photo-realistic style. A professional confident man in his early 40s, business casual outfit, "
    "sitting at laptop in modern minimalist office. Subtle smile, looking at camera. "
    "Clean light blue-grey background with soft natural window lighting. Depth of field. "
    "Bold Russian text on top of the image, large white serif font: «Запусти ИИ-агентство». "
    "Smaller white sans-serif subtitle below: «1 млн в месяц на внедрении ИИ». "
    "Subtle green brand accent #1DB573 — small badge in corner saying «Бесплатный практикум». "
    "Professional, premium, no AI-futurism cliches, no neon, no chaos."
)

print(f"OpenRouter image test — gpt-5.4-image-2")
print(f"Out: {OUT_DIR}")
print()

body = {
    "model": "openai/gpt-5.4-image-2",
    "messages": [{"role": "user", "content": PROMPT}],
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

print("Sending request...")
try:
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.loads(r.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:1000]}")
    sys.exit(1)

# Сохранить полный response для дебага
(OUT_DIR / "raw_response.json").write_text(
    json.dumps(resp, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"Saved raw response → {OUT_DIR / 'raw_response.json'}")

# Извлечь image — формат OpenRouter (может быть message.images[].image_url или content с image_url)
saved = []
for ch_idx, choice in enumerate(resp.get("choices", [])):
    msg = choice.get("message", {})
    # Вариант 1: message.images[]
    for i, img in enumerate(msg.get("images") or []):
        url = (img.get("image_url") or {}).get("url") or img.get("url")
        if not url:
            continue
        if url.startswith("data:image"):
            # base64 inline
            _, b64 = url.split(",", 1)
            data = base64.b64decode(b64)
            ext = "png"
        else:
            with urllib.request.urlopen(url, timeout=60) as ir:
                data = ir.read()
            ext = "png"
        out_path = OUT_DIR / f"sysai_v1_test_choice{ch_idx}_img{i}.{ext}"
        out_path.write_bytes(data)
        saved.append(str(out_path))
    # Вариант 2: content как list с image_url типом
    content = msg.get("content")
    if isinstance(content, list):
        for i, part in enumerate(content):
            if part.get("type") == "image_url":
                url = (part.get("image_url") or {}).get("url")
                if url and url.startswith("data:image"):
                    _, b64 = url.split(",", 1)
                    data = base64.b64decode(b64)
                    out_path = OUT_DIR / f"sysai_v1_test_choice{ch_idx}_part{i}.png"
                    out_path.write_bytes(data)
                    saved.append(str(out_path))

print()
print(f"Saved {len(saved)} image(s):")
for p in saved:
    print(f"  → {p}")

print()
usage = resp.get("usage", {})
print(f"Usage: {usage}")
print()
if not saved:
    print("⚠️  No images in response. Check raw_response.json for actual format.")
