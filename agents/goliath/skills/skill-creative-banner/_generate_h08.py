"""Массовая генерация 17 оставшихся баннеров H08 через OpenRouter gpt-5.4-image-2.

3 баннера уже готовы (тестовые) — переиспользуются:
  - sysai brief#1 (Title #1 «Запусти ИИ-агентство и выйди на 1 млн в месяц»)
  - law brief#1 (Title #1 «Как юристу создать ИИ-ассистента»)
  - openclaw brief#1 (Title #2 «Покажем как OpenClaw работает 24/7…»)

Остальные 17 (по 4 на sysai/openclaw/law + 5 на n8n) генерим параллельно (4 потока).
Стоимость: ~$3.9, время: ~15-20 мин.

Маппинг brief × title на каждый продукт — см. PLAN ниже.
Каждый brief = разная композиция, каждый Title = разный hook → максимальное разнообразие в комбинаторной связке.
"""
import os, json, urllib.request, urllib.error, base64, sys, time, shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding="utf-8")

ENV = Path("I:/neuro/GENERAL CLAUDE CODE/Zerocoder/dragonslayer/goliath_daily/.env")
for line in ENV.read_text(encoding="utf-8").splitlines():
    if line.startswith("OPENROUTER_API_KEY="):
        OR_KEY = line.split("=", 1)[1].strip()
        break

OUT_DIR = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/banners/H08_2026-05-06")
OUT_DIR.mkdir(parents=True, exist_ok=True)
TEST_DIR = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/banners/H08_test_2026-05-06")

# === Перенос готовых тестовых в production-папку ===
copy_map = {
    "sysai_v1_test.png": "sysai_brief1.png",
    "law_v1_test.png": "law_brief1.png",
    "openclaw_v1_test.png": "openclaw_brief1.png",
}
for src, dst in copy_map.items():
    s, d = TEST_DIR / src, OUT_DIR / dst
    if s.exists() and not d.exists():
        shutil.copy(s, d)
        print(f"copied {src} → {dst}")


# === Universal banner-prompt builder ===
# Все промпты строятся по одной структуре: scene + style_constraints + russian_text_overlay + brand_badge
def build_prompt(scene: str, style: str, title: str, subtitle: str, badge: str = "Бесплатный практикум", badge_color: str = "green #1DB573") -> str:
    return (
        f"Banner ad image, vertical 4:5 aspect ratio. {scene} "
        f"Photo-realistic style. {style} "
        f"Bold Russian text overlay at top, large readable font: «{title}». "
        f"Smaller subtitle below the title: «{subtitle}». "
        f"Small {badge_color} brand badge in corner saying: «{badge}». "
        f"Premium professional aesthetic. NO neon. NO AI-futurism cliches. NO chaos."
    )


# === SYSAI (4 brief'а: brief2-brief5) ===
SYSAI = [
    ("sysai_brief2", build_prompt(
        scene="Clean isometric illustration showing a small AI agency: 1 person at central desk surrounded by 4 floating AI assistants helping with tasks (email, documents, analytics, calls), money flow graphics. Light blue and white palette, flat vector business illustration style.",
        style="Modern B2B illustration, NOT photo. Clean geometry, soft shadows.",
        title="ИИ-эксперт",
        subtitle="Новая профессия с доходом от 1 млн ₽",
    )),
    ("sysai_brief3", build_prompt(
        scene="Text-dominant composition. Left half: huge bold typography '8 НЕДЕЛЬ' (8 weeks) in dark blue. Right half: subtitle text in smaller font. Background subtle gradient dark navy to grey. NO people. Clean minimalist.",
        style="Typography-led poster design.",
        title="Своё ИИ-агентство с нуля",
        subtitle="За 8 недель — пошаговая программа",
    )),
    ("sysai_brief4", build_prompt(
        scene="Infographic-style banner: 4 income models stacked as horizontal bars showing '350K' / '700K' / '1.2M' / '2M+' rubles per month, each with a small icon (consulting, agency, products, training). Dark blue background, white typography, financial dashboard aesthetic.",
        style="Infographic dashboard, professional financial aesthetic.",
        title="4 модели заработка на ИИ",
        subtitle="От консалтинга до своего ИИ-продукта",
    )),
    ("sysai_brief5", build_prompt(
        scene="Split before-after: left half shows a tired man buried in paperwork at chaotic desk (muted grey tones); right half shows the same man relaxed with a coffee, looking at one clean monitor with AI dashboard (light blue tones). Caption between: «было / стало». Photo-realistic split.",
        style="Cinematic before-after composition. Real adult man, mid-40s, NOT smile-stock.",
        title="Как опытные ИИ-эксперты",
        subtitle="Делают 1-3 млн ₽ в месяц",
    )),
]

