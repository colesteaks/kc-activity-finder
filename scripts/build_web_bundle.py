#!/usr/bin/env python3
"""Write a compact relational bundle, static RSS feeds, and a minified activities file.

The bundle is a browse index. It keeps source URLs and explicit dates and drops
evidence quotes. It does not invent events.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape

from enrichment import is_promo_listing

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_LIMIT = 1_000_000
CHANNEL = 'https://github.com/colesteaks/kc-activity-finder'


def _slug(region: str) -> str:
    return ''.join(ch.lower() if ch.isalnum() else '-' for ch in region).strip('-')


def compact_activity(row: dict) -> dict:
    schedule = row.get('schedule') or {}
    geo = row.get('geo') or None
    item = {
        'id': row.get('id'),
        'offering_id': row.get('offering_id') or row.get('id'),
        'parent_id': row.get('parent_id'),
        'title': row.get('title'),
        'venue': row.get('venue'),
        'city': row.get('city'),
        'region': row.get('region'),
        'categories': row.get('categories') or [],
        'type': row.get('type'),
        'date': row.get('date'),
        'end_date': row.get('end_date'),
        'start': row.get('start'),
        'end': row.get('end'),
        'all_day': row.get('all_day'),
        'status': row.get('status'),
        'stale': row.get('stale'),
        'url': row.get('url'),
        'source_id': row.get('source_id'),
        'source_name': row.get('source_name'),
        'source_kind': row.get('source_kind'),
        'schedule': {
            'kind': schedule.get('kind'),
            'start_date': schedule.get('start_date'),
            'end_date': schedule.get('end_date'),
            'sessions': schedule.get('sessions') or [],
            'recurrence': schedule.get('recurrence'),
            'exceptions': schedule.get('exceptions') or [],
            'note': schedule.get('note'),
            'operating_hours': schedule.get('operating_hours'),
            'kind_inferred': schedule.get('kind_inferred'),
        },
        'commitment': row.get('commitment'),
        'registration': row.get('registration'),
        'ages': row.get('ages'),
        'hints': row.get('hints'),
        'geo_meta': row.get('geo_meta'),
        'place_id': row.get('place_id'),
        'first_seen': row.get('first_seen'),
        'checked_at': row.get('checked_at'),
        'ticket_status': row.get('ticket_status'),
        'price': row.get('price'),
        'currency': row.get('currency'),
        'description': (row.get('description') or '')[:140],
        'evidence_format': (row.get('evidence') or {}).get('format'),
        'conflict_count': len(row.get('conflicts') or []),
    }
    if geo:
        item['geo'] = {
            'lat': geo.get('lat'),
            'lng': geo.get('lng'),
            'precision': geo.get('precision'),
            'source_url': geo.get('source_url'),
        }
    evidence = row.get('evidence') or {}
    if evidence.get('url'):
        item['evidence'] = {'url': evidence['url'], 'format': evidence.get('format')}
    return item


def compact_sources(sources: list[dict]) -> list[dict]:
    rows = []
    for source in sources:
        rows.append({
            'id': source.get('id'),
            'name': source.get('name'),
            'region': source.get('region'),
            'url': source.get('url'),
            'events': source.get('events', 0),
            'status': source.get('status'),
            'visited_count': source.get('visited_count', 0),
            'horizon_note': source.get('horizon_note'),
            'truncated': bool(source.get('truncated')),
            'unparsed_count': source.get('unparsed_count', 0),
            'errors': (source.get('errors') or [])[:1],
        })
    return rows


def slim_matrix(matrix: dict | None) -> dict | None:
    if not matrix:
        return None
    return {
        'summary_metrics': matrix.get('summary_metrics') or {},
        'category_by_region': [
            {
                'region': cell.get('region'),
                'category': cell.get('category'),
                'status': cell.get('status'),
                'depth_tier': cell.get('depth_tier'),
                'distinct_offerings': cell.get('distinct_offerings', 0),
            }
            for cell in matrix.get('category_by_region') or []
        ],
        'note': matrix.get('note'),
    }


def _prune(value):
    if isinstance(value, dict):
        return {key: _prune(item) for key, item in value.items() if item not in (None, '', [], {})}
    if isinstance(value, list):
        return [_prune(item) for item in value]
    return value


def compact_offering(row: dict) -> dict:
    schedule = row.get('schedule') or {}
    hints = row.get('hints') or {}
    geo = row.get('geo') or None
    ages = row.get('ages') or {}
    meta = row.get('geo_meta') or {}
    kept_hints = {}
    for key in ('audience', 'free_likely', 'indoor_outdoor', 'standout_score'):
        if hints.get(key) not in (None, False, [], ''):
            kept_hints[key] = hints[key]
    return _prune({
        'offering_id': row.get('offering_id') or row.get('id'),
        'title': row.get('title'),
        'venue': row.get('venue'),
        'city': row.get('city'),
        'region': row.get('region'),
        'categories': row.get('categories') or [],
        'type': row.get('type'),
        'url': row.get('url'),
        'source_id': row.get('source_id'),
        'source_kind': row.get('source_kind'),
        'place_id': row.get('place_id'),
        'schedule': {
            'kind': schedule.get('kind'),
            'start_date': schedule.get('start_date'),
            'end_date': schedule.get('end_date'),
        },
        'ages': {
            'min': ages.get('min'),
            'max': ages.get('max'),
            'all_ages': True if ages.get('all_ages') else None,
        },
        'hints': kept_hints,
        'geo_meta': {
            'corridor': meta.get('corridor'),
            'drive_band': meta.get('drive_band'),
            'amtrak_accessible': True if meta.get('amtrak_accessible') else None,
        },
        'geo': None if not geo else {
            'lat': round(float(geo['lat']), 5),
            'lng': round(float(geo['lng']), 5),
            'precision': geo.get('precision'),
        },
        'price': row.get('price'),
        'currency': row.get('currency'),
        'ticket_status': None if row.get('ticket_status') in (None, 'unknown') else row.get('ticket_status'),
    })


def occurrence_row(index: int, row: dict) -> list:
    end_date = row.get('end_date')
    if end_date == row.get('date'):
        end_date = None
    status = row.get('status')
    if status == 'scheduled':
        status = None
    return _prune([
        index,
        row.get('date'),
        end_date,
        row.get('start'),
        status,
        1 if row.get('stale') else 0,
    ])


def build_bundle(data: dict) -> dict:
    offerings = []
    index = {}
    occurrences = []
    for row in data.get('activities') or []:
        offering_id = row.get('offering_id') or row.get('id')
        if offering_id not in index:
            index[offering_id] = len(offerings)
            offerings.append(compact_offering(row))
        occurrences.append(occurrence_row(index[offering_id], row))
    return {
        'version': data.get('version', 1),
        'updated_at': data.get('updated_at'),
        'horizon_start': data.get('horizon_start'),
        'horizon_end': data.get('horizon_end'),
        'timezone': data.get('timezone'),
        'taxonomy': data.get('taxonomy'),
        'places': data.get('places') or [],
        'sources': compact_sources(data.get('sources') or []),
        'coverage_matrix': {
            'summary_metrics': (data.get('coverage_matrix') or {}).get('summary_metrics') or {},
            'note': (data.get('coverage_matrix') or {}).get('note'),
        },
        'offerings': offerings,
        'occurrences': occurrences,
    }


def _items(activities: list[dict], limit: int = 40) -> list[dict]:
    dated = [row for row in activities if row.get('date') and row.get('url') and not is_promo_listing(row)]
    dated.sort(key=lambda row: (row.get('date') or '9999', row.get('title') or ''))
    return dated[:limit]


def render_feed(title: str, activities: list[dict]) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        '<channel>',
        f'<title>{escape(title)}</title>',
        f'<link>{escape(CHANNEL)}</link>',
        '<description>Explicit-date listings already collected from organizer and official calendars. Confirm details with the source.</description>',
    ]
    for row in _items(activities):
        when = row.get('start') or row.get('date')
        description = f"{when} · {row.get('venue') or ''} · {row.get('city') or ''}".strip(' ·')
        parts.extend([
            '<item>',
            f'<title>{escape(row.get("title") or "Untitled listing")}</title>',
            f'<link>{escape(row["url"])}</link>',
            f'<guid isPermaLink="false">{escape(str(row.get("id")))}</guid>',
            f'<description>{escape(description)}</description>',
            '</item>',
        ])
    parts.extend(['</channel>', '</rss>', ''])
    return '\n'.join(line for line in parts if line != '')


def write_outputs(data: dict, root: Path = ROOT) -> dict:
    web = root / 'web'
    feeds = web / 'feeds'
    feeds.mkdir(parents=True, exist_ok=True)
    activities_path = web / 'activities.json'
    activities_path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')
    bundle = build_bundle(data)
    encoded = json.dumps(bundle, ensure_ascii=False, separators=(',', ':'))
    if len(encoded.encode('utf-8')) >= BUNDLE_LIMIT:
        for row in bundle['offerings']:
            row.pop('description', None)
            row.pop('commitment', None)
            row.pop('registration', None)
        encoded = json.dumps(bundle, ensure_ascii=False, separators=(',', ':'))
    size = len(encoded.encode('utf-8'))
    if size >= BUNDLE_LIMIT:
        raise RuntimeError(f'bundle.min.json is {size} bytes')
    (web / 'bundle.min.json').write_text(encoded + '\n')
    activities = data.get('activities') or []
    written = []
    catalog = [('all', 'What to do, KC — explicit dates', activities)]
    regions = (data.get('taxonomy') or {}).get('regions') or sorted({row.get('region') for row in activities if row.get('region')})
    for region in regions:
        catalog.append((_slug(region), f'What to do, KC — {region}', [row for row in activities if row.get('region') == region]))
    standouts = [
        row for row in activities
        if (row.get('hints') or {}).get('standout_score', 0) >= 70 and not is_promo_listing(row)
    ]
    catalog.append(('standouts', 'What to do, KC — standout hints', standouts))
    for slug, title, rows in catalog:
        path = feeds / f'{slug}.xml'
        path.write_text(render_feed(title, rows))
        written.append(str(path.relative_to(root)))
    return {
        'activities_bytes': activities_path.stat().st_size,
        'bundle_bytes': size,
        'feeds': written,
        'activities': len(activities),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--activities', type=Path, default=ROOT / 'web/activities.json')
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    data = json.loads(args.activities.read_text())
    stats = write_outputs(data, args.root)
    print(
        f"activities {stats['activities']} · file {stats['activities_bytes']} bytes · "
        f"bundle {stats['bundle_bytes']} bytes · feeds {len(stats['feeds'])}"
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
