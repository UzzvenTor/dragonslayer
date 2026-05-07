---
name: goliath-snapshots
description: >
  Persist daily aggregates per product into goliath.daily_snapshots (YC Postgres).
  Idempotent UPSERT keyed by (snapshot_date, product). Reads input from JSON
  produced by skill-analytics. Triggers: "запиши snapshot", "save daily snapshot",
  "записать в БД", "persist metrics".
---

# skill-snapshots — Голиаф

Запись агрегатов в `goliath.daily_snapshots` для трендов и графиков.
Источник истины для исторических данных Phase 1+.

## Когда вызывать

- После того как `skill-analytics` собрал snapshot за вчера.
- При повторном пересчёте за прошлую дату (`UPSERT` идемпотентен).

## Как вызывать

```bash
python skills/skill-snapshots/save.py --file /tmp/snap.json
```

или stdin:

```bash
python skills/skill-analytics/snapshot.py --date 2026-05-06 \
  | python skills/skill-snapshots/save.py
```

## Контракт

Вход: snapshot JSON формата skill-analytics (ключ `mtd.per_product` —
основной источник; `yday`/`week` тоже извлекаются для `raw_data`).

Запись в `goliath.daily_snapshots`:
- `snapshot_date` — `yday_date` из snapshot
- `product` — из `mtd.per_product[].product`
- `cost_rub`, `clicks`, `impressions`, `unique_leads`, `viewers`,
  `viewer_rate_pct`, `paid_orders`, `revenue_rub`, `cpa_rub`, `roas_pct` —
  из MTD-окна (это основное окно для трендов)
- `raw_data` (JSONB) — `{"yday": {...}, "week": {...}, "raw": {...},
                         "errors": [...], "fetched_at": "..."}`

ON CONFLICT (snapshot_date, product) DO UPDATE — обновляет все поля,
`fetched_at = now()`.

## Инварианты

- **Не пишет TOTAL-строку** — только per-product. Total всегда вычислимый
  из 4 строк, экономим место.
- **Best-effort на ошибках PG** — печатает WARN, exit 0. Чтобы не ломать
  общий цикл (TG-отчёт всё равно должен уйти).
- **PG_PASSWORD обязателен** — иначе скилл падает с понятной ошибкой.
