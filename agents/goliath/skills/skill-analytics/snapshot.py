"""skill-analytics — read-only pull данных Голиафа.

Запуск:
    python snapshot.py [--date YYYY-MM-DD] [--out path.json]

Эмитит на stdout полный snapshot (3 окна × per-product + states + errors).
По умолчанию date = вчера. Если --out указан — пишет в файл, иначе stdout.

Источники: Я.Директ Reports API, Метрика Reports API, GetCourse MySQL.
Source-of-truth по лидам = Метрика, цель `unic` (332807191).

Контракт описан в SKILL.md, спека — Wiki/.../skill-analytics.md.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import io
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent

# ─── IPv4 force для api.direct.yandex.com на Windows ───
if hasattr(socket, "AF_INET"):
    _orig = socket.getaddrinfo
    def _ipv4_only(host, *a, **kw):
        return [r for r in _orig(host, *a, **kw) if r[0] == socket.AF_INET] or _orig(host, *a, **kw)
    socket.getaddrinfo = _ipv4_only

# ─── .env loader (idempotent, не override env vars из routine) ───
# Cloud routine инжектит env через routine config — .env файла может не быть.
# Local-режим — .env лежит рядом или в legacy goliath_daily/.
_ENV_PATHS = [
    HERE / ".env",                          # рядом со скиллом
    HERE / ".." / ".." / ".env",            # agents/goliath/.env
]
_LEGACY_LOCAL_ENV = Path(r"I:\neuro\GENERAL CLAUDE CODE\Zerocoder\dragonslayer\goliath_daily\.env")
if _LEGACY_LOCAL_ENV.exists():
    _ENV_PATHS.append(_LEGACY_LOCAL_ENV)
try:
    from dotenv import load_dotenv
    for p in _ENV_PATHS:
        if p.exists():
            load_dotenv(p)
            break
except ImportError:
    for p in _ENV_PATHS:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
        break

YD_TOKEN = (os.environ.get("YANDEX_DIRECT_TOKEN") or "").strip().strip("'").strip('"')
YD_CABINET = os.environ.get("YD_CABINET", "porg-6vgf2ozq")
YD_CAMPAIGN_IDS = [int(x) for x in os.environ["YD_CAMPAIGN_IDS"].split(",")]
# Cloud routine не имеет доступа к Я.Директ API (IP whitelist). Hybrid-режим
# читает YD-данные из goliath.yd_raw_pulls (заполняется локальным cron).
YD_FROM_PG = os.environ.get("YD_FROM_PG", "0").lower() in ("1", "true", "yes") or not YD_TOKEN
METRIKA_TOKEN = os.environ["YANDEX_METRIKA_TOKEN"]
METRIKA_COUNTER = os.environ["METRIKA_COUNTER_ID"]
GOAL_REG_ID = os.environ["GOAL_REG_ID"]
DB_HOST = os.environ["DB_HOST"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_NAME = os.environ["DB_NAME"]
DB_PORT = int(os.environ.get("DB_PORT", 3306))
PG_HOST = os.environ.get("PG_HOST", "rc1b-nftoajilh0nnj0gf.mdb.yandexcloud.net")
PG_PORT = int(os.environ.get("PG_PORT", 6432))
PG_USER = os.environ.get("PG_USER", "kurzemnek_app")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "")
PG_DB = os.environ.get("PG_DB", "kurzemnek")

# ─── Маппинги (источник — Wiki/shared/agents/Голиаф v2 — спецификация агента.md) ───
PRODUCTS = ["sysai", "openclaw", "n8n", "law"]
TARGET_CPL = {"sysai": 1077, "openclaw": 1308, "n8n": 1231, "law": 846}
ARPL = {"sysai": 1400, "openclaw": 1700, "n8n": 1600, "law": 1100}

CAMP_TO_PRODUCT = {
    # H07 (контрольная группа, 2026-04-30)
    "709513073": "sysai",
    "709513492": "openclaw",
    "709513513": "n8n",
    "709513517": "law",
    # H08 (комбинаторные ЕПК, 2026-05-06)
    "709674000": "sysai",
    "709674060": "openclaw",
    "709674103": "n8n",
    "709674151": "law",
}

# Лендинг-слаг → продукт. Fallback когда utm_campaign в getcourseUsers/Метрике
# = slug лендинга, а не campaign_id.
LANDING_TO_PRODUCT = {
    "prompt-engineer-web-9": "sysai",
    "prompt-engineer-web-14": "openclaw",
    "n8n-web-1": "n8n",
    "law-web-1": "law",
}


def _resolve_product(key) -> str | None:
    return CAMP_TO_PRODUCT.get(str(key)) or LANDING_TO_PRODUCT.get(str(key))


# ─── Я.Директ Reports API ───

def yd_pull(date_from: str, date_to: str) -> list[dict]:
    body = {
        "params": {
            "SelectionCriteria": {
                "DateFrom": date_from, "DateTo": date_to,
                "Filter": [{"Field": "CampaignId", "Operator": "IN",
                            "Values": [str(c) for c in YD_CAMPAIGN_IDS]}],
            },
            "Goals": [int(GOAL_REG_ID)],
            "FieldNames": ["CampaignId", "CampaignName", "Impressions", "Clicks", "Cost", "Conversions"],
            "ReportName": f"goliath-snapshot-{date_from}-{date_to}-{int(time.time())}",
            "ReportType": "CAMPAIGN_PERFORMANCE_REPORT",
            "DateRangeType": "CUSTOM_DATE",
            "Format": "TSV",
            "IncludeVAT": "YES",
            "IncludeDiscount": "NO",
        }
    }
    headers = {
        "Authorization": f"Bearer {YD_TOKEN}",
        "Accept-Language": "ru",
        "Client-Login": YD_CABINET,
        "processingMode": "auto",
        "returnMoneyInMicros": "false",
        "skipReportHeader": "true",
        "skipColumnHeader": "false",
        "skipReportSummary": "true",
    }
    content = None
    for _ in range(40):
        try:
            req = urllib.request.Request(
                "https://api.direct.yandex.com/json/v5/reports",
                data=json.dumps(body).encode("utf-8"),
                headers=headers,
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                if resp.status == 200:
                    content = resp.read().decode("utf-8")
                    break
                time.sleep(8)
        except urllib.error.HTTPError as e:
            if e.code in (201, 202):
                time.sleep(8)
                continue
            raise RuntimeError(f"YD reports HTTP {e.code}: {e.read().decode('utf-8')[:500]}") from None
    if content is None:
        raise RuntimeError("YD reports не дождался Status=Done за 40 попыток")

    rows = []
    for row in csv.DictReader(io.StringIO(content), delimiter="\t"):
        rows.append({
            "campaign_id": int(row["CampaignId"]),
            "campaign_name": row["CampaignName"],
            "cost_rub": round(float(row.get("Cost") or 0), 2),
            "clicks": int(row.get("Clicks") or 0),
            "impressions": int(row.get("Impressions") or 0),
            "conversions": int(row.get("Conversions") or 0),
        })
    return rows


def yd_pull_from_pg(date_from: str, date_to: str) -> list[dict]:
    """Hybrid-режим: читает последний pull из goliath.yd_raw_pulls.
    Используется в cloud routine, где Я.Директ API недоступен (IP whitelist)."""
    import psycopg2
    if not PG_PASSWORD:
        raise RuntimeError("YD_FROM_PG=1 но PG_PASSWORD пуст")
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASSWORD,
        dbname=PG_DB, sslmode="require", connect_timeout=15,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SET search_path TO goliath, public")
            cur.execute("""
                SELECT campaign_id, campaign_name, cost_rub, clicks, impressions, conversions
                FROM v_yd_latest_pull
                WHERE date_from = %s AND date_to = %s
                ORDER BY campaign_id
            """, (date_from, date_to))
            return [{
                "campaign_id": int(r[0]),
                "campaign_name": r[1] or "",
                "cost_rub": float(r[2] or 0),
                "clicks": int(r[3] or 0),
                "impressions": int(r[4] or 0),
                "conversions": int(r[5] or 0),
            } for r in cur.fetchall()]
    finally:
        conn.close()


def yd_pull_auto(date_from: str, date_to: str) -> list[dict]:
    """Hybrid-aware wrapper: API в локальном режиме, Postgres в cloud."""
    if YD_FROM_PG:
        return yd_pull_from_pg(date_from, date_to)
    return yd_pull(date_from, date_to)


def yd_states() -> dict:
    if YD_FROM_PG or not YD_TOKEN:
        # Cloud-режим: states нет в hybrid-PG. Возвращаем пусто, отчёт без блока state.
        return {}
    body = {
        "method": "get",
        "params": {
            "SelectionCriteria": {"Ids": [int(c) for c in YD_CAMPAIGN_IDS]},
            "FieldNames": ["Id", "Name", "State", "Status", "StatusPayment"],
        }
    }
    req = urllib.request.Request(
        "https://api.direct.yandex.com/json/v5/campaigns",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {YD_TOKEN}",
            "Accept-Language": "ru",
            "Client-Login": YD_CABINET,
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    out = {}
    for c in (data.get("result", {}) or {}).get("Campaigns", []):
        out[str(c["Id"])] = {
            "name": c.get("Name"), "state": c.get("State"),
            "status": c.get("Status"), "payment": c.get("StatusPayment"),
        }
    return out


# ─── Метрика Reports API ───

def metrika_pull(date_from: str, date_to: str) -> list[dict]:
    params = {
        "ids": METRIKA_COUNTER,
        "date1": date_from, "date2": date_to,
        "metrics": f"ym:s:goal{GOAL_REG_ID}users,ym:s:visits",
        "dimensions": "ym:s:UTMCampaign,ym:s:UTMMedium",
        "filters": "ym:s:UTMSource=='yandex' AND ym:s:UTMMedium=~'^goliath'",
        "limit": 5000,
        "accuracy": "full",
    }
    url = "https://api-metrika.yandex.net/stat/v1/data?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"OAuth {METRIKA_TOKEN}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")[:500]
        raise RuntimeError(f"Metrika {e.code}: {body}") from None
    out = []
    for row in data.get("data", []):
        dims = row.get("dimensions", [])
        m = row.get("metrics", [])
        if len(dims) < 2 or len(m) < 1:
            continue
        out.append({
            "utm_campaign": dims[0].get("name", ""),
            "utm_medium": dims[1].get("name", ""),
            "unique_leads": int(m[0] or 0),
            "visits": int(m[1] or 0) if len(m) > 1 else 0,
        })
    return out


# ─── GetCourse MySQL ───

def _mysql_conn():
    import pymysql
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME,
        connect_timeout=15, cursorclass=pymysql.cursors.DictCursor,
    )


def cohort_viewers(date_from: str, date_to: str) -> dict:
    """getcourseUsers ∩ bizonViewers по email. Для sysai/openclaw/n8n."""
    sql = """
        SELECT
          SUBSTRING(gu.utm_campaign, 1, 30) AS utm_campaign,
          COUNT(DISTINCT gu.email) AS gc_leads,
          COUNT(DISTINCT CASE WHEN bv.email IS NOT NULL THEN gu.email END) AS viewers
        FROM getcourseUsers gu
        LEFT JOIN (
          SELECT DISTINCT email FROM bizonViewers
          WHERE DATE(webinar_date) BETWEEN %s AND %s
        ) bv ON bv.email = gu.email
        WHERE DATE(gu.registration) BETWEEN %s AND %s
          AND SUBSTRING(gu.utm_source, 1, 20) = 'yandex'
          AND gu.utm_medium LIKE 'goliath%%'
        GROUP BY SUBSTRING(gu.utm_campaign, 1, 30)
    """
    out = {}
    with _mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (date_from, date_to, date_from, date_to))
            for r in cur.fetchall():
                out[str(r["utm_campaign"])] = {"gc_leads": int(r["gc_leads"]),
                                                "viewers": int(r["viewers"])}
    return out


def bizon_direct_viewers(date_from: str, date_to: str) -> dict:
    """Для law (Bizon-direct): viewers по landing+goliath UTM без email-сшивки."""
    sql = """
        SELECT SUBSTRING(utm_campaign, 1, 30) AS landing, COUNT(DISTINCT email) AS viewers
        FROM bizonViewers
        WHERE DATE(webinar_date) BETWEEN %s AND %s
          AND SUBSTRING(utm_source, 1, 20) = 'yandex'
          AND utm_medium LIKE 'goliath%%'
        GROUP BY SUBSTRING(utm_campaign, 1, 30)
    """
    out = {}
    with _mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (date_from, date_to))
            for r in cur.fetchall():
                out[r["landing"]] = int(r["viewers"])
    return out


def gc_registrations(date_from: str, date_to: str) -> dict:
    """Side-метрика: все записи на webinar (включая retention). НЕ KPI."""
    sql = """
        SELECT SUBSTRING(utm_campaign, 1, 30) AS utm_campaign, COUNT(DISTINCT uid) AS regs
        FROM getcourseRegistrations
        WHERE DATE(date) BETWEEN %s AND %s
          AND SUBSTRING(utm_source, 1, 20) = 'yandex'
          AND utm_medium LIKE 'goliath%%'
        GROUP BY SUBSTRING(utm_campaign, 1, 30)
    """
    out = {}
    with _mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (date_from, date_to))
            for r in cur.fetchall():
                out[str(r["utm_campaign"])] = int(r["regs"])
    return out


def payments(date_from: str, date_to: str) -> dict:
    """Оплаты с дедупом по MIN(id) per number, исключая платное участие."""
    sql = """
        SELECT u.utm_campaign,
               COUNT(DISTINCT p.number) AS paid_orders,
               COALESCE(SUM(p.amount), 0) AS revenue
        FROM getcoursePayments p
        JOIN getcourseUsers u ON p.email = u.email
        WHERE DATE(p.date_created) BETWEEN %s AND %s
          AND p.status = 'Получен'
          AND p.id = (SELECT MIN(p2.id) FROM getcoursePayments p2 WHERE p2.number = p.number)
          AND SUBSTRING(u.utm_source, 1, 20) = 'yandex'
          AND u.utm_medium LIKE 'goliath%%'
          AND p.title NOT LIKE '%%платное участие%%'
        GROUP BY u.utm_campaign
    """
    out = {}
    with _mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (date_from, date_to))
            for r in cur.fetchall():
                out[str(r["utm_campaign"])] = {
                    "paid_orders": int(r["paid_orders"]),
                    "revenue_rub": float(r["revenue"]),
                }
    return out


# ─── Окна ───

def windows_for(yday: datetime.date) -> dict[str, tuple[datetime.date, datetime.date]]:
    week_start = yday - datetime.timedelta(days=yday.weekday())  # понедельник недели yday
    mtd_start = yday.replace(day=1)
    return {
        "yday": (yday, yday),
        "week": (week_start, yday),
        "mtd":  (mtd_start, yday),
    }


# ─── Агрегация ───

def aggregate(yd_rows: list[dict], metrika_rows: list[dict],
              cohort: dict, bizon_direct: dict,
              gc_regs: dict, pmts: dict, full_funnel: bool) -> dict:
    """Per-product aggregate. Если full_funnel=False (yday/week) — только cost/clicks/leads/cpa."""
    products = {p: {
        "cost": 0.0, "clicks": 0, "impressions": 0,
        "leads": 0,
        "viewers": 0,             # NEW acquisition (зарегился в периоде через Голиаф И дошёл)
        "viewers_retention": 0,   # старый лид пришёл на свежий голиаф-вебинар
        "paid_orders": 0, "revenue": 0.0,
        "leads_yd": 0,  # cross-check, не KPI
        "raw": {"cohort_via_email": 0, "bizon_direct_total": 0,
                "gc_registrations_side": 0, "metrika_unic_leads": 0},
    } for p in PRODUCTS}

    for r in yd_rows:
        p = _resolve_product(r["campaign_id"])
        if not p:
            continue
        products[p]["cost"] += r["cost_rub"]
        products[p]["clicks"] += r["clicks"]
        products[p]["impressions"] += r["impressions"]
        products[p]["leads_yd"] += r["conversions"]

    for r in metrika_rows:
        p = _resolve_product(r["utm_campaign"])
        if not p:
            continue
        products[p]["leads"] += r["unique_leads"]
        products[p]["raw"]["metrika_unic_leads"] += r["unique_leads"]

    if full_funnel:
        # Frame D из методологии атрибуции:
        #   NEW (acquisition)   = свежий голиаф-лид, который дошёл до веба
        #   RETURNING (retention) = старый лид Зерокодера на свежем голиаф-вебинаре
        # Главная метрика для доходимости = NEW (subset регистраций периода).
        # RETURNING — отдельно как индикатор «вторичной» воронки.
        # Spec: [[Голиаф-выручка — 4 фрейма атрибуции]], память
        # [[KPI = Метрика-уник.рег; зрители = …]].
        product_to_landings = {
            "sysai":    ["prompt-engineer-web-9"],
            "openclaw": ["prompt-engineer-web-14"],
            "n8n":      ["n8n-web-1"],
            "law":      ["law-web-1"],
        }

        # 1. cohort_via_email — NEW acquisition для sysai/openclaw/n8n
        for camp_key, c in cohort.items():
            p = _resolve_product(camp_key)
            if not p:
                continue
            products[p]["raw"]["cohort_via_email"] += c["viewers"]

        # 2. bizon_total — общее число зрителей с голиаф UTM на лендинге продукта
        for p, landings in product_to_landings.items():
            bizon_total = sum(bizon_direct.get(slug, 0) for slug in landings)
            cohort_new = products[p]["raw"]["cohort_via_email"]
            products[p]["raw"]["bizon_direct_total"] = bizon_total

            if p == "law":
                # Bizon-direct path: регистрация и просмотр оба через bizon,
                # все viewers — NEW для текущего периода (form fired Метрика
                # `unic` в этом периоде).
                products[p]["viewers"] = bizon_total
                products[p]["viewers_retention"] = 0
            else:
                # Стандартный путь: NEW = cohort, RETURNING = разница.
                products[p]["viewers"] = cohort_new
                products[p]["viewers_retention"] = max(bizon_total - cohort_new, 0)

        for camp_key, regs in gc_regs.items():
            p = _resolve_product(camp_key)
            if not p:
                continue
            products[p]["raw"]["gc_registrations_side"] += regs

        for camp_key, pay in pmts.items():
            p = _resolve_product(camp_key)
            if not p:
                continue
            products[p]["paid_orders"] += pay["paid_orders"]
            products[p]["revenue"] += pay["revenue_rub"]

    # Производные
    for p, d in products.items():
        d["cpa_rub"] = round(d["cost"] / d["leads"], 2) if d["leads"] else 0
        d["viewer_rate_pct"] = round(d["viewers"] / d["leads"] * 100, 1) if d["leads"] else 0
        d["roas_pct"] = round(d["revenue"] / d["cost"] * 100, 1) if d["cost"] else 0
        d["cost_rub"] = round(d["cost"], 2)
        d["revenue_rub"] = round(d["revenue"], 2)
        d.pop("cost"); d.pop("revenue")

    per_product = []
    total = {"product": "TOTAL", "cost_rub": 0.0, "clicks": 0, "impressions": 0,
             "leads": 0, "viewers": 0, "viewers_retention": 0,
             "paid_orders": 0, "revenue_rub": 0.0, "leads_yd": 0}
    for p in PRODUCTS:
        d = products[p]
        per_product.append({"product": p, **d})
        for k in ("cost_rub", "clicks", "impressions", "leads", "viewers",
                  "viewers_retention", "paid_orders", "revenue_rub", "leads_yd"):
            total[k] += d[k]
    total["cost_rub"] = round(total["cost_rub"], 2)
    total["revenue_rub"] = round(total["revenue_rub"], 2)
    total["cpa_rub"] = round(total["cost_rub"] / total["leads"], 2) if total["leads"] else 0
    total["viewer_rate_pct"] = (round(total["viewers"] / total["leads"] * 100, 1)
                                 if total["leads"] else 0)
    total["roas_pct"] = (round(total["revenue_rub"] / total["cost_rub"] * 100, 1)
                          if total["cost_rub"] else 0)
    return {"per_product": per_product, "total": total}


# ─── main ───

def build_snapshot(yday: datetime.date) -> dict:
    wins = windows_for(yday)
    errors = []

    def safe(fn, *args, _label=""):
        try:
            return fn(*args)
        except Exception as e:
            errors.append({"step": _label, "error": str(e)[:300]})
            return None

    yday_s = wins["yday"][0].isoformat()
    week_from_s, week_to_s = wins["week"][0].isoformat(), wins["week"][1].isoformat()
    mtd_from_s, mtd_to_s = wins["mtd"][0].isoformat(), wins["mtd"][1].isoformat()

    # YD per window (auto: API локально, Postgres hybrid в cloud)
    yd_yday = safe(yd_pull_auto, yday_s, yday_s, _label="yd_pull/yday") or []
    yd_week = safe(yd_pull_auto, week_from_s, week_to_s, _label="yd_pull/week") or []
    yd_mtd = safe(yd_pull_auto, mtd_from_s, mtd_to_s, _label="yd_pull/mtd") or []

    # Метрика per window
    m_yday = safe(metrika_pull, yday_s, yday_s, _label="metrika/yday") or []
    m_week = safe(metrika_pull, week_from_s, week_to_s, _label="metrika/week") or []
    m_mtd = safe(metrika_pull, mtd_from_s, mtd_to_s, _label="metrika/mtd") or []

    # Воронка только для MTD
    coh = safe(cohort_viewers, mtd_from_s, mtd_to_s, _label="cohort") or {}
    biz = safe(bizon_direct_viewers, mtd_from_s, mtd_to_s, _label="bizon_direct") or {}
    gcr = safe(gc_registrations, mtd_from_s, mtd_to_s, _label="gc_regs") or {}
    pay = safe(payments, mtd_from_s, mtd_to_s, _label="payments") or {}

    states = safe(yd_states, _label="yd_states") or {}

    return {
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "yday_date": yday_s,
        "windows": {"yday": [yday_s, yday_s],
                    "week": [week_from_s, week_to_s],
                    "mtd": [mtd_from_s, mtd_to_s]},
        "yday": aggregate(yd_yday, m_yday, {}, {}, {}, {}, full_funnel=False),
        "week": aggregate(yd_week, m_week, {}, {}, {}, {}, full_funnel=False),
        "mtd":  aggregate(yd_mtd, m_mtd, coh, biz, gcr, pay, full_funnel=True),
        "states": states,
        "errors": errors,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="yday в формате YYYY-MM-DD; по умолчанию today-1")
    ap.add_argument("--out", help="путь для записи JSON; по умолчанию stdout")
    args = ap.parse_args()

    yday = (datetime.date.fromisoformat(args.date) if args.date
            else datetime.date.today() - datetime.timedelta(days=1))
    snap = build_snapshot(yday)
    text = json.dumps(snap, ensure_ascii=False, indent=2)

    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"snapshot written to {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
