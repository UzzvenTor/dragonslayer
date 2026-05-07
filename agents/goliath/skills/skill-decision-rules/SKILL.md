---
name: goliath-decision-rules
description: >
  Deterministic Phase 1 evaluator for Голиаф decision rules 1, 3, 6 over a
  pre-built snapshot (skill-analytics output). Emits a list of proposed actions
  (pause/scale/urgent_arpl_stop) ready to feed into skill-proposals. Rules use
  campaign-level aggregates (ad-level планируется в Phase 2). Triggers:
  "примени правила", "evaluate decision rules", "find proposals from snapshot",
  "что предложит Голиаф".
---

# skill-decision-rules — Голиаф

Детерминированная проверка правил из [[Decision rules для Голиафа]] поверх
snapshot'а. Выдаёт **кандидатов** в proposals — финальное решение писать или
нет принимает агент в утреннем цикле (с учётом контекста и существующих
pending).

## Какие правила реализованы (Phase 1, campaign-level)

| Правило | Триггер | Категория предложения |
|---|---|---|
| **R1 / 3× ARPL** | MTD cost кампании ≥ 3×ARPL_per_product при 0 уник.лидов | `urgent_arpl_stop` |
| **R1 / 5× ARPL** | MTD cost ≥ 5×ARPL при 0 уник.лидов | `urgent_arpl_stop` (priority high) |
| **R1 / 10× ARPL** | MTD cost ≥ 10×ARPL при 0 уник.лидов | `urgent_arpl_stop` (priority urgent — в Phase 2 это auto) |
| **R3 / Scale** | week-окно: CPL ≤ ARPL/1.3 И week-leads ≥ 5 | `scale_budget` (+30%) |
| **R6 / CTR-trap** | MTD: CTR ≥ 2% И ROAS < 50% И cost ≥ 10К | `pause` |

**Что не делается в Phase 1** (требует ad-level данных):
- R1/R6 на уровне отдельных объявлений
- R5 (ротация креативов) — отдельный weekly skill
- R2 (13K без оплат) — отложено до восстановления pipeline оплат

## Как вызывать

```bash
# stdin — JSON snapshot от skill-analytics
python skills/skill-analytics/snapshot.py --date 2026-05-06 \
  | python skills/skill-decision-rules/rules.py
```

Или через файл:

```bash
python skills/skill-decision-rules/rules.py --file /tmp/snap.json
```

## Контракт выхода

JSON-array proposal-кандидатов — формат соответствует `skill-proposals insert`:

```json
[
  {
    "category": "urgent_arpl_stop",
    "product": "law",
    "campaign_id": 709674151,
    "ad_group_id": null, "ad_id": null,
    "description": "🔥 5×ARPL без лидов — рекомендую стоп кампании goliath__law_H08",
    "reasoning": "MTD: cost 5 800₽ ≥ 5×ARPL (5×1100=5500₽), уник.лидов 0. ARPL@1м=1100.",
    "proposed_action": {
      "tool": "direct.set_state",
      "args": {"campaign_id": 709674151, "state": "SUSPENDED"}
    },
    "ttl_hours": 24
  },
  ...
]
```

## Инварианты

- **ARPL/CPL_target пороги — из Wiki [[Decision rules для Голиафа]]:**
  sysai 1400/1077, openclaw 1700/1308, n8n 1600/1231, law 1100/846 ₽.
- **MTD как proxy для rolling-14d** в Phase 1 (пока нет дневных snapshots
  глубоко в истории). После 14+ дней наблюдения переходим на rolling 14d.
- **Не дублирует уже pending** — это работа вызывающего: перед `insert`
  агент должен сравнить с `list-active`.
- **Outputs суть кандидаты** — Phase 1 вообще не пишет в Я.Директ;
  максимум — в `goliath.proposals` как pending.
