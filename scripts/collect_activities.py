#!/usr/bin/env python3
"""Bounded, zero-LLM official event collection. Run daily; facts are not recommendations."""
from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import date, datetime, time as dt_time, timezone
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from dateutil.parser import isoparse, parse
from dateutil.relativedelta import relativedelta

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo('America/Chicago')
AGENT = 'KCActivityFinder/1.0 (+https://github.com/colesteaks/kc-activity-finder)'
MAX_PAGES = 12
MAX_BYTES = 6_000_000


def clean(value):
    text = html.unescape(str(value or ''))
    if '<' in text: text = BeautifulSoup(text, 'html.parser').get_text(' ', strip=True)
    return ' '.join(text.split())


def safe_url(value):
    p = urlsplit(value or '')
    return value if p.scheme in ('http', 'https') and p.hostname and not p.username and not p.password else None


def canonical(value):
    p = urlsplit(value)
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip('/'), p.query, ''))


def local_datetime(value):
    if not value: return None
    d = isoparse(str(value))
    if d.tzinfo is None: d = d.replace(tzinfo=TZ)
    return d.astimezone(TZ).isoformat()


class Fetcher:
    def __init__(self, cache):
        self.cache = cache; cache.mkdir(parents=True, exist_ok=True)
        self.robots = {}; self.requests = 0

    def fetch(self, url, robots=True):
        if not safe_url(url): raise ValueError('Invalid URL')
        p = urlsplit(url); origin = p.scheme + '://' + p.netloc
        if robots:
            if origin not in self.robots:
                rp = urllib.robotparser.RobotFileParser()
                try:
                    body = self.fetch(origin + '/robots.txt', robots=False)
                    rp.parse(body.splitlines())
                except urllib.error.HTTPError as e:
                    if e.code not in (404, 410): raise
                    rp.parse([])
                self.robots[origin] = rp
            if not self.robots[origin].can_fetch(AGENT, url):
                raise ValueError('robots.txt disallows this route')
        key = hashlib.sha256(url.encode()).hexdigest()
        meta_path = self.cache / (key + '.json'); body_path = self.cache / (key + '.gz')
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        headers = {'User-Agent': AGENT, 'Accept': 'text/html,application/json;q=0.9,*/*;q=0.5'}
        if body_path.exists():
            if meta.get('etag'): headers['If-None-Match'] = meta['etag']
            if meta.get('modified'): headers['If-Modified-Since'] = meta['modified']
        # One source per worker; a small inter-request delay avoids hammering a host.
        time.sleep(.25)
        self.requests += 1
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as response:
                if urlsplit(response.url).hostname != p.hostname:
                    raise ValueError('Cross-host redirect requires source registry review')
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES: raise ValueError('Source response exceeded size limit')
                text = body.decode('utf-8', errors='replace')
                gzip.open(body_path, 'wb').write(body)
                meta_path.write_text(json.dumps({'etag': response.headers.get('ETag'), 'modified': response.headers.get('Last-Modified')}))
                return text
        except urllib.error.HTTPError as e:
            if e.code == 304 and body_path.exists():
                return gzip.open(body_path, 'rb').read().decode('utf-8', errors='replace')
            # 403/429 are reported, never bypassed or converted into empty calendars.
            raise


def walk_json(data):
    if isinstance(data, list):
        for item in data: yield from walk_json(item)
    elif isinstance(data, dict):
        types = data.get('@type', [])
        if isinstance(types, str): types = [types]
        if any(t.endswith('Event') for t in types): yield data
        for v in data.values():
            if isinstance(v, (dict, list)): yield from walk_json(v)


def jsonld_events(body):
    soup = BeautifulSoup(body, 'html.parser'); result = []
    for script in soup.select('script[type="application/ld+json"]'):
        try: result.extend(walk_json(json.loads(script.string or script.get_text(), strict=False)))
        except (ValueError, TypeError): continue
    return result


def flight_objects(body):
    """Decode Next.js serialized JSON as data. Never eval source JavaScript."""
    def walk(v):
        if isinstance(v, dict):
            yield v
            for x in v.values(): yield from walk(x)
        elif isinstance(v, list):
            for x in v: yield from walk(x)
    for match in re.finditer(r'self\.__next_f\.push\(', body):
        try:
            parts, _ = json.JSONDecoder().raw_decode(body[match.end():])
            if len(parts) < 2 or not isinstance(parts[1], str): continue
            for line in parts[1].splitlines():
                try: yield from walk(json.loads(line.partition(':')[2]))
                except ValueError: continue
        except (ValueError, TypeError): continue


