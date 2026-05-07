---
name: goliath-negative-platforms
description: >
  Weekly review of РСЯ placements that burned budget without leads, and propose
  additions to negative-sites list. Pulls AD_PERFORMANCE_REPORT with PlacementName
  dimension via Я.Директ Reports API, joins with Метрика for unique-leads,
  applies 3×ARPL+50clicks rule. Phase 1: emits proposals (no auto-write).
  Triggers: "проверь минус-площадки", "negative-sites review", "что добавить
  в минусы".
---

# skill-negative-platforms — Голиаф

Раз в неделю (понедельник) — пересмотр площадок РСЯ. Защита от слива бюджета.

## Когда вызывать

**Только понедельник, утренний цикл.** В другие дни — пропустить.

## Как вызывать

```bash
python skills/skill-negative-platforms/review.py --lookback-days 14
```

Возвращает JSON: список proposal-кандидатов (категория `negative_site`)
готовых для skill-proposals.insert.

## Алгоритм

1. Pull AD_PERFORMANCE_REPORT (вместо CAMPAIGN_PERFORMANCE_REPORT) с
   dimensions `CampaignId, PlacementName` за `lookback_days` дней.
2. JOIN с Метрикой по `utm_campaign × utm_medium` чтобы получить уникальные
   лиды per кампания (площадка-уровня в Метрике нет напрямую — используем
   campaign-level lead-rate как прокси).
3. Применить правило: площадка-кандидат если
   - Cost ≥ 3 × ARPL_per_product
   - Clicks ≥ 50 (минимум статистики)
   - Кампания, которой принадлежит площадка, имеет нулевые лиды ИЛИ
     площадка непропорционально много откручивает на безлидовом дне
4. Защита: не минусуем агрегаторы (`yandex.ru`, `mail.ru`, `vk.com`).
5. Лимит: ≤ 30 новых площадок за один прогон (если кандидатов больше —
   самые «жирные» first; остальные на следующий понедельник).
6. Прочитать текущие `ExcludedSites` через `campaigns/get` — не дублировать.
7. Сформировать proposal с `proposed_action.tool = "direct.update_negative_sites"`.

## Phase 1 vs Phase 2

- **Phase 1**: эмитим proposal, ждём согласия Валерия в Claude Code, пишем
  «применено» в actions_log.
- **Phase 2**: при согласии вызываем skill-campaign-control.update_negative_sites
  → пишем в actions_log с `trigger_type='scheduled'`.

## Стартовый список (унаследован)

В `porg-6vgf2ozq` уже загружены **1 101 минус-площадка** из 4 кабинетов
подрядчиков (см. [[Минус-площадки для нового кабинета]]). Этот скилл
**дополняет** список из реальных данных нового кабинета.

## Инварианты

- **Только понедельник** (cron 08:00 МСК) — иначе шум.
- **Не удаляет** из минус-списка (только добавляет). Снять — отдельный
  редкий ручной кейс.
- **Не работает на кабинетах подрядчиков** (`imedia-zerocoder*`).

## Связи

- Wiki: [[skill-negative-platforms]] — расширенная документация
- Зависит: [[skill-analytics]] (per-platform pull в Phase 1 не реализован,
  делаем здесь)
- Применяет: [[skill-campaign-control]] · `update_negative_sites` (Phase 2)
- Стартовый список: [[Минус-площадки для нового кабинета]]
