# -*- coding: utf-8 -*-
"""Сбор вчерашних метрик для отчёта Драконоборца.

Три блока:
  1. Взрослое (вебинары) — новые uid в getcourseRegistrations по лончам *-web-* / *-intensive-*
     × платные каналы tg_pos / timepad / yandex|ya / ris
  2. Лидмагниты — остальные (нерегулярные) лончи, тоже новые uid
  3. Детское — уникальные gcid в getcourseOrders по каналам (см. 1_Дети.py:get_channel_data)

Результат — JSON в stdout (или в файл).
"""
import sys, os, json, argparse, datetime
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))
from shared_local.db import get_conn
from shared_local.filters import KIDS_LIKE, KIDS_NOISE_LIST


# ═════════════════════════════════════════════════════════════════════════════
# ВЗРОСЛОЕ + ЛИДМАГНИТЫ: регистрации из getcourseRegistrations
# ═════════════════════════════════════════════════════════════════════════════

PAID_CASE = """
    CASE
        WHEN utm_source IN ('yandex','ya')  THEN 'Яндекс Директ'
        WHEN utm_source = 'tg_pos'          THEN 'TG Посевы'
        WHEN utm_source = 'timepad'         THEN 'Timepad'
        WHEN utm_source = 'ris'             THEN 'RIS'
        ELSE 'прочее'
    END
"""

# Детские launch-префиксы — их исключаем из "взрослых"
KIDS_LAUNCH_PATTERNS = ['%kids%', '%teen%', '%scratch-kids%']


def _is_webinar_launch_sql():
    """SQL-предикат: launch выглядит как вебинар/интенсив."""
    return "(launch LIKE '%%-web-%%' OR launch LIKE '%%-intensive-%%')"


def _adult_launches_with_new_regs(cur, yday, webinar_only: bool):
    """Список лончей вчера со счётчиком новых uid.
    webinar_only=True → только *-web-* / *-intensive-*.
    webinar_only=False → только НЕ-вебинарные (= лидмагниты).
    """
    webinar_pred = _is_webinar_launch_sql()
    filt = webinar_pred if webinar_only else f"NOT {webinar_pred}"
    sql = f"""
        SELECT r.launch AS launch,
               COUNT(DISTINCT r.uid) AS new_regs
        FROM getcourseRegistrations r
        WHERE DATE(r.date) = %s
          AND r.launch NOT LIKE %s
          AND r.launch NOT LIKE %s
          AND r.launch NOT LIKE %s
          AND r.launch <> ''
          AND {filt}
          AND NOT EXISTS (
              SELECT 1 FROM getcourseRegistrations r2
              WHERE r2.uid = r.uid AND r2.date < %s
          )
        GROUP BY r.launch
        HAVING new_regs > 0
        ORDER BY new_regs DESC
    """
    cur.execute(sql, [yday] + KIDS_LAUNCH_PATTERNS + [f"{yday} 00:00:00"])
    return cur.fetchall()


def _adult_launch_by_channel(cur, yday, launch):
    """Разбивка лонча по каналам (только новые uid)."""
    sql = f"""
        SELECT {PAID_CASE.strip()} AS channel,
               COUNT(DISTINCT r.uid) AS new_regs
        FROM getcourseRegistrations r
        WHERE DATE(r.date) = %s
          AND r.launch = %s
          AND NOT EXISTS (
              SELECT 1 FROM getcourseRegistrations r2
              WHERE r2.uid = r.uid AND r2.date < %s
          )
        GROUP BY channel
        ORDER BY new_regs DESC
    """
    cur.execute(sql, [yday, launch, f"{yday} 00:00:00"])
    return {r['channel']: r['new_regs'] for r in cur.fetchall()}


# ═════════════════════════════════════════════════════════════════════════════
# ДЕТСКОЕ: gcid из getcourseOrders по каналам (паттерны из 1_Дети.py)
# ═════════════════════════════════════════════════════════════════════════════

