"""Сохранение отчёта в Obsidian: Wiki/channels/yandex-direct/daily_reports/YYYY-MM-DD.md"""
import os, json, datetime


def save(date: str, html_report: str, raw_metrics: dict) -> str:
    """Сохранить отчёт. Если задан и существует OBSIDIAN_REPORT_DIR (локалка) — туда.
    Иначе fallback в `<repo>/goliath_daily/reports/` — на CI это коммитится обратно в репо.
    """
    obsidian_dir = (os.environ.get('OBSIDIAN_REPORT_DIR') or '').strip()
    fallback = os.path.join(os.path.dirname(__file__), '..', 'reports')

    out_dir = None
    if obsidian_dir:
        parent = os.path.dirname(obsidian_dir.rstrip('/').rstrip('\\'))
        if parent and os.path.isdir(parent):
            out_dir = obsidian_dir
    if out_dir is None:
        out_dir = fallback

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f'{date}.md')

    # HTML → mostly markdown-friendly: переводим <b> → **, <i> → *
    md = (html_report
        .replace('<b>','**').replace('</b>','**')
        .replace('<i>','*').replace('</i>','*'))

    body = f"""---
type: daily-report
date: {date}
agent: goliath
status: published
related:
  - "[[2026-04-30 запуск porg-6vgf2ozq — 4 кампании]]"
  - "[[Decision rules для Голиафа]]"
tags: [daily, goliath, yandex-direct]
---

# 📊 Daily report Голиафа — {date}

> Автоматически сгенерировано {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} МСК. Источники: Я.Директ Reports API (porg-6vgf2ozq), Метрика (счётчик 72085663), getcourse БД (zerocoder_vps).

## Краткий отчёт

{md}

---

## Сырые метрики (для аудита)

```json
{json.dumps(raw_metrics, ensure_ascii=False, indent=2)}
```
"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(body)
    return path
