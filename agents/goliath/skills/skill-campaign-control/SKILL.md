---
name: goliath-campaign-control
description: >
  Я.Директ write API for Голиаф (Phase 2 only). Operations: set_state, set_daily_budget,
  set_target_cpa, set_bid, update_bidmodifiers, update_negative_sites, create_ad,
  create_adgroup, create_campaign, update_text_ad. **In Phase 1 этот скилл
  отключён** — все действия идут как proposals. Triggers: "примени предложение",
  "запусти изменение в Я.Директ", "set state SUSPENDED" (но Phase 1 заблокирует).
---

# skill-campaign-control — Голиаф

**🚫 В Phase 1 этот скилл — заглушка.** Все write-операции возвращают
ошибку «Phase 2 only». В Phase 1 любые изменения идут через
skill-proposals (predict + согласие в Claude Code).

## Phase 1 поведение

Любой вызов любой операции возвращает:

```json
{
  "ok": false,
  "error": "skill-campaign-control disabled in Phase 1. Create proposal via skill-proposals instead.",
  "proposal_template": { ... что бы вы написали в proposed_action ... }
}
```

## Phase 2 — что будет реализовано

Полный контракт — в [[skill-campaign-control]] (Wiki). Кратко 11 операций:

| Операция | Я.Директ метод | Hard-лимиты |
|---|---|---|
| `set_state` | `campaigns/update`, `adgroups/update`, `ads/update` | — |
| `set_daily_budget` | `campaigns/update.DailyBudget` | ≤3К/кампания, ≤10К сумма |
| `set_target_cpa` | `campaigns/update.BiddingStrategy` | per-product ARPL/1.3 как floor |
| `set_bid` | `bids/set` | max +30%/нед |
| `update_bidmodifiers` | `bidmodifiers/set` | demo Age+Gender вместе |
| `update_negative_sites` | `campaigns/update.ExcludedSites` | дополняем, не удаляем |
| `create_ad` | `ads/add` | формат TextAdBuilderAd для ЕПК |
| `create_adgroup` | `adgroups/add` | 1 кампания = 1 группа |
| `create_campaign` | `campaigns/add` | TextCampaign + Network AVERAGE_CPA |
| `update_text_ad` | `ads/update` | **только для модерации**, не для тестов |
| `revert_action` | по записи `actions_log` — обратное действие | rollback ≤24ч |

Каждое действие пишется в `goliath.actions_log` с before/after snapshot.

## Запреты (даже в Phase 2)

- Кабинеты подрядчиков `imedia-zerocoder*` — не трогать.
- Цели Метрики (зафиксированы на `unic` 332807191) — не менять.
- Тексты объявлений ради тестов — только для модерационных правок;
  тесты = новое объявление.

## Связи

- Wiki: [[skill-campaign-control]] — детальный контракт
- Спека: [[Голиаф v2 — спецификация агента]] раздел 10 (безопасность)
- Связано: [[skill-proposals]] (Phase 1 заменяет write на propose),
  [[Я.Директ API — рабочая справка для агента]] (как реализовать вызовы)
