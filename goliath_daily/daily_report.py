"""Голиаф — главный daily report.

Pipeline:
  1. Я.Директ /reports — траты, клики, конверсии (по цели «Уник.регистрация») за вчера и MTD
  2. Метрика — уникальные регистрации (та же цель) по utm_campaign × utm_medium за вчера и MTD
  3. getcourse БД — зрители вебинаров + продажи за вчера и MTD
  4. Агрегация per-продукт + total для MTD
  5. Claude (Sonnet 4.6 через OpenRouter) — генерирует отчёт + инсайты
  6. ТГ — отправка в @goliath77_bot
  7. Obsidian — сохранение копии в Wiki/channels/yandex-direct/daily_reports/

Запуск:
  python daily_report.py            # за вчера
  python daily_report.py --date 2026-05-05
  python daily_report.py --dry-run  # без отправки в ТГ
"""
import os, sys, json, datetime, argparse, traceback

sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from modules import yandex_direct, metrika, getcourse_db, claude_insights, tg_send, obsidian_save


def _campaign_short(name: str) -> str:
    """goliath__start-your-business-with-ai → sysai и т.п. — короткое имя продукта."""
    n = (name or '').lower()
    if 'start-your-business' in n or 'sysai' in n: return 'sysai'
    if 'openclaw'             in n:                return 'openclaw'
    if 'n8n'                  in n:                return 'n8n'
    if 'law'                  in n:                return 'law'
    return name or '?'


def _aggregate_mtd(yd_rows, metrika_rows, viewers_rows, payments_rows) -> dict:
    """Схлопнуть MTD-данные per продукт + total. На вход — сырые ответы модулей.

    Источник правды по лидам = Метрика (цель unic = 332807191). Я.Директ-Conversions
    при `Goals:[id]` может быть 0, если Директ ещё не подхватил новую цель — на цифры
    отчёта это не влияет, всё равно считаем CPA = YD.cost / Метрика.leads.
    leads_yd оставляем рядом для диагностики/сверки.
    """
    products: dict[str, dict] = {}

    def slot(key: str) -> dict:
        return products.setdefault(key, {
            'product': key,
            'cost_rub': 0.0,
            'clicks': 0,
            'leads': 0,           # Метрика, цель unic — основной KPI
            'leads_yd': 0,        # Я.Директ Conversions — для сверки
            'viewers': 0,
            'sales': 0,
            'revenue_rub': 0.0,
        })

    for r in yd_rows or []:
        if '_error' in r: continue
        p = slot(_campaign_short(r.get('campaign_name', '')))
        p['cost_rub'] += float(r.get('cost_rub') or 0)
        p['clicks']   += int(r.get('clicks') or 0)
        p['leads_yd'] += int(r.get('conversions') or 0)

    for r in metrika_rows or []:
        if '_error' in r: continue
        short = _id_to_short(r.get('utm_campaign', ''))
        slot(short)['leads'] += int(r.get('unique_leads') or 0)

    for r in viewers_rows or []:
        if '_error' in r: continue
        short = _id_to_short(r.get('utm_campaign', ''))
        slot(short)['viewers'] += int(r.get('viewers') or 0)

    for r in payments_rows or []:
        if '_error' in r: continue
        short = _id_to_short(r.get('utm_campaign', ''))
        p = slot(short)
        p['sales']       += int(r.get('sales') or 0)
        p['revenue_rub'] += float(r.get('revenue') or 0)

    for p in products.values():
        p['cpa_rub']  = round(p['cost_rub'] / p['leads'], 0)        if p['leads']     else 0
        p['roas_pct'] = round(p['revenue_rub'] / p['cost_rub'] * 100, 0) if p['cost_rub'] else 0
        p['cost_rub']    = round(p['cost_rub'], 0)
        p['revenue_rub'] = round(p['revenue_rub'], 0)

    rows = sorted(products.values(), key=lambda x: -x['cost_rub'])

    total = {
        'product':     'TOTAL',
        'cost_rub':    sum(p['cost_rub']    for p in rows),
        'clicks':      sum(p['clicks']      for p in rows),
        'leads':       sum(p['leads']       for p in rows),
        'leads_yd':    sum(p['leads_yd']    for p in rows),
        'viewers':     sum(p['viewers']     for p in rows),
        'sales':       sum(p['sales']       for p in rows),
        'revenue_rub': sum(p['revenue_rub'] for p in rows),
    }
    total['cpa_rub']  = round(total['cost_rub'] / total['leads'], 0)        if total['leads']     else 0
    total['roas_pct'] = round(total['revenue_rub'] / total['cost_rub'] * 100, 0) if total['cost_rub'] else 0

    return {'per_product': rows, 'total': total}


# id→short таблица. Стабильные id-шники из YD_CAMPAIGN_IDS.
_ID_TO_SHORT = {
    '709513073': 'sysai',
    '709513492': 'openclaw',
    '709513513': 'n8n',
    '709513517': 'law',
}
def _id_to_short(utm_camp: str) -> str:
    return _ID_TO_SHORT.get(str(utm_camp).strip(), str(utm_camp) or '?')