# === OPENCLAW (4 brief'а: brief2-brief5) ===
OPENCLAW = [
    ("openclaw_brief2", build_prompt(
        scene="Composition centered on the OpenClaw word-mark in clean modern sans-serif typography (white on dark blue gradient background). Below the wordmark — small subtitle text. Subtle floating UI elements around. NO chaotic graphics. Black + deep blue palette.",
        style="Brand-poster design, typography-led, calm.",
        title="OpenClaw",
        subtitle="ИИ-помощник, про которого все говорят",
    )),
    ("openclaw_brief3", build_prompt(
        scene="Split-screen banner: left half shows a person sleeping peacefully in bed at night (warm soft lighting); right half shows a laptop screen with AI agent running automated tasks (cool blue glow). Soft transition between halves. Calm, NOT chaotic.",
        style="Cinematic split, photo-realistic, soft mood lighting.",
        title="Запусти ИИ-агента OpenClaw",
        subtitle="За один вечер — пошаговый практикум",
    )),
    ("openclaw_brief4", build_prompt(
        scene="Five clean flat-style icons in a horizontal row: email automation, document processing, web research, data analysis, code generation. Each icon has a small Russian label below. Dark blue background, white icons with green accent, professional UI illustration style. NO 3D, NO neon.",
        style="Flat UI illustration, clean tech aesthetic.",
        title="OpenClaw на твоём ПК",
        subtitle="5 готовых сценариев — практикум",
    )),
    ("openclaw_brief5", build_prompt(
        scene="Text-dominant composition. Top: huge bold 'АВТОНОМНЫЙ' / 'ИИ-АГЕНТ' (2 lines) in white sans-serif on dark navy. Bottom: three smaller tags «локально» «без подписки» «на твоём ПК» separated by dots. NO people. Clean tech-poster.",
        style="Typography poster, dark navy palette, premium tech.",
        title="ИИ-платформа OpenClaw",
        subtitle="Революция в нейросетях",
    )),
]

# === N8N (5 brief'ов: brief1-brief5, ВСЕ генерим) ===
N8N = [
    ("n8n_brief1", build_prompt(
        scene="Clean visual workflow diagram with connected nodes in n8n style: trigger node → AI processing node → output node, connected with simple lines. Each node is a rounded rectangle with small icon inside. Light grey background, professional automation illustration.",
        style="Technical workflow diagram, NOT photo. Clean and minimal.",
        title="За 90 минут",
        subtitle="Собери ИИ-автоматизацию на n8n",
        badge_color="orange #FF6E33",
    )),
    ("n8n_brief2", build_prompt(
        scene="Factory conveyor belt metaphor: at the left end raw text and idea inputs flow in, at the right end finished video clips come out stacked vertically. Soft modern illustration style, blue + orange accent palette, clean white background. NOT photo.",
        style="Modern flat illustration, business-friendly.",
        title="Инструмент n8n",
        subtitle="Контент-завод вместо платной рекламы",
        badge_color="orange #FF6E33",
    )),
    ("n8n_brief3", build_prompt(
        scene="Real photo of a focused marketing professional in early 40s, working at a laptop with multiple browser tabs and an n8n workflow visible on screen. Modern home office, natural daylight, organized workspace. Realistic, NOT smile-stock.",
        style="Photo-realistic, candid working moment.",
        title="Как маркетологи",
        subtitle="Автоматизируют контент на n8n",
        badge_color="orange #FF6E33",
    )),
    ("n8n_brief4", build_prompt(
        scene="Text-dominant composition. Left: huge bold '20-50' in oversized typography. Right vertically stacked: 'видео в день' and 'на автомате'. Below: small logos n8n + Veo3. Clean white background, black typography, orange accent.",
        style="Typography-led poster, bold numbers.",
        title="20-50 видео в день",
        subtitle="Для соцсетей на n8n + Veo 3",
        badge_color="orange #FF6E33",
    )),
    ("n8n_brief5", build_prompt(
        scene="Split before-after: left half shows tired person manually copying data between spreadsheets (muted greys, slight blur); right half shows empty desk with laptop running automation alone, person relaxed with coffee in the background (warm blues). Caption between: «руками / автоматом».",
        style="Cinematic split, photo-realistic.",
        title="Собери контент-завод на n8n",
        subtitle="За 1 вечер без кода",
        badge_color="orange #FF6E33",
    )),
]

