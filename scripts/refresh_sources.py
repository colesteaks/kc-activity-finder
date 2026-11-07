#!/usr/bin/env python3
"""Refresh a generated graph and discover untrusted source proposals without an LLM.

The supplied seed and curated source graph are read-only. Only reviewed registry
sources are fetched; outbound links are proposals, never automatically crawled.
"""
import hashlib
import argparse
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from collect_activities import ROOT, TZ, Fetcher, safe_url, canonical
from activity_model import coverage_matrix
from newsletter_sources import archive_page, issue_record, discovery_kind


def add_place_leaves(graph, root=ROOT):
    """Reviewed place facts are leaves, not automatically followed crawl routes."""
    path = root / 'data/places.json'
    definitions = json.loads(path.read_text())['places'] if path.exists() else []
    graph['place_leaves'] = [{
        'id': p['id'], 'label': p['name'], 'url': p['source_url'],
        'parent_route_ids': p['match']['source_ids'],
        'hours_source': p['hours']['source_url'] if p['hours'] else None,
        'coordinate_source': p['geo']['source_url'] if p['geo'] else None,
        'offering_sources': sorted({a['source_url'] for a in p['activities']}),
        'provenance': 'reviewed-place-registry',
    } for p in definitions]
    for node in graph['nodes']:
        node['place_ids'] = [p['id'] for p in definitions if node['id'] in p['match']['source_ids']]


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
    history_path=root/'data/kc-daily-source-map.json'
    history=json.loads(history_path.read_text()) if history_path.exists() else None
    if history:
        for target in history['targets']:
            if target.get('discovery_kind') in ('media-sensor','advertising-or-subscription','map-or-location-lead'):continue
            if not any(k in (target['label']+' '+target['url']).lower() for k in ('event','calendar','ticket','register','festival','museum','race','class','camp','concert','park','trail','league','season','exhibit','program','volunteer','market','theat','music','family','opera','flea')):continue
            url=canonical(target['url'])
            proposals.setdefault(url,{'url':url,'label':target['label'],'discovered_on':target.get('latest_issue') or target['example_issues'][0],
                'first_seen':history['checked_at'],'last_seen':history['checked_at'],'status':'unreviewed',
                'discovery_kind':target.get('discovery_kind'),'newsletter_published_at':target.get('latest_published_at')})
    approved = {urlsplit(s['url']).hostname for s in registry}
    graph = {'version': 1, 'generated_at': now, 'seed_sha256': original['seed_material']['sha256'],
             'authority': 'data/source-graph.json', 'approved_registry': 'data/collection-sources.json',
             'nodes': [], 'edges': [], 'discovery_health': []}
    if history:graph['newsletter_source_map']={'path':'data/kc-daily-source-map.json','summary':history['summary'],'archive':history['archive']}
    for source in registry:
        if source.get('month_template'):
            source = dict(source, url=source['month_template'].format(month=now[:7]))
        graph['nodes'].append({'id': source['id'], 'label': source['name'], 'url': source['url'],
            'role': source['kind'], 'region': source['region'], 'categories': source.get('categories', []),
            'activity_kinds': source.get('activity_kinds', []), 'required_leaves': source.get('required_leaves', []),
            'discovery_evidence': source.get('discovery_evidence', []),
            'provenance': 'provided-seed' if source['id'] == 'kc-daily' else 'reviewed-supplement'})
        fetcher = Fetcher(root / '.collector-cache' / source['id'])
        try:
            # API sources are already approved routes. Discovery operates on HTML calendars.
            if source['format'] == 'tribe': continue
            page = fetcher.fetch(source['url']); pages = [(source['url'], page)]
            if source['id'] == 'kc-daily':
                # Latest archive pages include the weekend edition; homepage featured
                # guides must never crowd recent newsletters out of the frontier.
                issues={};archive_url=urljoin(source['url'],'/archive')
                for _ in range(2):
                    if not archive_url:break
                    archive_body=fetcher.fetch(archive_url);pages.append((archive_url,archive_body))
                    found,archive_url=archive_page(archive_body,archive_url);issues.update(found)
                for issue in issues:
                    try: pages.append((issue, fetcher.fetch(issue)))
                    except Exception as e: graph['discovery_health'].append({'url': issue, 'error': str(e)})
            for page_url, body in pages:
                if source['id']=='kc-daily' and urlsplit(page_url).path.startswith('/p/'):
                    newsletter=issue_record(body,page_url)
                    for item in newsletter['links']:
                        target=canonical(item['url']);host=urlsplit(target).hostname or ''
                        proposals.setdefault(target,{'url':target,'label':item['label'],'discovered_on':page_url,
                            'first_seen':now,'status':'unreviewed','discovery_kind':discovery_kind(host,item['label']),
                            'newsletter_published_at':newsletter.get('published_at')})
                        proposals[target]['last_seen']=now
                        graph['edges'].append({'from':source['id'],'to_url':target,'relationship':'unreviewed-newsletter-link','observed_on':page_url})
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
                    if not label: continue
                    # Same-provider program, trail and registration leaves matter too.
                    if any(host.endswith(suffix) for suffix in ('facebook.com','instagram.com','youtube.com','twitter.com','x.com','linkedin.com','google.com','beehiiv.com')): continue
                    if not any(k in (label + ' ' + target).lower() for k in ('event','calendar','ticket','register','registration','workshop','festival','museum','race','class','camp','concert','park','family','trail','hiking','paddling','league','season','exhibit','program','volunteer','games','club','sport','lessons','aquatic','guide')): continue
                    target = canonical(target)
                    if target not in proposals:
                        proposals[target] = {'url': target, 'label': label, 'discovered_on': page_url,
                                             'first_seen': now, 'status': 'unreviewed'}
                    proposals[target]['last_seen'] = now
                    graph['edges'].append({'from': source['id'], 'to_url': target, 'relationship': 'unreviewed-outbound-link', 'observed_on': page_url})
            graph['discovery_health'].append({'id': source['id'], 'status': 'checked', 'pages': len(pages)})
        except Exception as e: graph['discovery_health'].append({'id': source['id'], 'status': 'failed', 'error': str(e)})
    taxonomy = json.loads((root / 'data/activity-taxonomy.json').read_text())
    public_path = root / 'web/activities.json'
    health = json.loads(public_path.read_text()).get('sources', []) if public_path.exists() else []
    graph['coverage_matrix'] = coverage_matrix(registry, taxonomy, health)
    add_place_leaves(graph, root)
    (root / 'data/generated-source-graph.json').write_text(json.dumps(graph, indent=2) + '\n')
    (root / 'data/source-proposals.json').write_text(json.dumps({'updated_at': now, 'proposals': sorted(proposals.values(), key=lambda x:x['url'])}, indent=2) + '\n')
    print(f"Refreshed {len(graph['nodes'])} approved routes; {len(proposals)} unreviewed proposals")


def refresh_coverage(root=ROOT):
    path = root / 'data/generated-source-graph.json'
    graph = json.loads(path.read_text())
    public = json.loads((root / 'web/activities.json').read_text())
    registry = json.loads((root / 'data/collection-sources.json').read_text())['sources']
    taxonomy = json.loads((root / 'data/activity-taxonomy.json').read_text())
    graph['coverage_matrix'] = coverage_matrix(registry, taxonomy, public['sources'])
    add_place_leaves(graph, root)
    path.write_text(json.dumps(graph, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--coverage-only', action='store_true')
    args = parser.parse_args()
    refresh_coverage() if args.coverage_only else refresh()
