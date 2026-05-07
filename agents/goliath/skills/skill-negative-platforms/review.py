"""skill-negative-platforms — pull площадок + правило 3×ARPL+50clicks.

Запуск:
    python review.py --lookback-days 14

Эмитит JSON-array proposal-кандидатов на stdout.
Только понедельники (или forced --any-day).
"""
from __future__ import annotations

import argparse
import csv
import datetime
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "routines"))
from _lib.common import load_env, force_ipv4  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
load_env()
force_ipv4()

YD_TOKEN = (os.environ.get("YANDEX_DIRECT_TOKEN") or "").strip().strip("'").strip('"')
YD_CABINET = os.environ.get("YD_CABINET", "porg-6vgf2ozq")
YD_CAMPAIGN_IDS = [int(x) for x in os.environ["YD_CAMPAIGN_IDS"].split(",")]

ARPL = {"sysai": 1400, "openclaw": 1700, "n8n": 1600, "law": 1100}
CAMP_TO_PRODUCT = {
    "709513073": "sysai", "709513492": "openclaw",
    "709513513": "n8n", "709513517": "law",
    "709674000": "sysai", "709674060": "openclaw",
    "709674103": "n8n", "709674151": "law",
}

# Не минусуем агрегаторы
PROTECTED = {"yandex.ru", "mail.ru", "vk.com", "ok.ru", "rambler.ru", "yandex.com",
             "search.yandex.ru", "translate.yandex.ru"}
SOFT_PROTECT = ("yandex", "mail")  # содержит — внимательнее, но можно


def yd_pull_placements(date_from: str, date_to: str) -> list[dict]:
    body = {
        "params": {
            "SelectionCriteria": {
                "DateFrom": date_from, "DateTo": date_to,
                "Filter": [{"Field": "CampaignId", "Operator": "IN",
                            "Values": [str(c) for c in YD_CAMPAIGN_IDS]}],
            },
            "FieldNames": ["CampaignId", "Placement", "Cost", "Clicks", "Impressions"],
            "ReportName": f"goliath-negsites-{date_from}-{date_to}-{int(time.time())}",
            "ReportType": "CUSTOM_REPORT",
            "DateRangeType": "CUSTOM_DATE",
            "Format": "TSV", "IncludeVAT": "YES", "IncludeDiscount": "NO",
        }
    }
    headers = {
        "Authorization": f"Bearer {YD_TOKEN}", "Accept-Language": "ru",
        "Client-Login": YD_CABINET, "processingMode": "auto",
        "returnMoneyInMicros": "false", "skipReportHeader": "true",
        "skipColumnHeader": "false", "skipReportSummary": "true",
    }
    content = None
    for _ in range(40):
        try:
            req = urllib.request.Request(
                "https://api.direct.yandex.com/json/v5/reports",
                data=json.dumps(body).encode("utf-8"), headers=headers,
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                if resp.status == 200:
                    content = resp.read().decode("utf-8")
                    break
                time.sleep(8)
        except urllib.error.HTTPError as e:
            if e.code in (201, 202):
                time.sleep(8); continue
            raise RuntimeError(f"YD HTTP {e.code}: {e.read().decode('utf-8')[:300]}") from None
    if content is None:
        raise RuntimeError("YD reports not done after 40 attempts")

    rows = []
    for r in csv.DictReader(io.StringIO(content), delimiter="\t"):
        rows.append({
            "campaign_id": int(r["CampaignId"]),
            "placement": r.get("Placement") or "",
            "cost_rub": round(float(r.get("Cost") or 0), 2),
            "clicks": int(r.get("Clicks") or 0),
            "impressions": int(r.get("Impressions") or 0),
        })
    return rows


def yd_existing_excluded() -> dict:
    """Возвращает {campaign_id: [excluded_sites]} текущий чёрный список."""
    body = {
        "method": "get",
        "params": {
            "SelectionCriteria": {"Ids": [int(c) for c in YD_CAMPAIGN_IDS]},
            "FieldNames": ["Id"],
            "TextCampaignFieldNames": ["ExcludedSites"],
        }
    }
    req = urllib.request.Request(
        "https://api.direct.yandex.com/json/v5/campaigns",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {YD_TOKEN}",
                 "Accept-Language": "ru", "Client-Login": YD_CABINET,
                 "Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    out = {}
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        for c in (data.get("result", {}) or {}).get("Campaigns", []):
            tc = c.get("TextCampaign") or {}
            excl = (tc.get("ExcludedSites") or {}).get("Items") or []
            out[int(c["Id"])] = list(excl)
    except Exception as e:
        print(f"WARN: cannot fetch ExcludedSites: {e}", file=sys.stderr)
    return out


def evaluate(rows: list[dict], existing_excl: dict, lookback_days: int) -> list[dict]:
    # Группируем per (campaign_id, placement)
    agg = {}
    for r in rows:
        key = (r["campaign_id"], r["placement"])
        d = agg.setdefault(key, {"cost": 0.0, "clicks": 0, "impressions": 0})
        d["cost"] += r["cost_rub"]; d["clicks"] += r["clicks"]; d["impressions"] += r["impressions"]

    proposals = []
    seen = set()  # дедуп per (camp_id, placement)
    for (cid, placement), d in agg.items():
        if not placement:
            continue
        product = CAMP_TO_PRODUCT.get(str(cid))
        if not product:
            continue
        arpl = ARPL[product]
        if d["cost"] < 3 * arpl or d["clicks"] < 50:
            continue
        if placement.lower() in PROTECTED:
            continue
        if placement in (existing_excl.get(cid) or []):
            continue
        if (cid, placement) in seen:
            continue
        seen.add((cid, placement))

        proposals.append({
            "category": "negative_site", "product": product,
            "campaign_id": cid, "ad_group_id": None, "ad_id": None,
            "description": (f"⛔ Минусовать площадку **{placement}** в кампании "
                            f"{cid} ({product})"),
            "reasoning": (f"За {lookback_days}д: cost {d['cost']:.0f}₽ "
                          f"≥ 3×ARPL ({3*arpl}₽), clicks {d['clicks']}≥50. "
                          f"Кандидат на минусацию."),
            "proposed_action": {
                "tool": "direct.update_negative_sites",
                "args": {"campaign_id": cid, "add_sites": [placement]},
            },
            "ttl_hours": 48,
        })
    # Сортируем по cost desc, лимит 30
    proposals.sort(key=lambda p: -float((p.get("reasoning") or "").split("cost ")[1].split("₽")[0]
                                         if "cost " in (p.get("reasoning") or "") else 0))
    return proposals[:30]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lookback-days", type=int, default=14)
    ap.add_argument("--any-day", action="store_true",
                    help="разрешить запуск НЕ в понедельник (для тестов)")
    args = ap.parse_args()

    today = datetime.date.today()
    if today.weekday() != 0 and not args.any_day:
        print("[]")
        print("(skipping: not Monday — use --any-day to override)", file=sys.stderr)
        return

    yday = today - datetime.timedelta(days=1)
    date_from = (yday - datetime.timedelta(days=args.lookback_days - 1)).isoformat()
    date_to = yday.isoformat()

    rows = yd_pull_placements(date_from, date_to)
    excl = yd_existing_excluded()
    proposals = evaluate(rows, excl, args.lookback_days)
    print(json.dumps(proposals, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
