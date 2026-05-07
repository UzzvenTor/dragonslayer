"""skill-decision-rules — детерминированный evaluator правил R1/R3/R6.

Запуск:
    python rules.py --file snap.json
    cat snap.json | python rules.py
"""
from __future__ import annotations

import argparse
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")


# Из Wiki: Decision rules для Голиафа.md
ARPL = {"sysai": 1400, "openclaw": 1700, "n8n": 1600, "law": 1100}
TARGET_CPL = {"sysai": 1077, "openclaw": 1308, "n8n": 1231, "law": 846}

# campaign_id → product (зеркало CAMP_TO_PRODUCT в snapshot.py)
CAMP_TO_PRODUCT = {
    "709513073": "sysai", "709513492": "openclaw",
    "709513513": "n8n", "709513517": "law",
    "709674000": "sysai", "709674060": "openclaw",
    "709674103": "n8n", "709674151": "law",
}


def _state_aware(states: dict, p: str, *, want_active=True) -> bool:
    """True если есть хотя бы одна ON+ACCEPTED кампания этого продукта."""
    for cid, st in (states or {}).items():
        if CAMP_TO_PRODUCT.get(str(cid)) != p:
            continue
        active = (st.get("state") == "ON" and st.get("status") == "ACCEPTED")
        if want_active and active:
            return True
    return False


def evaluate(snapshot: dict) -> list[dict]:
    """Возвращает список proposal-кандидатов."""
    out = []
    states = snapshot.get("states") or {}

    # MTD per_product — основное окно для R1 и R6
    mtd_pp = (snapshot.get("mtd") or {}).get("per_product") or []
    mtd_by_product = {r["product"]: r for r in mtd_pp}

    # Week per_product — для R3
    week_pp = (snapshot.get("week") or {}).get("per_product") or []
    week_by_product = {r["product"]: r for r in week_pp}

    for p in ("sysai", "openclaw", "n8n", "law"):
        m = mtd_by_product.get(p) or {}
        w = week_by_product.get(p) or {}
        cost_mtd = float(m.get("cost_rub") or 0)
        leads_mtd = int(m.get("leads") or 0)
        impressions_mtd = int(m.get("impressions") or 0)
        clicks_mtd = int(m.get("clicks") or 0)
        revenue_mtd = float(m.get("revenue_rub") or 0)
        ctr_mtd = (clicks_mtd / impressions_mtd * 100) if impressions_mtd else 0
        roas_mtd = (revenue_mtd / cost_mtd * 100) if cost_mtd else 0

        cost_week = float(w.get("cost_rub") or 0)
        leads_week = int(w.get("leads") or 0)
        clicks_week = int(w.get("clicks") or 0)
        cpl_week = (cost_week / leads_week) if leads_week else 0

        arpl = ARPL[p]
        target_cpl = TARGET_CPL[p]
        is_active = _state_aware(states, p, want_active=True)

        # ── R1 ARPL-каскад ──
        if leads_mtd == 0 and is_active:
            if cost_mtd >= 10 * arpl:
                ratio = cost_mtd / arpl
                out.append({
                    "category": "urgent_arpl_stop", "product": p,
                    "campaign_id": None,
                    "description": (f"🔥🔥🔥 10×ARPL без лидов — стоп ВСЕХ активных "
                                    f"кампаний продукта **{p}**"),
                    "reasoning": (f"MTD cost {cost_mtd:.0f}₽ ≥ 10×ARPL "
                                  f"(10×{arpl}={10*arpl}₽), уник.лидов 0 ({ratio:.1f}×). "
                                  f"Phase 1: предложение, не auto."),
                    "proposed_action": {"tool": "direct.set_state",
                                        "args": {"product": p, "state": "SUSPENDED",
                                                 "scope": "all_active"}},
                    "ttl_hours": 12,
                })
            elif cost_mtd >= 5 * arpl:
                ratio = cost_mtd / arpl
                out.append({
                    "category": "urgent_arpl_stop", "product": p,
                    "campaign_id": None,
                    "description": f"🔥🔥 5×ARPL без лидов — рассмотреть стоп адсета **{p}**",
                    "reasoning": (f"MTD cost {cost_mtd:.0f}₽ ≥ 5×ARPL "
                                  f"(5×{arpl}={5*arpl}₽), уник.лидов 0 ({ratio:.1f}×)."),
                    "proposed_action": {"tool": "direct.set_state",
                                        "args": {"product": p, "state": "SUSPENDED",
                                                 "scope": "ad_group"}},
                    "ttl_hours": 24,
                })
            elif cost_mtd >= 3 * arpl:
                ratio = cost_mtd / arpl
                out.append({
                    "category": "urgent_arpl_stop", "product": p,
                    "campaign_id": None,
                    "description": f"🔥 3×ARPL без лидов — рассмотреть стоп **{p}**",
                    "reasoning": (f"MTD cost {cost_mtd:.0f}₽ ≥ 3×ARPL "
                                  f"(3×{arpl}={3*arpl}₽), уник.лидов 0 ({ratio:.1f}×)."),
                    "proposed_action": {"tool": "direct.set_state",
                                        "args": {"product": p, "state": "SUSPENDED",
                                                 "scope": "ad"}},
                    "ttl_hours": 24,
                })

        # ── R3 Scale +30% (week-окно) ──
        # CPL ≤ ARPL/1.3 = ROAS≥130% по cash-flow per-lead. clicks ≥ 30 как
        # минимум статистики.
        if leads_week >= 5 and clicks_week >= 30 and cpl_week and cpl_week <= target_cpl:
            out.append({
                "category": "scale_budget", "product": p,
                "campaign_id": None,
                "description": f"📈 ROAS≥130% за неделю — рассмотреть скейл +30% **{p}**",
                "reasoning": (f"Week: cost {cost_week:.0f}₽, лиды {leads_week}, "
                              f"CPL {cpl_week:.0f}₽ ≤ target {target_cpl}₽. "
                              f"+30% бюджета — следующая неделя; контроль: "
                              f"объём лидов должен вырасти ≥+15%, иначе откат."),
                "proposed_action": {"tool": "direct.set_daily_budget",
                                    "args": {"product": p, "delta_pct": 30}},
                "ttl_hours": 36,
            })

        # ── R6 CTR-trap ──
        if cost_mtd >= 10000 and ctr_mtd >= 2.0 and roas_mtd < 50 and revenue_mtd > 0:
            out.append({
                "category": "pause", "product": p,
                "campaign_id": None,
                "description": (f"⚠️ CTR-ловушка: высокий CTR при низком ROAS — "
                                f"рассмотреть стоп **{p}**"),
                "reasoning": (f"MTD: cost {cost_mtd:.0f}₽, CTR {ctr_mtd:.1f}%≥2%, "
                              f"ROAS {roas_mtd:.0f}%<50%. "
                              f"Я.Директ скейлит CTR-сильное → бюджет сгорает."),
                "proposed_action": {"tool": "direct.set_state",
                                    "args": {"product": p, "state": "SUSPENDED",
                                             "scope": "ad"}},
                "ttl_hours": 24,
            })

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="JSON snapshot; иначе stdin")
    args = ap.parse_args()

    text = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
    snap = json.loads(text)
    proposals = evaluate(snap)
    print(json.dumps(proposals, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