# === LAW (4 brief'а: brief2-brief5) ===
LAW = [
    ("law_brief2", build_prompt(
        scene="Clean illustration: a stack of legal documents on the left (cream paper with subtle text), a clean AI-assistant chat icon on the right (small modern UI bubble), a subtle arrow connecting them. Dark navy background with cream accents. Premium legal-tech aesthetic. NOT photo.",
        style="Minimal flat illustration, legal-professional palette.",
        title="Почему юристы",
        subtitle="Пользуются нейросетями в 2026 году",
        badge_color="gold #C5A572",
    )),
    ("law_brief3", build_prompt(
        scene="Text-dominant composition. Top: huge bold '10' typography in deep navy. Below: 'РУТИННЫХ ЗАДАЧ' and smaller 'которые можно поручить ИИ-ассистенту'. Cream background with navy serif typography. NO illustration. Authoritative, lawyerly.",
        style="Typography poster, classical serif font, premium legal aesthetic.",
        title="10 рутинных задач юриста",
        subtitle="Которые поручим ИИ",
        badge_color="gold #C5A572",
    )),
    ("law_brief4", build_prompt(
        scene="Clean isometric illustration of a lawyer's daily workflow: contract review, document drafting, case research — each task visualized as small icon along a horizontal line. AI-assistant icon takes over half of them with subtle arrows. Cream + navy palette, professional, NOT futuristic.",
        style="Isometric workflow illustration, clean and warm.",
        title="5 нейросетей",
        subtitle="Которые уже используют юристы",
        badge_color="gold #C5A572",
    )),
    ("law_brief5", build_prompt(
        scene="Photo-realistic scene: a traditional law-office bookshelf with thick legal volumes in the background (dark wood, warm lighting), and on the desk in foreground a sleek modern laptop showing AI assistant interface. Beautiful contrast between tradition and modern tech. Warm ambient light.",
        style="Photo-realistic, traditional law office aesthetic, warm tones.",
        title="ИИ-помощник юриста",
        subtitle="5 шагов от установки до работы",
        badge_color="gold #C5A572",
    )),
]

ALL_BANNERS = SYSAI + OPENCLAW + N8N + LAW
print(f"Total to generate: {len(ALL_BANNERS)} banners")
print(f"Already in production folder: {sum(1 for _,d in copy_map.items() if (OUT_DIR/d).exists())}")


# === API call ===
def call_image(prompt: str, retry: int = 2) -> bytes | None:
    body = {
        "model": "openai/gpt-5.4-image-2",
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image", "text"],
    }
    last_err = None
    for attempt in range(retry):
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {OR_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://kurzemnek.ru",
                "X-Title": "Goliath skill-creative-banner H08",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                resp = json.loads(r.read().decode("utf-8"))
            for choice in resp.get("choices", []):
                msg = choice.get("message", {})
                for img in msg.get("images") or []:
                    url = (img.get("image_url") or {}).get("url") or img.get("url")
                    if url and url.startswith("data:image"):
                        _, b64 = url.split(",", 1)
                        return base64.b64decode(b64), (resp.get("usage") or {}).get("cost", 0)
                    if url and url.startswith("http"):
                        with urllib.request.urlopen(url, timeout=60) as ir:
                            return ir.read(), (resp.get("usage") or {}).get("cost", 0)
            last_err = "no image in response"
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}: {e.read().decode('utf-8',errors='replace')[:200]}"
            time.sleep(5)
        except Exception as e:
            last_err = repr(e)
            time.sleep(5)
    return None, last_err


def gen_one(name: str, prompt: str):
    out_path = OUT_DIR / f"{name}.png"
    if out_path.exists():
        return name, "skipped (exists)", 0.0
    t0 = time.time()
    img, cost = call_image(prompt)
    if not img or isinstance(img, str):
        return name, f"FAIL: {cost}", 0.0
    out_path.write_bytes(img)
    return name, f"ok ({time.time()-t0:.0f}s, ${cost:.3f})", cost


# === Запуск 4 параллельно ===
print("\n=== Generating ===")
total_cost = 0.0
results = []
with ThreadPoolExecutor(max_workers=4) as exe:
    futures = {exe.submit(gen_one, name, prompt): name for name, prompt in ALL_BANNERS}
    for f in as_completed(futures):
        name, status, cost = f.result()
        total_cost += cost if isinstance(cost, (int, float)) else 0
        results.append((name, status))
        print(f"  [{len(results):2d}/{len(ALL_BANNERS)}] {name}: {status}")

print(f"\nTotal cost: ${total_cost:.2f}")
print(f"Output: {OUT_DIR}")
print(f"\nFiles in production folder:")
for f in sorted(OUT_DIR.glob("*.png")):
    print(f"  {f.name}")
