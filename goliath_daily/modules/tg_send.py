"""Отправка сообщения в ТГ-бота."""
import os, urllib.request, urllib.parse, json


def send(text: str, parse_mode: str = 'HTML') -> bool:
    token = os.environ['TG_BOT_TOKEN']
    chat_id = os.environ['TG_CHAT_ID']
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)] or ['(пусто)']
    for chunk in chunks:
        data = urllib.parse.urlencode({
            'chat_id': chat_id,
            'text': chunk,
            'parse_mode': parse_mode,
            'disable_web_page_preview': 'true',
        }).encode()
        req = urllib.request.Request(
            f'https://api.telegram.org/bot{token}/sendMessage',
            data=data, method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.loads(r.read())
                if not body.get('ok'):
                    raise RuntimeError(f'TG error: {body}')
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            raise RuntimeError(f'TG HTTP {e.code}: {body[:300]}')
    return True
