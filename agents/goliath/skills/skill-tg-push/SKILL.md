---
name: goliath-tg-push
description: >
  Send HTML-formatted message to Telegram bot @goliath77_bot (chat_id Валерия
  37116590). Use for the morning daily report, urgent ARPL-trigger pushes,
  applied-action confirmations. Triggers: "push в ТГ", "send to telegram",
  "отправь отчёт", "уведоми Валерия".
---

# skill-tg-push — Голиаф

Чистый push-канал. **TG = только уведомления; диалог в Claude Code.**

## Когда вызывать

- Финал утреннего цикла — отправить HTML-отчёт.
- (Phase 2) Постфактум-уведомление об auto-stop.
- Подтверждение применённого предложения после диалога с Валерием.

## Как вызывать

```bash
# stdin: HTML-text. Альтернативно — через --file.
echo "<b>Тест</b>" | python skills/skill-tg-push/push.py
python skills/skill-tg-push/push.py --file /tmp/report.html
```

## Контракт

stdin или `--file` → POST `api.telegram.org/bot<TOKEN>/sendMessage`,
parse_mode=HTML, disable_web_page_preview=true. Печатает `ok=true,
message_id=...` или ошибку.

## Инварианты

- **HTML, не Markdown** — Telegram умеет HTML, но крайне ограниченный
  набор тегов: `<b>`, `<i>`, `<u>`, `<s>`, `<code>`, `<pre>`, `<a href>`.
  Списки/таблицы — только через `<pre>` с моноширинным выравниванием.
- **Лимит 4096 символов** на одно сообщение. Если длиннее — резать на части
  с продолжением `(2/N)`. В Phase 1 одно сообщение всегда ≤4К.
- **chat_id и token из env** — `TG_CHAT_ID`, `TG_BOT_TOKEN`. Не хардкодим.
