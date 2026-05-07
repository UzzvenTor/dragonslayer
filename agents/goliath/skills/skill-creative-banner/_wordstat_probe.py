"""Wordstat probe — проверка частотности 80 H08 ключей через keywordsresearch API.
Если API не выдаст — пишем что нужен браузерный плагин.
"""
import urllib.request, json, socket, sys, time
sys.stdout.reconfigure(encoding="utf-8")
_orig = socket.getaddrinfo
socket.getaddrinfo = lambda h,*a,**k: [r for r in _orig(h,*a,**k) if r[0]==socket.AF_INET] or _orig(h,*a,**k)

for line in open(r"I:/neuro/GENERAL CLAUDE CODE/Zerocoder/dragonslayer/goliath_daily/.env",encoding="utf-8"):
    if line.startswith("YANDEX_DIRECT_TOKEN="):
        TOK = line.split("=",1)[1].strip()


def call(svc, method, params, version="v5"):
    body = json.dumps({"method":method,"params":params}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.direct.yandex.com/json/{version}/{svc}",
        data=body,
        headers={"Authorization":f"Bearer {TOK}","Accept-Language":"ru","Client-Login":"porg-6vgf2ozq","Content-Type":"application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        try: return json.loads(e.read().decode("utf-8"))
        except: return {"_err": repr(e)}


# Пробуем разные endpoint имена
print("=== probe Wordstat endpoints ===")
PROBES = [
    ("v5", "keywordsresearch", "hasSearchVolume", {"Keywords":["ии для бизнеса"], "RegionIds":[225]}),
    ("v5", "keywordsresearch", "get", {"SelectionCriteria":{"Keywords":["ии для бизнеса"]},"FieldNames":["Keyword","SearchVolume"]}),
    ("v5", "wordstat", "create", {"Phrases":["ии для бизнеса"],"GeoID":[225]}),
    ("v501", "keywordsresearch", "hasSearchVolume", {"Keywords":["ии для бизнеса"], "RegionIds":[225]}),
    ("v4", "keywordsresearch", "hasSearchVolume", {"Keywords":["ии для бизнеса"], "RegionIds":[225]}),
    ("v5", "keywordresearch", "hasSearchVolume", {"Keywords":["ии для бизнеса"], "RegionIds":[225]}),
    ("v5", "keywords", "hasSearchVolume", {"Keywords":["ии для бизнеса"], "RegionIds":[225]}),
]

found = None
for ver, svc, method, params in PROBES:
    print(f"\n{ver}/{svc}.{method}:")
    r = call(svc, method, params, version=ver)
    if "result" in r:
        print(f"  ✓ WORKS: {json.dumps(r,ensure_ascii=False)[:400]}")
        found = (ver, svc, method)
        break
    err = r.get("error", {}).get("error_detail") or r.get("_err","")
    print(f"  ✗ {err[:200]}")

if found:
    print(f"\n>>> Используем: {found[0]}/{found[1]}.{found[2]}")
else:
    print("\n>>> Wordstat API недоступен — нужен браузерный плагин")
