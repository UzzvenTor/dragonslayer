"""Голиаф · daily orchestrator (thin).

**Это НЕ агент.** Агент = Claude Code session, читающий `daily-prompt.md` под
Anthropic Cloud Routine 08:00 МСК. Этот скрипт — детерминированный
helper для:

1. Cross-check данных (запусти локально с --dry-run, сравни с тем что Голиаф
   прислал в ТГ — должно совпадать).
2. Backup-режим: если cloud routine упал, можно вручную дёрнуть
   `python daily.py` и хотя бы snapshot-write пройдёт.
3. Тест в pre-deploy: запустить с --dry-run --date 2026-05-06 и убедиться
   что pipeline собирается.

Этот скрипт **не** генерирует narrative, **не** отправляет TG, **не**
формулирует proposals. Это работа Claude в routine.

Запуск:
    python daily.py [--date YYYY-MM-DD] [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
GOLIATH = HERE.parent
SKILLS = GOLIATH / "skills"


def _run(cmd: list[str], stdin: str | None = None) -> tuple[int, str, str]:
    """Выполняет subprocess, возвращает (returncode, stdout, stderr)."""
    p = subprocess.run(
        cmd, input=stdin, capture_output=True, text=True,
        encoding="utf-8", cwd=str(GOLIATH),
    )
    return p.returncode, p.stdout, p.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="yday в формате YYYY-MM-DD; default = today-1")
    ap.add_argument("--dry-run", action="store_true",
                    help="не пишет в БД и не вызывает rules; только snapshot + summary")
    ap.add_argument("--snap-out", default=str(Path(os.environ.get("TEMP", "/tmp")) / "goliath_snap.json"),
                    help="куда сохранить snapshot JSON")
    args = ap.parse_args()

    yday = (args.date or (datetime.date.today() - datetime.timedelta(days=1)).isoformat())

    print(f"=== Голиаф daily.py ({'DRY-RUN' if args.dry_run else 'LIVE'}) · yday={yday} ===\n")

    # 1. Snapshot
    print("[1/4] Pull snapshot via skill-analytics ...")
    rc, out, err = _run([
        sys.executable, str(SKILLS / "skill-analytics" / "snapshot.py"),
        "--date", yday, "--out", args.snap_out,
    ])
    if rc != 0:
        print(f"  ❌ snapshot failed: rc={rc}", file=sys.stderr)
        print(err[:1000], file=sys.stderr)
        sys.exit(1)
    print(f"  ✅ saved → {args.snap_out}")

    # Quick read snapshot for summary
    snap = json.loads(Path(args.snap_out).read_text(encoding="utf-8"))
    mtd_total = snap.get("mtd", {}).get("total", {}) or {}
    states = snap.get("states", {}) or {}
    errs = snap.get("errors", [])
    active = sum(1 for v in states.values() if v.get("state") == "ON")
    print(f"  states: {active}/{len(states)} ON, mtd.cost={mtd_total.get('cost_rub', 0):.0f}₽, "
          f"mtd.leads={mtd_total.get('leads', 0)}, errors={len(errs)}")

    if errs:
        for e in errs:
            print(f"    WARN {e.get('step')}: {e.get('error', '')[:120]}")

    # 2. Decision rules → JSON-кандидаты (всегда вычисляем для diagnostics)
    print("\n[2/4] Apply decision rules ...")
    rc, out, err = _run([
        sys.executable, str(SKILLS / "skill-decision-rules" / "rules.py"),
        "--file", args.snap_out,
    ])
    if rc != 0:
        print(f"  ❌ rules failed: rc={rc}", file=sys.stderr)
        print(err[:1000], file=sys.stderr)
        proposals = []
    else:
        proposals = json.loads(out or "[]")
        print(f"  ✅ {len(proposals)} rule-candidates")
        for p in proposals:
            print(f"    [{p['category']:20}] {p.get('product','?'):8} — {p['description'][:80]}")

    # 3. Save daily_snapshots (skip in dry-run)
    if args.dry_run:
        print("\n[3/4] (dry-run) skip persist daily_snapshots")
    else:
        print("\n[3/4] Persist daily_snapshots ...")
        rc, out, err = _run([
            sys.executable, str(SKILLS / "skill-snapshots" / "save.py"),
            "--file", args.snap_out,
        ])
        if rc == 0:
            print(f"  ✅ {out.strip()}")
        else:
            print(f"  ⚠️  persist failed: {err[:300]}")

    # 4. Reminder
    print("\n[4/4] Done.")
    print("\nNote: daily.py — thin orchestrator. Полный цикл (proposals, narrative, TG,")
    print("Wiki) делает Claude Code session под Anthropic routine — см. daily-prompt.md.")
    print(f"\nSnapshot для inspection: {args.snap_out}")


if __name__ == "__main__":
    main()
