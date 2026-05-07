"""skill-tg-push — отправить HTML в @goliath77_bot.

Использование:
    echo "<b>текст</b>" | python push.py
    python push.py --file /tmp/report.html
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "routines"))
from _lib.common import load_env  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
load_env()

TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]


def send_html(text: str) -> dict:
    if len(text) > 4096:
        raise ValueError(f"TG message too long: {len(text)} > 4096 chars")
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": TG_CHAT_ID, "text": text,
        "parse_mode": "HTML", "disable_web_page_preview": "true",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="прочитать HTML из файла; иначе из stdin")
    args = ap.parse_args()

    text = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
    text = text.rstrip()
    if not text:
        print("EMPTY message — abort", file=sys.stderr)
        sys.exit(1)

    resp = send_html(text)
    print(f"ok={resp.get('ok')}, msg_id={resp.get('result', {}).get('message_id')}")
    if not resp.get("ok"):
        print(f"FULL response: {resp}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
