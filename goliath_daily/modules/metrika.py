"""Метрика Reports API — уникальные регистрации (цель GOAL_REG_ID) по utm за период."""
import os, json, urllib.request, urllib.error, socket

orig=socket.getaddrinfo
def _v4(*a,**k): return [r for r in orig(*a,**k) if r[0]==socket.AF_INET]
socket.getaddrinfo=_v4


def fetch_goals_by_campaign(date_from: str, date_to: str | None = None) -> list[dict]:
    """Уникальные посетители достигшие цели регистрации, в разрезе campaign_id и utm_medium.
    Фильтруем только goliath__* трафик из Я.Директа.
    """
    if date_to is None:
        date_to = date_from
    tok = os.environ['YANDEX_METRIKA_TOKEN'].strip().strip("'").strip('"')
    counter = os.environ['METRIKA_COUNTER_ID']
    goal = os.environ['GOAL_REG_ID']

    params = {
        'ids': counter,
        'date1': date_from,
        'date2': date_to,
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


def fetch_totals(date_from: str, date_to: str | None = None) -> dict:
    """Общие цифры по Голиаф-трафику за период: визиты, уники, уникальные регистрации."""
    if date_to is None:
        date_to = date_from
    tok = os.environ['YANDEX_METRIKA_TOKEN'].strip().strip("'").strip('"')
    counter = os.environ['METRIKA_COUNTER_ID']
    goal = os.environ['GOAL_REG_ID']
    params = {
        'ids': counter,
        'date1': date_from, 'date2': date_to,
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


def list_goals() -> list[dict]:
    """Список всех целей счётчика — для верификации правильного goal_id.
    Управляющий API: /management/v1/counter/{id}/goals.
    """
    tok = os.environ['YANDEX_METRIKA_TOKEN'].strip().strip("'").strip('"')
    counter = os.environ['METRIKA_COUNTER_ID']
    req = urllib.request.Request(
        f'https://api-metrika.yandex.net/management/v1/counter/{counter}/goals',
        headers={'Authorization':f'OAuth {tok}'},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return [{'_error': f'HTTP {e.code}: {e.read().decode()[:300]}'}]
    return [
        {'id': g.get('id'), 'name': g.get('name'), 'type': g.get('type'),
         'is_retargeting': g.get('is_retargeting'), 'default_price': g.get('default_price')}
        for g in d.get('goals', [])
    ]


if __name__ == '__main__':
    import sys, datetime, argparse
    sys.stdout.reconfigure(encoding='utf-8')
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__),'..','.env'))

    ap = argparse.ArgumentParser()
    ap.add_argument('--list-goals', action='store_true', help='Показать все цели счётчика')
    args = ap.parse_args()

    if args.list_goals:
        print(f"=== Все цели счётчика {os.environ['METRIKA_COUNTER_ID']} ===")
        goals = list_goals()
        for g in goals:
            if '_error' in g:
                print(g); break
            mark = '  ⚠️ TARGET' if str(g['id']) == str(os.environ.get('GOAL_REG_ID','')) else ''
            print(f"  {g['id']}  {g['name']!r}  type={g['type']}{mark}")
        sys.exit(0)

    yday = (datetime.date.today()-datetime.timedelta(days=1)).isoformat()
    mtd_from = yday[:8] + '01'
    print(f'=== TOTALS yday {yday} ===')
    print(json.dumps(fetch_totals(yday), ensure_ascii=False, indent=2))
    print(f'\n=== TOTALS MTD {mtd_from}..{yday} ===')
    print(json.dumps(fetch_totals(mtd_from, yday), ensure_ascii=False, indent=2))
    print(f'\n=== PER CAMPAIGN yday ===')
    print(json.dumps(fetch_goals_by_campaign(yday), ensure_ascii=False, indent=2))
    print(f'\n=== PER CAMPAIGN MTD ===')
    print(json.dumps(fetch_goals_by_campaign(mtd_from, yday), ensure_ascii=False, indent=2))
