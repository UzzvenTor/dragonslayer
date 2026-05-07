---
name: goliath-creative-banner
description: >
  Generate РСЯ banner images for Голиаф via OpenRouter gpt-image API
  (currently gpt-5.4-image-2). Three РСЯ aspect ratios: 1080×607 (16:9),
  1080×1350 (4:5), 600×600 (1:1). Triggers: "сгенерируй баннер", "новые
  визуалы для H08", "banner for openclaw v3".
---

# skill-creative-banner — Голиаф

Генерация баннеров под РСЯ. В Phase 1 — Голиаф **ставит ТЗ**, генерирует
варианты, показывает в ТГ; Валерий одобряет/правит → Голиаф загружает
через skill-campaign-control (Phase 2). В Phase 1 загрузка делается руками
если предложение принято.

## Когда вызывать

- skill-hypothesis предлагает visual-test или anti-burnout → нужно 3-5
  свежих визуалов под одну гипотезу.
- Phase 2: weekly creative rotation в понедельник.
- Валерий просит «сделай 2 баннера для openclaw H08 v4».

## Существующие скрипты (исторические)

В этой папке лежат helper-скрипты от запуска H08 (2026-05-06):

| Файл | Что делает |
|---|---|
| `_generate_h08.py` | Массовая генерация 17 баннеров H08 (4×sysai + 4×openclaw + 5×n8n + 4×law) |
| `_relaunch_h08_v2.py` | Перегенерация после правок brief |
| `_apply_h08_corrections.py` | Точечные правки конкретных баннеров |
| `_test_one.py`, `_test_styles.py` | Single-banner проба разных стилей |
| `_wordstat_check.py`, `_wordstat_filter.py`, `_wordstat_probe.py` | Проверка ключей через Wordstat (для копи, не для баннеров) |

Их паттерн = **прямой POST в OpenRouter** (chat/completions с image
generation), параллелизм через ThreadPoolExecutor (4 потока). Стоимость
~$0.20/баннер.

## Контракт нового вызова (общий шаблон)

**Вход:**
- `product` — sysai/openclaw/n8n/law
- `hook` — главный тезис (от skill-ad-copy)
- `style` — `tech` / `business` / `education` / `legal` / `flat-isometric`
- `sizes` — список из `["1080x607", "1080x1350", "600x600"]`
- `count` — обычно 1-2

**Выход:**
- Файлы в `I:/OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер Трафик/Raw/banners/<H_NN>/`
- Метаданные prompt'а в `<H_NN>_metadata.json` рядом

## Алгоритм

1. Базовый prompt-template — `build_prompt(scene, style, title, subtitle, badge)`
   — см. `_generate_h08.py:45`. Структура: scene + style_constraints +
   russian_text_overlay + brand_badge.
2. POST в OpenRouter `chat/completions` с image-generation моделью.
3. Декодировать base64-PNG, сохранить в Raw/banners/<H_NN>/.
4. **Брендинг Зерокодера**: маленький бейдж в углу зелёного цвета
   `#1DB573` с надписью «Бесплатный практикум». Только для education/business
   стилей (не для tech/legal).
5. **Запреты в prompt** (всегда добавлять):
   - NO neon
   - NO AI-futurism cliches (роботы со светящимися глазами, чипы,
     киберпанк)
   - NO chaos (всё в композиции)
   - Photo-realistic OR clean illustration — без middle-ground

## Размеры РСЯ (важно)

| Aspect | Resolution | Где показывается |
|---|---|---|
| 16:9 | 1080×607 | Главные плейсменты, видео-замены |
| 4:5 | 1080×1350 | Mobile feed, stories-like |
| 1:1 | 600×600 | Сжатые превью, native ads |

Я.Директ комбинаторные ЕПК (TextAdBuilderAd) хотят все 3 размера на каждый
визуальный «вариант».

## Инварианты

- **Текст overlay — Russian**, кириллица. Модели иногда плохо рисуют
  кириллицу — Phase 1 решение: render через HTML+Puppeteer overlay поверх
  PNG (TODO: spec этого пайплайна, в `_generate_h08.py` пока через prompt).
- **Output только в Raw/banners/** — никаких stray PNG в код или в C:/.
- **OPENROUTER_API_KEY** — из dragonslayer .env, не дублируем.
- **Цена** — генерация 4 баннеров × 3 размера = 12 запросов × $0.20 ≈ $2.4.
  Лимит на одну гипотезу.

## TODO (Phase 2)

- Унифицировать все исторические `_*.py` скрипты в один `banner.py` с
  единым CLI: `python banner.py --product sysai --hook "..." --hypothesis H10
  --count 2 --sizes 1080x607,1080x1350`.
- Добавить HTML-overlay шаг для надёжной кириллицы.
- Связать с skill-campaign-control для авто-загрузки `AdImageHashes`.

## Связи

- Wiki: [[skill-creative-banner]] — расширенная документация
- Зависит: [[skill-ad-copy]] (откуда hook/title/body)
- Применяется: [[skill-campaign-control]] (загрузка ImageAd, Phase 2)
- Источник `OPENROUTER_API_KEY`: `dragonslayer/goliath_daily/.env`
