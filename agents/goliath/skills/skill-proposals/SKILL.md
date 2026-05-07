---
name: goliath-proposals
description: >
  CRUD operations for Голиаф's proposals queue and chat_context memory in
  goliath.proposals. Handles inserting new proposals (24h TTL), reading active/
  pending, marking decided (applied/rejected/superseded), expiring stale, and
  recording dialog turns. Use when creating new daily proposals, looking up what's
  pending, recording Валерий's decision, or auditing past dialog. Triggers:
  "запиши предложение", "новое предложение", "что в pending", "expire старое",
  "active proposals", "pending list".
---

# skill-proposals — Голиаф

Очередь предложений + память диалога. **Главный механизм Phase 1**: всё что
агент хочет сделать с Я.Директом — сначала пишется сюда, ждёт согласия Валерия
в Claude Code, потом помечается applied/rejected.

## Когда вызывать

- Утренний цикл: `list_pending` → переоценить → `expire_old` → `insert_batch`
  свежих предложений.
- Когда Валерий говорит «обсудим предложение №7»: `get_one(7)` + запись в
  chat_context.
- Когда Валерий решил: `mark_decided(7, status='applied'|'rejected', reason=...)`.

## Подкоманды (CLI)

```bash
# Pending активные (не истекшие)
python skills/skill-proposals/proposals.py list-active [--json]

# Один по id
python skills/skill-proposals/proposals.py get 7

# Вставить новые (читает JSON-array из stdin или --file)
echo '[{"category":"pause", ...}]' | python skills/skill-proposals/proposals.py insert

# Пометить решение
python skills/skill-proposals/proposals.py decide 7 --status applied --reason "ОК, применяй"

# Превратить устаревшие pending в expired
python skills/skill-proposals/proposals.py expire-old

# Записать ход диалога
python skills/skill-proposals/proposals.py chat 7 --speaker valerii --message "почему именно эта кампания?"
```

## Контракт `insert`

JSON-array (одна или больше записей):

```json
[
  {
    "category": "pause" | "scale_budget" | "change_target_cpa" | "new_hypothesis" |
                "creative_rotate" | "negative_site" | "urgent_arpl_stop" | ...,
    "product": "sysai" | "openclaw" | "n8n" | "law" | null,
    "campaign_id": 709513073,
    "ad_group_id": null,
    "ad_id": null,
    "description": "markdown — что предлагаем и зачем",
    "reasoning": "цифры обоснования: cost X, leads Y, ARPL ratio Z",
    "proposed_action": {"tool": "direct.set_state", "args": {...}},
    "ttl_hours": 24
  },
  ...
]
```

Скилл сам ставит `expires_at = now() + ttl_hours` и `status='pending'`.
Возвращает массив `[{id: N, expires_at: "..."}, ...]`.

## Жизненный цикл

```
pending  ──── 24ч ────►  expired (не обсуждали)
   │
   │ диалог
   ▼
discussing
   │
   ├──► applied (Валерий сказал «применяй»)
   ├──► rejected (Валерий отказал; reason обязателен)
   └──► superseded (новое предложение перекрыло старое)
```

## Инварианты

- **TTL 24ч по умолчанию** — потом `expire-old` помечает как expired.
- **`reasoning` обязательно** — иначе просто шум для Валерия.
- **`proposed_action` структурирован** — чтобы Phase 2 мог авто-применять.
  В Phase 1 — поле справочное.
- **Не повторяй уже pending** — перед `insert` агент должен проверить
  `list-active` чтобы не дублировать предложение.
- **chat_context** пишется при любом обмене — позволяет восстанавливать
  диалог через дни.

## Связи

- Схема: `goliath.proposals`, `goliath.chat_context`
  ([[Голиаф v2 — спецификация агента]] раздел 6)
- Используется: `routines/daily.py`, любая Claude Code сессия Валерия
- View: `goliath.v_active_proposals`
