"""Локальный YD-pull → YC Postgres `goliath.yd_raw_pulls`.

Запускается на ноуте Валерия (Windows Task Scheduler). Здесь IP — в whitelist'е
Я.Директа, поэтому работает. Cloud-routine утром читает свежий snapshot из этой
таблицы вместо вызова YD API.

Запуск:
    python yd_pull_local.py

Можно явно: --date 2026-05-04 (только этот день + MTD)
"""
import os, sys, json, time, csv, io, datetime, urllib.request, urllib.error, socket
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent

# IPv4 для Я.Директа
_orig = socket.getaddrinfo
socket.getaddrinfo = lambda h, *a, **k: [r for r in _orig(h, *a, **k) if r[0] == socket.AF_INET] or _orig(h, *a, **k)

try:
    from dotenv import load_dotenv
    load_dotenv(HERE / ".env")
except ImportError:
    for line in (HERE / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

YD_TOKEN = os.environ["YANDEX_DIRECT_TOKEN"].strip().strip("'").strip('"')
YD_CABINET = os.environ["YD_CABINET"]
YD_CAMPAIGN_IDS = [int(x) for x in os.environ["YD_CAMPAIGN_IDS"].split(",")]
GOAL_REG_ID = os.environ["GOAL_REG_ID"]

PG_HOST = os.environ.get("PG_HOST", "rc1b-nftoajilh0nnj0gf.mdb.yandexcloud.net")
PG_PORT = int(os.environ.get("PG_PORT", 6432))
PG_USER = os.environ.get("PG_USER", "kurzemnek_app")
PG_PASSWORD = os.environ["PG_PASSWORD"]
PG_DB = os.environ.get("PG_DB", "kurzemnek")


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
            "ReportName": f"goliath-pull-{date_from}-{date_to}-{int(time.time())}",
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
        req = urllib.request.Request(
            "https://api.direct.yandex.com/json/v5/reports",
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
        )
        try:
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
        raise RuntimeError("YD reports timeout")

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


def write_pulls(date_from, date_to, rows):
    import psycopg2
    from psycopg2.extras import Json
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASSWORD,
        dbname=PG_DB, sslmode="require", connect_timeout=15,
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SET search_path TO goliath, public")
            for r in rows:
                cur.execute("""
                    INSERT INTO yd_raw_pulls
                      (date_from, date_to, campaign_id, campaign_name,
                       cost_rub, clicks, impressions, conversions, raw)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (date_from, date_to, r["campaign_id"], r["campaign_name"],
                      r["cost_rub"], r["clicks"], r["impressions"], r["conversions"],
                      Json(r)))
        return len(rows)
    finally:
        conn.close()


def main():
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "--date":
        yday = datetime.date.fromisoformat(args[1])
    else:
        yday = datetime.date.today() - datetime.timedelta(days=1)
    mtd_from = yday.replace(day=1)

    print(f"=== YD pull @ {datetime.datetime.now().isoformat(timespec='seconds')} ===")
    print(f"Pulling YD: yday={yday}, MTD={mtd_from}..{yday}")

    print(f"\n[1/2] Pull yday {yday}...")
    rows_yday = yd_pull(yday.isoformat(), yday.isoformat())
    n = write_pulls(yday.isoformat(), yday.isoformat(), rows_yday)
    print(f"  → {n} rows written for yday")

    print(f"\n[2/2] Pull MTD {mtd_from}..{yday}...")
    rows_mtd = yd_pull(mtd_from.isoformat(), yday.isoformat())
    n = write_pulls(mtd_from.isoformat(), yday.isoformat(), rows_mtd)
    print(f"  → {n} rows written for MTD")

    print(f"\n✓ Done")


if __name__ == "__main__":
    main()
