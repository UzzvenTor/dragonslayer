"""Голиаф v2 — ежедневный отчёт.

Полный самостоятельный pipeline для запуска в Anthropic routine (cloud):
  1. Pull YD Reports API — cost/clicks/impressions per кампания за вчера + MTD
  2. Pull Метрика — уник.рег по цели `unic` 332807191 (KPI лидов)
  3. Pull GetCourse MySQL:
     - cohort viewers через getcourseUsers ∩ bizonViewers по email
     - Bizon-direct viewers для law (особая воронка)
     - getcourseRegistrations как side-метрика
  4. Запись snapshot в YC Postgres `goliath.daily_snapshots` (схема `goliath`)
  5. HTML-отчёт с воронкой → Telegram bot @goliath77_bot

Запуск:
  python daily_report_v2.py            # за вчера
  python daily_report_v2.py 2026-05-04 # за конкретную дату

Все секреты — из .env (создаётся routine prompt'ом перед запуском).
"""
import os, sys, json, time, csv, io, datetime, urllib.request, urllib.parse, urllib.error, socket
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent

# Force IPv4 для Я.Директа на Windows; в Linux безвредно
if hasattr(socket, "AF_INET"):
    _orig = socket.getaddrinfo
    def _ipv4_only(host, *a, **kw):
        return [r for r in _orig(host, *a, **kw) if r[0] == socket.AF_INET] or _orig(host, *a, **kw)
    socket.getaddrinfo = _ipv4_only

# .env
try:
    from dotenv import load_dotenv
    load_dotenv(HERE / ".env")
except ImportError:
    for line in (HERE / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

# ── env
TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]
YD_TOKEN = os.environ["YANDEX_DIRECT_TOKEN"].strip().strip("'").strip('"')
YD_CABINET = os.environ["YD_CABINET"]
YD_CAMPAIGN_IDS = [int(x) for x in os.environ["YD_CAMPAIGN_IDS"].split(",")]
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
PG_PASSWORD = os.environ.get("PG_PASSWORD", os.environ.get("DATABASE_PASSWORD", ""))
PG_DB = os.environ.get("PG_DB", "kurzemnek")

PRODUCTS = ["sysai", "openclaw", "n8n", "law"]
TARGET_CPL = {"sysai": 1077, "openclaw": 1308, "n8n": 1231, "law": 846}
ARPL = {"sysai": 1400, "openclaw": 1700, "n8n": 1600, "law": 1100}
CAMP_TO_PRODUCT = {
    "709513073": "sysai",
    "709513492": "openclaw",
    "709513513": "n8n",
    "709513517": "law",
}
LANDING_TO_PRODUCT = {
    "prompt-engineer-web-9": "sysai",
    "prompt-engineer-web-14": "openclaw",
    "n8n-web-1": "n8n",
    "law-web-1": "law",
}


# ─────────────────────── Я.Директ Reports API ───────────────────────

