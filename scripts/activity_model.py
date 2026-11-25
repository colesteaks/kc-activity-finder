"""Orthogonal subject, offering, schedule, registration, hints and depth-coverage semantics.

Dates in source markup remain source facts. Classification and discovery hints
may be inferred and are explicitly labeled as estimates, separate from verified
organizer age/price policies. Never expand an unverified date range into fake sessions.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from urllib.parse import urlsplit, urlunsplit

from enrichment import build_hints
from geo_model import geo_metadata
from place_model import attach_place

KINDS = (
    'one_off', 'multi_day', 'exhibit', 'sports_season', 'course', 'camp',
    'recurring_program', 'evergreen', 'program_catalog', 'date_range_unknown',
)
_STATIC_FORMATS = {'discovery', 'offering', 'reviewed-capture'}


def offering_id(url):
    p = urlsplit(url)
    # Query parameters can distinguish programs. Preserve them, while omitting
    # fragments, so registration and program identities do not collapse.
    value = urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip('/'), p.query, ''))
    return hashlib.sha256(value.encode()).hexdigest()[:20]


def schedule_model(raw, start, end):
    supplied = raw.get('_schedule') or {}
    title = str(raw.get('name', '')).lower()
    types = raw.get('@type', [])
    if isinstance(types, str):
        types = [types]
    explicit = supplied.get('kind')
    if explicit and explicit not in KINDS:
        raise ValueError('Unknown activity kind')
    if explicit:
        kind, inferred = explicit, False
    elif 'ExhibitionEvent' in types or re.search(r'\bexhibit(?:ion)?\b', title) or raw.get('_is_exhibition'):
        kind, inferred = 'exhibit', True
    elif start and end and start[:10] != end[:10]:
        kind, inferred = 'date_range_unknown', True
    else:
        kind, inferred = 'one_off', True
    # For unknown end dates, a known start is not a proven single-day run.
    start_date = supplied.get('start_date', start[:10] if start else None)
    end_date = supplied.get('end_date', end[:10] if end else (start_date if kind == 'one_off' else None))
    return {
        'kind': kind,
        'kind_inferred': inferred,
        'start_date': start_date,
        'end_date': end_date,
        'timezone': 'America/Chicago',
        'recurrence': supplied.get('recurrence'),
        'sessions': supplied.get('sessions', []),
        'operating_hours': supplied.get('operating_hours'),
        'exceptions': supplied.get('exceptions', []),
        'note': supplied.get('note') or (
            'Date range does not establish individual sessions or opening hours.'
            if kind in ('date_range_unknown', 'exhibit')
            else 'Confirm current hours, conditions and registration with the source.'
        ),
    }


def enrich(row, raw=None, source=None):
    raw = raw or {'name': row['title']}
    source = source or {}
    row['offering_id'] = offering_id(row['url'])
    row['parent_id'] = raw.get('_parent_id')
    fallback = {
        'Sports & movement': 'sports_participation',
        'Classes & workshops': 'classes_skills',
        'Music & performance': 'music_performance',
        'Food & markets': 'food_drink',
        'Festivals & seasonal': 'festivals_seasonal',
        'Arts & museums': 'arts_exhibits',
        'Nature & animals': 'nature_animals',
        'Talks & community': 'community_social',
    }
    text = (row['title'] + ' ' + row.get('description', '')).lower()
    subjects = [
        cid for cid, pattern in (
            ('outdoor_recreation', r'\bhik(?:e|ing)\b|\btrail\b|\bpaddl|\bcamping\b|\bfishing\b|\bcycling\b'),
            ('sports_participation', r'\bleague\b|\btournament\b|\bsoccer program\b'),
            ('sports_spectating', r'\bvs\.?\b|\bhome game\b'),
            ('arts_exhibits', r'\bexhibit|\bgallery\b'),
            ('camps', r'\bcamp\b'),
            ('libraries_learning', r'\bstorytime\b|\blibrary\b'),
            ('volunteering', r'\bvolunteer\b'),
            ('games_hobbies', r'\bboard game|\bchess\b'),
            ('fitness_wellness', r'\byoga\b|\bworkout\b|\bfitness\b'),
            ('markets_shopping', r'\bmarket\b'),
            ('science_technology', r'\brobot|\bplanetarium|\bscience\b'),
        )
        if re.search(pattern, text)
    ]
    supplied_categories = raw.get('_categories') or (source.get('categories') if source.get('offering') else None)
    row['categories'] = (
        list(dict.fromkeys(supplied_categories + subjects))
        if supplied_categories
        else subjects or [fallback.get(row['type'], 'community_social')]
    )
    row['category_inferred'] = not bool(raw.get('_categories')) or any(
        c not in (supplied_categories or []) for c in subjects
    )
    row['schedule'] = schedule_model(raw, row.get('start'), row.get('end'))
    if source.get('offering'):
        row['schedule'] = schedule_model({'_schedule': source['offering']['schedule']}, row.get('start'), row.get('end'))
    row['registration'] = raw.get('_registration') or {
        'status': 'unknown',
        'opens_at': None,
        'deadline': row.get('deadline'),
        'url': None,
        'note': 'Event being listed does not confirm registration or ticket availability.',
    }
    row['commitment'] = raw.get('_commitment') or {
        'attendance': 'unknown',
        'duration': None,
        'equipment': None,
        'note': 'Check whether this is drop-in, a single session or a full-season commitment.',
    }
    attach_place(row, raw)
    row['geo_meta'] = geo_metadata(row)
    row['hints'] = build_hints(row, source)
    return row


def in_horizon(row, first, last):
    s = row['schedule']
    if s['kind'] in ('evergreen', 'program_catalog'):
        return True
    low, high = s['start_date'], s['end_date']
    if low and low > last:
        return False
    if high and high < first:
        return False
    # Missing dates are unresolved opportunities, never automatically "today".
    return True


def coverage_matrix(registry, taxonomy, health=None, activities=None):
    health_map = {h['id']: h for h in health or []}
    format_by_id = {s['id']: s.get('format') for s in registry}

    cell_offerings: dict[tuple[str, str], set[str]] = {}
    cell_live_offerings: dict[tuple[str, str], set[str]] = {}
    cell_first_party: dict[tuple[str, str], set[str]] = {}
    if activities:
        for row in activities:
            if row.get('stale') or row.get('disappeared'):
                continue
            reg = row.get('region')
            oid = row.get('offering_id') or row.get('id')
            fmt = format_by_id.get(row.get('source_id'), (row.get('evidence') or {}).get('format'))
            for cat in row.get('categories') or []:
                key = (reg, cat)
                cell_offerings.setdefault(key, set()).add(oid)
                if fmt not in _STATIC_FORMATS:
                    cell_live_offerings.setdefault(key, set()).add(oid)
                if row.get('source_kind') == 'organizer':
                    cell_first_party.setdefault(key, set()).add(oid)

    cells = []
    for region in taxonomy['regions']:
        for category in taxonomy['categories']:
            routes = [
                s for s in registry
                if region in s.get('coverage_regions', [s['region']]) and category['id'] in s.get('categories', [])
            ]
            collected = [
                s['id'] for s in routes
                if health_map.get(s['id'], {}).get('category_counts', {}).get(category['id'], 0) > 0
            ]
            status = 'collecting' if collected else 'route_only' if routes else 'gap'
            key = (region, category['id'])
            if activities is not None:
                distinct_cnt = len(cell_offerings.get(key, set()))
                live_cnt = len(cell_live_offerings.get(key, set()))
                fp_cnt = len(cell_first_party.get(key, set()))
            else:
                distinct_cnt = sum(
                    health_map.get(sid, {}).get('category_counts', {}).get(category['id'], 0)
                    for sid in collected
                )
                live_cnt = sum(
                    1 for sid in collected if format_by_id.get(sid) not in _STATIC_FORMATS
                )
                fp_cnt = sum(
                    1 for sid in collected if next((r.get('kind') for r in routes if r['id'] == sid), '') == 'organizer'
                )

            if status == 'gap':
                depth_tier = 'gap'
            elif status == 'route_only' or (activities is not None and distinct_cnt == 0):
                depth_tier = 'route_only' if routes else 'gap'
            elif distinct_cnt < 3 or live_cnt == 0:
                depth_tier = 'thin'
            elif distinct_cnt >= 15 and fp_cnt >= 5:
                depth_tier = 'strong'
            else:
                depth_tier = 'active'

            cells.append({
                'region': region,
                'category': category['id'],
                'routes': [s['id'] for s in routes],
                'collecting_routes': collected,
                'status': status,
                'depth_tier': depth_tier,
                'distinct_offerings': distinct_cnt,
                'live_calendar_offerings': live_cnt,
                'first_party_offerings': fp_cnt,
                'next_search': f"{region} {category['search_terms']} official programs calendar registration",
            })

    forms = [
        {
            'kind': kind,
            'routes': [s['id'] for s in registry if kind in s.get('activity_kinds', [])],
            'collecting_routes': [
                s['id'] for s in registry if health_map.get(s['id'], {}).get('kind_counts', {}).get(kind, 0) > 0
            ],
        }
        for kind in KINDS if kind != 'date_range_unknown'
    ]

    summary_metrics = {'depth_tier_counts': dict(Counter(c['depth_tier'] for c in cells))}
    if activities:
        total = len(activities)
        top3 = sum(cnt for _, cnt in Counter(a.get('source_id') for a in activities).most_common(3))
        summary_metrics.update({
            'total_records': total,
            'distinct_offerings': len({a.get('offering_id') or a.get('id') for a in activities}),
            'concentration_top3_share': round(top3 / total, 4),
            'pct_with_verified_age': round(
                sum(1 for a in activities if (a.get('ages') or {}).get('all_ages') or (a.get('ages') or {}).get('min') is not None) / total,
                4,
            ),
            'pct_with_audience_hint': round(
                sum(1 for a in activities if (a.get('hints') or {}).get('audience')) / total,
                4,
            ),
            'pct_with_geo': round(sum(1 for a in activities if a.get('geo')) / total, 4),
            'pct_stale': round(sum(1 for a in activities if a.get('stale')) / total, 4),
        })

    return {
        'category_by_region': cells,
        'activity_kinds': forms,
        'summary_metrics': summary_metrics,
        'note': 'A route is a research lead, not proof that every program has been collected. Depth tiers distinguish single-stub thin cells from active/strong live calendars.',
    }
