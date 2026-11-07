#!/usr/bin/env python3
"""Refresh a generated graph and discover untrusted source proposals without an LLM.

The supplied seed and curated source graph are read-only. Only reviewed registry
sources are fetched; outbound links are proposals, never automatically crawled.
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from collect_activities import ROOT, TZ, Fetcher, safe_url, canonical


def refresh(root=ROOT):
    original = json.loads((root / 'data/source-graph.json').read_text())
    seed = root / original['seed_material']['path']
    if hashlib.sha256(seed.read_bytes()).hexdigest() != original['seed_material']['sha256']:
        raise ValueError('Authoritative source seed changed')
    registry = json.loads((root / 'data/collection-sources.json').read_text())['sources']
    now = datetime.now(TZ).isoformat()
    previous_path = root / 'data/source-proposals.json'
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {'proposals': []}
    proposals = {x['url']: x for x in previous['proposals']}
    approved = {urlsplit(s['url']).hostname for s in registry}
    graph = {'version': 1, 'generated_at': now, 'seed_sha256': original['seed_material']['sha256'],
             'authority': 'data/source-graph.json', 'approved_registry': 'data/collection-sources.json',
             'nodes': [], 'edges': [], 'discovery_health': []}
    for source in registry:
        if source.get('month_template'):
            source = dict(source, url=source['month_template'].format(month=now[:7]))
        graph['nodes'].append({'id': source['id'], 'label': source['name'], 'url': source['url'],
            'role': source['kind'], 'region': source['region'], 'provenance': 'provided-seed' if source['id'] == 'kc-daily' else 'reviewed-supplement'})
        fetcher = Fetcher(root / '.collector-cache' / source['id'])
        try:
            # API sources are already approved routes. Discovery operates on HTML calendars.
            if source['format'] == 'tribe': continue
            page = fetcher.fetch(source['url']); pages = [(source['url'], page)]
            if source['id'] == 'kc-daily':
                soup = BeautifulSoup(page, 'html.parser')
                issues = sorted({urljoin(source['url'], a['href']) for a in soup.select('a[href]')
                    if '/p/' in a['href'] and urlsplit(urljoin(source['url'], a['href'])).hostname == urlsplit(source['url']).hostname})[:4]
                for issue in issues:
                    try: pages.append((issue, fetcher.fetch(issue)))
                    except Exception as e: graph['discovery_health'].append({'url': issue, 'error': str(e)})
            for page_url, body in pages:
                soup = BeautifulSoup(body, 'html.parser')
                for alternate in soup.select('link[rel="alternate"][href], a[href]'):
                    target = safe_url(urljoin(page_url, alternate['href']))
                    if not target: continue
                    fmt = 'ical' if any(k in target.lower() for k in ('.ics', 'ical=','icalendar')) else 'rss' if any(k in (target + ' ' + alternate.get('type','')).lower() for k in ('rss','atom','/feed')) else None
                    if fmt:
                        target = canonical(target)
                        proposals.setdefault(target, {'url': target, 'label': alternate.get('title') or alternate.get_text(' ',strip=True)[:160] or 'Advertised calendar feed',
                            'discovered_on': page_url, 'first_seen': now, 'status': 'unreviewed', 'candidate_format': fmt})
                        proposals[target]['last_seen'] = now
                for a in soup.select('a[href]'):
                    target = safe_url(urljoin(page_url, a['href']))
                    if not target: continue
                    host = urlsplit(target).hostname
                    label = a.get_text(' ', strip=True)[:160]
                    if host in approved or not label: continue
                    if any(host.endswith(suffix) for suffix in ('facebook.com','instagram.com','youtube.com','twitter.com','x.com','linkedin.com','google.com','beehiiv.com')): continue
                    if not any(k in (label + ' ' + target).lower() for k in ('event','calendar','ticket','register','workshop','festival','museum','race','class','camp','concert','park','family')): continue
                    target = canonical(target)
                    if target not in proposals:
                        proposals[target] = {'url': target, 'label': label, 'discovered_on': page_url,
                                             'first_seen': now, 'status': 'unreviewed'}
                    proposals[target]['last_seen'] = now
                    graph['edges'].append({'from': source['id'], 'to_url': target, 'relationship': 'unreviewed-outbound-link', 'observed_on': page_url})
            graph['discovery_health'].append({'id': source['id'], 'status': 'checked', 'pages': len(pages)})
        except Exception as e: graph['discovery_health'].append({'id': source['id'], 'status': 'failed', 'error': str(e)})
    (root / 'data/generated-source-graph.json').write_text(json.dumps(graph, indent=2) + '\n')
    (root / 'data/source-proposals.json').write_text(json.dumps({'updated_at': now, 'proposals': sorted(proposals.values(), key=lambda x:x['url'])[:500]}, indent=2) + '\n')
    print(f"Refreshed {len(graph['nodes'])} approved routes; {len(proposals)} unreviewed proposals")


if __name__ == '__main__': refresh()
