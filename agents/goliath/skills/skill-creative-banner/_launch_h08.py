"""Создаёт 4 новых кампании Голиафа по стандарту H08 на porg-6vgf2ozq.

Структура per продукт (4 шт: sysai/openclaw/n8n/law):
  - 1 TextCampaign (Network = AVERAGE_CPA по уник.рег, недельный лимит 14 000 ₽)
  - 1 adgroup с автотаргетом ON
  - 5 баннеров загружено в Я.Директ (adimages.add)
  - 7 TEXT_IMAGE_AD: 7 уникальных Title × 5 баннеров (с повторами) × 3 Text (с ротацией)
  - 20 keywords в группе
  - 20 минус-фраз кампании (cross-minus защита от автотаргета)

UTM: utm_source=yandex, utm_medium=goliath, utm_campaign={campaign_id},
     utm_content={ad_id}, utm_term=H08__<product>__v1

Запуск:
  python _launch_h08.py             # dry-run: показать план
  python _launch_h08.py --apply     # реально создать
  python _launch_h08.py --product sysai --apply    # только один продукт

После успеха: сохраняет snapshot в `Wiki/Raw/exports/H08_launch_<ts>.json`
"""
import os, sys, json, time, base64, socket, urllib.request, urllib.error, datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

_orig = socket.getaddrinfo
socket.getaddrinfo = lambda h,*a,**k: [r for r in _orig(h,*a,**k) if r[0]==socket.AF_INET] or _orig(h,*a,**k)

# === ENV ===
ENV = Path("I:/neuro/GENERAL CLAUDE CODE/Zerocoder/dragonslayer/goliath_daily/.env")
for line in ENV.read_text(encoding="utf-8").splitlines():
    if line.startswith("YANDEX_DIRECT_TOKEN="):
        YD_TOKEN = line.split("=", 1)[1].strip()
    if line.startswith("YD_CABINET="):
        YD_CABINET = line.split("=", 1)[1].strip()

BANNER_DIR = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/banners/H08_2026-05-06")
SNAPSHOT_DIR = Path("I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/exports")
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

# === API ===
API = "https://api.direct.yandex.com/json/v5/"

