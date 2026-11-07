#!/usr/bin/env python3
"""Evidence-first research ledger and recommendation engine. No live facts are fabricated.

Browsing is performed by a human or agent; this program validates their artifacts.
Run --help for the workflow. All changes stay local until explicitly pushed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator, FormatChecker
from validate_repo import EXPECTED_STAGES, FIRST_PARTY_TYPES, REQUIRED_COVERAGE

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo('America/Chicago')
CHECKS = {'identity', 'schedule', 'location', 'availability', 'audience', 'cost',
          'registration', 'conflicts', 'logistics', 'provenance'}
WEIGHTS = {'age_fit': 20, 'interest_fit': 30, 'movement': 0,
           'distinctiveness': 20, 'logistics': 20, 'value': 10}


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def validate(data, name):
    Draft202012Validator(load(ROOT / 'schemas' / (name + '.schema.json')),
                        format_checker=FormatChecker()).validate(data)


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.utcoffset() is None:
        raise ValueError('Timestamp must include a UTC offset')
    return parsed


def url(value):
    p = urlsplit(value)
    if p.scheme not in ('https', 'http') or not p.hostname or p.username or p.password:
        raise ValueError('Expected an HTTP(S) URL without credentials')
    return value


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def graph_identity(graph):
    seed = (ROOT / graph['seed_material']['path']).read_bytes()
    if hashlib.sha256(seed).hexdigest() != graph['seed_material']['sha256']:
        raise ValueError('Authoritative seed hash mismatch')
    validate(graph, 'source-graph')
    return digest(graph)


def initialize(request, graph, fixture=False):
    validate(request, 'query')
    timestamp(request['as_of'])
    if request['window']['start'] > request['window']['end']:
        raise ValueError('Reversed date window')
    return {'version': 1, 'fixture': fixture, 'request': request,
            'graph_digest': graph_identity(graph), 'completed': [],
            'coverage': [{'node_id': n['id'], 'status': 'pending', 'observed_at': None,
                          'visited_urls': [], 'notes': ''} for n in graph['nodes'] if n['status'] == 'active'],
            'searches': [], 'candidates': [], 'merged': [], 'ranking': [],
            'graph_proposals': [], 'review': None}


def validate_candidate(c):
    validate(c, 'candidate')
    start = timestamp(c['timing']['start']) if c['timing']['start'] else None
    end = timestamp(c['timing']['end']) if c['timing']['end'] else None
    if end and (not start or end < start):
        raise ValueError('End precedes start')
    if c.get('audience'):
        a = c['audience']
        if a['min_age'] is not None and a['max_age'] is not None and a['min_age'] > a['max_age']:
            raise ValueError('Age bounds reversed')
    for proof in c['verification']:
        url(proof['url']); timestamp(proof['observed_at'])
    if c.get('action_url'):
        url(c['action_url'])


def merge(candidates):
    """Only exact occurrences merge. Preserve original records and conflicts."""
    result, log, seen = [], [], {}
    remap = {}
    for original in candidates:
        c = copy.deepcopy(original)
        validate_candidate(c)
        norm = lambda x: re.sub(r'\W+', '', x.casefold())
        key = (norm(c['title']), norm(c['place']['venue']), c['place']['city'].casefold(),
               timestamp(c['timing']['start']).astimezone(timezone.utc).isoformat()
               if c['timing']['start'] else c['candidate_id'], c.get('parent_event_id'))
        if key not in seen:
            seen[key] = c; result.append(c); continue
        kept = seen[key]
        differences = []
        for field in ('timing', 'availability', 'cost', 'audience', 'registration', 'action_url'):
            if kept.get(field) != c.get(field):
                differences.append({'field': field, 'values': [kept.get(field), c.get(field)]})
        kept.setdefault('conflicts', []).extend(differences)
        kept['conflicts'].extend(c.get('conflicts', []))
        for proof in c['verification']:
            if proof not in kept['verification']:
                kept['verification'].append(proof)
        kept.setdefault('discoveries', [kept['discovery']]).append(c['discovery'])
        log.append({'kept': kept['candidate_id'], 'original': c, 'differences': differences})
        remap[c['candidate_id']] = kept['candidate_id']
    for c in result:
        if c.get('parent_event_id') in remap:
            c['parent_event_id'] = remap[c['parent_event_id']]
    return result, log


def exclusions(c, request):
    reasons = []
    as_of = timestamp(request['as_of'])
    f = request.get('filters', {})
    max_age_hours = f.get('evidence_max_age_hours', 48)
    if c['mode'] != request['mode']:
        reasons.append('wrong-mode')
    if c['timing']['start'] is None:
        reasons.append('unknown-time')
    else:
        start = timestamp(c['timing']['start']).astimezone(TZ).date()
        end = timestamp(c['timing']['end']).astimezone(TZ).date() if c['timing']['end'] else start
        if start > date.fromisoformat(request['window']['end']) or end < date.fromisoformat(request['window']['start']):
            reasons.append('outside-window')
    if c['availability']['status'] not in ('available', 'limited'):
        reasons.append('availability-' + c['availability']['status'])
    if c.get('conflicts'):
        reasons.append('unresolved-conflict')
    audience = c.get('audience') or {}
    ages = request.get('party', {}).get('ages', [])
    if ages:
        low, high = audience.get('min_age'), audience.get('max_age')
        if low is None or high is None:
            reasons.append('age-eligibility-unknown')
        elif not all(low <= age <= high for age in ages):
            reasons.append('age-ineligible')
    if f.get('regions') and c['place']['region'] not in f['regions']:
        reasons.append('region-filter')
    if f.get('event_types') and c['event_type'] not in f['event_types']:
        reasons.append('type-filter')
    if f.get('max_price_per_person') is not None:
        maximum = c['cost']['max']
        if maximum is None or c['cost']['fees_unknown'] or maximum > f['max_price_per_person']:
            reasons.append('budget-exceeded-or-unverified')
    if f.get('max_travel_minutes') is not None:
        travel = c.get('travel_minutes')
        if travel is None or travel > f['max_travel_minutes']:
            reasons.append('travel-exceeded-or-unverified')
    if f.get('min_movement') is not None:
        movement = c.get('fit', {}).get('movement', {}).get('score')
        if movement is None or movement < f['min_movement']:
            reasons.append('movement-filter')
    registration = c.get('registration') or {}
    if request['mode'] == 'signup-horizon' and registration.get('required') is not True:
        reasons.append('no-confirmed-signup-action')
    if registration.get('required') and not c.get('action_url'):
        reasons.append('no-registration-link')
    if c['availability']['deadline'] and timestamp(c['availability']['deadline']) < as_of:
        reasons.append('deadline-passed')
    needed = {'identity', 'date', 'time', 'location', 'availability'}
    if ages:
        needed.add('ages')
    if f.get('max_price_per_person') is not None:
        needed.add('cost')
    if request['mode'] == 'signup-horizon':
        needed.add('registration')
    if c['availability']['deadline']:
        needed.add('deadline')
    supported = set()
    for p in c['verification']:
        age = as_of - timestamp(p['observed_at'])
        if p['evidence_type'] in FIRST_PARTY_TYPES and timedelta(0) <= age <= timedelta(hours=max_age_hours) and p.get('quote'):
            supported.update(p['supports'])
    if needed - supported:
        reasons.append('missing-fresh-official-evidence:' + ','.join(sorted(needed - supported)))
    return reasons


def rank(run):
    weights = run['request'].get('weights', WEIGHTS)
    if set(weights) != set(WEIGHTS) or sum(weights.values()) != 100:
        raise ValueError('Weights must cover six dimensions and sum to 100')
    rows = []
    for c in run['candidates']:
        fit = c.get('fit')
        if not fit:
            raise ValueError('Assign fit scores with reasons before ranking: ' + c['candidate_id'])
        total = round(sum(weights[k] * fit[k]['score'] / 5 for k in weights), 2)
        rows.append({'candidate_id': c['candidate_id'], 'score': total,
                     'exclusions': exclusions(c, run['request'])})
    return sorted(rows, key=lambda r: (-r['score'], r['candidate_id']))


def audit(run, graph):
    validate(run, 'run')
    validate(run['request'], 'query')
    timestamp(run['request']['as_of'])
    if run['request']['window']['start'] > run['request']['window']['end']:
        raise ValueError('Reversed date window')
    if run['graph_digest'] != graph_identity(graph):
        raise ValueError('Graph changed; initialize a new run')
    ids = [c['candidate_id'] for c in run['candidates']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate candidate IDs')
    by_id = {c['candidate_id']: c for c in run['candidates']}
    for c in run['candidates']:
        validate_candidate(c)
        seen = {c['candidate_id']}; parent = c.get('parent_event_id')
        while parent:
            if parent not in by_id or parent in seen:
                raise ValueError('Orphan or cyclic parent event')
            seen.add(parent); parent = by_id[parent].get('parent_event_id')
        node = c['discovery'].get('source_node_id')
        if c['discovery']['channel'] == 'source-graph' and node not in {n['id'] for n in graph['nodes']}:
            raise ValueError('Unknown discovery source node')


def complete(run, stage, graph):
    index = len(run['completed'])
    if index >= len(EXPECTED_STAGES) or stage != EXPECTED_STAGES[index]:
        raise ValueError('Stages must execute in order; next is ' + str(EXPECTED_STAGES[index:index+1]))
    audit(run, graph)
    if stage == 'deep-first-party-sweep':
        required = {n['id'] for n in graph['nodes'] if n['status'] == 'active'}
        rows = run['coverage']
        if len(rows) != len(required) or {r['node_id'] for r in rows} != required:
            raise ValueError('Coverage needs one row for every active graph node')
        for r in rows:
            if r['status'] not in ('checked', 'empty', 'failed', 'deferred') or not r['notes']:
                raise ValueError('Unfinished or unexplained coverage')
            if r['status'] in ('checked', 'empty'):
                timestamp(r['observed_at'])
                if not r['visited_urls']:
                    raise ValueError('Visit evidence required')
                for u in r['visited_urls']: url(u)
    elif stage == 'broader-web-search':
        if not REQUIRED_COVERAGE <= {s['region'] for s in run['searches']}:
            raise ValueError('Record search coverage or explicit gaps for all regions')
        for s in run['searches']:
            if not s['query'] or not s['outcome']:
                raise ValueError('Search query and outcome required')
            timestamp(s['observed_at'])
    elif stage == 'merge':
        run['candidates'], merged = merge(run['candidates']); run['merged'].extend(merged)
        audit(run, graph)
    elif stage == 'fit-based-ranking':
        run['ranking'] = rank(run)
    elif stage == 'adversarial-review':
        review = run.get('review') or {}
        if not review.get('reviewer') or review.get('blocking_findings') != []:
            raise ValueError('Named reviewer and zero unresolved blocking findings required')
        if run['ranking'] != rank(run):
            raise ValueError('Ranking stale')
        for row in run['ranking']:
            if row['exclusions']: continue
            checks = review.get('candidates', {}).get(row['candidate_id'], [])
            if {x['id'] for x in checks if x['status'] == 'pass' and x['notes']} != CHECKS or len(checks) != len(CHECKS):
                raise ValueError('Every eligible candidate needs all adversarial checks')
        review['digest'] = review_digest(run)
    run['completed'].append(stage)


def review_digest(run):
    return digest({k: v for k, v in run.items() if k not in ('review', 'completed')})


def report(run, graph):
    audit(run, graph)
    if run['completed'] != EXPECTED_STAGES[:7] and run['completed'] != EXPECTED_STAGES:
        raise ValueError('Complete all seven research stages before reporting')
    if (run.get('review') or {}).get('digest') != review_digest(run):
        raise ValueError('Review missing or stale; changes require a new review')
    review_check = copy.deepcopy(run)
    review_check['completed'] = EXPECTED_STAGES[:6]
    complete(review_check, 'adversarial-review', graph)
    if run['ranking'] != rank(run):
        raise ValueError('Ranking stale')
    # The as_of date is a reproducible research clock. Live publication cannot reuse an old clock.
    if not run['fixture'] and abs(datetime.now(timezone.utc) - timestamp(run['request']['as_of'])) > timedelta(hours=24):
        raise ValueError('Live research clock older than 24 hours; refresh evidence and review')
    rows = run['ranking']; by_id = {c['candidate_id']: c for c in run['candidates']}
    gaps = [r for r in run['coverage'] if r['status'] in ('failed', 'deferred')]
    lines = ['# ' + ('FICTIONAL DEMO — ' if run['fixture'] else '') + 'Activity recommendations', '',
             'As of: ' + run['request']['as_of'], '',
             'Coverage: ' + ('PARTIAL — failed/deferred graph routes remain.' if gaps else 'All registered graph routes accounted for; broader coverage is described below.'),
             'A single newsletter seed is a starting graph, not proof of comprehensive regional coverage.', '',
             '## Recommendations', '']
    eligible = [r for r in rows if not r['exclusions']]
    if not eligible: lines += ['No confirmed actionable matches. Inventory and gaps remain below.', '']
    for row in eligible[:run['request'].get('limit', 10)]:
        c = by_id[row['candidate_id']]
        lines += [f"### {c['title']} · {row['score']}/100", '',
                  f"{c['timing']['start']} · {c['place']['venue']}, {c['place']['city']} · {c['availability']['status']}", '',
                  'Fit: ' + ' '.join(f"{k}: {v['reason']}" for k, v in c['fit'].items()), '',
                  'Audience: ' + json.dumps(c.get('audience')), '',
                  'Cost (per person, USD): ' + json.dumps(c['cost']) + '; travel minutes: ' + str(c.get('travel_minutes')), '',
                  'Tradeoffs: ' + '; '.join(c.get('restrictions', []) + c.get('tradeoffs', [])), '',
                  'Deadline: ' + str(c['availability']['deadline']) + '; action: ' + str(c.get('action_url')), '',
                  'Evidence: ' + '; '.join(p['url'] + ' (observed ' + p['observed_at'] + ')' for p in c['verification']), '']
    lines += ['## Full inventory (including excluded and unresolved)', '']
    for row in rows:
        c = by_id[row['candidate_id']]
        lines += [f"- {c['candidate_id']}: {c['title']} · {c['place']['region']} · {c['timing']['start']} · " + ('; '.join(row['exclusions']) or 'eligible')]
        if c.get('conflicts'): lines += ['  Conflicts: ' + json.dumps(c['conflicts'])]
    lines += ['', '## Coverage ledger', '', *['- ' + json.dumps(r) for r in run['coverage']],
              '', '## Broader search coverage', '', *['- ' + json.dumps(s) for s in run['searches']],
              '', '## Proposed graph additions', '', *['- ' + json.dumps(p) for p in run['graph_proposals']],
              '', '## Review', '', 'Reviewer: ' + run['review']['reviewer'], '']
    return '\n'.join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--graph', type=Path, default=ROOT / 'data/source-graph.json')
    sub = p.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init'); init.add_argument('request'); init.add_argument('out'); init.add_argument('--fixture', action='store_true')
    stage = sub.add_parser('stage'); stage.add_argument('run'); stage.add_argument('stage', choices=EXPECTED_STAGES[:-1])
    final = sub.add_parser('report'); final.add_argument('run'); final.add_argument('out')
    args = p.parse_args(argv)
    try:
        graph = load(args.graph)
        if args.command == 'init':
            save(args.out, initialize(load(args.request), graph, args.fixture))
        else:
            run = load(args.run)
            if args.command == 'stage': complete(run, args.stage, graph)
            else:
                output = report(run, graph)
                Path(args.out).write_text(output, encoding='utf-8')
                run['completed'] = EXPECTED_STAGES.copy()
            save(args.run, run)
        return 0
    except Exception as exc:
        print(f'Validation failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
