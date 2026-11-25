#!/usr/bin/env python3
"""Probe repository-known official URLs and promote only verified parsers.

Candidates come from data already in the repo (collection registry and
unreviewed feed proposals). This script never invents URLs, dates, prices,
or hours. HTTP 403/429 and robots denials stay blocked; they are not
recorded as empty calendars.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from platform_adapters import ics_events, rss_events

TZ = ZoneInfo('America/Chicago')
ROOT = Path(__file__).resolve().parents[1]
FEED_RE = re.compile(r'(\.ics\b|ical=|icalendar|/feed\b|/rss\b|\batom\b)', re.I)
SKIP_RE = re.compile(r'/comments/feed|articleid=|/games/\d{4}/', re.I)
TIERS = {
    'tier1_backyard': {
        'Kansas City metro', 'Lawrence', 'Columbia', 'Bentonville', 'surrounding areas',
    },
    'tier2_day_trip': {'Topeka & Flint Hills', 'St. Joseph & Pony Express'},
    'tier3_weekend': {'Omaha', 'Des Moines', 'Springfield & Ozarks', 'Wichita & Hutchinson'},
}


def tier_for_region(region: str | None) -> str:
    for name, regions in TIERS.items():
        if region in regions:
            return name
    return 'unassigned'


def _host(url: str) -> str:
    host = (urlsplit(url).hostname or '').lower()
    return host[4:] if host.startswith('www.') else host


def repo_candidates(root: Path = ROOT) -> list[dict]:
    """Feed URLs already stored in proposals, tagged with a region only when a reviewed source shares the host."""
    registry = json.loads((root / 'data/collection-sources.json').read_text())['sources']
    proposals = json.loads((root / 'data/source-proposals.json').read_text()).get('proposals', [])
    host_region = {}
    known_urls = set()
    for source in registry:
        known_urls.add(source['url'])
        host_region.setdefault(_host(source['url']), source['region'])
    found = []
    seen = set()
    for proposal in proposals:
        url = proposal.get('url') or ''
        if not url.startswith('https://') or url in seen or not FEED_RE.search(url):
            continue
        seen.add(url)
        region = host_region.get(_host(url))
        found.append({
            'url': url,
            'label': proposal.get('label') or url,
            'region': region,
            'tier': tier_for_region(region),
            'already_registered': url in known_urls,
            'skip_promotion': bool(SKIP_RE.search(url)),
        })
    return found


def classify_response(url: str, status: int, body: str, content_type: str = '') -> dict:
    """Classify a fetched body. Blocked statuses are never parsed into events."""
    result = {
        'url': url,
        'status': status,
        'content_type': content_type,
        'classification': 'error',
        'format': None,
        'event_count': 0,
        'error': None,
    }
    if status in (403, 429):
        result['classification'] = 'blocked'
        result['error'] = f'HTTP {status}'
        return result
    if status != 200:
        result['error'] = f'HTTP {status}'
        return result
    source = {'id': 'probe', 'name': 'Probe', 'categories': []}
    lowered = (content_type + ' ' + url + ' ' + body[:400]).lower()
    events: list[dict] = []
    fmt = None
    if 'begin:vcalendar' in lowered or url.lower().endswith('.ics') or 'text/calendar' in lowered:
        fmt = 'ics'
        events = ics_events(body, source, url)
    elif '<rss' in lowered or '<feed' in lowered or 'application/rss' in lowered or 'atom' in lowered:
        fmt = 'rss'
        events = rss_events(body, source, url)
    result['format'] = fmt
    result['event_count'] = len(events)
    if fmt and events:
        result['classification'] = 'verified_parser'
    elif fmt:
        result['classification'] = 'discovery'
        result['error'] = 'Feed parsed with no explicit-date events'
    else:
        result['classification'] = 'discovery'
        result['error'] = 'Fetched page has no ICS or RSS event feed'
    return result


def _slug(url: str, taken: set[str]) -> str:
    host = _host(url).split('.')[0]
    path = re.sub(r'[^a-z0-9]+', '-', urlsplit(url).path.lower()).strip('-')
    base = re.sub(r'[^a-z0-9]+', '-', f'{host}-{path}'.lower()).strip('-')[:40] or 'feed'
    slug = base
    n = 2
    while slug in taken:
        suffix = f'-{n}'
        slug = base[:40 - len(suffix)] + suffix
        n += 1
    taken.add(slug)
    return slug


def _source_entry(probe: dict, candidate: dict, today: str, taken: set[str]) -> dict:
    verified = probe['classification'] == 'verified_parser'
    return {
        'id': _slug(probe['url'], taken),
        'name': (candidate.get('label') or probe['url'])[:80],
        'region': candidate['region'],
        'city': candidate['region'],
        'kind': 'organizer',
        'format': probe['format'] if verified else 'discovery',
        'url': probe['url'],
        'categories': ['community_social'],
        'activity_kinds': ['one_off'],
        'required_leaves': ['specific event or program'],
        'pattern': '/no-automatic-detail/',
        'max_pages': 1,
        'max_details': 0,
        'collection_note': (
            f"Promoted {today} after probe found {probe['event_count']} explicit-date events."
            if verified else
            f"Discovery only on {today}: {probe.get('error') or 'no explicit-date feed'}."
        ),
        'probe': {
            'checked_at': today,
            'classification': probe['classification'],
            'event_count': probe['event_count'],
            'evidence_url': probe['url'],
        },
    }


def _graph_node(source: dict, today: str) -> dict:
    verified = source['format'] != 'discovery'
    return {
        'id': source['id'],
        'label': source['name'],
        'canonical_url': source['url'],
        'source_class': 'event-organizer',
        'roles': ['first-party-sweep'],
        'status': 'active' if verified else 'deferred',
        'coverage': [source['region']],
        'provenance': {
            'kind': 'reviewed-supplement',
            'discovered_on': source['url'],
            'observed_relation': source['collection_note'],
        },
        'verification': {
            'last_checked': today,
            'evidence_url': source['url'],
            'collector_status': 'verified-parser' if verified else 'discovery-only',
            'captured_records': source['probe']['event_count'],
        },
        'crawl': {
            'entrypoints': [source['url']],
            'sweep_targets': ['specific event or program'],
        },
    }


def apply_probe(registry: dict, graph: dict, probes: list[dict], candidates: list[dict], today: str,
                discovery_limit: int = 6) -> dict:
    """Add verified parsers and a few honest discovery rows. The provided-seed node is copied back unchanged."""
    seed_nodes = [node for node in graph.get('nodes', []) if node.get('provenance', {}).get('kind') == 'provided-seed']
    seed_snapshot = json.dumps(seed_nodes, sort_keys=True)
    by_url = {item['url']: item for item in candidates}
    known_urls = {source['url'] for source in registry.get('sources', [])}
    taken = {source['id'] for source in registry.get('sources', [])} | {node['id'] for node in graph.get('nodes', [])}
    promoted = []
    withheld = []
    discoveries = 0
    for probe in probes:
        candidate = by_url.get(probe['url'], {})
        reason = None
        if probe['url'] in known_urls:
            reason = 'already registered'
        elif candidate.get('skip_promotion') or SKIP_RE.search(probe['url'] or ''):
            reason = 'single-event or comment feed'
        elif not candidate.get('region'):
            reason = 'region not tied to a reviewed host'
        elif probe['classification'] == 'blocked':
            reason = probe.get('error') or 'blocked'
        elif probe['classification'] == 'verified_parser' and probe.get('format') in ('ics', 'rss') and probe.get('event_count', 0) > 0:
            reason = None
        elif probe['classification'] == 'discovery':
            if discoveries >= discovery_limit:
                reason = 'discovery limit reached'
            else:
                reason = None
        else:
            reason = probe.get('error') or probe['classification']
        if reason:
            withheld.append({'url': probe['url'], 'reason': reason})
            continue
        if probe['classification'] == 'discovery':
            discoveries += 1
        source = _source_entry(probe, candidate, today, taken)
        registry.setdefault('sources', []).append(source)
        graph.setdefault('nodes', []).append(_graph_node(source, today))
        known_urls.add(probe['url'])
        promoted.append({'id': source['id'], 'url': source['url'], 'format': source['format']})
    restored = json.loads(seed_snapshot)
    graph['nodes'] = restored + [node for node in graph['nodes'] if node.get('provenance', {}).get('kind') != 'provided-seed']
    if json.dumps(restored, sort_keys=True) != seed_snapshot:
        raise RuntimeError('provided-seed node changed')
    graph['last_reviewed'] = today
    return {'promoted': promoted, 'withheld': withheld}


def postal_addresses(html: str, page_url: str) -> list[dict]:
    """Pull schema.org street addresses from JSON-LD. No address is inferred from visible prose."""
    soup = BeautifulSoup(html, 'html.parser')
    found = []
    seen = set()
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text() or '', strict=False)
        except (ValueError, TypeError):
            continue
        for item in _walk(payload):
            address = item.get('address')
            if not isinstance(address, dict):
                continue
            street = str(address.get('streetAddress') or '').strip()
            locality = str(address.get('addressLocality') or '').strip()
            region = str(address.get('addressRegion') or '').strip()
            if not street or not locality or not region:
                continue
            name = str(item.get('name') or '').strip()
            if not name:
                continue
            postal = str(address.get('postalCode') or '').strip()
            formatted = ', '.join(part for part in (street, locality, f'{region} {postal}'.strip()) if part)
            key = formatted.casefold()
            if key in seen:
                continue
            seen.add(key)
            found.append({'name': name, 'address': formatted, 'source_url': page_url})
    return found


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


_FULL_ADDRESS = re.compile(
    r'(\d{2,6}\s+[A-Za-z0-9.\'’\- ]{2,40}?\s(?:St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Blvd|Boulevard|Way|Pkwy|Hwy|Highway)\.?'
    r',\s*[A-Za-z .\'’]+,\s*[A-Z]{2}(?:\s+\d{5})?)',
    re.I,
)


def addresses_from_proposals(proposals: list[dict]) -> list[dict]:
    """Use a proposal only when its own label already contains a street, city, and state, and the URL is https and not a map redirect."""
    rows = []
    seen = set()
    for proposal in proposals:
        url = proposal.get('url') or ''
        host = _host(url)
        if not url.startswith('https://') or host in ('google.com', 'maps.google.com'):
            continue
        match = _FULL_ADDRESS.search(proposal.get('label') or '')
        if not match:
            continue
        address = re.sub(r'\s+', ' ', match.group(1)).strip()
        if address.casefold() in seen:
            continue
        seen.add(address.casefold())
        label = (proposal.get('label') or '').strip()
        name = label[:label.lower().find(address.lower())].strip(' -–—') or host
        rows.append({'name': name[:80], 'address': address, 'source_url': url})
    return rows


def place_record(observation: dict, geo: dict, source_ids: list[str] | None = None) -> dict:
    if not geo or geo.get('precision') != 'address':
        raise ValueError('A new place requires a Census street-address match')
    slug = re.sub(r'[^a-z0-9]+', '-', observation['name'].lower()).strip('-')[:48] or 'place'
    return {
        'id': slug,
        'name': observation['name'],
        'address': observation['address'],
        'geo': geo,
        'hours': None,
        'activities': [],
        'source_url': observation['source_url'],
        'match': {
            'source_ids': list(source_ids or []),
            'venue_aliases': [observation['name']],
        },
    }


def merge_places(places: list[dict], additions: list[dict]) -> list[dict]:
    ids = {place['id'] for place in places}
    identities = {
        (source, re.sub(r'\W+', '', alias.casefold()))
        for place in places
        for source in place.get('match', {}).get('source_ids', [])
        for alias in place.get('match', {}).get('venue_aliases', [])
    }
    for place in additions:
        if place['id'] in ids:
            continue
        conflict = False
        for source in place.get('match', {}).get('source_ids', []):
            for alias in place.get('match', {}).get('venue_aliases', []):
                key = (source, re.sub(r'\W+', '', alias.casefold()))
                if key in identities:
                    conflict = True
                identities.add(key)
        if conflict:
            continue
        ids.add(place['id'])
        places.append(place)
    return places


def summarize(probes: list[dict], candidates: list[dict], promotion: dict) -> dict:
    return {
        'probes': probes,
        'candidate_count': len(candidates),
        'by_tier': {
            tier: sum(1 for item in candidates if item['tier'] == tier)
            for tier in list(TIERS) + ['unassigned']
        },
        'promoted': promotion['promoted'],
        'withheld': promotion['withheld'],
        'note': 'Tier 2 and tier 3 counts are zero when the repository has no reviewed host in that corridor. Missing corridors are gaps, not invented sources.',
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--report', type=Path, default=None)
    parser.add_argument('--promote', action='store_true')
    parser.add_argument('--places', action='store_true', help='Geocode observed addresses onto data/places.json')
    parser.add_argument('--today', default=datetime.now(TZ).date().isoformat())
    args = parser.parse_args()
    root = args.root
    candidates = repo_candidates(root)
    from collect_activities import Fetcher
    fetcher = Fetcher(root / '.collector-cache' / 'probes')
    probes = []
    for candidate in candidates:
        if candidate['already_registered']:
            continue
        try:
            body = fetcher.fetch(candidate['url'])
            probe = classify_response(candidate['url'], 200, body)
        except Exception as exc:
            message = str(exc)
            status = 403 if '403' in message else 429 if '429' in message else 0
            classification = 'blocked' if 'robots.txt' in message or status in (403, 429) else 'error'
            probe = {
                'url': candidate['url'],
                'status': status or None,
                'classification': classification,
                'format': None,
                'event_count': 0,
                'error': message,
            }
        probe['tier'] = candidate['tier']
        probe['region'] = candidate['region']
        probes.append(probe)
        print(f"{probe['classification']:16} {probe.get('event_count', 0):3} {candidate['url']}")
    registry = json.loads((root / 'data/collection-sources.json').read_text())
    graph = json.loads((root / 'data/source-graph.json').read_text())
    promotion = {'promoted': [], 'withheld': []}
    if args.promote:
        promotion = apply_probe(registry, graph, probes, candidates, args.today)
        (root / 'data/collection-sources.json').write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n')
        (root / 'data/source-graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2) + '\n')
    report = summarize(probes, candidates, promotion)
    if args.places:
        report['places'] = _expand_places(root, fetcher, args.today)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(f"Wrote {args.report}")
    print(f"Promoted {len(promotion['promoted'])}; withheld {len(promotion['withheld'])}")
    return 0


def _expand_places(root: Path, fetcher, today: str) -> dict:
    from geocode_places import geocode_address, geocode_places_file
    attempted, updated = geocode_places_file(root / 'data/places.json')
    payload = json.loads((root / 'data/places.json').read_text())
    registry = json.loads((root / 'data/collection-sources.json').read_text())['sources']
    proposals = json.loads((root / 'data/source-proposals.json').read_text()).get('proposals', [])
    observations = addresses_from_proposals(proposals)
    known_addresses = {place['address'].casefold() for place in payload['places']}
    for source in registry:
        if source.get('format') in ('ics', 'rss', 'discovery'):
            continue
        try:
            body = fetcher.fetch(source['url'])
        except Exception as exc:
            print(f"PLACE SKIP {source['id']}: {exc}")
            continue
        for item in postal_addresses(body, source['url']):
            item['source_ids'] = [source['id']]
            observations.append(item)
    added = []
    unmatched = []
    for item in observations:
        if item['address'].casefold() in known_addresses:
            continue
        geo = geocode_address(item['address'], observed_at=datetime.now(TZ).isoformat())
        if not geo:
            unmatched.append(item['address'])
            continue
        before = len(payload['places'])
        place = place_record(item, geo, item.get('source_ids'))
        merge_places(payload['places'], [place])
        if len(payload['places']) > before:
            known_addresses.add(item['address'].casefold())
            added.append(place['id'])
    payload_path = root / 'data/places.json'
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    return {
        'existing_geocoded': updated,
        'existing_attempted': attempted,
        'added': added,
        'unmatched': unmatched,
        'total_places': len(payload['places']),
        'with_coordinates': sum(1 for place in payload['places'] if place.get('geo')),
        'checked_at': today,
    }


if __name__ == '__main__':
    raise SystemExit(main())
