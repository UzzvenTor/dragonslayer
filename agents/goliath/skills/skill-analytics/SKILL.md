---
name: goliath-analytics
description: >
  Pull aggregated traffic metrics for Голиаф daily report. Combines Я.Директ
  Reports API, Метрика Reports API, and GetCourse MySQL into a single snapshot
  grouped by 3 windows (yesterday / current week Mon→Sun / month-to-date) per
  product (sysai/openclaw/n8n/law) plus total. Use when generating Голиаф's
  morning report or when other skills need current numbers (CPL/CPA/ROAS/viewer
  rate). Triggers: "собери snapshot", "посчитай метрики Голиафа", "what's the
  daily snapshot", "pull goliath data", "voronka mtd".
---

# skill-analytics — Голиаф

Source-of-truth слой для всех read-метрик Голиафа. Все остальные скиллы
(`skill-decision-rules`, `skill-hypothesis`, `skill-snapshots`,
форматирование отчёта) потребляют snapshot, который возвращает этот скилл.

## Когда вызывать

- Утренний цикл агента (routine 08:00 МСК) — первым шагом.
- Любой запрос Валерия в Claude Code «что у Голиафа», «дай свежий snapshot»,
  «посчитай воронку MTD».
- Перед генерацией гипотез или предложений по решениям — нужен актуальный
  data view.

## Как вызывать

```bash
python skills/skill-analytics/snapshot.py --date 2026-05-06 --out /tmp/snap.json
```

Или без `--out` — печатает JSON в stdout.

`--date` опционален; по умолчанию yesterday.

Скрипт автоматически загружает `.env`. Ищет в порядке:
1. `skills/skill-analytics/.env` (приоритет)
2. `agents/goliath/.env`
3. `dragonslayer/goliath_daily/.env` (legacy fallback)

## Контракт выхода

```jsonc
{
  "fetched_at": "2026-05-07T08:00:15",
  "yday_date": "2026-05-06",
  "windows": {
    "yday": ["2026-05-06", "2026-05-06"],
    "week": ["2026-05-04", "2026-05-06"],   // Пн → yday
    "mtd":  ["2026-05-01", "2026-05-06"]
  },
  "yday": {                                  // легкое окно: cost/clicks/leads/cpa
    "per_product": [
      {"product": "sysai", "cost_rub": 1450.20, "clicks": 35, "leads": 1,
       "leads_yd": 0, "cpa_rub": 1450.20, "viewers": 0, ...}, ...
    ],
    "total": {"product": "TOTAL", "cost_rub": 5200.00, "leads": 6, "cpa_rub": 866.67, ...}
  },
  "week": { ... },                            // как yday
  "mtd": {                                    // полная воронка
    "per_product": [
      {"product": "sysai", "cost_rub": 23400, "clicks": 580, "impressions": 18500,
       "leads": 17, "viewers": 12, "viewer_rate_pct": 70.6,
       "paid_orders": 0, "revenue_rub": 0.0, "cpa_rub": 1376, "roas_pct": 0.0,
       "raw": {"cohort_via_email": 12, "bizon_direct": 0,
               "gc_registrations_side": 23, "metrika_unic_leads": 17}}, ...
    ],
    "total": { ... }
  },
  "states": {
    "709513073": {"name": "goliath__start-your-business-with-ai",
                  "state": "ON", "status": "ACCEPTED", "payment": "ALLOWED"},
    ...
  },
  "errors": []                                // [{step, error}] — частичные сбои
}
```

## Источники и алгоритм

| Метрика | Источник | Что считаем |
|---|---|---|
| `cost_rub`, `clicks`, `impressions`, `leads_yd` | YD Reports API · `CAMPAIGN_PERFORMANCE_REPORT` | per CampaignId, IncludeVAT=YES |
| `leads` (KPI) | Метрика · цель `unic` (332807191) | `goal{N}users` per `utm_campaign × utm_medium`, фильтр `medium=~^goliath` |
| `viewers` (NEW acquisition) | GetCourse MySQL | для sysai/openclaw/n8n: cohort через email (gu.registration в периоде ∩ bv по landing); для law: bizon_direct (Bizon-direct path). **Всегда ≤ leads.** |
| `viewers_retention` | GetCourse MySQL | `bizon_direct[landing] - cohort` для sysai/openclaw/n8n. Для law=0 (все viewers — NEW в Bizon). |
| `paid_orders`, `revenue_rub` | GetCourse MySQL | `getcoursePayments status='Получен'` с дедупом `MIN(id) per number`, исключая `платное участие` |
| `states` | YD `campaigns/get` | per CampaignId: State/Status/StatusPayment |
| `gc_registrations_side` (raw) | GetCourse MySQL | `getcourseRegistrations` — все записи (включая retention), не KPI |

