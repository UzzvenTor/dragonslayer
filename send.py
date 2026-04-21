# -*- coding: utf-8 -*-
"""Отправка отчёта Драконоборца в ТГ-бота @dragonslayerr_bot."""
import os, sys, argparse
import urllib.request, urllib.parse, json
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

TOKEN   = os.environ['TG_BOT_TOKEN']
CHAT_ID = os.environ['TG_CHAT_ID']


def send(text: str, chat_id: str = None, parse_mode: str = 'HTML'):
    """Отправляет сообщение. Telegram режет > 4096 — бьём на части."""
    chat_id = chat_id or CHAT_ID
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)] or ['(пусто)']
    for chunk in chunks:
        data = urllib.parse.urlencode({
            'chat_id': chat_id,
            'text': chunk,
            'parse_mode': parse_mode,
            'disable_web_page_preview': 'true',
        }).encode()
        req = urllib.request.Request(
            f'https://api.telegram.org/bot{TOKEN}/sendMessage',
            data=data, method='POST')
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
            if not body.get('ok'):
                raise RuntimeError(f'TG error: {body}')
    return True


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('file', nargs='?', help='файл с текстом (или stdin)')
    ap.add_argument('--plain', action='store_true', help='без parse_mode')
    args = ap.parse_args()

    if args.file:
        with open(args.file, encoding='utf-8') as f:
            txt = f.read()
    else:
        txt = sys.stdin.read()

    mode = None if args.plain else 'HTML'
    send(txt, parse_mode=mode)
    print('SENT')