def _kids_channel_counts(cur, yday):
    """Вернёт dict {канал: уникальные_gcid} за один день."""
    kl = ' OR '.join(['title LIKE %s'] * len(KIDS_LIKE))
    kn = ' AND '.join(['title NOT LIKE %s'] * len(KIDS_NOISE_LIST))

    def by_source(src):
        cur.execute(f"""SELECT DISTINCT gcid FROM getcourseOrders
            WHERE DATE(date_created) = %s AND utm_source = %s
              AND ({kl}) AND title NOT LIKE %s AND {kn}""",
            [yday, src] + KIDS_LIKE + ['%вебинара%'] + KIDS_NOISE_LIST)
        return {r['gcid'] for r in cur.fetchall()}

    def by_title_kids(pattern):
        cur.execute(f"""SELECT DISTINCT gcid FROM getcourseOrders
            WHERE DATE(date_created) = %s AND title LIKE %s
              AND ({kl}) AND title NOT LIKE %s AND {kn}""",
            [yday, pattern] + KIDS_LIKE + ['%вебинара%'] + KIDS_NOISE_LIST)
        return {r['gcid'] for r in cur.fetchall()}

    def by_title_any(pattern):
        cur.execute("""SELECT DISTINCT gcid FROM getcourseOrders
            WHERE DATE(date_created) = %s AND title LIKE %s""",
            [yday, pattern])
        return {r['gcid'] for r in cur.fetchall()}

    # Каналы (названия — как в дашборде)
    channels = {
        'Яндекс Директ': by_source('yandex') | by_source('ya'),
        'ВК Ads':        by_source('VK_ads'),        # MySQL ci — VK_ads и vk_ads сольются
        'TG Посевы':     by_source('tg_pos'),
        'Авито':         by_title_any('%авито%'),
        'Центриум':      by_title_any('%центриум%'),
        'Flocktory':     by_title_kids('%flocktory%'),
        'RIS':           by_title_kids('%[ris]%'),
        'Reffection':    by_title_any('%Reffection%'),
        'Primelead (Рустем)':      by_title_any('%обзвона. Р%'),
        'Автообзвоны (Алёна)':     by_title_kids('%обзвона. А%'),
        'ОП / робот':              by_title_any('%обзвона роботом%'),
    }
    # Дедуп между каналами — приоритет по порядку выше: gcid уходит в первый попавший канал
    seen = set()
    result = {}
    for name, gcids in channels.items():
        fresh = gcids - seen
        seen.update(gcids)
        if fresh:
            result[name] = len(fresh)
    return result


# ═════════════════════════════════════════════════════════════════════════════
# ГЛАВНЫЙ СБОРЩИК
# ═════════════════════════════════════════════════════════════════════════════

def collect(yday: str, prev: str):
    """yday, prev — строки 'YYYY-MM-DD'."""
    conn = get_conn()
    try:
        cur = conn.cursor()

        out = {
            'yesterday': yday,
            'prev_day':  prev,
            'adult_webinars': {'launches': [], 'total_new': 0},
            'leadmagnets':    {'launches': [], 'total_new': 0},
            'kids':           {'channels_yesterday': {}, 'channels_prev': {}, 'total_yesterday': 0, 'total_prev': 0},
        }

        # Взрослое вебинары
        for launch_row in _adult_launches_with_new_regs(cur, yday, webinar_only=True):
            lname = launch_row['launch']
            new_regs = launch_row['new_regs']
            by_ch = _adult_launch_by_channel(cur, yday, lname)
            out['adult_webinars']['launches'].append({
                'launch': lname,
                'new_regs': new_regs,
                'by_channel': by_ch,
            })
            out['adult_webinars']['total_new'] += new_regs

        # Лидмагниты
        for launch_row in _adult_launches_with_new_regs(cur, yday, webinar_only=False):
            lname = launch_row['launch']
            new_regs = launch_row['new_regs']
            by_ch = _adult_launch_by_channel(cur, yday, lname)
            out['leadmagnets']['launches'].append({
                'launch': lname,
                'new_regs': new_regs,
                'by_channel': by_ch,
            })
            out['leadmagnets']['total_new'] += new_regs

        # Детское — вчера и позавчера (для сравнения в тексте)
        ch_y = _kids_channel_counts(cur, yday)
        ch_p = _kids_channel_counts(cur, prev)
        out['kids']['channels_yesterday'] = ch_y
        out['kids']['channels_prev']      = ch_p
        out['kids']['total_yesterday']    = sum(ch_y.values())
        out['kids']['total_prev']         = sum(ch_p.values())

        return out
    finally:
        try: conn.close()
        except Exception: pass


def _default_dates():
    today = datetime.date.today()
    return (today - datetime.timedelta(days=1)).isoformat(), \
           (today - datetime.timedelta(days=2)).isoformat()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--yday', help='YYYY-MM-DD (default: сегодня-1)')
    ap.add_argument('--prev', help='YYYY-MM-DD (default: сегодня-2)')
    ap.add_argument('--out', help='путь к JSON (default: stdout)')
    args = ap.parse_args()

    default_y, default_p = _default_dates()
    yday = args.yday or default_y
    prev = args.prev or default_p

    data = collect(yday, prev)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write(payload)
        print(f'OK → {args.out}')
    else:
        print(payload)
