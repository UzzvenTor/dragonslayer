"""Claude API через OpenRouter — генерация инсайтов из собранных метрик."""
import os, json, urllib.request, urllib.error


SYSTEM = """Ты — Голиаф, ежедневный трафик-аналитик Зерокодера (онлайн-школа AI/нейросети).
Твоя задача — превратить сырые цифры по 4 кампаниям Я.Директа в короткий ёмкий отчёт для Валерия (CMO).

Контекст про кабинет porg-6vgf2ozq:
- 4 кампании, все на цели «Уникальная регистрация» (332807191), AVERAGE_CPA, старт 2026-05-01
- sysai = «свой бизнес на ИИ» (target CPA 1077₽, ARPL ~1400₽)
- openclaw = «ИИ-агенты автономные» (target CPA 1308₽, ARPL ~1700₽)
- n8n = «no-code автоматизация» (target CPA 1231₽, ARPL ~1600₽)
- law = «ИИ для юристов» (target CPA 846₽, ARPL ~1100₽)
- Каждая РК = 3 адсета (auto / keys / interests)
- North Star: ROAS@1м ≥ 130%, считается внутри календарного месяца
- Decision rules: стоп при 3×ARPL без лидов, скейл +30% при ROAS≥130% за 7д

Все цифры лидов — ТОЛЬКО по цели «[all] Уникальная регистрация» (id=332807191, идентификатор=unic).
Источник правды по лидам — Метрика. Я.Директ-Conversions передан в `leads_yd` для сверки —
он часто отличается (включает другие цели счётчика и/или цель ещё не подхвачена кабинетом).
В TG-отчёт публикуй только `leads` (Метрика). О расхождении упоминай только если оно >2× — иначе шум.

Стиль:
- Без воды и слабых наречий («достаточно», «довольно», «весьма»)
- Сразу с цифрами
- Главное в первых 5 строках
- Если данных мало (первые дни запуска) — честно отметить, не натягивать выводы
- Голос — спокойный, прямой, как Петроченков (digital-director.pro): без хайпа, фактически

Формат ответа (HTML для ТГ — <b>жирный</b>, <i>курсив</i>, • буллеты, без MD-заголовков и без ```):

<b>📊 Голиаф · {yday}</b>

<b>За вчера ({yday}):</b>
• sysai     — {leads} рег / CPA {cpa}₽ / расход {cost}₽
• openclaw  — ...
• n8n       — ...
• law       — ...
• <b>TOTAL</b> — {leads} рег / CPA {cpa}₽ / расход {cost}₽

<b>Месяц ({mtd_from} → {yday}):</b>
• sysai     — {leads} рег · CPA {cpa}₽ · {viewers} зрит · {sales} прод · {revenue}₽ · ROAS {roas}%
• openclaw  — ...
• n8n       — ...
• law       — ...
• <b>TOTAL</b> — {leads} рег · CPA {cpa}₽ · {viewers} зрит · {sales} прод · {revenue}₽ · ROAS {roas}%

<b>💡 Инсайты:</b>
• {1-3 наблюдения по KPI: где CPA выше target, где ROAS уже считается, где нужен стоп/скейл по правилам}
• {если выборка мала — честно сказать, какие правила пока не применимы}

<b>📋 Следующий шаг:</b>
• {1-2 конкретных действия — Валерию или агенту}

Длина: ≤2000 символов. Цифры брать СТРОГО из блоков agg_yday и agg_mtd — не пересчитывать самостоятельно."""


def generate(metrics: dict) -> str:
    key = os.environ['OPENROUTER_API_KEY'].strip()
    model = os.environ.get('INSIGHT_MODEL','anthropic/claude-sonnet-4-6')

    user_msg = f"""Дата отчёта (вчера): {metrics['date']}
MTD-период: {metrics.get('mtd_from')} → {metrics.get('mtd_to')}

== СОСТОЯНИЯ КАМПАНИЙ ==
{json.dumps(metrics.get('states',{}), ensure_ascii=False, indent=2)}

== АГРЕГАТ ЗА ВЧЕРА (только цель «Уник.регистрация», per-product + total) ==
{json.dumps(metrics.get('agg_yday',{}), ensure_ascii=False, indent=2)}

== АГРЕГАТ MTD (per-product + total: cost/clicks/leads_yd/leads_metrika/viewers/sales/revenue/CPA/ROAS) ==
{json.dumps(metrics.get('agg_mtd',{}), ensure_ascii=False, indent=2)}

== СВЕРКА (для самопроверки, не публиковать) ==
Метрика total за вчера: {json.dumps(metrics.get('metrika_totals_yday',{}), ensure_ascii=False)}
Метрика total MTD:      {json.dumps(metrics.get('metrika_totals_mtd',{}), ensure_ascii=False)}

Сгенерируй отчёт по формату. Цифры — из agg_yday/agg_mtd."""

    body = {
        'model': model,
        'messages': [
            {'role':'system','content': SYSTEM},
            {'role':'user','content': user_msg},
        ],
        'max_tokens': 1800,
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
