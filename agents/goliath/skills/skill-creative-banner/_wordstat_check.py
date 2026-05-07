"""Wordstat частотность для всех 80 H08 ключей через keywordsresearch.hasSearchVolume v5.

Вход — 80 ключей из 4 продуктов H08.
Выход — таблица частотностей и рекомендация (заменить низкочастотные).
"""
import urllib.request, json, socket, sys, time
sys.stdout.reconfigure(encoding="utf-8")
_orig = socket.getaddrinfo
socket.getaddrinfo = lambda h,*a,**k: [r for r in _orig(h,*a,**k) if r[0]==socket.AF_INET] or _orig(h,*a,**k)

for line in open(r"I:/neuro/GENERAL CLAUDE CODE/Zerocoder/dragonslayer/goliath_daily/.env",encoding="utf-8"):
    if line.startswith("YANDEX_DIRECT_TOKEN="): TOK=line.split("=",1)[1].strip()


def call(svc, method, params):
    body = json.dumps({"method":method,"params":params}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.direct.yandex.com/json/v5/{svc}",
        data=body,
        headers={"Authorization":f"Bearer {TOK}","Accept-Language":"ru","Client-Login":"porg-6vgf2ozq","Content-Type":"application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        try: return json.loads(e.read().decode("utf-8"))
        except: return {"_err": repr(e)}


KEYWORDS = {
    "sysai": ["ии студия бизнес","внедрение ии в компании","как открыть ии студию","как заработать на ии","бизнес на нейросетях","ии консалтинг","ai консалтинг","внедрение нейросетей в бизнес","ии эксперт обучение","ии для предпринимателей","ии студия обучение","ии в бизнесе курс","как продавать внедрение ии","промпт инженер обучение","свой бизнес на ии","как стать ии экспертом","практикум по ии для бизнеса","ии стартап","зарабатывать на ии","ии агентство с нуля"],
    "openclaw": ["ии агент скачать","openclaw настройка","ии агент на пк","автономный ии агент","установка ии агента","как настроить ии агента","локальный ии помощник","свой ии помощник","ии помощник на компьютер","ии агент для рутины","ии агент без подписки","персональный ии агент","ии агент для бизнеса","бесплатный ии агент","как сделать ии помощника","open source ии агент","ии агент по умолчанию","практикум по ии агентам","claude agent установка","локальный llm агент"],
    "n8n": ["n8n обучение","n8n воркфлоу","автоматизация без кода","n8n для бизнеса","визуальная автоматизация","n8n уроки","n8n для маркетолога","контент завод n8n","n8n veo 3","ии автоматизация на n8n","как настроить n8n","n8n шаблоны","n8n интеграция","n8n бесплатно","курс n8n","n8n с нуля","как зарабатывать на n8n","видео контент автоматизация","n8n openai","low code платформы 2026"],
    "law": ["ии для юристов","нейросети для юристов","ии помощник юристу","автоматизация юридических задач","ии для договоров","как юристу использовать ии","ии в юриспруденции","ии ассистент юриста","чат бот для юристов","проверка договоров ии","сервис для юристов ии","адвокат и нейросети","правовой ии","legal tech ии","ии для адвокатов","экономия времени юриста","курс ии для юристов","практикум юристам ии","судебные документы ии","составление документов ии"],
}

# 1. Сначала пробуем правильную структуру SelectionCriteria
print("=== probe правильный SelectionCriteria ===")
test = call("keywordsresearch","hasSearchVolume",{"SelectionCriteria":{"Keywords":["ии для бизнеса"], "RegionIds":[225]}})
print(json.dumps(test, ensure_ascii=False)[:500])

# 2. Если работает — прогоняем все 80
if "result" in test:
    print("\n=== Прогоняю все 80 ключей ===")
    results = {}
    for product, kws in KEYWORDS.items():
        # API в одном запросе принимает несколько keywords
        resp = call("keywordsresearch","hasSearchVolume",{
            "SelectionCriteria":{"Keywords":kws,"RegionIds":[225]},
        })
        items = resp.get("result", {}).get("HasSearchVolumeItems") or resp.get("result", {}).get("Items") or []
        print(f"\n--- {product.upper()} ({len(items)} результатов) ---")
        for item in items[:30]:
            print(f"  {json.dumps(item, ensure_ascii=False)[:200]}")
        results[product] = items
        time.sleep(1)

    # Сохранить результат
    out_path = r"I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/exports/H08_wordstat_2026-05-06.json"
    open(out_path, "w", encoding="utf-8").write(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nSaved → {out_path}")