def structured_events(body, source):
    result = jsonld_events(body)
    for obj in flight_objects(body):
        if source['id'] == 'kc-zoo' and obj.get('type') == 'special_event':
            data = obj.get('data', {})
            title = ' '.join(x.get('text', '') for x in data.get('title', []) if isinstance(x, dict))
            for occurrence in data.get('activity_time', []):
                if occurrence.get('start_time'):
                    result.append({'name': title, 'startDate': occurrence['start_time'], 'endDate': occurrence.get('end_time'),
                        'url': urljoin(source['url'], '/event/' + obj['uid']),
                        'description': data.get('description1') or '', 'location': {'name': occurrence.get('other_location') or occurrence.get('timelocation') or source['name']}})
        elif source['id'] == 'crystal-bridges' and obj.get('title') and obj.get('startDateTime'):
            end = None
            # Explicit year on both dates is required. This represents a series range,
            # not invented daily sessions. Individual tickets remain on the source page.
            dates = re.findall(r'[A-Z][a-z]+ \d{1,2}, 20\d\d', obj.get('dateRange', ''))
            if len(dates) == 2:
                end = parse(dates[-1]).replace(hour=23, minute=59, tzinfo=TZ).isoformat()
            result.append({'name': obj['title'], 'startDate': obj['startDateTime'], 'endDate': end,
                'url': urljoin(source['url'], obj.get('href') or '/events/' + obj.get('slug', obj.get('id', ''))),
                'description': obj.get('description', ''), 'location': {'name': obj.get('location') or source['name']}})
    return result


def classify(title, categories=''):
    text = (title + ' ' + categories).lower()
    rules = [('Sports & movement', r'\brace\b|\brun\b|yoga|hike|fitness|sports|football|volleyball|dance'),
             ('Classes & workshops', r'workshop|\bclass\b|camp|lesson|conference'),
             ('Music & performance', r'concert|music|theat|ballet|comedy|performance|choir'),
             ('Food & markets', r'market|food|dinner|tasting|supper'),
             ('Festivals & seasonal', r'festival|holiday|christmas|halloween|parade'),
             ('Arts & museums', r'art|museum|gallery|exhibition|tour|print'),
             ('Nature & animals', r'zoo|animal|nature|garden|penguin|bird'),
             ('Talks & community', r'talk|lecture|book|storytime|community')]
    return next((name for name, pattern in rules if re.search(pattern, text)), 'Other')


def age_rules(raw):
    # Only explicit source age policies. Categories like "family" are not age rules.
    text = clean(raw)
    result = {'min': None, 'max': None, 'all_ages': False, 'label': 'Age guidance not supplied'}
    if re.search(r'\ball ages\b', text, re.I):
        return {'min': 0, 'max': None, 'all_ages': True, 'label': 'All ages (source stated)'}
    m = re.fullmatch(r'\s*(\d+)\s*[-–]\s*(\d+)\s*', text)
    if m: return {'min': int(m[1]), 'max': int(m[2]), 'all_ages': False, 'label': text}
    m = re.fullmatch(r'(\d+)\s*\+', text)
    if m: return {'min': int(m[1]), 'max': None, 'all_ages': False, 'label': text}
    return result


def explicit_age_guidance(title, description):
    """Recognize explicit audience rules, not generic family/category labels."""
    text = clean(title + ' ' + clean(description))
    prefix = r'(?:\bfor\s+(?:(?:children|adults|participants)\s+)?ages?\s*:?|\bages?\s*:)\s*'
    match = re.search(prefix + r'(\d{1,2})\s*(?:[-–]|to|through)\s*(\d{1,2})\b', text, re.I)
    if match:
        low, high = map(int, match.groups())
        if low <= high: return age_rules(f'{low}–{high}')
    match = re.search(prefix + r'(\d{1,2})\s*(?:\+|(?:and|or) (?:up|older|over))', text, re.I)
    if match: return age_rules(match[1] + '+')
    match = re.search(r'\b(18|21)\s*\+\s*[)\]]?\s*$', title)
    if match: return age_rules(match[1] + '+')
    if re.search(r'\b(?:for all ages|all ages (?:are )?welcome|open to all ages)\b', text, re.I): return age_rules('All ages')
    return age_rules('')


