# Драконоборец

Ежедневный автоотчёт CMO Zerocoder: новые реги на вебинары, лидмагниты, заявки на детское демо — за вчерашний день. Стартует удалённой Claude Code сессией по крону в 08:00 МСК и шлёт в ТГ-бота `@dragonslayerr_bot`.

## Архитектура

- `metrics.py` — тянет цифры из MySQL Zerocoder, пишет `out/latest.json`
- `send.py` — отправка HTML-сообщения в Telegram
- `shared_local/db.py`, `shared_local/filters.py` — коннект к БД + фильтры детских лидов
- `RUN.md` — инструкция для крон-сессии (что делать, как верстать)
- `STYLE.md` — тон отчёта (сухая сводка, без образных глаголов)
- `out/` — артефакты прогонов (не в git)

## Секреты

Все в `.env` в корне — TG-токен, chat_id, MySQL-креды. Репо приватный.

## Запуск вручную

```bash
pip install -r requirements.txt
python metrics.py --out out/latest.json
# Claude-агент (или ты) пишет отчёт в out/latest.txt по STYLE.md
python send.py out/latest.txt
```

## Крон-сессия

Triggered через Anthropic Scheduled Agents. Промпт сессии:
> Прочитай `RUN.md` и выполни шаги. Не задавай вопросов.

См. `RUN.md` для пошаговой инструкции.