def call(svc: str, method: str, params: dict) -> dict:
    body = json.dumps({"method": method, "params": params}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        API + svc,
        data=body,
        headers={
            "Authorization": f"Bearer {YD_TOKEN}",
            "Accept-Language": "ru",
            "Client-Login": YD_CABINET,
            "Content-Type": "application/json; charset=utf-8",
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
        raise RuntimeError(f"API error {svc}.{method}: code={err.get('error_code')} detail={err.get('error_detail')} string={err.get('error_string')}")
    # check per-item errors in AddResults / UpdateResults
    res_block = resp.get("result", {})
    for key in ("AddResults", "UpdateResults", "SuspendResults"):
        items = res_block.get(key) or []
        for i, it in enumerate(items):
            if "Errors" in it:
                raise RuntimeError(f"{svc}.{method} item[{i}] errors: {it['Errors']}")
            if "Warnings" in it:
                print(f"   [warn] {svc}.{method} item[{i}]: {it['Warnings']}")
    return resp


# === CONFIGS ===
RUR_TO_MICRO = 1_000_000  # 1 рубль = 1 000 000 микрорублей
GOAL_ID = 332807191       # [all] Уникальная регистрация
COUNTER_ID = 72085663

PRODUCTS = {
    "sysai": {
        "campaign_name": "goliath__sysai_H08",
        "adgroup_name": "sysai-h08",
        "landing": "https://zerocoder.ru/start-your-business-with-ai",
        "target_cpa_rub": 1077,
        "weekly_limit_rub": 14000,
        "title2": "Бесплатный практикум",
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
        "keywords": [
            "ии студия бизнес","внедрение ии в компании","как открыть ии студию",
            "как заработать на ии","бизнес на нейросетях","ии консалтинг",
            "ai консалтинг","внедрение нейросетей в бизнес","ии эксперт обучение",
            "ии для предпринимателей","ии студия обучение","ии в бизнесе курс",
            "как продавать внедрение ии","промпт инженер обучение","свой бизнес на ии",
            "как стать ии экспертом","практикум по ии для бизнеса","ии стартап",
            "зарабатывать на ии","ии агентство с нуля",
        ],
    },
    "openclaw": {
        "campaign_name": "goliath__openclaw_H08",
        "adgroup_name": "openclaw-h08",
        "landing": "https://zerocoder.ru/openclaw",
        "target_cpa_rub": 1308,
        "weekly_limit_rub": 14000,
        "title2": "Бесплатный воркшоп",
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
        "keywords": [
            "ии агент скачать","openclaw настройка","ии агент на пк",
            "автономный ии агент","установка ии агента","как настроить ии агента",
            "локальный ии помощник","свой ии помощник","ии помощник на компьютер",
            "ии агент для рутины","ии агент без подписки","персональный ии агент",
            "ии агент для бизнеса","бесплатный ии агент","как сделать ии помощника",
            "open source ии агент","ии агент по умолчанию","практикум по ии агентам",
            "claude agent установка","локальный llm агент",
        ],
    },
    "n8n": {
        "campaign_name": "goliath__n8n_H08",
        "adgroup_name": "n8n-h08",
        "landing": "https://zerocoder.ru/open-lesson-on-visual-automation-n8n",
        "target_cpa_rub": 1231,
        "weekly_limit_rub": 14000,
        "title2": "Бесплатный урок",
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
        "keywords": [
            "n8n обучение","n8n воркфлоу","автоматизация без кода",
            "n8n для бизнеса","визуальная автоматизация","n8n уроки",
            "n8n для маркетолога","контент завод n8n","n8n veo 3",
            "ии автоматизация на n8n","как настроить n8n","n8n шаблоны",
            "n8n интеграция","n8n бесплатно","курс n8n",
            "n8n с нуля","как зарабатывать на n8n","видео контент автоматизация",
            "n8n openai","low code платформы 2026",
        ],
    },
    "law": {
        "campaign_name": "goliath__law_H08",
        "adgroup_name": "law-h08",
        "landing": "https://zerocoder.ru/lecture-practice-using-ai-for-legal-tasks",
        "target_cpa_rub": 846,
        "weekly_limit_rub": 14000,
        "title2": "Бесплатная лекция",
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
        "keywords": [
            "ии для юристов","нейросети для юристов","ии помощник юристу",
            "автоматизация юридических задач","ии для договоров","как юристу использовать ии",
            "ии в юриспруденции","ии ассистент юриста","чат бот для юристов",
            "проверка договоров ии","сервис для юристов ии","адвокат и нейросети",
            "правовой ии","legal tech ии","ии для адвокатов",
            "экономия времени юриста","курс ии для юристов","практикум юристам ии",
            "судебные документы ии","составление документов ии",
        ],
    },
}

# Маппинг brief × Title × Text для 7 ad на продукт (1 ad = 1 уникальная связка)
# brief 1-5 = banner_brief1.png .. banner_brief5.png; для ad 6,7 банеры повторяем
AD_MAPPING = [
    {"title_idx": 0, "text_idx": 0, "brief": 1},  # ad 1: hero claim + Banner 1 (фото-герой)
    {"title_idx": 1, "text_idx": 1, "brief": 2},  # ad 2: профессия + Banner 2 (метафора)
    {"title_idx": 2, "text_idx": 2, "brief": 3},  # ad 3: научись + Banner 3 (типография)
    {"title_idx": 3, "text_idx": 0, "brief": 4},  # ad 4: соц-доказ + Banner 4 (инфограф)
    {"title_idx": 4, "text_idx": 1, "brief": 5},  # ad 5: новая + Banner 5 (before-after)
    {"title_idx": 5, "text_idx": 2, "brief": 1},  # ad 6: вопрос + Banner 1 (повтор)
    {"title_idx": 6, "text_idx": 0, "brief": 2},  # ad 7: 4 модели + Banner 2 (повтор)
]


# === HELPERS ===
def upload_banner(path: Path, name: str = None) -> str:
    """adimages.add → AdImageHash."""
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    resp = call("adimages", "add", {
        "AdImages": [{"ImageData": b64, "Name": name or path.stem[:255]}],
    })
    res = resp.get("result", {}).get("AddResults", [])
    if not res or "Errors" in res[0]:
        raise RuntimeError(f"upload_banner failed: {res}")
    return res[0]["AdImageHash"]


def create_campaign(p: dict) -> int:
    today = datetime.date.today().isoformat()
    payload = {
        "Campaigns": [{
            "Name": p["campaign_name"],
            "StartDate": today,
            "ClientInfo": "Голиаф H08",
            "TextCampaign": {
                "BiddingStrategy": {
                    "Search": {"BiddingStrategyType": "SERVING_OFF"},
                    "Network": {
                        "BiddingStrategyType": "AVERAGE_CPA",
                        "AverageCpa": {
                            "AverageCpa": p["target_cpa_rub"] * RUR_TO_MICRO,
                            "WeeklySpendLimit": p["weekly_limit_rub"] * RUR_TO_MICRO,
                            "GoalId": GOAL_ID,
                        },
                    },
                },
                "Settings": [
                    {"Option": "ADD_METRICA_TAG", "Value": "YES"},
                    {"Option": "ENABLE_AREA_OF_INTEREST_TARGETING", "Value": "YES"},
                ],
                "CounterIds": {"Items": [COUNTER_ID]},
            },
        }]
    }
    resp = call("campaigns", "add", payload)
    res = resp.get("result", {}).get("AddResults", [])
    if not res or "Errors" in res[0]:
        raise RuntimeError(f"create_campaign failed: {res}")
    return res[0]["Id"]


def create_adgroup(campaign_id: int, p: dict) -> int:
    """Создаёт TEXT_AD_GROUP. Автотаргет на уровне группы добавится отдельно через
    keywords.add с типом AUTOTARGETING (или через campaigns.update Settings)."""
    payload = {
        "AdGroups": [{
            "Name": p["adgroup_name"],
            "CampaignId": campaign_id,
            "RegionIds": [225],  # Россия
        }]
    }
    resp = call("adgroups", "add", payload)
    res = resp.get("result", {}).get("AddResults", [])
    return res[0]["Id"]


def enable_autotargeting(adgroup_id: int) -> bool:
    """Добавляет автотаргет к группе через keywords.add со специальным флагом.
    В Я.Директ API автотаргет — это особый Keyword с пустым текстом и категориями."""
    payload = {
        "Keywords": [{
            "AdGroupId": adgroup_id,
            "AutotargetingExactMatch": "YES",
            "AutotargetingAlternative": "YES",
            "AutotargetingCompetitor": "YES",
            "AutotargetingBroader": "YES",
            "AutotargetingAccessory": "YES",
        }]
    }
    try:
        resp = call("keywords", "add", payload)
        return True
    except RuntimeError as e:
        # Автотаргет API может отличаться — не падаем, отмечаем
        print(f"   [warn] enable_autotargeting failed (skipping): {str(e)[:200]}")
        return False


def add_keywords(adgroup_id: int, keywords: list[str]) -> list[int]:
    payload = {
        "Keywords": [{"AdGroupId": adgroup_id, "Keyword": k} for k in keywords]
    }
    resp = call("keywords", "add", payload)
    res = resp.get("result", {}).get("AddResults", [])
    return [r.get("Id") for r in res if "Id" in r]


def add_negative_phrases(campaign_id: int, phrases: list[str]) -> bool:
    """campaigns.update: NegativeKeywords. Cross-minus защита от автотаргета."""
    payload = {
        "Campaigns": [{
            "Id": campaign_id,
            "NegativeKeywords": {"Items": phrases},
        }]
    }
    resp = call("campaigns", "update", payload)
    res = resp.get("result", {}).get("UpdateResults", [])
    return res and "Id" in res[0]


def suspend_campaign(campaign_id: int) -> bool:
    """campaigns.suspend — оставить в SUSPENDED, чтобы Валерий проверил перед активацией."""
    resp = call("campaigns", "suspend", {
        "SelectionCriteria": {"Ids": [campaign_id]},
    })
    res = resp.get("result", {}).get("SuspendResults", [])
    return bool(res and "Id" in res[0])


def create_ad(adgroup_id: int, campaign_id: int, title: str, title2: str, text: str,
              banner_hash: str, landing: str, product: str) -> int:
    href = (
        f"{landing}?utm_source=yandex"
        f"&utm_medium=goliath"
        "&utm_campaign={campaign_id}"
        "&utm_content={ad_id}"
        f"&utm_term=H08__{product}__v1"
    )
    # Я.Директ TextAdBuilderAd: один Title + Title2 + Text + Href + 1 AdImage
    # AdImage внутри Creative как list для RESPONSIVE — но для simple TextAdBuilderAd
    # это просто `AdImageHash` или TextAdImageHash.
    # Пробуем поэтапно несколько форматов — какой пройдёт.
    formats = [
        # формат 1: TextAdBuilderAd с прямым AdImageHash
        {"TextAdBuilderAd": {"Title": title, "Title2": title2, "Text": text, "Href": href, "AdImageHash": banner_hash}},
        # формат 2: TextAd (без картинки)
        {"TextAd": {"Title": title, "Title2": title2, "Text": text, "Href": href}},
    ]
    last_err = None
    for fmt in formats:
        try:
            payload = {"Ads": [{"AdGroupId": adgroup_id, **fmt}]}
            resp = call("ads", "add", payload)
            res = resp.get("result", {}).get("AddResults", [])
            if res and "Id" in res[0]:
                return res[0]["Id"]
        except RuntimeError as e:
            last_err = e
            continue
    raise RuntimeError(f"create_ad: all formats failed, last: {last_err}")


# === MAIN ===
def launch_one(product: str, dry_run: bool = True) -> dict:
    p = PRODUCTS[product]
    out = {
        "product": product,
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "dry_run": dry_run,
    }

    print(f"\n{'='*70}\n[{product.upper()}] {p['campaign_name']}")
    print(f"  Landing: {p['landing']}")
    print(f"  Target CPA: {p['target_cpa_rub']}₽, Weekly limit: {p['weekly_limit_rub']}₽")
    print(f"  Banners: {BANNER_DIR}/{product}_brief{{1..5}}.png")
    print(f"  7 Title × 5 Banner × 3 Text = 7 ad'ов в 1 группе")
    print(f"  Keywords: {len(p['keywords'])}, Cross-minus: {len(p['keywords'])}")
    print(f"  UTM: ...&utm_medium=goliath&utm_term=H08__{product}__v1")

    # Sanity check banners
    banner_paths = [BANNER_DIR / f"{product}_brief{i}.png" for i in range(1, 6)]
    missing = [str(p) for p in banner_paths if not p.exists()]
    if missing:
        out["error"] = f"Missing banners: {missing}"
        print(f"  ⚠️ MISSING BANNERS: {missing}")
        return out

    if dry_run:
        out["plan"] = {
            "create_campaign": p["campaign_name"],
            "create_adgroup": p["adgroup_name"],
            "upload_banners": len(banner_paths),
            "create_ads": len(AD_MAPPING),
            "add_keywords": len(p["keywords"]),
            "add_negative_phrases": len(p["keywords"]),
        }
        print("  → DRY-RUN: план зафиксирован, ничего не записано")
        return out

    # === APPLY ===
    print(f"  → APPLY MODE")
    print(f"  [1/6] Creating campaign...")
    campaign_id = create_campaign(p)
    out["campaign_id"] = campaign_id
    print(f"    campaign_id = {campaign_id}")

    print(f"  [2/6] Uploading 5 banners...")
    banner_hashes = []
    for path in banner_paths:
        h = upload_banner(path, name=f"H08__{product}__{path.stem}")
        banner_hashes.append(h)
        print(f"    {path.name} → {h}")
    out["banner_hashes"] = banner_hashes

    print(f"  [3/7] Creating adgroup...")
    adgroup_id = create_adgroup(campaign_id, p)
    out["adgroup_id"] = adgroup_id
    print(f"    adgroup_id = {adgroup_id}")

    print(f"  [3.5] Enabling autotargeting on adgroup...")
    auto_ok = enable_autotargeting(adgroup_id)
    out["autotargeting"] = auto_ok
    print(f"    autotargeting: {'ON' if auto_ok else 'SKIPPED (manual via UI)'}")

    print(f"  [4/7] Adding 20 keywords...")
    keyword_ids = add_keywords(adgroup_id, p["keywords"])
    out["keyword_ids"] = keyword_ids
    print(f"    {len(keyword_ids)} keywords added")

    print(f"  [5/6] Adding 20 negative phrases (cross-minus)...")
    add_negative_phrases(campaign_id, p["keywords"])
    print(f"    cross-minus set on campaign")

    print(f"  [6/6] Creating 7 ads (Title × Banner × Text)...")
    ad_ids = []
    for m in AD_MAPPING:
        title = p["titles"][m["title_idx"]]
        text = p["texts"][m["text_idx"]]
        banner_hash = banner_hashes[m["brief"] - 1]
        ad_id = create_ad(
            adgroup_id, campaign_id,
            title, p["title2"], text,
            banner_hash, p["landing"], product,
        )
        ad_ids.append(ad_id)
        print(f"    ad {ad_id}: '{title[:40]}' / brief{m['brief']}")
    out["ad_ids"] = ad_ids

    print(f"  [7/7] Confirming campaign is in DRAFT (Я.Директ default for new campaigns)...")
    try:
        suspend_campaign(campaign_id)
        out["state"] = "SUSPENDED"
        print(f"    state = SUSPENDED")
    except RuntimeError as e:
        # Если ругается «черновик не может быть остановлен» — это норма,
        # черновик и так не активен.
        if "черновик" in str(e).lower() or "draft" in str(e).lower():
            out["state"] = "DRAFT"
            print(f"    state = DRAFT (по умолчанию, ожидает запуска через UI)")
        else:
            out["state"] = "UNKNOWN"
            print(f"    [warn] suspend failed: {str(e)[:200]}")

    print(f"  ✓ DONE: campaign={campaign_id} [{out.get('state')}], adgroup={adgroup_id}, ads={len(ad_ids)}")
    return out


def main():
    args = sys.argv[1:]
    apply_mode = "--apply" in args
    only_product = None
    if "--product" in args:
        only_product = args[args.index("--product") + 1]

    products_to_run = [only_product] if only_product else list(PRODUCTS.keys())

    print(f"=== H08 launch ({'APPLY' if apply_mode else 'DRY-RUN'}) ===")
    print(f"Cabinet: {YD_CABINET}")
    print(f"Products: {products_to_run}")
    print(f"Banner dir: {BANNER_DIR}")

    snapshot = {
        "started": datetime.datetime.now().isoformat(timespec="seconds"),
        "cabinet": YD_CABINET,
        "mode": "apply" if apply_mode else "dry-run",
        "products": [],
    }

    for product in products_to_run:
        try:
            result = launch_one(product, dry_run=not apply_mode)
            snapshot["products"].append(result)
        except Exception as e:
            print(f"  ❌ FAIL: {e}")
            snapshot["products"].append({"product": product, "error": str(e)})

    snapshot["finished"] = datetime.datetime.now().isoformat(timespec="seconds")

    if apply_mode:
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        out_file = SNAPSHOT_DIR / f"H08_launch_{ts}.json"
        out_file.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSnapshot saved → {out_file}")

    print(f"\n{'='*70}")
    print(f"Done. {sum(1 for p in snapshot['products'] if 'campaign_id' in p)} campaign(s) created.")


if __name__ == "__main__":
    main()