def yd_pull(date_from, date_to):
    body = {
        "params": {
            "SelectionCriteria": {
                "DateFrom": date_from, "DateTo": date_to,
                "Filter": [{"Field": "CampaignId", "Operator": "IN",
                            "Values": [str(c) for c in YD_CAMPAIGN_IDS]}],
            },
            "Goals": [int(GOAL_REG_ID)],
            "FieldNames": ["CampaignId", "CampaignName", "Impressions", "Clicks", "Cost", "Conversions"],
            "ReportName": f"goliath-v2-{date_from}-{date_to}-{int(time.time())}",
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
    for attempt in range(40):
        try:
            req = urllib.request.Request(
                "https://api.direct.yandex.com/json/v5/reports",
                data=json.dumps(body).encode("utf-8"),
                headers=headers,
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                code = resp.status
                content = resp.read().decode("utf-8")
                if code == 200:
                    break
                time.sleep(8)
        except urllib.error.HTTPError as e:
            if e.code in (201, 202):
                time.sleep(8)
                continue
            raise RuntimeError(f"YD reports HTTP {e.code}: {e.read().decode('utf-8')[:500]}")
    if content is None:
        raise RuntimeError("YD reports не дождался Status=Done")

    rows = []
    reader = csv.DictReader(io.StringIO(content), delimiter="\t")
    for row in reader:
        rows.append({
            "campaign_id": int(row["CampaignId"]),
            "campaign_name": row["CampaignName"],
            "cost_rub": round(float(row.get("Cost") or 0), 2),
            "clicks": int(row.get("Clicks") or 0),
            "impressions": int(row.get("Impressions") or 0),
            "conversions": int(row.get("Conversions") or 0),
        })
    return rows


# ────────────────────────── Метрика ──────────────────────────

def metrika_pull(date_from, date_to):
    params = {
        "ids": METRIKA_COUNTER,
        "date1": date_from, "date2": date_to,
        "metrics": f"ym:s:goal{GOAL_REG_ID}users,ym:s:visits",
        "dimensions": "ym:s:UTMCampaign,ym:s:UTMMedium",
        "filters": "ym:s:UTMSource=='yandex' AND ym:s:UTMMedium=~'^goliath__'",
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
        raise RuntimeError(f"Metrika {e.code}: {body}")
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


# ────────────────────── GetCourse MySQL ──────────────────────

def mysql_conn():
    import pymysql
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME,
        connect_timeout=15, cursorclass=pymysql.cursors.DictCursor,
    )


def fetch_cohort_viewers(date_from, date_to):
    """Cohort: уники goliath__ из getcourseUsers за период ∩ bizonViewers по email.

    Работает для sysai/openclaw/n8n. Для law даст 0 — там воронка через Bizon-direct.
    """
    sql = """
        SELECT
          SUBSTRING(gu.utm_campaign, 1, 15) AS utm_campaign,
          COUNT(DISTINCT gu.email) AS gc_leads,
          COUNT(DISTINCT CASE WHEN bv.email IS NOT NULL THEN gu.email END) AS viewers
        FROM getcourseUsers gu
        LEFT JOIN (
          SELECT DISTINCT email FROM bizonViewers
          WHERE DATE(webinar_date) BETWEEN %s AND %s
        ) bv ON bv.email = gu.email
        WHERE DATE(gu.registration) BETWEEN %s AND %s
          AND SUBSTRING(gu.utm_source, 1, 20) = 'yandex'
          AND gu.utm_medium LIKE 'goliath__%%'
        GROUP BY SUBSTRING(gu.utm_campaign, 1, 15)
    """
    out = {}
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (date_from, date_to, date_from, date_to))
            for r in cur.fetchall():
                out[str(r["utm_campaign"])] = (int(r["gc_leads"]), int(r["viewers"]))
    return out


def fetch_bizon_direct_viewers(date_from, date_to):
    """Для law (Bizon-direct): viewers по landing+goliath UTM без email-сшивки."""
    sql = """
        SELECT SUBSTRING(utm_campaign, 1, 30) AS landing, COUNT(DISTINCT email) AS viewers
        FROM bizonViewers
        WHERE DATE(webinar_date) BETWEEN %s AND %s
          AND SUBSTRING(utm_source, 1, 20) = 'yandex'
          AND utm_medium LIKE 'goliath__%%'
        GROUP BY SUBSTRING(utm_campaign, 1, 30)
    """
    out = {}
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (date_from, date_to))
            for r in cur.fetchall():
                out[r["landing"]] = int(r["viewers"])
    return out


def fetch_gc_registrations(date_from, date_to):
    """Side-метрика: все записи на webinar (включая retention)."""
    sql = """
        SELECT SUBSTRING(utm_campaign, 1, 15) AS utm_campaign, COUNT(DISTINCT uid) AS regs
        FROM getcourseRegistrations
        WHERE DATE(date) BETWEEN %s AND %s
          AND SUBSTRING(utm_source, 1, 20) = 'yandex'
          AND utm_medium LIKE 'goliath__%%'
        GROUP BY SUBSTRING(utm_campaign, 1, 15)
    """
    out = {}
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (date_from, date_to))
            for r in cur.fetchall():
                out[str(r["utm_campaign"])] = int(r["regs"])
    return out