## Источник правды по лидам

**KPI лидов = Метрика, цель `unic` (id 332807191).** YD `Conversions` — шум,
держим только в `leads_yd` для cross-check. Источник прописан в
[[Голиаф — лиды по Метрике, не Я.Директ]] memory.

## Критичные инварианты

- **CAMP_TO_PRODUCT** содержит ВСЕ актуальные campaign_id (H07 + H08).
  При запуске новых кампаний обязательно обновить словарь.
- **LANDING_TO_PRODUCT** — fallback для случаев когда `utm_campaign` в
  getcourseUsers/Метрике = slug лендинга (`prompt-engineer-web-9`), а не
  campaign_id. Пропатчено 2026-05-07 — bug в v1 был что fallback не
  использовался.
- **SUBSTRING(30)** в SQL — 15 символов резало landing slugs (`prompt-engineer-`),
  ломало маппинг. Раздвинуто до 30.
- **Force IPv4** — для `api.direct.yandex.com` обязательно (в скрипте есть).
- **Partial failures don't abort** — каждый pull завёрнут в `safe()`,
  ошибка пишется в `errors[]`, остальные данные собираются.

## Воронка месяца — нюансы

- `viewer_rate_pct = viewers / leads × 100` (KPI знаменатель = Метрика-уник).
  Ключевая прокси-метрика на доходимость до веба.
- `cpa_rub = cost / leads`. При 0 лидов = 0 (не делим на ноль).
- `roas_pct = revenue / cost × 100`. Цикл сделки sysai/openclaw/n8n/law ≈
  10 дней, поэтому в первые 10 дней после старта 0 продаж — норма.
- **NEW (acquisition) vs RETURNING (retention) split** — Frame D из методологии
  атрибуции ([[Голиаф-выручка — 4 фрейма атрибуции]]):
  - `viewers` (главная метрика) = NEW: свежий голиаф-лид этого периода, дошёл
    до веба. Subset регистраций, **всегда ≤ leads**.
  - `viewers_retention` = старый лид Зерокодера на свежем голиаф-вебинаре
    (зарегистрирован раньше / через других подрядчиков, на голиаф-метку
    попадает на этапе webinar attendance).
  - Для law — Bizon-direct path: все viewers считаются NEW (форма обходит
    getcourseUsers; регистрация и просмотр оба в текущем периоде).
- **`viewer_rate_pct` считается по NEW**: `viewers_NEW / leads × 100`. Никогда
  не >100%. На 2026-05-06 типичный паттерн: 5-15% доходимость на свежих
  лидах + 30-50 retention viewers (90% общего bizon-трафика).
- **Эмпирическое наблюдение** (memory `project_zerocoder_attribution_methodology`):
  Голиаф пока работает как retention/upsell-канал > acquisition. Это видно
  в Ret-колонке: на МТД 2026-05-06 33 retention vs 13 NEW.
- **Автовебинар — временной лаг (важно).** Регистрация и просмотр разнесены:
  лид сегодня → вебинар завтра/послезавтра. **Один лид может пойти на 2-3
  вебинара в течение месяца** — общая воронка большая. Поэтому:
  - `viewer_rate_pct` — **лаговая** метрика. Минимум 3-5 дней до полного
    отображения per snapshot_date.
  - `viewers` для свежих регистраций будет 0 — это **не сломанная воронка**,
    они ещё не дошли. Не паниковать.
  - При re-pull MTD за прошлые даты число viewers может расти (один лид
    пришёл на второй вебинар позже).
  - Decision Rule 1 (3×ARPL без лидов) опирается на Метрика-уник
    (регистрации) — работает по горячим следам, лаг не мешает.
  - Правила про ROAS/оплаты уже учитывают 10-дневный цикл.

## Связи

- Wiki: [[skill-analytics]] — версия для документации
- Используется: `routines/daily.py`, `skill-decision-rules`,
  `skill-hypothesis`, `skill-snapshots`
- Спека: [[Голиаф v2 — спецификация агента]] разделы 5 (Окна и метрики),
  6 (Схема БД)