def normalize(raw, source, observed, page):
    title = clean(raw.get('name')); start_raw = raw.get('startDate')
    if not title or not start_raw: return None
    start = local_datetime(start_raw); end = local_datetime(raw.get('endDate'))
    if end and isoparse(end) < isoparse(start): raise ValueError('Event end precedes start')
    link = safe_url(urljoin(page, raw.get('url') or page))
    if not link: return None
    location = raw.get('location') or {}
    if isinstance(location, list): location = next((x for x in location if isinstance(x, dict)), {})
    if isinstance(location, str): location = {'name': location}
    address = location.get('address') or {}
    if isinstance(address, str): address = {'streetAddress': address}
    status = str(raw.get('eventStatus', 'EventScheduled')).split('/')[-1]
    # Some official sites leave schema status unchanged after editing the title.
    # An explicit cancellation prefix must override that stale default.
    if re.match(r'^\s*(?:\[)?cancel[le]*d\b', title, re.I): status = 'EventCancelled'
    offers = raw.get('offers') or []
    if isinstance(offers, dict): offers = [offers]
    offer = next((x for x in offers if isinstance(x, dict)), {})
    all_day = len(str(start_raw)) == 10 or raw.get('_all_day', False)
    signature = canonical(link) + '|' + start
    return {'id': hashlib.sha256(signature.encode()).hexdigest()[:20], 'title': title,
            'start': start, 'end': end, 'date': start[:10], 'end_date': end[:10] if end else start[:10],
            'all_day': bool(all_day), 'region': source['region'], 'city': clean(address.get('addressLocality') or source['city']),
            'venue': clean(location.get('name') or source['name']), 'type': classify(title, str(raw.get('keywords', ''))),
            'type_inferred': True, 'ages': age_rules(raw['typicalAgeRange']) if raw.get('typicalAgeRange') else explicit_age_guidance(title, raw.get('description', '')),
            'status': {'EventCancelled':'canceled','EventPostponed':'postponed','EventRescheduled':'rescheduled'}.get(status, 'scheduled'),
            'ticket_status': clean(offer.get('availability')).split('/')[-1] or 'unknown',
            'price': clean(offer.get('price')) or None, 'currency': offer.get('priceCurrency') or None,
            'deadline': None, 'url': link, 'source_id': source['id'], 'source_name': source['name'],
            'source_kind': source['kind'], 'checked_at': observed, 'first_seen': observed,
            'description': clean(raw.get('description'))[:200],
            'evidence': {'url': page, 'format': source['format'], 'start_as_published': str(start_raw)},
            'stale': False, 'conflicts': [], 'disappeared': False}


def tribe_events(raw):
    venue = raw.get('venue') or {}
    if not isinstance(venue, dict): venue = {}
    return {'name': raw.get('title'), 'startDate': raw.get('utc_start_date') + '+00:00' if raw.get('utc_start_date') else raw.get('start_date'),
            'endDate': raw.get('utc_end_date') + '+00:00' if raw.get('utc_end_date') else raw.get('end_date'),
            'url': raw.get('url'), 'description': raw.get('excerpt') or raw.get('description') or '', '_all_day': raw.get('all_day', False),
            'location': {'name': venue.get('venue'), 'address': {'addressLocality': venue.get('city')}},
            'eventStatus': 'EventScheduled', 'keywords': ' '.join(c.get('name', '') for c in raw.get('categories', []))}


def columbia_event(body, page):
    soup = BeautifulSoup(body, 'html.parser'); d = soup.select_one('.event_date'); h = soup.select_one('h1')
    if not d or not h: return []
    stamp = d.get_text(' ', strip=True)
    # A missing year must not be silently assigned to the current year.
    if not re.search(r'\b20\d\d\b', stamp): return []
    times = d.select_one('.event_times')
    if times: times.extract()
    day = parse(d.get_text(' ', strip=True), fuzzy=False)
    start_text = times.get_text(' ', strip=True).split(' to ')[0] if times else '00:00'
    start = parse(start_text, default=day).replace(tzinfo=TZ)
    return [{'name': h.get_text(' ', strip=True), 'startDate': start.isoformat(), 'url': page, '_all_day': times is None}]


