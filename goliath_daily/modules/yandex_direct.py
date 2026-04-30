"""Я.Директ Reports API — асинхронный отчёт за вчера по 4 кампаниям Голиафа."""
import os, json, time, csv, io, urllib.request, urllib.error, socket

orig=socket.getaddrinfo
def _v4(*a,**k): return [r for r in orig(*a,**k) if r[0]==socket.AF_INET]
socket.getaddrinfo=_v4


def fetch_daily(yday: str) -> list[dict]:
    """Возвращает список dict: campaign_id, campaign_name, cost(₽), impressions, clicks, ctr, conversions, avg_cpc, cpa."""
    tok = os.environ['YANDEX_DIRECT_TOKEN'].strip().strip("'").strip('"')
    cabinet = os.environ['YD_CABINET']
    camp_ids = [int(x) for x in os.environ['YD_CAMPAIGN_IDS'].split(',')]

    body = {
        'params': {
            'SelectionCriteria': {
                'DateFrom': yday,
                'DateTo': yday,
                'Filter': [{'Field':'CampaignId','Operator':'IN','Values':[str(c) for c in camp_ids]}]
            },
            'FieldNames': ['Date','CampaignId','CampaignName','Impressions','Clicks','Cost','Conversions'],
            'ReportName': f'goliath_daily_{yday}_{int(time.time())}',
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

    # processingMode=auto — Я.Директ держит коннект до готовности (или возвращает 201/202)
    for attempt in range(40):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                code = r.status
                content = r.read().decode('utf-8')
                if code == 200:
                    break
                # 201/202 — отчёт ещё формируется, ретраим
                time.sleep(8)
        except urllib.error.HTTPError as e:
            if e.code in (201, 202):
                time.sleep(8)
                continue
            raise RuntimeError(f'YD reports HTTP {e.code}: {e.read().decode()[:500]}')
    else:
        raise RuntimeError('YD reports не дождался Status=Done')

    # TSV parse
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
    print(f"=== Состояния кампаний ===")
    print(json.dumps(fetch_campaign_states(), ensure_ascii=False, indent=2))
    print(f"\n=== Метрики за {yday} ===")
    print(json.dumps(fetch_daily(yday), ensure_ascii=False, indent=2))
