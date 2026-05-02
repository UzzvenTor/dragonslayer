"""Я.Директ Reports API — отчёт по 4 кампаниям Голиафа за день или период.

Конверсии считаются строго по одной цели — `[all] Уникальная регистрация`
(env GOAL_REG_ID). Без фильтра Я.Директ возвращает сумму по всем целям счётчика,
поэтому цифры расходятся с Метрикой и нашим KPI.
"""
import os, json, time, csv, io, urllib.request, urllib.error, socket

orig=socket.getaddrinfo
def _v4(*a,**k): return [r for r in orig(*a,**k) if r[0]==socket.AF_INET]
socket.getaddrinfo=_v4


def _fetch_report(date_from: str, date_to: str) -> list[dict]:
    """Собрать CAMPAIGN_PERFORMANCE_REPORT по 4 кампаниям Голиафа за период.
    Конверсии — только по цели GOAL_REG_ID.
    """
    tok = os.environ['YANDEX_DIRECT_TOKEN'].strip().strip("'").strip('"')
    cabinet = os.environ['YD_CABINET']
    camp_ids = [int(x) for x in os.environ['YD_CAMPAIGN_IDS'].split(',')]
    goal_id = int(os.environ['GOAL_REG_ID'])

    body = {
        'params': {
            'SelectionCriteria': {
                'DateFrom': date_from,
                'DateTo': date_to,
                'Filter': [{'Field':'CampaignId','Operator':'IN','Values':[str(c) for c in camp_ids]}],
            },
            'Goals': [goal_id],
            'FieldNames': ['CampaignId','CampaignName','Impressions','Clicks','Cost','Conversions'],
            'ReportName': f'goliath_{date_from}_{date_to}_{int(time.time())}',
            'ReportType': 'CAMPAIGN_PERFORMANCE_REPORT',
            'DateRangeType': 'CUSTOM_DATE',
            'Format': 'TSV',
            'IncludeVAT': 'YES',
            'IncludeDiscount': 'NO',
        }
    }

    headers = {
        'Authorization': f'Bearer {tok}',
        'Accept-Language': 'ru',
        'Client-Login': cabinet,
        'processingMode': 'auto',
        'returnMoneyInMicros': 'false',
        'skipReportHeader': 'true',
        'skipColumnHeader': 'false',
        'skipReportSummary': 'true',
    }

    req = urllib.request.Request(
        'https://api.direct.yandex.com/json/v5/reports',
        data=json.dumps(body).encode(),
        headers=headers,
    )

    content = None
    for attempt in range(40):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                code = r.status
                content = r.read().decode('utf-8')
                if code == 200:
                    break
                time.sleep(8)
        except urllib.error.HTTPError as e:
            if e.code in (201, 202):
                time.sleep(8)
                continue
            raise RuntimeError(f'YD reports HTTP {e.code}: {e.read().decode()[:500]}')
    if content is None:
        raise RuntimeError('YD reports не дождался Status=Done')

    rows = []
    reader = csv.DictReader(io.StringIO(content), delimiter='\t')
    for row in reader:
        cost = float(row.get('Cost') or 0)
        clicks = int(row.get('Clicks') or 0)
        impr = int(row.get('Impressions') or 0)
        conv = int(row.get('Conversions') or 0)
        rows.append({
            'campaign_id': int(row['CampaignId']),
            'campaign_name': row['CampaignName'],
            'cost_rub': round(cost, 2),
            'impressions': impr,
            'clicks': clicks,
            'ctr_pct': round(clicks/impr*100, 2) if impr else 0,
            'conversions': conv,
            'cpc_rub': round(cost/clicks, 2) if clicks else 0,
            'cpa_rub': round(cost/conv, 2) if conv else 0,
        })
    return rows


def fetch_daily(yday: str) -> list[dict]:
    return _fetch_report(yday, yday)


def fetch_period(date_from: str, date_to: str) -> list[dict]:
    return _fetch_report(date_from, date_to)


def fetch_campaign_states() -> dict[int,dict]:
    """Текущие состояния кампаний — для проверки что всё крутится."""
    tok = os.environ['YANDEX_DIRECT_TOKEN'].strip().strip("'").strip('"')
    cabinet = os.environ['YD_CABINET']
    camp_ids = [int(x) for x in os.environ['YD_CAMPAIGN_IDS'].split(',')]

    body = {'method':'get','params':{
        'SelectionCriteria':{'Ids':camp_ids},
        'FieldNames':['Id','Name','State','Status','StatusPayment','Statistics']
    }}
    req = urllib.request.Request(
        'https://api.direct.yandex.com/json/v5/campaigns',
        data=json.dumps(body).encode(),
        headers={
            'Authorization':f'Bearer {tok}',
            'Accept-Language':'ru',
            'Content-Type':'application/json; charset=utf-8',
            'Client-Login':cabinet,
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read())
    out = {}
    for c in d.get('result',{}).get('Campaigns',[]):
        out[c['Id']] = {
            'name': c.get('Name'),
            'state': c.get('State'),
            'status': c.get('Status'),
            'payment': c.get('StatusPayment'),
        }
    return out


if __name__ == '__main__':
    import sys, datetime
    sys.stdout.reconfigure(encoding='utf-8')
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__),'..','.env'))

    yday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    mtd_from = yday[:8] + '01'
    print(f"=== Состояния кампаний ===")
    print(json.dumps(fetch_campaign_states(), ensure_ascii=False, indent=2))
    print(f"\n=== Метрики за {yday} (по цели УР) ===")
    print(json.dumps(fetch_daily(yday), ensure_ascii=False, indent=2))
    print(f"\n=== Метрики MTD {mtd_from}..{yday} ===")
    print(json.dumps(fetch_period(mtd_from, yday), ensure_ascii=False, indent=2))
