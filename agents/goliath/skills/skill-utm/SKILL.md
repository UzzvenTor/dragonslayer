---
name: goliath-utm
description: >
  Generate UTM tags for Голиаф's campaigns following the v0.2 schema:
  utm_medium=goliath, utm_term=H<NN>__<product>__v<N>. Used by skill-hypothesis
  when proposing new ads. Triggers: "сгенерируй UTM", "make UTM", "разметка
  для гипотезы H08".
---

# skill-utm — Голиаф

Единая UTM-разметка кампаний агента. Из спеки [[Голиаф — UTM-схема разметки]].

## Каноническая схема

```
utm_source   = yandex
utm_medium   = goliath              ← всегда ровно так, без суффиксов
utm_campaign = {campaign_id}        ← ID кампании Я.Директа
utm_content  = {ad_id}              ← ID объявления (если есть)
utm_term     = H<NN>__<product>__v<N>
```

Зарезервированные префиксы term:
- `H<NN>__` — стандартная гипотеза (H07, H08, ...)
- `Hexp<NN>__` — A/B-эксперимент в рамках гипотезы
- `Hret<NN>__` — ретаргет
- `Hscale<NN>__` — масштабирование винера

## Как вызывать

```bash
python skills/skill-utm/utm.py --campaign-id 709674000 --ad-id 12345 \
    --hypothesis H08 --product sysai --variation v1
```

stdout — JSON с 5 полями.

## Зачем единая схема

По utm_term Голиаф собирает свой ROAS одним SQL:

```sql
WHERE utm_medium = 'goliath' AND utm_term LIKE 'H08__%'
```

Подрядчики не используют medium=goliath (у них `vika3`, `egor`, ...) —
автоматическая изоляция.