def _aggregate_yday(yd_rows, metrika_rows) -> dict:
    """Блок «За вчера» — лиды и CPA per продукт.
    Cost/clicks из Я.Директ, лиды из Метрики (цель unic). leads_yd для сверки.
    """
    products: dict[str, dict] = {}

    def slot(key: str) -> dict:
        return products.setdefault(key, {
            'product':  key,
            'cost_rub': 0.0,
            'leads':    0,
            'leads_yd': 0,
        })

    for r in yd_rows or []:
        if '_error' in r: continue
        p = slot(_campaign_short(r.get('campaign_name', '')))
        p['cost_rub'] += float(r.get('cost_rub') or 0)
        p['leads_yd'] += int(r.get('conversions') or 0)

    for r in metrika_rows or []:
        if '_error' in r: continue
        slot(_id_to_short(r.get('utm_campaign', '')))['leads'] += int(r.get('unique_leads') or 0)

    for p in products.values():
        p['cpa_rub'] = round(p['cost_rub'] / p['leads'], 0) if p['leads'] else 0
        p['cost_rub'] = round(p['cost_rub'], 0)

    rows = sorted(products.values(), key=lambda x: -x['cost_rub'])
    total = {
        'product':  'TOTAL',
        'cost_rub': sum(p['cost_rub'] for p in rows),
        'leads':    sum(p['leads']    for p in rows),
        'leads_yd': sum(p['leads_yd'] for p in rows),
    }
    total['cpa_rub'] = round(total['cost_rub'] / total['leads'], 0) if total['leads'] else 0
    return {'per_product': rows, 'total': total}


def collect(yday: str) -> dict:
    """Соберёт все метрики, ошибки в каждом модуле не валят весь отчёт."""
    out = {'date': yday}

    # MTD-границы: первое число месяца yday → yday включительно
    mtd_from = yday[:8] + '01'
    out['mtd_from'] = mtd_from
    out['mtd_to']   = yday

    print('[1/6] Я.Директ — состояния...')
    try:
        out['states'] = yandex_direct.fetch_campaign_states()
    except Exception as e:
        out['states'] = {'_error': str(e)[:300]}
        traceback.print_exc()

    print('[2/6] Я.Директ — отчёт за вчера + MTD (по цели УР)...')
    try:
        out['yandex_direct_yday'] = yandex_direct.fetch_daily(yday)
    except Exception as e:
        out['yandex_direct_yday'] = [{'_error': str(e)[:500]}]
        traceback.print_exc()
    try:
        out['yandex_direct_mtd'] = yandex_direct.fetch_period(mtd_from, yday)
    except Exception as e:
        out['yandex_direct_mtd'] = [{'_error': str(e)[:500]}]
        traceback.print_exc()

    print('[3/6] Метрика — лиды по campaign × medium (вчера + MTD)...')
    try:
        out['metrika_per_campaign_yday'] = metrika.fetch_goals_by_campaign(yday)
        out['metrika_totals_yday']       = metrika.fetch_totals(yday)
        out['metrika_per_campaign_mtd']  = metrika.fetch_goals_by_campaign(mtd_from, yday)
        out['metrika_totals_mtd']        = metrika.fetch_totals(mtd_from, yday)
    except Exception as e:
        out['metrika_per_campaign_yday'] = [{'_error': str(e)[:300]}]
        out['metrika_totals_yday']       = {'_error': str(e)[:300]}
        out['metrika_per_campaign_mtd']  = [{'_error': str(e)[:300]}]
        out['metrika_totals_mtd']        = {'_error': str(e)[:300]}
        traceback.print_exc()

    print('[4/6] getcourse БД — зрители + продажи (вчера + MTD)...')
    try:
        out['viewers_yday']  = getcourse_db.fetch_viewers(yday)
        out['payments_yday'] = getcourse_db.fetch_payments(yday)
        out['viewers_mtd']   = getcourse_db.fetch_viewers_period(mtd_from, yday)
        out['payments_mtd']  = getcourse_db.fetch_payments_period(mtd_from, yday)
    except Exception as e:
        out['viewers_yday']  = [{'_error': str(e)[:300]}]
        out['payments_yday'] = [{'_error': str(e)[:300]}]
        out['viewers_mtd']   = [{'_error': str(e)[:300]}]
        out['payments_mtd']  = [{'_error': str(e)[:300]}]
        traceback.print_exc()

    print('[5/6] Агрегация per-продукт (вчера + MTD)...')
    out['agg_yday'] = _aggregate_yday(
        out.get('yandex_direct_yday', []),
        out.get('metrika_per_campaign_yday', []),
    )
    out['agg_mtd']  = _aggregate_mtd(
        out.get('yandex_direct_mtd', []),
        out.get('metrika_per_campaign_mtd', []),
        out.get('viewers_mtd', []),
        out.get('payments_mtd', []),
    )

    return out


def run(yday: str, dry_run: bool = False) -> str:
    metrics = collect(yday)

    raw_path = os.path.join(os.path.dirname(__file__), 'reports', f'{yday}.json')
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)
    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(f'  raw saved → {raw_path}')

    print('[6/6] Claude — генерация инсайтов...')
    report = claude_insights.generate(metrics)
    print(f'  report length: {len(report)} chars')

    obs_path = obsidian_save.save(yday, report, metrics)
    print(f'  obsidian → {obs_path}')

    if dry_run:
        print('\n--- DRY RUN, не отправляем в ТГ. Текст отчёта: ---\n')
        print(report)
    else:
        try:
            tg_send.send(report)
            print('  tg → SENT')
        except Exception as e:
            print(f'  tg → FAIL: {str(e)[:300]}')
            print('  Если "chat not found" — напиши /start боту @goliath77_bot.')

    return report


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', help='YYYY-MM-DD (default: вчера по МСК)')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    if args.date:
        yday = args.date
    else:
        today_msk = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
        yday = (today_msk.date() - datetime.timedelta(days=1)).isoformat()

    print(f'\n=== Голиаф daily report за {yday} ===\n')
    run(yday, dry_run=args.dry_run)
    print('\n=== DONE ===\n')
