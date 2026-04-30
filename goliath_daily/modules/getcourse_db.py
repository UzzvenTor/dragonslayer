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


def fetch_viewers(yday: str) -> list[dict]:
    """Уникальные зрители вебинаров (bizonViewers) от трафика Голиафа за yday.
    Группировка по utm_campaign + utm_medium. Ключ = email.
    """
    if get_conn is None:
        return [{'_error':'shared_local недоступен — поставь dragonslayer/shared_local рядом'}]
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT utm_campaign(255) AS utm_campaign,
                   utm_medium(255) AS utm_medium,
                   COUNT(DISTINCT email(255)) AS viewers
            FROM bizonViewers
            WHERE DATE(webinar_date) = %s
              AND utm_source(50) = 'yandex'
              AND utm_medium LIKE 'goliath__%%'
            GROUP BY utm_campaign(255), utm_medium(255)
            ORDER BY viewers DESC
        """.replace('utm_campaign(255)','SUBSTRING(utm_campaign,1,255)')
           .replace('utm_medium(255)','SUBSTRING(utm_medium,1,255)')
           .replace('utm_source(50)','SUBSTRING(utm_source,1,50)')
           .replace('email(255)','SUBSTRING(email,1,255)'),
           [yday])
        return [dict(r) for r in cur.fetchall()]
    finally:
        try: conn.close()
        except: pass


def fetch_payments(yday: str) -> list[dict]:
    """Продажи (getcoursePayments status='Получен') атрибуцированные на трафик Голиафа за yday.
    Связка: getcoursePayments.email → getcourseUsers.email → getcourseUsers.gcuid → main_yandex.uid → utm.
    """
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
            WHERE DATE(p.date_created) = %s
              AND p.status = 'Получен'
              AND SUBSTRING(m.utm_source,1,50) = 'yandex'
              AND m.utm_medium LIKE 'goliath__%%'
            GROUP BY SUBSTRING(m.utm_campaign,1,255), SUBSTRING(m.utm_medium,1,255)
            ORDER BY revenue DESC
        """, [yday])
        return [dict(r) for r in cur.fetchall()]
    finally:
        try: conn.close()
        except: pass


if __name__ == '__main__':
    import datetime
    sys.stdout.reconfigure(encoding='utf-8')
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__),'..','.env'))
    yday = (datetime.date.today()-datetime.timedelta(days=1)).isoformat()
    print('Viewers:', json.dumps(fetch_viewers(yday), ensure_ascii=False, indent=2))
    print('Payments:', json.dumps(fetch_payments(yday), ensure_ascii=False, indent=2))
