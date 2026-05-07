"""Голиаф v2 — тестовый прогон отчёта в ТГ.

Минимальный runner. Берёт snapshot из БД goliath.daily_snapshots (уже посчитан с правильной
cohort-доходимостью), cost/state из последнего v1 raw JSON, формирует HTML-отчёт и шлёт
в @goliath77_bot.

В будущем заменится полноценным routines/daily.py с самостоятельным pull данных.

Запуск:
    python test_run.py [--snapshot-date YYYY-MM-DD] [--dry-run]
"""
import os, sys, json, datetime, argparse, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
import psycopg2

# Используем .env старого v1 для токенов
load_dotenv(r"I:\neuro\GENERAL CLAUDE CODE\Zerocoder\dragonslayer\goliath_daily\.env")

TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

PG_DSN = ("host=rc1b-nftoajilh0nnj0gf.mdb.yandexcloud.net port=6432 "
          "user=kurzemnek_app password='zvriR-DTtbyhx3b' dbname=kurzemnek sslmode=require")

PRODUCT_ORDER = ["sysai", "openclaw", "n8n", "law"]
TARGET_CPL = {"sysai": 1077, "openclaw": 1308, "n8n": 1231, "law": 846}
ARPL = {"sysai": 1400, "openclaw": 1700, "n8n": 1600, "law": 1100}


def fetch_snapshot(snapshot_date):
    pg = psycopg2.connect(PG_DSN, connect_timeout=15)
    rows = []
    with pg.cursor() as cur:
        cur.execute("SET search_path TO goliath, public")
        cur.execute("""
            SELECT product, cost_rub, clicks, impressions, unique_leads, viewers,
                   viewer_rate_pct, paid_orders, revenue_rub, cpa_rub, roas_pct, raw_data
            FROM daily_snapshots
            WHERE snapshot_date = %s
            ORDER BY array_position(%s::text[], product)
        """, (snapshot_date, PRODUCT_ORDER))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    pg.close()
    return rows


def fetch_states(date_str):
    """Подцепить states из последнего raw JSON v1."""
    p = rf"I:\neuro\GENERAL CLAUDE CODE\Zerocoder\dragonslayer\goliath_daily\reports\{date_str}.json"
    if not os.path.isfile(p):
        return {}
    raw = json.load(open(p, encoding="utf-8"))
    return raw.get("states") or {}


def fmt_rub(n):
    if n is None: return "—"
    n = float(n)
    if n == 0: return "0"
    return f"{n:,.0f}".replace(",", " ")