def fetch_payments(date_from, date_to):
    """Оплаты с дедупом по MIN(id) per number, исключая платное участие в вебе."""
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
          AND u.utm_medium LIKE 'goliath__%%'
          AND p.title NOT LIKE '%%платное участие%%'
        GROUP BY u.utm_campaign
    """
    out = {}
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (date_from, date_to))
            for r in cur.fetchall():
                out[str(r["utm_campaign"])] = {
                    "paid_orders": int(r["paid_orders"]),
                    "revenue_rub": float(r["revenue"]),
                }
    return out


# ─────────────────────── Postgres snapshot ───────────────────────

def write_snapshot(snapshot_date, products):
    try:
        import psycopg2
        from psycopg2.extras import Json
    except ImportError:
        print("WARN: psycopg2 not installed — snapshot не записан")
        return False

    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASSWORD,
        dbname=PG_DB, sslmode="require", connect_timeout=15,
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SET search_path TO goliath, public")
            for p_name, d in products.items():
                cur.execute("""
                    INSERT INTO daily_snapshots (
                        snapshot_date, product, cost_rub, clicks, impressions,
                        unique_leads, viewers, viewer_rate_pct,
                        paid_orders, revenue_rub, cpa_rub, roas_pct, raw_data
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (snapshot_date, product) DO UPDATE SET
                        cost_rub=EXCLUDED.cost_rub, clicks=EXCLUDED.clicks,
                        impressions=EXCLUDED.impressions, unique_leads=EXCLUDED.unique_leads,
                        viewers=EXCLUDED.viewers, viewer_rate_pct=EXCLUDED.viewer_rate_pct,
                        paid_orders=EXCLUDED.paid_orders, revenue_rub=EXCLUDED.revenue_rub,
                        cpa_rub=EXCLUDED.cpa_rub, roas_pct=EXCLUDED.roas_pct,
                        raw_data=EXCLUDED.raw_data, fetched_at=now()
                """, (
                    snapshot_date, p_name, d["cost"], d["clicks"], d["impressions"],
                    d["leads"], d["viewers"], d["viewer_rate"],
                    d["paid_orders"], d["revenue"], d["cpa"], d["roas"],
                    Json(d.get("raw", {})),
                ))
        return True
    finally:
        conn.close()


# ─────────────────────── Агрегация ───────────────────────

def short_name(name_or_landing):
    s = (name_or_landing or "").lower()
    if "start-your-business" in s or "prompt-engineer-web-9" in s: return "sysai"
    if "openclaw" in s or "prompt-engineer-web-14" in s: return "openclaw"
    if "n8n" in s: return "n8n"
    if "law" in s: return "law"
    return None


def aggregate(yd_rows, metrika_rows, cohort, bizon_direct, gc_regs, payments):
    """Cobрать per-продукт MTD."""
    products = {p: {
        "cost": 0.0, "clicks": 0, "impressions": 0,
        "leads": 0, "viewers": 0, "paid_orders": 0, "revenue": 0.0,
        "raw": {"cohort_via_email": 0, "bizon_direct": 0, "gc_registrations_side": 0,
                "metrika_unic_leads": 0},
    } for p in PRODUCTS}

    # YD: cost/clicks/impressions
    for r in yd_rows:
        p = CAMP_TO_PRODUCT.get(str(r["campaign_id"])) or short_name(r.get("campaign_name"))
        if not p: continue
        products[p]["cost"] += r["cost_rub"]
        products[p]["clicks"] += r["clicks"]
        products[p]["impressions"] += r["impressions"]

    # Метрика: KPI лидов
    for r in metrika_rows:
        p = CAMP_TO_PRODUCT.get(str(r["utm_campaign"]))
        if not p: continue
        products[p]["leads"] += r["unique_leads"]
        products[p]["raw"]["metrika_unic_leads"] += r["unique_leads"]

    # Cohort viewers через getcourseUsers ∩ bizonViewers (для sysai/openclaw/n8n)
    for camp_id, (gc_leads, viewers) in cohort.items():
        p = CAMP_TO_PRODUCT.get(camp_id)
        if not p or p == "law": continue
        products[p]["viewers"] += viewers
        products[p]["raw"]["cohort_via_email"] += viewers

    # Для law — Bizon-direct viewers через landing
    law_v = bizon_direct.get("law-web-1", 0)
    products["law"]["viewers"] = law_v
    products["law"]["raw"]["bizon_direct"] = law_v

    # gc_regs — side-метрика
    for camp_id, regs in gc_regs.items():
        p = CAMP_TO_PRODUCT.get(camp_id)
        if not p: continue
        products[p]["raw"]["gc_registrations_side"] += regs

    # Payments
    for camp_id, pay in payments.items():
        p = CAMP_TO_PRODUCT.get(camp_id)
        if not p: continue
        products[p]["paid_orders"] += pay["paid_orders"]
        products[p]["revenue"] += pay["revenue_rub"]

    # Производные
    for p, d in products.items():
        d["cpa"] = d["cost"] / d["leads"] if d["leads"] else 0
        d["viewer_rate"] = d["viewers"] / d["leads"] * 100 if d["leads"] else 0
        d["roas"] = d["revenue"] / d["cost"] * 100 if d["cost"] else 0
    return products


# ─────────────────────── Отчёт ───────────────────────

def fmt_rub(n):
    if n is None: return "—"
    return f"{int(round(float(n))):,}".replace(",", " ")


def build_html(snapshot_date, products_yday, products_mtd, mtd_from, states):
    lines = []
    lines.append(f"<b>📊 Голиаф · {snapshot_date}</b>")
    if states:
        all_on = all(v.get("state") == "ON" and v.get("status") == "ACCEPTED" for v in states.values())
        if not all_on:
            lines.append("⚠️ Не все кампании ON — см. логи routine")
    lines.append("")

    # Вчера
    lines.append(f"<b>За вчера ({snapshot_date}):</b>")
    tot_y = {"cost": 0, "leads": 0}
    for p in PRODUCTS:
        d = products_yday[p]
        cpa_str = f"{int(d['cpa'])}₽" if d["leads"] else "—"
        lines.append(f"• {p:8} — {d['leads']} рег / CPA {cpa_str} / расход {fmt_rub(d['cost'])}₽")
        tot_y["cost"] += d["cost"]; tot_y["leads"] += d["leads"]
    tot_y_cpa = tot_y["cost"] / tot_y["leads"] if tot_y["leads"] else 0
    lines.append(f"• <b>TOTAL</b> — {tot_y['leads']} рег / CPA {int(tot_y_cpa) if tot_y['leads'] else '—'}₽ / расход {fmt_rub(tot_y['cost'])}₽")

    # MTD воронка
    lines.append("")
    lines.append(f"<b>Воронка MTD ({mtd_from} → {snapshot_date}):</b>")
    lines.append("<pre>")
    lines.append(f"{'Прод.':8} {'Расход':>8} {'Уник':>5} {'Зрит':>5} {'Дох%':>5} {'Опл':>4} {'CPA':>6}")
    tot = {"cost": 0, "leads": 0, "viewers": 0, "paid": 0, "revenue": 0}
    insights = []
    for p in PRODUCTS:
        d = products_mtd[p]
        target = TARGET_CPL[p]
        cpa_ratio = (d["cpa"] / target) if (d["cpa"] and target) else 0
        if d["leads"] == 0:
            cpa_str = "—"; flag = "⏳"
        else:
            cpa_str = str(int(d["cpa"]))
            if cpa_ratio <= 1.05: flag = "✅"
            elif cpa_ratio <= 1.5: flag = "⚠️"
            else: flag = "🚨"
        lines.append(f"{p:8} {fmt_rub(d['cost']):>8} {d['leads']:>5} {d['viewers']:>5} "
                     f"{int(d['viewer_rate']):>4}% {d['paid_orders']:>4} {cpa_str:>5}{flag}")
        tot["cost"] += d["cost"]; tot["leads"] += d["leads"]; tot["viewers"] += d["viewers"]
        tot["paid"] += d["paid_orders"]; tot["revenue"] += d["revenue"]

        # Инсайты
        if d["leads"] > 0 and d["viewers"] == 0:
            insights.append(f"🚨 <b>{p}</b>: {d['leads']} уник.рег, 0 дошли до веба. "
                            f"CPA {int(d['cpa'])}₽ — деньги в холостую. Сигнал на пересмотр.")
        elif d["leads"] >= 2 and cpa_ratio > 1.5:
            insights.append(f"⚠️ <b>{p}</b>: CPA {int(d['cpa'])}₽ = {cpa_ratio:.1f}× target {target}₽. "
                            f"Порог стопа адсета 5×ARPL = {ARPL[p]*5}₽.")

    tot_cpa = tot["cost"] / tot["leads"] if tot["leads"] else 0
    tot_rate = tot["viewers"] / tot["leads"] * 100 if tot["leads"] else 0
    tot_roas = tot["revenue"] / tot["cost"] * 100 if tot["cost"] else 0
    lines.append(f"{'TOTAL':8} {fmt_rub(tot['cost']):>8} {tot['leads']:>5} {tot['viewers']:>5} "
                 f"{int(tot_rate):>4}% {tot['paid']:>4} {int(tot_cpa):>5}")
    lines.append("</pre>")

    if tot["paid"]:
        lines.append(f"<b>💰 Выручка MTD:</b> {fmt_rub(tot['revenue'])}₽ · ROAS {int(tot_roas)}%")

    if insights:
        lines.append("")
        lines.append("<b>💡 Инсайты:</b>")
        for ins in insights:
            lines.append(f"• {ins}")

    # Side
    side_regs = sum(products_mtd[p]["raw"]["gc_registrations_side"] for p in PRODUCTS)
    lines.append("")
    lines.append("<i>📋 Заметки:</i>")
    lines.append("• KPI = Метрика-уник.рег (цель <code>unic</code> 332807191); зрители — cohort по уникам через email")
    if products_mtd["law"]["viewers"]:
        lines.append("• <b>law</b> — Bizon-direct воронка (форма обходит getcourseRegistrations)")
    if side_regs:
        lines.append(f"• Side: записей на webinar за MTD — {side_regs} (KPI ещё не зашит)")
    lines.append("• 0 продаж = норма для цикла сделки 10 дней; первые оплаты ждём через ~10д от старта")

    return "\n".join(lines)


def send_tg(html):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": TG_CHAT_ID, "text": html,
        "parse_mode": "HTML", "disable_web_page_preview": "true",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def get_states():
    """Pull текущих state per кампания через campaigns/get."""
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
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
        out = {}
        for c in (data.get("result", {}) or {}).get("Campaigns", []):
            out[str(c["Id"])] = {
                "name": c.get("Name"), "state": c.get("State"),
                "status": c.get("Status"), "payment": c.get("StatusPayment"),
            }
        return out
    except Exception as e:
        print(f"WARN: states pull failed: {e}")
        return {}


# ─────────────────────── main ───────────────────────

def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg:
        yday = datetime.date.fromisoformat(arg)
    else:
        yday = datetime.date.today() - datetime.timedelta(days=1)
    mtd_from = yday.replace(day=1)
    yday_s = yday.isoformat()
    mtd_from_s = mtd_from.isoformat()

    print(f"=== Голиаф v2 · {yday_s} ===\n")

    print("[1/8] YD за вчера...")
    yd_yday = yd_pull(yday_s, yday_s)
    print("[2/8] YD за MTD...")
    yd_mtd = yd_pull(mtd_from_s, yday_s)
    print("[3/8] Метрика за вчера + MTD...")
    metrika_yday = metrika_pull(yday_s, yday_s)
    metrika_mtd = metrika_pull(mtd_from_s, yday_s)
    print("[4/8] GetCourse — cohort viewers...")
    cohort = fetch_cohort_viewers(mtd_from_s, yday_s)
    bizon_direct = fetch_bizon_direct_viewers(mtd_from_s, yday_s)
    print("[5/8] GetCourse — registrations side-metric...")
    gc_regs = fetch_gc_registrations(mtd_from_s, yday_s)
    print("[6/8] GetCourse — payments...")
    payments = fetch_payments(mtd_from_s, yday_s)

    # Cohort за вчера тоже
    cohort_yday = fetch_cohort_viewers(yday_s, yday_s)
    bizon_direct_yday = fetch_bizon_direct_viewers(yday_s, yday_s)
    gc_regs_yday = fetch_gc_registrations(yday_s, yday_s)
    payments_yday = fetch_payments(yday_s, yday_s)

    print("[7/8] Агрегация...")
    products_yday = aggregate(yd_yday, metrika_yday, cohort_yday, bizon_direct_yday, gc_regs_yday, payments_yday)
    products_mtd = aggregate(yd_mtd, metrika_mtd, cohort, bizon_direct, gc_regs, payments)

    states = get_states()

    print("[8/8] Запись snapshot в YC Postgres...")
    ok = write_snapshot(yday_s, products_mtd)
    print(f"    snapshot saved: {ok}")

    html = build_html(yday_s, products_yday, products_mtd, mtd_from_s, states)
    print("\n=== HTML отчёт ===")
    print(html.replace("<b>", "").replace("</b>", "").replace("<pre>", "").replace("</pre>", "")
              .replace("<i>", "").replace("</i>", "").replace("<code>", "").replace("</code>", ""))

    if "--dry-run" in sys.argv:
        print("\n--- DRY RUN, не отправляем в ТГ ---")
        return

    print("\nОтправка в ТГ...")
    resp = send_tg(html)
    print(f"TG: ok={resp.get('ok')}, msg_id={resp.get('result', {}).get('message_id')}")
    if not resp.get("ok"):
        print(f"TG full response: {resp}")
        sys.exit(1)


if __name__ == "__main__":
    main()