def collect_source(source, start, until, observed, cache):
    if source.get('month_template'):
        source = dict(source, url=source['month_template'].format(month=start.strftime('%Y-%m')))
    f = Fetcher(cache); records = []; errors = []; visited = []; leads = []; truncated = False
    try:
        if source['format'] == 'tribe':
            for page in range(1, MAX_PAGES + 1):
                target = source['url'] + '?' + urlencode({'start_date': start.isoformat(), 'end_date': until.isoformat(), 'per_page': 50, 'page': page})
                data = json.loads(f.fetch(target)); visited.append(target)
                for event in data.get('events', []):
                    try:
                        row = normalize(tribe_events(event), source, observed, event.get('url') or target)
                        if row: records.append(row)
                    except (ValueError, TypeError) as e: errors.append(str(e))
                if page >= data.get('total_pages', 1): break
                if page == MAX_PAGES: truncated = True
        else:
            entries = [source['url']]
            if source.get('month_template'):
                entries = [source['month_template'].format(month=(start + relativedelta(months=i)).strftime('%Y-%m')) for i in range(8)]
            seen_pages = set(); detail_links = {}
            for entry in entries:
                next_page = entry
                for _ in range(MAX_PAGES):
                    if next_page in seen_pages: break
                    body = f.fetch(next_page); seen_pages.add(next_page); visited.append(next_page)
                    soup = BeautifulSoup(body, 'html.parser')
                    for event in structured_events(body, source):
                        try:
                            row = normalize(event, source, observed, next_page)
                            if row: records.append(row)
                        except (ValueError, TypeError) as e: errors.append(str(e))
                    for a in soup.select('a[href]'):
                        link = urljoin(next_page, a['href']); p = urlsplit(link)
                        if p.hostname == urlsplit(source['url']).hostname and re.search(source['pattern'], p.path):
                            detail_links.setdefault(canonical(link), None)
                    nxt = soup.select_one('a[rel="next"], a.next.page-numbers')
                    if not nxt: break
                    candidate = urljoin(next_page, nxt['href'])
                    if urlsplit(candidate).hostname != urlsplit(source['url']).hostname: break
                    next_page = candidate
                else: truncated = True
            limit = source.get('max_details', 60)
            truncated |= len(detail_links) > limit
            for link in list(detail_links)[:limit]:
                try:
                    body = f.fetch(link); visited.append(link)
                    items = structured_events(body, source)
                    if not items and source['format'] == 'columbia': items = columbia_event(body, link)
                    found = False
                    for item in items:
                        row = normalize(item, source, observed, link)
                        if row: records.append(row); found = True
                    if not found: leads.append({'url': link, 'reason': 'No supported explicit event date; needs adapter or review'})
                except Exception as e: errors.append(link + ': ' + str(e))
    except Exception as e: errors.append(str(e))
    # Apply a seven-calendar-month horizon after capture; preserve ongoing ranges.
    records = [r for r in records if r['date'] <= until.isoformat() and r['end_date'] >= start.isoformat()]
    unique = {r['id']: r for r in records}
    return list(unique.values()), {'id': source['id'], 'name': source['name'], 'url': source['url'], 'region': source['region'],
        'status': 'partial' if errors or leads or truncated else ('checked' if records else 'no-structured-events'),
        'checked_at': observed, 'events': len(unique), 'requests': f.requests, 'visited_count': len(visited),
        'errors': errors[:15], 'unparsed_count': len(leads), 'unparsed_leads': leads[:25], 'truncated': truncated,
        'latest_published_date': max((r['date'] for r in records), default=None),
        'horizon_note': 'Requested through ' + until.isoformat() + '; sources may not yet publish that far ahead.'}


def reconcile(old, fresh, health, now):
    new = {r['id']: r for r in fresh}; old_by_id = {r['id']: r for r in old}
    for key, row in new.items():
        if key in old_by_id: row['first_seen'] = old_by_id[key]['first_seen']
    for row in old:
        if row['id'] in new or row['end_date'] < now.date().isoformat(): continue
        kept = dict(row); kept['stale'] = True; kept['disappeared'] = True
        new[row['id']] = kept
    # Exact title/venue/instant duplicates share evidence; differing statuses remain conflicts.
    result = {}; norm = lambda s: re.sub(r'\W+', '', s.casefold())
    for row in new.values():
        key = (norm(row['title']), norm(row['venue']), row['city'].casefold(), row['start'])
        if key not in result:
            row['sources'] = row.get('sources') or [row['evidence']]; result[key] = row; continue
        kept = result[key]; kept['sources'].append(row['evidence'])
        if kept['status'] != row['status']: kept['conflicts'].append('Source status disagreement')
    return sorted(result.values(), key=lambda r: (r['start'], r['title']))


def run(registry, output, cache, now=None):
    now = now or datetime.now(TZ); start = now.date(); until = start + relativedelta(months=7)
    observed = now.isoformat(); sources = json.loads(registry.read_text())['sources']
    old = json.loads(output.read_text()) if output.exists() else {'activities': []}
    health = []; fresh = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(collect_source, s, start, until, observed, cache / s['id']) for s in sources]
        for job in jobs:
            rows, status = job.result(); fresh.extend(rows); health.append(status)
            print(status['id'], status['status'], status['events'], flush=True)
    if not any(h['visited_count'] for h in health): raise RuntimeError('All sources failed; preserving previous dataset')
    result = {'version': 1, 'updated_at': observed, 'horizon_start': start.isoformat(), 'horizon_end': until.isoformat(),
              'timezone': 'America/Chicago', 'collection_mode': 'deterministic-no-llm', 'sources': health,
              'activities': reconcile(old['activities'], fresh, health, now)}
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix('.tmp'); temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n'); temp.replace(output)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sources', type=Path, default=ROOT / 'data/collection-sources.json')
    p.add_argument('--out', type=Path, default=ROOT / 'web/activities.json')
    p.add_argument('--cache', type=Path, default=ROOT / '.collector-cache')
    a = p.parse_args(); result = run(a.sources, a.out, a.cache)
    print(f"Saved {len(result['activities'])} activities; horizon ends {result['horizon_end']}")
