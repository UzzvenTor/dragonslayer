"""skill-snapshots — UPSERT в goliath.daily_snapshots.

Запуск:
    python save.py --file snap.json
    python skill-analytics/snapshot.py | python save.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "routines"))
from _lib.common import load_env, pg_conn  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
load_env()


SQL = """
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
"""


def save(snap: dict) -> int:
    """Вставляет/обновляет 4 продуктовые строки. Возвращает кол-во записанных."""
    from psycopg2.extras import Json
    snapshot_date = snap["yday_date"]
    mtd_rows = (snap.get("mtd") or {}).get("per_product") or []
    yday_rows = {r["product"]: r for r in (snap.get("yday") or {}).get("per_product") or []}
    week_rows = {r["product"]: r for r in (snap.get("week") or {}).get("per_product") or []}

    written = 0
    try:
        conn = pg_conn(autocommit=True)
    except OSError as e:
        print(f"WARN snapshots: {e} — skipping persist", file=sys.stderr)
        return 0

    try:
        with conn.cursor() as cur:
            for r in mtd_rows:
                p = r["product"]
                raw_data = {
                    "yday": yday_rows.get(p),
                    "week": week_rows.get(p),
                    "raw": r.get("raw") or {},
                    "fetched_at": snap.get("fetched_at"),
                    "errors": snap.get("errors") or [],
                    "states": snap.get("states") or {},
                }
                cur.execute(SQL, (
                    snapshot_date, p,
                    r.get("cost_rub", 0), r.get("clicks", 0), r.get("impressions", 0),
                    r.get("leads", 0), r.get("viewers", 0), r.get("viewer_rate_pct", 0),
                    r.get("paid_orders", 0), r.get("revenue_rub", 0),
                    r.get("cpa_rub", 0), r.get("roas_pct", 0),
                    Json(raw_data),
                ))
                written += 1
    finally:
        conn.close()
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="JSON snapshot; иначе stdin")
    args = ap.parse_args()

    text = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
    snap = json.loads(text)
    n = save(snap)
    print(f"snapshots saved: {n} rows for {snap.get('yday_date')}")


if __name__ == "__main__":
    main()
