# Голиаф v2 — код агента

Исполнимая часть write-агента Я.Директа Зерокодера. Архитектура и правила
решений описаны в Wiki:

- `I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Wiki/shared/agents/Голиаф v2 — спецификация агента.md`
- `Wiki/channels/yandex-direct/playbooks/Decision rules для Голиафа.md`

## Статус: Phase 1 — read+propose · 2026-05-07

Все 7 скиллов написаны (1 заглушка для Phase 2):

| Скилл | Тип | Статус |
|---|---|---|
| `skill-analytics` | thick (Python) | ✅ active |
| `skill-proposals` | thick | ✅ active |
| `skill-snapshots` | thick | ✅ active |
| `skill-tg-push` | thick | ✅ active |
| `skill-decision-rules` | thick | ✅ active (R1+R3+R6 на campaign-level) |
| `skill-utm` | thick | ✅ active |
| `skill-ad-copy` | LLM-driven | ✅ active |
| `skill-hypothesis` | LLM-driven | ✅ active |
| `skill-negative-platforms` | thick | ✅ active (понедельники) |
| `skill-creative-banner` | thick | ✅ active (исторические скрипты) |
| `skill-campaign-control` | заглушка | 🚫 заблокирован Phase 1 |

## Структура

```
goliath/
├── README.md                              ← этот файл
├── routines/
│   ├── daily-prompt.md                    ← главный prompt для Anthropic Cloud Routine
│   ├── daily.py                           ← thin orchestrator (cross-check, backup)
│   ├── test_run.py                        ← legacy debug runner
│   └── _lib/
│       ├── __init__.py
│       └── common.py                      ← env+pg+timewin helpers
├── skills/                                ← по одной папке на capability
│   └── skill-<name>/
│       ├── SKILL.md                       ← инструкция Claude (frontmatter + body)
│       └── *.py                           ← исполнимые helper-скрипты (если нужно)
└── migrations/
    ├── 001_init.sql                       ← proposals/actions_log/daily_snapshots/...
    ├── 002_yd_raw_pulls.sql               ← гибрид-режим (локальный YD pull → PG)
    └── 003_voice.sql                      ← Эхо v1 (отдельный pipeline)
```

## Запуск миграций (если БД ещё пустая)

```bash
psql "host=rc1b-nftoajilh0nnj0gf.mdb.yandexcloud.net port=6432 user=<admin> dbname=postgres" -c "
CREATE DATABASE kurzemnek;  -- если ещё нет
"
psql "host=... port=6432 user=kurzemnek_app dbname=kurzemnek" -f migrations/001_init.sql
psql "host=... port=6432 user=kurzemnek_app dbname=kurzemnek" -f migrations/002_yd_raw_pulls.sql
```

`PG_PASSWORD` — в `dragonslayer/goliath_daily/.env` (общий .env на оба
проекта).

## Локальный smoke-test

```bash
cd I:/neuro/GENERAL CLAUDE CODE/Zerocoder/agents/goliath

# 1. Snapshot за вчера в JSON
python skills/skill-analytics/snapshot.py --date 2026-05-06 --out /tmp/snap.json

# 2. Decision rules → кандидаты proposals
python skills/skill-decision-rules/rules.py --file /tmp/snap.json

# 3. Полный thin pipeline (запись в БД)
python routines/daily.py --date 2026-05-06 --dry-run    # без записи
python routines/daily.py --date 2026-05-06              # с записью в daily_snapshots
```

## Cron в Anthropic Cloud Routine

Главный entrypoint = `routines/daily-prompt.md`. Создать routine
(в Claude Code UI или через `/schedule`):

- Cron: `0 5 * * *` (UTC) = 08:00 МСК
- Working directory: `Zerocoder/agents/goliath/`
- Prompt: содержимое `routines/daily-prompt.md`
- Env: TG_BOT_TOKEN, TG_CHAT_ID, YANDEX_DIRECT_TOKEN, YD_CABINET,
  YD_CAMPAIGN_IDS, YANDEX_METRIKA_TOKEN, METRIKA_COUNTER_ID, GOAL_REG_ID,
  DB_HOST/PORT/USER/PASSWORD/NAME, PG_PASSWORD

Биллинг — MAX-подписка Валерия (LLM-вызов = Claude Code session).

## Скиллы — единый паттерн

Каждый скилл = папка с `SKILL.md` (frontmatter `name`/`description` +
markdown body). Если есть исполнимая часть — рядом `*.py` файлы. Скиллы
автономны: каждый сам грузит .env и держит зависимости минимально.

Wiki-документация скиллов лежит в
`Wiki/shared/agents/Голиаф/skills/skill-*.md` — там подробное описание входов/
выходов/инвариантов. SKILL.md в коде = краткая инструкция Claude в момент
вызова.

## Гранулярность Phase 1

R1 / R3 / R6 — на уровне **кампании** (не объявления). Объяснение: snapshot
текущей версии собирает только CAMPAIGN_PERFORMANCE_REPORT (без AdId).
Ad-level — следующая итерация после 14 дней наблюдений.

## Связи

- Wiki: [[Голиаф v2 — спецификация агента]] · [[Голиаф v2 — журнал реализации]]
- Decision rules: [[Decision rules для Голиафа]]
- API справка: [[Я.Директ API — рабочая справка для агента]]
- Старая v1 (legacy): `dragonslayer/goliath_daily/` — параллельно работает
  ещё 2-3 дня для cross-check, затем cron отключим.
