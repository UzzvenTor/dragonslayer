# Голиаф — Daily Report (запуск)

Ежедневный отчёт по 4 кампаниям в `porg-6vgf2ozq`. В 08:00 МСК через Windows Task Scheduler.

## Структура

```
goliath_daily/
├── .env                       — токены и конфиг
├── daily_report.py            — главный скрипт
├── run_goliath.bat            — обёртка для cron
├── modules/
│   ├── yandex_direct.py       — Reports API: cost/clicks/conversions
│   ├── metrika.py             — уникальные лиды per utm_campaign×medium
│   ├── getcourse_db.py        — зрители + продажи из MySQL
│   ├── claude_insights.py     — генерация отчёта (OpenRouter → Sonnet 4.6)
│   ├── tg_send.py             — отправка в @goliath77_bot
│   └── obsidian_save.py       — копия в Wiki/.../daily_reports/
└── reports/                   — архив raw JSON + логи
```

## Первый запуск

### 1. Установить зависимости

```bash
pip install -r requirements.txt
```

### 2. Получить chat_id (один раз)

Напиши `/start` боту **@goliath77_bot** в Telegram. После этого Голиаф сможет тебе писать.

Проверить, что chat_id поймался:

```bash
curl "https://api.telegram.org/bot8774625736:AAF5cy4iz4_NULD0CpmcDlhTVbnx6cwSjI4/getUpdates"
```

`message.chat.id` должен быть `37116590` (текущее значение в `.env`). Если другой — поменять.

### 3. Тестовый запуск

```bash
# Без отправки в ТГ — просто текст в консоль
python daily_report.py --dry-run

# Конкретная дата
python daily_report.py --date 2026-05-05 --dry-run

# Реальный отчёт за вчера
python daily_report.py
```

В Obsidian отчёт появится в `Wiki/channels/yandex-direct/daily_reports/YYYY-MM-DD.md`.

## Cron (Windows Task Scheduler)

### Создать задачу

```powershell
# В PowerShell от админа
schtasks /create /tn "Goliath Daily Report" ^
  /tr "I:\neuro\GENERAL CLAUDE CODE\Zerocoder\goliath_daily\run_goliath.bat" ^
  /sc daily /st 08:00 /f
```

Или через GUI:
1. **Win** → `Планировщик заданий` → `Создать простую задачу`
2. **Имя:** `Goliath Daily Report`
3. **Триггер:** Ежедневно, начало `08:00`
4. **Действие:** Запуск `I:\neuro\GENERAL CLAUDE CODE\Zerocoder\goliath_daily\run_goliath.bat`
5. **Свойства задачи** → Условия → снять «Запускать только при питании от сети»
6. **Свойства** → Параметры → ✅ «Выполнять задачу как можно скорее, если запланированный запуск был пропущен»

### Проверить расписание

```powershell
schtasks /query /tn "Goliath Daily Report" /v
```

### Тест — запустить вручную

```powershell
schtasks /run /tn "Goliath Daily Report"
```

Лог появится в `reports\run_YYYY-MM-DD.log`.

## Источники данных

| Блок | Источник | Что берём |
|---|---|---|
| Траты, клики, конверсии Я.Директа | `/json/v5/reports` (CAMPAIGN_PERFORMANCE_REPORT) | Cost, Clicks, Impressions, Conversions per CampaignId |
| Состояния кампаний | `/json/v5/campaigns get` | State, Status, StatusPayment |
| Уникальные лиды | Метрика Reports API | goal `332807191` users per utm_campaign × utm_medium |
| Зрители вебинаров | `bizonViewers` MySQL | DISTINCT user_email per utm_campaign × utm_medium |
| Продажи | `getcoursePayments` × `main_yandex` | DISTINCT number, SUM(sum) per utm_campaign |

## Стоимость

Каждый отчёт расходует ~3-5 К токенов в Sonnet 4.6 через OpenRouter (~₽1-2 за день). Месяц = ~₽30-60.

## Отладка

Если что-то не работает:

1. Смотрим лог последнего запуска: `reports/run_YYYY-MM-DD.log`
2. Смотрим raw JSON: `reports/YYYY-MM-DD.json` — там видно, какой блок упал и с какой ошибкой
3. Каждый модуль можно запустить отдельно для проверки:

```bash
python modules/yandex_direct.py    # тестовый pull Я.Директа
python modules/metrika.py          # тестовый pull Метрики
python modules/getcourse_db.py     # тестовый pull MySQL
```

## Связанные

- Кабинет: `porg-6vgf2ozq` ([snapshot](../../OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер%20Трафик/Wiki/channels/yandex-direct/launches/2026-04-30%20запуск%20porg-6vgf2ozq%20%E2%80%94%204%20кампании.md))
- API справка: [Я.Директ API — рабочая справка для агента](../../OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер%20Трафик/Wiki/channels/yandex-direct/playbooks/Я.Директ%20API%20—%20рабочая%20справка%20для%20агента.md)
- Decision rules: [Decision rules для Голиафа](../../OBSIDIAN/Obsidian/KURZEMNEK/Зерокодер%20Трафик/Wiki/channels/yandex-direct/playbooks/Decision%20rules%20для%20Голиафа.md)
