#!/usr/bin/env python3
"""Make a small, coverage-prioritized brief for the weekly Codex maintainer.

This command is offline. It ranks proposals, respects review cooldowns, limits
host repetition and rotates uncovered cells. It never promotes a source.
"""
import argparse
import hashlib
import ipaddress
import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from check_recall import compare

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text())


def public_url(value):
    try:
        p = urlsplit(value or '')
        host = (p.hostname or '').lower()
    except ValueError: return None
    if p.scheme not in ('http', 'https') or not host or p.username or p.password: return None
    if host == 'localhost' or host.endswith(('.local', '.internal', '.localhost')): return None
    try:
        if not ipaddress.ip_address(host).is_global: return None
    except ValueError: pass
    query = [(k,v) for k,v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid')]
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip('/') or '/', urlencode(sorted(query)), ''))


def eligible(review, today):
    if not review: return True
    if review['status'] in ('accepted', 'rejected'): return False
    retry = review.get('next_review_after')
    return bool(retry and date.fromisoformat(retry) <= today)


def build(root=ROOT, today=None):
    today = today or date.today()
    policy = load(root/'data/weekly-discovery-policy.json')
    ledger = load(root/'data/source-review-ledger.json')
    registry = load(root/'data/collection-sources.json')['sources']
    public = load(root/'web/activities.json')
    proposals = load(root/'data/source-proposals.json')['proposals']
    taxonomy = load(root/'data/activity-taxonomy.json')
    reviewed = {public_url(r['url']):r for r in ledger['reviews']}
    known = {public_url(s['url']) for s in registry}
    hosts = {urlsplit(s['url']).hostname for s in registry}
    cells = public['coverage_matrix']['category_by_region']
    gaps = {(c['region'],c['category']):c for c in cells if c['status']!='collecting'}
    categories = taxonomy['categories']
    scored = {}; week = today.isocalendar().week
    for proposal in proposals:
        target = public_url(proposal['url'])
        if not target or target in known or not eligible(reviewed.get(target),today): continue
        p = urlsplit(target)
        if re.search(r'/(?:privacy|terms|login|sign-in|cart|donate|contact)(?:/|$)',p.path,re.I): continue
        referring = urlsplit(proposal.get('discovered_on','')).hostname
        parents = [s for s in registry if urlsplit(s['url']).hostname == referring]
        regions = sorted({s['region'] for s in parents})
        text = re.sub(r'[^a-z0-9]+',' ',(proposal.get('label','')+' '+target).lower())
        topics = [c['id'] for c in categories if any(re.search(r'\b'+re.escape(t)+r'\b',text) for t in c['search_terms'].split())]
        relevant = [gaps[(r,c)] for r in regions for c in topics if (r,c) in gaps]
        reasons = []
        score = 0
        if relevant: score += 40; reasons.append('May address an uncovered subject/region cell')
        if re.search(r'league|season|exhibit|trail|camp|course|registration|program',text): score+=20;reasons.append('May add a missing long-run or non-calendar offering')
        if p.hostname not in hosts: score+=15;reasons.append('New provider host')
        if proposal.get('candidate_format') in ('ical','rss') or re.search(r'\.ics|/feed|/wp-json/',target): score+=15;reasons.append('Potential reusable structured feed; verify adapter support')
        if target not in reviewed: score+=10;reasons.append('Not previously reviewed')
        entry = {'id':hashlib.sha256(target.encode()).hexdigest()[:20], 'url':target,
                 'label':proposal.get('label',''), 'discovered_on':proposal.get('discovered_on'),
                 'score':score, 'reasons':reasons, 'region_hints':regions, 'category_hints':topics,
                 'hint_warning':'Referrer and keyword hints are unverified; inspect actual geography, ownership and content.'}
        if target not in scored or score>scored[target]['score']: scored[target]=entry
    candidates = sorted(scored.values(),key=lambda r:(-r['score'],r['url']))
    selected=[];per_host=Counter()
    for row in candidates:
        host=urlsplit(row['url']).hostname
        if per_host[host]>=policy['budgets']['links_per_host']: continue
        selected.append(row);per_host[host]+=1
        if len(selected)>=policy['budgets']['candidate_links']:break
    # Rotate by week while prioritizing cells with no source at all. Round-robin
    # regions so one museum-heavy metro does not consume the search budget.
    gap_rows=sorted(gaps.values(),key=lambda c:(c['status']!='gap',c['category']))
    region_queues={region:[c for c in gap_rows if c['region']==region] for region in taxonomy['regions']}
    for region,queue in region_queues.items():
        if queue: offset=week%len(queue);region_queues[region]=queue[offset:]+queue[:offset]
    regions=taxonomy['regions'][week%len(taxonomy['regions']):]+taxonomy['regions'][:week%len(taxonomy['regions'])]
    searches=[]
    while len(searches)<policy['budgets']['gap_searches'] and any(region_queues.values()):
        for region in regions:
            if region_queues[region]: searches.append(region_queues[region].pop(0))
            if len(searches)>=policy['budgets']['gap_searches']:break
    repairs=sorted([{'id':h['id'],'name':h['name'],'events':h['events'],'unparsed_count':h.get('unparsed_count',0),
                    'errors':h.get('errors',[])[:2],'url':h['url']} for h in public['sources'] if h['events']==0],
                   key=lambda h:(-h['unparsed_count'],h['id']))[:3]
    place_health = []
    for place in public.get('places', []):
        hours = place.get('hours')
        age = (today-date.fromisoformat(hours['checked_at'][:10])).days if hours else None
        if not hours or age > 21:
            place_health.append({'id':place['id'], 'url':hours['source_url'] if hours else place['source_url'],
                                 'reason':'Missing verified hours' if not hours else 'Hours approaching the 30-day freshness limit'})
    benchmarks=sorted((root/'data/recall-benchmarks').glob('*.json')) if (root/'data/recall-benchmarks').exists() else []
    recall=None
    if benchmarks:
        benchmark=load(benchmarks[-1]);recall=compare(public,benchmark)
        recall['needs_new_weekend_benchmark']=benchmark['window']['end']<today.isoformat()
        recall['results']=[r for r in recall['results'] if r['status']=='gap']
    return {'version':1,'as_of':today.isoformat(),'repository':policy['repository'],'budgets':policy['budgets'],
        'baseline':{'routes':len(registry),'records':len(public['activities']),
            'unique_offerings':len({a.get('offering_id',a['id']) for a in public['activities']}),
            'coverage_cells':dict(Counter(c['status'] for c in cells)),
            'activity_kinds':dict(Counter(a['schedule']['kind'] for a in public['activities'])),
            'stale_records':sum(a['stale'] for a in public['activities']),
            'places':len(public.get('places',[])),
            'unmapped_offerings':len({a.get('offering_id',a['id']) for a in public['activities'] if not a.get('geo')}),
            'unreviewed_proposals':len(scored)},
        'candidates':selected,'gap_searches':searches,'repair_candidates':repairs,'place_maintenance':place_health[:6],
        'weekend_recall':recall,
        'publication_policy':policy['publication']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path);p.add_argument('--today',type=date.fromisoformat)
    a=p.parse_args();text=json.dumps(build(today=a.today),indent=2)+'\n'
    if a.out: a.out.write_text(text)
    else: print(text,end='')
