"""Голиаф — главный daily report.

Pipeline:
  1. Я.Директ /reports — траты, клики, конверсии за вчера
  2. Метрика — уникальные лиды (цель 332807191) per utm_campaign × utm_medium
  3. getcourse БД — зрители вебинаров + продажи
  4. Claude (Sonnet 4.6 через OpenRouter) — генерирует отчёт + инсайты
  5. ТГ — отправка в @goliath77_bot
  6. Obsidian — сохранение копии в Wiki/channels/yandex-direct/daily_reports/

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


def collect(date: str) -> dict:
    """Соберёт все метрики, ошибки в каждом модуле не валят весь отчёт."""
    out = {'date': date}

    print('[1/5] Я.Директ — состояния...')
    try:
        out['states'] = yandex_direct.fetch_campaign_states()
    except Exception as e:
        out['states'] = {'_error': str(e)[:300]}
        traceback.print_exc()

    print('[2/5] Я.Директ — отчёт за день...')
    try:
        out['yandex_direct'] = yandex_direct.fetch_daily(date)
    except Exception as e:
        out['yandex_direct'] = [{'_error': str(e)[:500]}]
        traceback.print_exc()

    print('[3/5] Метрика — лиды по campaign × medium...')
    try:
        out['metrika_per_campaign'] = metrika.fetch_goals_by_campaign(date)
        out['metrika_totals'] = metrika.fetch_totals(date)
    except Exception as e:
        out['metrika_per_campaign'] = [{'_error': str(e)[:300]}]
        out['metrika_totals'] = {'_error': str(e)[:300]}
        traceback.print_exc()

    print('[4/5] getcourse БД — зрители + продажи...')
    try:
        out['viewers'] = getcourse_db.fetch_viewers(date)
        out['payments'] = getcourse_db.fetch_payments(date)
    except Exception as e:
        out['viewers'] = [{'_error': str(e)[:300]}]
        out['payments'] = [{'_error': str(e)[:300]}]
        traceback.print_exc()

    return out


def run(date: str, dry_run: bool = False) -> str:
    metrics = collect(date)

    # save raw
    raw_path = os.path.join(os.path.dirname(__file__), 'reports', f'{date}.json')
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)
    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(f'  raw saved → {raw_path}')

    print('[5/5] Claude — генерация инсайтов...')
    report = claude_insights.generate(metrics)
    print(f'  report length: {len(report)} chars')

    # Obsidian
    obs_path = obsidian_save.save(date, report, metrics)
    print(f'  obsidian → {obs_path}')

    # Telegram
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
        date = args.date
    else:
        # Вчера по МСК. Запуск в 08:00 МСК → берём предыдущие сутки.
        today_msk = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
        date = (today_msk.date() - datetime.timedelta(days=1)).isoformat()

    print(f'\n=== Голиаф daily report за {date} ===\n')
    run(date, dry_run=args.dry_run)
    print('\n=== DONE ===\n')
