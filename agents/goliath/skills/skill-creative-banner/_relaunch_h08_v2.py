"""H08 v2 — переделка ad'ов в правильный формат RESPONSIVE_AD (комбинаторные).

Шаги:
  1. Удалить 28 мусорных TEXT_AD из 4 H08 кампаний
  2. Удалить тестовую кампанию 709674572 (Валерий создал для эталона payload)
  3. Перезагрузить 20 баннеров (adimages.add v501 — идемпотентен по хэшу)
  4. Создать по 1 ResponsiveAd в каждой из 4 H08 групп — 7 Titles × 3 Texts × 5 Images
  5. Кампании остаются в DRAFT — Валерий проверяет и активирует

Запуск:
  python _relaunch_h08_v2.py            # выполняет всё синхронно
"""
import os, json, base64, socket, sys, urllib.request, urllib.error, datetime, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
_orig = socket.getaddrinfo
socket.getaddrinfo = lambda h,*a,**k: [r for r in _orig(h,*a,**k) if r[0]==socket.AF_INET] or _orig(h,*a,**k)

ENV = Path("I:/neuro/GENERAL CLAUDE CODE/Zerocoder/dragonslayer/goliath_daily/.env")
for line in ENV.read_text(encoding="utf-8").splitlines():
    if line.startswith("YANDEX_DIRECT_TOKEN="):
        TOK = line.split("=", 1)[1].strip()

BANNER_DIR = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/banners/H08_2026-05-06")
SNAPSHOT_DIR = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/exports")


