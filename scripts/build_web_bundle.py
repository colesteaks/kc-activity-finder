#!/usr/bin/env python3
"""Write a compact relational v2 bundle, static RSS feeds, and a minified activities file.

The bundle is a browse index. It keeps source URLs and explicit dates and drops
evidence quotes. It does not invent events.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

from enrichment import is_promo_listing

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_LIMIT = 1_000_000
CHANNEL = 'https://github.com/colesteaks/kc-activity-finder'
_START_RE = re.compile(r'^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})(?::\d{2})?([+-]\d{2}):?\d{2}$')


def _slug(region: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', region.lower()).strip('-')


def _prune(value):
    if isinstance(value, dict):
        return {key: _prune(item) for key, item in value.items() if item not in (None, '', [], {})}
    if isinstance(value, list):
        return [_prune(item) for item in value]
    return value


def compact_sources(sources: list[dict]) -> list[dict]:
    rows = []
    for source in sources:
        rows.append(_prune({
            'id': source.get('id'),
            'name': source.get('name'),
            'region': source.get('region'),
            'url': source.get('url'),
            'events': source.get('events', 0),
            'status': source.get('status'),
            'visited_count': source.get('visited_count', 0),
            'horizon_note': source.get('horizon_note'),
            'truncated': True if source.get('truncated') else None,
            'unparsed_count': source.get('unparsed_count') or None,
            'errors': (source.get('errors') or [])[:1] or None,
        }))
    return rows


def _intern(table: list[str], value: str | None):
    if value is None or value == '':
        return None
    try:
        return table.index(value)
    except ValueError:
        table.append(value)
        return len(table) - 1


def _encode_start(date_val: str | None, start_val: str | None, all_day: bool | None) -> str:
    if all_day or not start_val:
        return ''
    m = _START_RE.match(str(start_val))
    if m and date_val and m[1] == date_val:
        return f'{m[2]}{m[3]}'
    return str(start_val)


def _age_tuple(ages: dict | None):
    ag = ages or {}
    if ag.get('all_ages'):
        return [1]
    if ag.get('min') is not None or ag.get('max') is not None:
        return [0, ag.get('min'), ag.get('max')]
    return None


def build_bundle(data: dict) -> dict:
    """Build v2 string-interned relational browse bundle (< 1 MB uncompressed)."""
    tables: dict[str, list[str]] = {
        'venues': [],
        'cities': [],
        'regions': [],
        'sources': [],
        'categories': [],
        'types': [],
        'kinds': [],
        'bands': [],
        'corridors': [],
        'audiences': [],
        'io': [],
    }
    offerings = []
    index: dict[str, int] = {}
    occurrences = []

    for row in data.get('activities') or []:
        oid = row.get('offering_id') or row.get('id')
        if oid not in index:
            index[oid] = len(offerings)
            sched = row.get('schedule') or {}
            hints = row.get('hints') or {}
            geo_meta = row.get('geo_meta') or {}
            geo = row.get('geo') or None
            kind = sched.get('kind') or 'one_off'
            sk = row.get('source_kind')
            sk_code = 1 if sk == 'organizer' else (2 if sk == 'official-calendar' else 0)
            free_raw = hints.get('free_likely')
            free_code = 1 if free_raw is True else (0 if free_raw is False else None)
            ranged = (
                [sched.get('start_date'), sched.get('end_date')]
                if kind != 'one_off' and (sched.get('start_date') or sched.get('end_date'))
                else None
            )
            conflicts = len(row.get('conflicts') or []) or None
            item = [
                oid,
                row.get('title'),
                row.get('url'),
                _intern(tables['venues'], row.get('venue')),
                _intern(tables['cities'], row.get('city')),
                _intern(tables['regions'], row.get('region')),
                _intern(tables['sources'], row.get('source_id')),
                sk_code,
                [_intern(tables['categories'], c) for c in (row.get('categories') or [])],
                _intern(tables['types'], row.get('type')),
                _intern(tables['kinds'], kind),
                int(hints.get('standout_score') or 0),
                [_intern(tables['audiences'], a) for a in (hints.get('audience') or [])],
                free_code,
                _intern(tables['io'], hints.get('indoor_outdoor')),
                _intern(tables['bands'], geo_meta.get('drive_band')),
                _intern(tables['corridors'], geo_meta.get('corridor')),
                1 if geo_meta.get('amtrak_accessible') else 0,
                (row.get('first_seen') or '')[:10] or None,
                [round(float(geo['lat']), 4), round(float(geo['lng']), 4)] if geo else None,
                _age_tuple(row.get('ages')),
                row.get('place_id') or None,
                row.get('price'),
                ranged,
                conflicts,
            ]
            while item and item[-1] is None:
                item.pop()
            offerings.append(item)

        date_val = row.get('date') or ''
        end_date = row.get('end_date') or ''
        end_diff = '' if (not end_date or end_date == date_val) else end_date
        time_part = _encode_start(date_val, row.get('start'), row.get('all_day'))
        status = row.get('status') or 'scheduled'
        st_diff = '' if status == 'scheduled' else status
        occ = [
            index[oid],
            date_val,
            end_diff,
            time_part,
            st_diff,
            1 if row.get('stale') else 0,
        ]
        while occ and occ[-1] in ('', 0, None):
            occ.pop()
        occurrences.append(occ)

    matrix = data.get('coverage_matrix') or {}
    region_gaps: dict[str, list[str]] = {}
    for cell in matrix.get('category_by_region') or []:
        if cell.get('status') == 'gap':
            region_gaps.setdefault(cell['region'], []).append(cell['category'])

    return {
        'version': 2,
        'updated_at': data.get('updated_at'),
        'horizon_start': data.get('horizon_start'),
        'horizon_end': data.get('horizon_end'),
        'timezone': data.get('timezone'),
        'taxonomy': data.get('taxonomy'),
        'places': data.get('places') or [],
        'sources': compact_sources(data.get('sources') or []),
        'coverage_matrix': {
            'summary_metrics': matrix.get('summary_metrics') or {},
            'region_gaps': region_gaps,
            'note': matrix.get('note'),
        },
        'tables': tables,
        'offerings': offerings,
        'occurrences': occurrences,
    }


def _items(activities: list[dict], limit: int = 40) -> list[dict]:
    dated = [
        row for row in activities
        if row.get('date') and row.get('url')
        and not row.get('stale') and not row.get('disappeared')
        and not is_promo_listing(row)
    ]
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
    size = len(encoded.encode('utf-8'))
    if size >= BUNDLE_LIMIT:
        raise RuntimeError(f'bundle.min.json is {size} bytes (>= {BUNDLE_LIMIT})')
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
    expected_names = {f'{slug}.xml' for slug, _, _ in catalog}
    for old_xml in feeds.glob('*.xml'):
        if old_xml.name not in expected_names:
            old_xml.unlink()
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
