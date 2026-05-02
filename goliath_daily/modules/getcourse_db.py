"""Зрители (bizonViewers) и продажи (getcoursePayments) per кампания Голиафа из MySQL."""
import os, json, sys

# shared_local импортируется из dragonslayer/. Поддерживаем 2 размещения goliath_daily:
#   - вложено: dragonslayer/goliath_daily/  (production, GitHub)
#   - рядом:   Zerocoder/goliath_daily/     (legacy local)
_HERE = os.path.dirname(__file__)
for _cand in (
    os.path.join(_HERE, '..', '..'),                  # вложенный
    os.path.join(_HERE, '..', '..', 'dragonslayer'),  # legacy
):
    if os.path.isdir(os.path.join(_cand, 'shared_local')):
        sys.path.insert(0, os.path.abspath(_cand))
        break

try:
    from shared_local.db import get_conn
except ImportError:
    get_conn = None


def _viewers_query(date_from: str, date_to: str) -> list[dict]:
    if get_conn is None:
        return [{'_error':'shared_local недоступен — поставь dragonslayer/shared_local рядом'}]
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT SUBSTRING(utm_campaign,1,255) AS utm_campaign,
                   SUBSTRING(utm_medium,1,255) AS utm_medium,
                   COUNT(DISTINCT SUBSTRING(email,1,255)) AS viewers
            FROM bizonViewers
            WHERE DATE(webinar_date) BETWEEN %s AND %s
              AND SUBSTRING(utm_source,1,50) = 'yandex'
              AND utm_medium LIKE 'goliath__%%'
            GROUP BY SUBSTRING(utm_campaign,1,255), SUBSTRING(utm_medium,1,255)
            ORDER BY viewers DESC
        """, [date_from, date_to])
        return [dict(r) for r in cur.fetchall()]
    finally:
        try: conn.close()
        except: pass


def _payments_query(date_from: str, date_to: str) -> list[dict]:
    if get_conn is None:
        return [{'_error':'shared_local недоступен'}]
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                SUBSTRING(m.utm_campaign,1,255) AS utm_campaign,
                SUBSTRING(m.utm_medium,1,255) AS utm_medium,
                COUNT(DISTINCT p.number) AS sales,
                ROUND(SUM(p.amount), 0) AS revenue
            FROM getcoursePayments p
            JOIN getcourseUsers u ON p.email = u.email
            JOIN main_yandex m ON u.gcuid = m.uid
            WHERE DATE(p.date_created) BETWEEN %s AND %s
              AND p.status = 'Получен'
              AND SUBSTRING(m.utm_source,1,50) = 'yandex'
              AND m.utm_medium LIKE 'goliath__%%'
            GROUP BY SUBSTRING(m.utm_campaign,1,255), SUBSTRING(m.utm_medium,1,255)
            ORDER BY revenue DESC
        """, [date_from, date_to])
        return [dict(r) for r in cur.fetchall()]
    finally:
        try: conn.close()
        except: pass


def fetch_viewers(yday: str) -> list[dict]:
    return _viewers_query(yday, yday)


def fetch_payments(yday: str) -> list[dict]:
    return _payments_query(yday, yday)


def fetch_viewers_period(date_from: str, date_to: str) -> list[dict]:
    return _viewers_query(date_from, date_to)


def fetch_payments_period(date_from: str, date_to: str) -> list[dict]:
    return _payments_query(date_from, date_to)


if __name__ == '__main__':
    import datetime
    sys.stdout.reconfigure(encoding='utf-8')
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__),'..','.env'))
    yday = (datetime.date.today()-datetime.timedelta(days=1)).isoformat()
    mtd_from = yday[:8] + '01'
    print('Viewers yday:', json.dumps(fetch_viewers(yday), ensure_ascii=False, indent=2))
    print('Viewers MTD:', json.dumps(fetch_viewers_period(mtd_from, yday), ensure_ascii=False, indent=2))
    print('Payments yday:', json.dumps(fetch_payments(yday), ensure_ascii=False, indent=2))
    print('Payments MTD:', json.dumps(fetch_payments_period(mtd_from, yday), ensure_ascii=False, indent=2))