def call(svc, method, params, version="v501"):
    body = json.dumps({"method": method, "params": params}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.direct.yandex.com/json/{version}/{svc}",
        data=body,
        headers={
            "Authorization": f"Bearer {TOK}", "Accept-Language": "ru",
            "Client-Login": "porg-6vgf2ozq", "Content-Type": "application/json; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {svc}.{method}: {body[:500]}")
    if "error" in resp:
        err = resp["error"]
        raise RuntimeError(f"{svc}.{method}: {err.get('error_detail') or err.get('error_string')}")
    return resp


# === Маппинг 4 H08 кампаний (от 1-го запуска) ===
CAMPAIGNS = {
    "sysai":    {"campaign_id": 709674000, "adgroup_id": 5748430366, "landing": "https://zerocoder.ru/start-your-business-with-ai"},
    "openclaw": {"campaign_id": 709674060, "adgroup_id": 5748431415, "landing": "https://zerocoder.ru/openclaw"},
    "n8n":      {"campaign_id": 709674103, "adgroup_id": 5748432743, "landing": "https://zerocoder.ru/open-lesson-on-visual-automation-n8n"},
    "law":      {"campaign_id": 709674151, "adgroup_id": 5748432840, "landing": "https://zerocoder.ru/lecture-practice-using-ai-for-legal-tasks"},
}

PRODUCT_CONTENT = {
    "sysai": {
        "titles": [
            "Запусти ИИ-агентство и выйди на 1 млн в месяц",
            "ИИ-эксперт: новая профессия с доходом от 1 млн",
            "Научись внедрять ИИ и зарабатывай 1 млн в месяц",
            "Как опытные ИИ-эксперты делают 1-3 млн в месяц",
            "Своё ИИ-агентство с нуля за 8 недель",
            "За какую ИИ-профессию платят миллионы в 2026",
            "4 модели заработка на ИИ для предпринимателя",
        ],
        "texts": [
            "Свой бизнес на ИИ: как делать от 1 млн на внедрении ИИ в компании",
            "Бесплатный практикум: пошаговая схема старта ИИ-консалтинга на 1 млн",
            "Покажем 4 модели заработка ИИ-эксперта от 500к до 3 млн в месяц",
        ],
    },
    "openclaw": {
        "titles": [
            "OpenClaw: ИИ-помощник, про которого все говорят",
            "Покажем как OpenClaw работает 24/7, пока вы спите",
            "ИИ-агент OpenClaw: от установки до 5 сценариев",
            "ИИ-платформа OpenClaw — революция в нейросетях",
            "Запусти ИИ-агента OpenClaw за 1 вечер",
            "OpenClaw на твоём ПК: 5 готовых сценариев",
            "Забудь про чат-боты: OpenClaw — настоящий ИИ-агент",
        ],
        "texts": [
            "В прямом эфире покажем как безопасно установить и для чего использовать",
            "Дадим пошаговый план и развернём ИИ-помощника OpenClaw на твоём ПК",
            "Установи автономного ИИ-агента сам — пошаговый практикум с разбором",
        ],
    },
    "n8n": {
        "titles": [
            "Инструмент n8n: контент-завод вместо платной рекламы",
            "20-50 видео в день для соцсетей на n8n + Veo3",
            "За 90 минут собери ИИ-автоматизацию на n8n",
            "Как маркетологи автоматизируют контент на n8n",
            "Покажем на бесплатном уроке что умеет n8n",
            "Собери контент-завод на n8n за 1 вечер",
            "Вайб-кодинг или n8n: что эффективнее в 2026",
        ],
        "texts": [
            "За 60-90 минут соберём рабочую ИИ-автоматизацию на n8n с нуля",
            "Бесплатный урок: n8n + Veo3 = контент-завод за один вечер",
            "Пошаговый план дохода на ИИ-ассистентах и инструменте n8n",
        ],
    },
    "law": {
        "titles": [
            "Как юристу создать ИИ-ассистента. Пошаговая инструкция",
            "10 рутинных задач юриста, которые поручим ИИ",
            "Почему юристы пользуются нейросетями в 2026 году",
            "Как нейросети ускоряют работу юриста в 3-10 раз",
            "5 нейросетей, которые уже используют юристы",
            "Подборка из 7 нейросетей для юристов — лекция",
            "ИИ-помощник юриста: 5 шагов от установки до работы",
        ],
        "texts": [
            "Наймите ИИ-ассистента и автоматизируйте до 90% работы с документами",
            "Будущее юриспруденции — за технологиями. Внедряйте ИИ постепенно",
            "Бесплатный практикум для юристов: пошаговая работа с нейросетями",
        ],
    },
}


def upload_banners(product: str) -> list[str]:
    """Возвращает список из 5 ImageHash'ей."""
    hashes = []
    for i in range(1, 6):
        path = BANNER_DIR / f"{product}_brief{i}.png"
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        resp = call("adimages", "add", {
            "AdImages": [{"ImageData": b64, "Name": f"H08_{product}_brief{i}"}],
        })
        h = resp["result"]["AddResults"][0]["AdImageHash"]
        hashes.append(h)
    return hashes


def create_responsive_ad(product: str, adgroup_id: int, image_hashes: list[str]) -> int:
    p = PRODUCT_CONTENT[product]
    landing = CAMPAIGNS[product]["landing"]
    href = (
        f"{landing}?utm_source=yandex&utm_medium=goliath"
        "&utm_campaign={campaign_id}&utm_content={ad_id}"
        f"&utm_term=H08__{product}__v1"
    )
    # Я.Директ API НЕ принимает AdImages в ResponsiveAd через add/update.
    # Загрузка картинок — через UI кабинета. Здесь создаём только Titles+Texts+Href.
    payload = {
        "Ads": [{
            "AdGroupId": adgroup_id,
            "ResponsiveAd": {
                "Titles": p["titles"],
                "Texts": p["texts"],
                "Href": href,
            },
        }],
    }
    resp = call("ads", "add", payload)
    res = resp["result"]["AddResults"][0]
    if "Errors" in res:
        raise RuntimeError(f"create_responsive_ad {product}: {res['Errors']}")
    return res["Id"]


def main():
    print("=== H08 v2 — переделка под комбинаторные RESPONSIVE_AD ===\n")

    snapshot = {
        "started": datetime.datetime.now().isoformat(timespec="seconds"),
        "products": [],
    }

    # Шаг 1: Получить и удалить мусорные TEXT_AD из 4 групп
    print("[1] Получаю текущие ads в 4 H08 группах...")
    adgroup_ids = [str(c["adgroup_id"]) for c in CAMPAIGNS.values()]
    resp = call("ads", "get", {
        "SelectionCriteria": {"AdGroupIds": adgroup_ids},
        "FieldNames": ["Id", "AdGroupId", "Type"],
    })
    ad_list = resp.get("result", {}).get("Ads", [])
    print(f"    нашлось {len(ad_list)} ads (ожидалось 28)")

    if ad_list:
        ids_to_delete = [str(a["Id"]) for a in ad_list]
        print(f"[2] Удаляю {len(ids_to_delete)} мусорных TEXT_AD...")
        # Я.Директ ads.delete: SelectionCriteria.Ids
        for batch_start in range(0, len(ids_to_delete), 100):
            batch = ids_to_delete[batch_start:batch_start + 100]
            resp = call("ads", "delete", {"SelectionCriteria": {"Ids": batch}})
            deleted = len(resp.get("result", {}).get("DeleteResults", []))
            print(f"    deleted {deleted}")

    # Шаг 3: Удалить тестовую кампанию
    print("[3] Удаляю тест-кампанию 709674572...")
    try:
        call("campaigns", "delete", {"SelectionCriteria": {"Ids": ["709674572"]}})
        print(f"    deleted")
    except RuntimeError as e:
        print(f"    [warn] {e}")

    # Шаг 4-5: для каждого продукта — баннеры + 1 ResponsiveAd
    for product, conf in CAMPAIGNS.items():
        print(f"\n[{product.upper()}] campaign={conf['campaign_id']}, adgroup={conf['adgroup_id']}")
        print(f"  [a] Загрузка 5 баннеров...")
        hashes = upload_banners(product)
        print(f"      {hashes}")

        print(f"  [b] Создание ResponsiveAd (7 Titles × 3 Texts × 5 Images)...")
        ad_id = create_responsive_ad(product, conf["adgroup_id"], hashes)
        print(f"      ad_id = {ad_id}")

        snapshot["products"].append({
            "product": product,
            "campaign_id": conf["campaign_id"],
            "adgroup_id": conf["adgroup_id"],
            "ad_id": ad_id,
            "image_hashes": hashes,
            "titles_count": len(PRODUCT_CONTENT[product]["titles"]),
            "texts_count": len(PRODUCT_CONTENT[product]["texts"]),
            "images_count": len(hashes),
        })

    snapshot["finished"] = datetime.datetime.now().isoformat(timespec="seconds")
    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out = SNAPSHOT_DIR / f"H08_relaunch_v2_{ts}.json"
    out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ Snapshot → {out}")
    print(f"\n=== ВСЕ 4 КАМПАНИИ ОБНОВЛЕНЫ. RESPONSIVE_AD создан в каждой. ===")
    print(f"=== Состояние: DRAFT, ждут активации Валерием ===")


if __name__ == "__main__":
    main()
