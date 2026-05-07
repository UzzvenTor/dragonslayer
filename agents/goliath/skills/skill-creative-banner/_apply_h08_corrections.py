"""H08 corrections: 4 правки за раз.
1. Cross-minus убираем (NegativeKeywords пустой)
2. ExcludedSites копируем из контрольной 709513073
3. RegionIds на adgroup → per-product топ-10
4. DemographicsAdjustments → per-product 2 сегмента +30%, остальное 0

После — Settings standard v0.3, memory update.
"""
import urllib.request, json, socket, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
_orig = socket.getaddrinfo
socket.getaddrinfo = lambda h,*a,**k: [r for r in _orig(h,*a,**k) if r[0]==socket.AF_INET] or _orig(h,*a,**k)

for line in open(r"I:/neuro/GENERAL CLAUDE CODE/Zerocoder/dragonslayer/goliath_daily/.env",encoding="utf-8"):
    if line.startswith("YANDEX_DIRECT_TOKEN="): TOK=line.split("=",1)[1].strip()

def call(svc, method, params):
    body=json.dumps({"method":method,"params":params}, ensure_ascii=False).encode()
    req=urllib.request.Request(f"https://api.direct.yandex.com/json/v501/{svc}",data=body,
        headers={"Authorization":f"Bearer {TOK}","Accept-Language":"ru","Client-Login":"porg-6vgf2ozq","Content-Type":"application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        try: return json.loads(e.read().decode("utf-8"))
        except: return {"_err":repr(e)}

# Per-product config
H08 = {
    "sysai":    {"campaign":709674000, "adgroup":5748430366,
                 "regions":[1, 10174, 10995, 11162, 11119, 11079, 11111, 11095, 10832, 11225],
                 "boost":[("GENDER_MALE","AGE_35_44"),("GENDER_MALE","AGE_45_54")]},
    "openclaw": {"campaign":709674060, "adgroup":5748431415,
                 "regions":[1, 11111, 10174, 11029, 10795, 11225, 11131, 11070, 11457, 10995],
                 "boost":[("GENDER_MALE","AGE_25_34"),("GENDER_MALE","AGE_35_44")]},
    "n8n":      {"campaign":709674103, "adgroup":5748432743,
                 "regions":[1, 10174, 11316, 10995, 10672, 11162, 11318, 11266, 11225, 11119],
                 "boost":[("GENDER_MALE","AGE_35_44"),("GENDER_FEMALE","AGE_35_44")]},
    "law":      {"campaign":709674151, "adgroup":5748432840,
                 "regions":[1, 10174, 10995, 11162, 11029, 11111, 11316, 11119, 11131, 11079],
                 "boost":[("GENDER_MALE","AGE_35_44"),("GENDER_FEMALE","AGE_35_44")]},
}

ALL_AGES = ["AGE_0_17","AGE_18_24","AGE_25_34","AGE_35_44","AGE_45_54","AGE_55"]
ALL_GENDERS = ["GENDER_MALE","GENDER_FEMALE"]

# === 1. Get ExcludedSites from control 709513073 ===
print("=== [1] Pulling ExcludedSites from control 709513073 ===")
exc_path = Path(r"I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/exports/excluded_sites_control_709513073.json")
exc_sites = json.loads(exc_path.read_text(encoding="utf-8"))
# Я.Директ позволяет хранить ExcludedSites доменов и категорий (Inner-active, MoPub etc — это категории)
print(f"  loaded {len(exc_sites)} sites")

# === 2. Per-campaign: clear cross-minus + apply ExcludedSites ===
print("\n=== [2] Cross-minus убираем + ExcludedSites копируем ===")
for prod, cfg in H08.items():
    payload = {"Campaigns":[{"Id":cfg["campaign"],
        "NegativeKeywords":{"Items":[]},
        "ExcludedSites":{"Items":exc_sites},
    }]}
    r = call("campaigns","update",payload)
    if "error" in r: print(f"  {prod}: ❌ {r['error']['error_detail']}")
    else:
        results = r.get("result",{}).get("UpdateResults",[])
        for res in results:
            if "Errors" in res: print(f"  {prod}: ❌ {res['Errors']}")
            else: print(f"  {prod}: ✓ Id={res.get('Id')}")

# === 3. RegionIds per adgroup ===
print("\n=== [3] RegionIds → топ-10 per продукт ===")
for prod, cfg in H08.items():
    payload = {"AdGroups":[{"Id":cfg["adgroup"],"RegionIds":cfg["regions"]}]}
    r = call("adgroups","update",payload)
    if "error" in r: print(f"  {prod}: ❌ {r['error']['error_detail']}")
    else:
        results = r.get("result",{}).get("UpdateResults",[])
        for res in results:
            if "Errors" in res: print(f"  {prod}: ❌ {res['Errors']}")
            else: print(f"  {prod}: ✓ {len(cfg['regions'])} регионов")

# === 4. Удалить старые DEMOGRAPHICS + поставить новые ===
print("\n=== [4a] Delete old DEMOGRAPHICS bid modifiers ===")
all_camp_ids = [str(c["campaign"]) for c in H08.values()]
r = call("bidmodifiers","get",{
    "SelectionCriteria":{"CampaignIds":all_camp_ids,"Levels":["CAMPAIGN"]},
    "FieldNames":["Id","CampaignId","Type"],
})
old_demo_ids = [bm["Id"] for bm in r.get("result",{}).get("BidModifiers",[]) if bm.get("Type")=="DEMOGRAPHICS_ADJUSTMENT"]
print(f"  Found {len(old_demo_ids)} old DEMO bidmodifiers, deleting...")
if old_demo_ids:
    r = call("bidmodifiers","delete",{"SelectionCriteria":{"Ids":old_demo_ids}})
    if "error" in r: print(f"    ❌ {r['error']['error_detail']}")
    else:
        deleted = len(r.get("result",{}).get("DeleteResults",[]))
        print(f"    ✓ deleted {deleted}")

print("\n=== [4b] Apply new narrow DEMOGRAPHICS (2 сегмента +30%, остальное 0) ===")
for prod, cfg in H08.items():
    boost_set = set(cfg["boost"])
    demos = []
    # 2 целевых
    for g, a in cfg["boost"]:
        demos.append({"Gender":g,"Age":a,"BidModifier":130})
    # все остальные пары → 0
    for g in ALL_GENDERS:
        for a in ALL_AGES:
            if (g,a) in boost_set: continue
            demos.append({"Gender":g,"Age":a,"BidModifier":0})

    payload = {"BidModifiers":[{"CampaignId":cfg["campaign"],"DemographicsAdjustments":demos}]}
    r = call("bidmodifiers","add",payload)
    if "error" in r: print(f"  {prod}: ❌ {r['error']['error_detail']}")
    else:
        results = r.get("result",{}).get("AddResults",[])
        ok = sum(1 for x in results if "Id" in x)
        errs = [x for x in results if "Errors" in x]
        print(f"  {prod}: ✓ {ok}/{len(demos)} ({len(cfg['boost'])} boost +30%, остальное 0)")
        for e in errs[:3]:
            print(f"    err: {e}")

# === Verify ===
print("\n=== ИТОГ ===")
for prod, cfg in H08.items():
    # bidmodifiers
    bm_resp = call("bidmodifiers","get",{
        "SelectionCriteria":{"CampaignIds":[str(cfg["campaign"])],"Levels":["CAMPAIGN"]},
        "FieldNames":["CampaignId","Type"],
        "DemographicsAdjustmentFieldNames":["Gender","Age","BidModifier"],
    })
    bms = [b for b in bm_resp.get("result",{}).get("BidModifiers",[]) if b.get("Type")=="DEMOGRAPHICS_ADJUSTMENT"]
    boost = [b for b in bms if (b.get("DemographicsAdjustment") or {}).get("BidModifier") == 130]

    # adgroup regions
    ag_resp = call("adgroups","get",{"SelectionCriteria":{"Ids":[str(cfg["adgroup"])]},"FieldNames":["Id","RegionIds"]})
    ag = ag_resp.get("result",{}).get("AdGroups",[{}])[0]

    # campaign exc + neg
    c_resp = call("campaigns","get",{"SelectionCriteria":{"Ids":[str(cfg["campaign"])]},"FieldNames":["Id","ExcludedSites","NegativeKeywords"]})
    c = c_resp.get("result",{}).get("Campaigns",[{}])[0]
    excs = (c.get("ExcludedSites") or {}).get("Items") or []
    negs = (c.get("NegativeKeywords") or {}).get("Items") or []

    print(f"\n[{prod.upper()}]")
    print(f"  RegionIds: {ag.get('RegionIds')}")
    print(f"  ExcludedSites: {len(excs)} sites")
    print(f"  NegativeKeywords: {len(negs)} (должно 0)")
    print(f"  Demo: {len(bms)} total, {len(boost)} с boost +30%:")
    for b in boost:
        a = b.get("DemographicsAdjustment",{})
        print(f"    {a.get('Gender')} {a.get('Age')} → {a.get('BidModifier')}")

print("\n✓ DONE")
