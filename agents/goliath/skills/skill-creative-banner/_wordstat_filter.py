"""Прогоняет 80 H08 ключей через keywordsresearch.hasSearchVolume.
API возвращает только boolean (есть/нет запросов). Числа — только через Wordstat UI / плагин.
Цель: выявить «Мало показов» ключи (которые НЕ возвращаются в результате) → их менять.
"""
import urllib.request, json, socket, sys, time
sys.stdout.reconfigure(encoding="utf-8")
_orig = socket.getaddrinfo
socket.getaddrinfo = lambda h,*a,**k: [r for r in _orig(h,*a,**k) if r[0]==socket.AF_INET] or _orig(h,*a,**k)

for line in open(r"I:/neuro/GENERAL CLAUDE CODE/Zerocoder/dragonslayer/goliath_daily/.env",encoding="utf-8"):
    if line.startswith("YANDEX_DIRECT_TOKEN="): TOK=line.split("=",1)[1].strip()


def has_volume(keywords: list[str], region_id: int = 225) -> dict:
    body = json.dumps({"method":"hasSearchVolume","params":{
        "SelectionCriteria":{"Keywords":keywords,"RegionIds":[region_id]},
        "FieldNames":["Keyword","RegionIds"],
    }}, ensure_ascii=False).encode()
    req = urllib.request.Request(
        "https://api.direct.yandex.com/json/v5/keywordsresearch",
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

results = {}
for product, kws in KEYWORDS.items():
    print(f"\n=== {product.upper()} ===")
    resp = has_volume(kws)
    items = resp.get("result", {}).get("HasSearchVolumeResults", [])
    has_set = {it["Keyword"] for it in items}
    has = [k for k in kws if k in has_set]
    no = [k for k in kws if k not in has_set]
    results[product] = {"has_volume": has, "low_volume": no}
    print(f"  ✓ есть охват ({len(has)}): {', '.join(has)}")
    print(f"  ✗ мало показов ({len(no)}): {', '.join(no)}")
    time.sleep(1)

# Save
out = r"I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/exports/H08_wordstat_2026-05-06.json"
open(out, "w", encoding="utf-8").write(json.dumps(results, ensure_ascii=False, indent=2))
print(f"\nSaved → {out}")

# Summary
total_has = sum(len(r["has_volume"]) for r in results.values())
total_low = sum(len(r["low_volume"]) for r in results.values())
print(f"\nИТОГО: {total_has}/{total_has+total_low} ключей с охватом, {total_low} нужно заменить")
