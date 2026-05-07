"""skill-proposals — CRUD к goliath.proposals + chat_context.

Подкоманды:
    list-active [--json]
    get <id>
    insert (stdin или --file: JSON array)
    decide <id> --status applied|rejected|superseded|discussing --reason "..."
    expire-old
    chat <proposal_id> --speaker valerii|goliath --message "..."
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "routines"))
from _lib.common import load_env, pg_conn  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
load_env()


VALID_CATEGORIES = {
    "pause", "resume", "scale_budget", "change_target_cpa", "change_bid",
    "new_hypothesis", "creative_rotate", "creative_text", "negative_site",
    "bidmodifiers_update", "urgent_arpl_stop",
}
VALID_DECISIONS = {"applied", "rejected", "superseded", "discussing"}


def _row_to_dict(cur, row) -> dict:
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


# ─── Команды ───

def cmd_list_active(args):
    conn = pg_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM v_active_proposals ORDER BY id DESC")
            rows = [_row_to_dict(cur, r) for r in cur.fetchall()]
    finally:
        conn.close()

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, default=str, indent=2))
        return
    if not rows:
        print("(нет активных предложений)")
        return
    print(f"=== {len(rows)} active proposals ===")
    for r in rows:
        ttl = ""
        if r.get("expires_at"):
            now = datetime.now(timezone.utc)
            delta = r["expires_at"] - now
            hours = int(delta.total_seconds() / 3600)
            ttl = f" (≈{hours}ч до expiry)"
        print(f"[#{r['id']}] {r['category']:20} | {r['product'] or '-':10} | {r['status']}{ttl}")
        print(f"  {(r.get('description') or '')[:160]}")


def cmd_get(args):
    conn = pg_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM proposals WHERE id = %s", (args.id,))
            row = cur.fetchone()
            if not row:
                print(f"(no proposal id={args.id})", file=sys.stderr)
                sys.exit(1)
            d = _row_to_dict(cur, row)
            cur.execute("""SELECT date_recorded, speaker, message
                           FROM chat_context WHERE proposal_id = %s
                           ORDER BY date_recorded""", (args.id,))
            chat = [_row_to_dict(cur, r) for r in cur.fetchall()]
    finally:
        conn.close()
    out = {"proposal": d, "chat": chat}
    print(json.dumps(out, ensure_ascii=False, default=str, indent=2))


def cmd_insert(args):
    text = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
    items = json.loads(text)
    if isinstance(items, dict):
        items = [items]
    if not items:
        print("[]")
        return

    written = []
    conn = pg_conn(autocommit=True)
    try:
        from psycopg2.extras import Json
        with conn.cursor() as cur:
            for it in items:
                cat = it.get("category")
                if cat not in VALID_CATEGORIES:
                    raise ValueError(f"category '{cat}' invalid; allowed: {sorted(VALID_CATEGORIES)}")
                ttl = int(it.get("ttl_hours", 24))
                expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl)
                cur.execute("""
                    INSERT INTO proposals (category, product, campaign_id, ad_group_id,
                        ad_id, description, reasoning, proposed_action, status, expires_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'pending',%s)
                    RETURNING id, expires_at
                """, (
                    cat, it.get("product"), it.get("campaign_id"), it.get("ad_group_id"),
                    it.get("ad_id"), it.get("description") or "",
                    it.get("reasoning"),
                    Json(it.get("proposed_action") or {}),
                    expires_at,
                ))
                pid, exp = cur.fetchone()
                written.append({"id": int(pid), "expires_at": exp.isoformat()})
    finally:
        conn.close()
    print(json.dumps(written, ensure_ascii=False, indent=2))


def cmd_decide(args):
    if args.status not in VALID_DECISIONS:
        raise SystemExit(f"status must be in {VALID_DECISIONS}")
    conn = pg_conn(autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE proposals
                SET status=%s, decided_at=now(), decision_reason=%s
                WHERE id=%s
                RETURNING id, status
            """, (args.status, args.reason, args.id))
            r = cur.fetchone()
            if not r:
                print(f"no proposal id={args.id}", file=sys.stderr)
                sys.exit(1)
            print(f"#{r[0]} → {r[1]}")
    finally:
        conn.close()


def cmd_expire_old(args):
    conn = pg_conn(autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE proposals SET status='expired', decided_at=now()
                WHERE status='pending' AND expires_at < now()
                RETURNING id
            """)
            ids = [int(r[0]) for r in cur.fetchall()]
    finally:
        conn.close()
    print(f"expired: {len(ids)} → {ids}")


def cmd_chat(args):
    if args.speaker not in ("valerii", "goliath"):
        raise SystemExit("speaker must be valerii or goliath")
    conn = pg_conn(autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO chat_context (proposal_id, speaker, message)
                VALUES (%s,%s,%s) RETURNING id
            """, (args.proposal_id, args.speaker, args.message))
            cid = cur.fetchone()[0]
            # Если статус pending — двигаем в discussing
            cur.execute("""
                UPDATE proposals SET status='discussing'
                WHERE id=%s AND status='pending'
            """, (args.proposal_id,))
    finally:
        conn.close()
    print(f"chat #{cid} written")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list-active"); s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_list_active)

    s = sub.add_parser("get"); s.add_argument("id", type=int); s.set_defaults(fn=cmd_get)

    s = sub.add_parser("insert"); s.add_argument("--file"); s.set_defaults(fn=cmd_insert)

    s = sub.add_parser("decide")
    s.add_argument("id", type=int)
    s.add_argument("--status", required=True)
    s.add_argument("--reason", default=None)
    s.set_defaults(fn=cmd_decide)

    s = sub.add_parser("expire-old"); s.set_defaults(fn=cmd_expire_old)

    s = sub.add_parser("chat")
    s.add_argument("proposal_id", type=int)
    s.add_argument("--speaker", required=True)
    s.add_argument("--message", required=True)
    s.set_defaults(fn=cmd_chat)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
