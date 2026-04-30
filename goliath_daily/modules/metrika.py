"""Метрика Reports API — уникальные регистрации по utm_campaign и utm_medium за вчера."""
import os, json, urllib.request, urllib.error, socket

orig=socket.getaddrinfo
def _v4(*a,**k): return [r for r in orig(*a,**k) if r[0]==socket.AF_INET]
socket.getaddrinfo=_v4


def fetch_goals_by_campaign(yday: str) -> list[dict]:
    """Уникальные посетители достигшие цели регистрации, в разрезе campaign_id и utm_medium.
    Фильтруем только goliath__* трафик из Я.Директа.
    """
    tok = os.environ['YANDEX_METRIKA_TOKEN'].strip().strip("'").strip('"')
    counter = os.environ['METRIKA_COUNTER_ID']
    goal = os.environ['GOAL_REG_ID']

    params = {
        'ids': counter,
        'date1': yday,
        'date2': yday,
        'dimensions': 'ym:s:UTMCampaign,ym:s:UTMMedium',
        'metrics': f'ym:s:goal{goal}users,ym:s:visits,ym:s:goal{goal}reaches',
        'filters': "ym:s:UTMSource=='yandex' AND ym:s:UTMMedium=~'^goliath__'",
        'limit': 1000,
        'accuracy':'full',
    }
    qs = '&'.join(f'{k}={urllib.request.quote(str(v))}' for k,v in params.items())
    req = urllib.request.Request(
        f'https://api-metrika.yandex.net/stat/v1/data?{qs}',
        headers={'Authorization': f'OAuth {tok}'},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return [{'_error': f'HTTP {e.code}: {e.read().decode()[:300]}'}]

    rows = []
    for item in d.get('data',[]):
        dims = item['dimensions']
        metrics = item['metrics']
        rows.append({
            'utm_campaign': dims[0].get('name','(none)'),
            'utm_medium':   dims[1].get('name','(none)'),
            'unique_leads': int(metrics[0]),
            'visits':       int(metrics[1]),
            'goal_reaches': int(metrics[2]),
        })
    rows.sort(key=lambda x: -x['unique_leads'])
    return rows


def fetch_totals(yday: str) -> dict:
    """Общие цифры по счётчику за вчера: визиты, уники, отказы."""
    tok = os.environ['YANDEX_METRIKA_TOKEN'].strip().strip("'").strip('"')
    counter = os.environ['METRIKA_COUNTER_ID']
    goal = os.environ['GOAL_REG_ID']
    params = {
        'ids': counter,
        'date1': yday, 'date2': yday,
        'metrics': f'ym:s:visits,ym:s:users,ym:s:goal{goal}users',
        'filters': "ym:s:UTMSource=='yandex' AND ym:s:UTMMedium=~'^goliath__'",
    }
    qs = '&'.join(f'{k}={urllib.request.quote(str(v))}' for k,v in params.items())
    req = urllib.request.Request(
        f'https://api-metrika.yandex.net/stat/v1/data?{qs}',
        headers={'Authorization':f'OAuth {tok}'},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {'_error': f'HTTP {e.code}: {e.read().decode()[:300]}'}
    totals = d.get('totals') or [0,0,0]
    return {'visits':int(totals[0]),'users':int(totals[1]),'unique_leads':int(totals[2])}


if __name__ == '__main__':
    import sys, datetime
    sys.stdout.reconfigure(encoding='utf-8')
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__),'..','.env'))
    yday = (datetime.date.today()-datetime.timedelta(days=1)).isoformat()
    print(json.dumps(fetch_totals(yday), ensure_ascii=False, indent=2))
    print(json.dumps(fetch_goals_by_campaign(yday), ensure_ascii=False, indent=2))
