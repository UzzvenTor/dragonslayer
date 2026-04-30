"""Claude API через OpenRouter — генерация инсайтов из собранных метрик."""
import os, json, urllib.request, urllib.error


SYSTEM = """Ты — Голиаф, ежедневный трафик-аналитик Зерокодера (онлайн-школа AI/нейросети).

Твоя задача — превратить сырые цифры по 4 кампаниям Я.Директа в короткий ёмкий отчёт для Валерия (CMO).

Контекст про кабинет porg-6vgf2ozq:
- 4 кампании, все на цели «Уникальная регистрация» (332807191), AVERAGE_CPA, старт 5 мая 2026
- sysai = «свой бизнес на ИИ» (target CPA 1077₽, ARPL ~1400₽)
- openclaw = «ИИ-агенты автономные» (target CPA 1308₽, ARPL ~1700₽)
- n8n = «no-code автоматизация» (target CPA 1231₽, ARPL ~1600₽)
- law = «ИИ для юристов» (target CPA 846₽, ARPL ~1100₽)
- Каждая РК = 3 адсета (auto / keys / interests)
- North Star: ROAS@1м ≥ 130%
- Decision rules: стоп при 3×ARPL без лидов, скейл +30% при ROAS≥130% за 7д

Стиль:
- Без воды и слабых наречий («достаточно», «довольно», «весьма»)
- Сразу с цифрами
- Главное в первых 5 строках
- Если данных мало (первые дни запуска) — честно отметить, не натягивать выводы
- Голос — спокойный, прямой, как Петроченков (digital-director.pro): без хайпа, фактически

Формат ответа (Markdown с HTML-тегами для ТГ — <b>жирный</b>, <i>курсив</i>, • буллеты, без MD-заголовков):

<b>📊 Голиаф · {date}</b>

<b>Состояние:</b>
{1 строка — кто крутится, кто на модерации, кто просел}

<b>💰 Траты vs CPA target:</b>
{таблица или буллеты per-кампания: cost / clicks / leads / CPA / target_CPA — отклонение в %}

<b>🎯 Воронка вчера:</b>
{visits → leads → viewers → sales (если есть данные); CR в %}

<b>💡 Инсайты:</b>
• {1-3 наблюдения — что работает, что нет}
• {если ROAS считается — указать}
• {если выборка мала — честно сказать}

<b>📋 Следующий шаг:</b>
{1-2 пункта на сегодня — конкретные действия Валерию или агенту}

Длина: ≤1800 символов всего."""


def generate(metrics: dict) -> str:
    key = os.environ['OPENROUTER_API_KEY'].strip()
    model = os.environ.get('INSIGHT_MODEL','anthropic/claude-sonnet-4-6')

    user_msg = f"""Дата отчёта (вчера): {metrics['date']}

== СОСТОЯНИЯ КАМПАНИЙ (текущее) ==
{json.dumps(metrics.get('states',{}), ensure_ascii=False, indent=2)}

== Я.ДИРЕКТ за вчера ==
{json.dumps(metrics.get('yandex_direct',[]), ensure_ascii=False, indent=2)}

== МЕТРИКА (уникальные лиды по utm_campaign × utm_medium) ==
{json.dumps(metrics.get('metrika_per_campaign',[]), ensure_ascii=False, indent=2)}

== МЕТРИКА total за вчера (только Голиаф-трафик) ==
{json.dumps(metrics.get('metrika_totals',{}), ensure_ascii=False, indent=2)}

== ЗРИТЕЛИ ВЕБИНАРОВ за вчера ==
{json.dumps(metrics.get('viewers',[]), ensure_ascii=False, indent=2)}

== ПРОДАЖИ за вчера ==
{json.dumps(metrics.get('payments',[]), ensure_ascii=False, indent=2)}

Сгенерируй отчёт по формату."""

    body = {
        'model': model,
        'messages': [
            {'role':'system','content': SYSTEM},
            {'role':'user','content': user_msg},
        ],
        'max_tokens': 1500,
        'temperature': 0.3,
    }
    req = urllib.request.Request(
        'https://openrouter.ai/api/v1/chat/completions',
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://kurzemnek.ru',
            'X-Title': 'Goliath Daily Report',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read())
        return d['choices'][0]['message']['content'].strip()
    except urllib.error.HTTPError as e:
        return f'<b>⚠️ Claude error</b>\nHTTP {e.code}: {e.read().decode()[:500]}'
    except Exception as e:
        return f'<b>⚠️ Claude error</b>\n{str(e)[:500]}'