def build_report(snapshot_date, rows, states):
    """Формат HTML для Telegram (parse_mode=HTML)."""
    yday = snapshot_date
    mtd_from = snapshot_date[:8] + "01"

    lines = []
    lines.append("🧪 <b>ТЕСТОВЫЙ ПРОГОН — Голиаф v2 (cohort-логика)</b>\n")
    lines.append(f"<b>📊 Снапшот за {snapshot_date} (MTD {mtd_from} → {yday})</b>\n")

    # Состояние кампаний
    if states:
        all_on = all(v.get("state") == "ON" and v.get("status") == "ACCEPTED" for v in states.values())
        if all_on:
            lines.append("✅ Все 4 кампании ON / ACCEPTED\n")
        else:
            lines.append("⚠️ Не все кампании ON:")
            for cid, v in states.items():
                if v.get("state") != "ON":
                    lines.append(f"  • {v.get('name', cid)} — state={v.get('state')}, status={v.get('status')}")
            lines.append("")

    # Воронка месяца
    lines.append(f"<b>Воронка MTD ({mtd_from} → {yday}):</b>")
    lines.append("<pre>")
    lines.append(f"{'Прод.':8} {'Расход':>8} {'Уник':>5} {'Зрит':>5} {'Дох%':>5} {'CPA':>6} {'CPL/ARPL':>8}")
    tot = {"cost": 0, "leads": 0, "viewers": 0}
    insights = []
    for r in rows:
        p = r["product"]
        cost = float(r["cost_rub"] or 0)
        leads = int(r["unique_leads"] or 0)
        viewers = int(r["viewers"] or 0)
        rate = float(r["viewer_rate_pct"] or 0)
        cpa = float(r["cpa_rub"] or 0)
        target = TARGET_CPL[p]
        cpa_ratio = cpa / target if target else 0
        cpa_flag = "✅" if cpa_ratio <= 1.0 and leads > 0 else ("⚠️" if cpa_ratio <= 1.5 else "🚨")
        if leads == 0:
            cpa_str = "—"
            cpa_flag = "⏳"
        else:
            cpa_str = f"{cpa:.0f}"
        lines.append(f"{p:8} {fmt_rub(cost):>8} {leads:>5} {viewers:>5} {rate:>4.0f}% {cpa_str:>6} {cpa_flag} {target}")
        tot["cost"] += cost
        tot["leads"] += leads
        tot["viewers"] += viewers

        # Сборка инсайтов
        if leads > 0 and viewers == 0:
            insights.append(f"🚨 <b>{p}</b>: {leads} рег, 0 дошли до веба за 4 дня. CPA {cpa:.0f} = деньги тратятся в холостую. Сигнал на пересмотр (лендинг/время веба/тексты).")
        elif cpa_ratio > 1.5 and leads >= 2:
            insights.append(f"⚠️ <b>{p}</b>: CPA {cpa:.0f} = {cpa_ratio:.1f}× target {target}. Наблюдаем — порог стопа адсета по 5×ARPL = {ARPL[p]*5:.0f}₽.")
        elif rate >= 100:
            insights.append(f"✨ <b>{p}</b>: доходимость {rate:.0f}% (cohort = все уники дошли). Top для этого периода.")

    tot_cpa = tot["cost"] / tot["leads"] if tot["leads"] else 0
    tot_rate = tot["viewers"] / tot["leads"] * 100 if tot["leads"] else 0
    lines.append(f"{'TOTAL':8} {fmt_rub(tot['cost']):>8} {tot['leads']:>5} {tot['viewers']:>5} {tot_rate:>4.0f}% {tot_cpa:>6.0f}")
    lines.append("</pre>")

    # Инсайты
    if insights:
        lines.append("\n<b>💡 Инсайты:</b>")
        for ins in insights:
            lines.append(f"• {ins}")

    # Спец-замечание
    lines.append("\n<i>📋 Заметки:</i>")
    lines.append("• <b>KPI лидов</b> = Метрика-уник.рег (цель <code>unic</code> 332807191)")
    lines.append("• <b>Зрители</b> — cohort по тем же уникам через email-сшивку (getcourseUsers ∩ bizonViewers)")
    lines.append("• <b>law</b> — Bizon-direct воронка (форма обходит getcourseRegistrations)")
    lines.append("• 0 продаж пока — норма для цикла сделки 10 дней. Первые оплаты ждём 11-15 мая")

    # Side-метрика gcReg
    side_gc_regs = sum(int((r.get("raw_data") or {}).get("gc_registrations_side_metric") or 0) for r in rows)
    if side_gc_regs:
        lines.append(f"• <i>Side: записей на webinar (gcReg) — {side_gc_regs} за MTD (KPI ещё не зашит)</i>")

    return "\n".join(lines)


def send_tg(html):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": TG_CHAT_ID,
        "text": html,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot-date", default="2026-05-04")
    ap.add_argument("--dry-run", action="store_true", help="не отправлять в ТГ — только показать")
    args = ap.parse_args()

    rows = fetch_snapshot(args.snapshot_date)
    if not rows:
        print(f"ERR: snapshot for {args.snapshot_date} not found in goliath.daily_snapshots")
        sys.exit(1)
    states = fetch_states(args.snapshot_date)
    html = build_report(args.snapshot_date, rows, states)

    print("=== HTML отчёт ===\n")
    # Превью без HTML-тегов для консоли
    preview = html.replace("<b>", "").replace("</b>", "").replace("<pre>", "").replace("</pre>", "").replace("<i>", "").replace("</i>", "").replace("<code>", "").replace("</code>", "")
    print(preview)
    print("\n" + "=" * 60)

    if args.dry_run:
        print("--- DRY RUN, не отправляем в ТГ ---")
        return

    print("\nОтправка в ТГ...")
    resp = send_tg(html)
    print(f"TG response: ok={resp.get('ok')}, message_id={resp.get('result', {}).get('message_id')}")


if __name__ == "__main__":
    main()
