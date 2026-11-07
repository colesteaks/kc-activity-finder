"""Orthogonal subject, offering, schedule and registration semantics.

Dates in source markup remain source facts. Classification may be inferred and
is labeled as such. Never expand a date range into invented daily sessions.
"""
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit
from place_model import attach_place

KINDS = ('one_off', 'multi_day', 'exhibit', 'sports_season', 'course', 'camp',
         'recurring_program', 'evergreen', 'program_catalog', 'date_range_unknown')


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
    if isinstance(types, str): types = [types]
    explicit = supplied.get('kind')
    if explicit and explicit not in KINDS: raise ValueError('Unknown activity kind')
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
    return {'kind': kind, 'kind_inferred': inferred, 'start_date': start_date,
            'end_date': end_date, 'timezone': 'America/Chicago',
            'recurrence': supplied.get('recurrence'), 'sessions': supplied.get('sessions', []),
            'operating_hours': supplied.get('operating_hours'),
            'exceptions': supplied.get('exceptions', []),
            'note': supplied.get('note') or ('Date range does not establish individual sessions or opening hours.'
                if kind in ('date_range_unknown', 'exhibit') else 'Confirm current hours, conditions and registration with the source.')}


def enrich(row, raw=None, source=None):
    raw = raw or {'name': row['title']}
    source = source or {}
    row['offering_id'] = offering_id(row['url'])
    row['parent_id'] = raw.get('_parent_id')
    fallback = {'Sports & movement':'sports_participation', 'Classes & workshops':'classes_skills',
        'Music & performance':'music_performance', 'Food & markets':'food_drink', 'Festivals & seasonal':'festivals_seasonal',
        'Arts & museums':'arts_exhibits', 'Nature & animals':'nature_animals', 'Talks & community':'community_social'}
    text = (row['title'] + ' ' + row.get('description', '')).lower()
    subjects = [id for id, pattern in (
        ('outdoor_recreation', r'\bhik(?:e|ing)\b|\btrail\b|\bpaddl|\bcamping\b|\bfishing\b|\bcycling\b'),
        ('sports_participation', r'\bleague\b|\btournament\b|\bsoccer program\b'),
        ('sports_spectating', r'\bvs\.?\b|\bhome game\b'),
        ('arts_exhibits', r'\bexhibit|\bgallery\b'), ('camps', r'\bcamp\b'),
        ('libraries_learning', r'\bstorytime\b|\blibrary\b'),
        ('volunteering', r'\bvolunteer\b'), ('games_hobbies', r'\bboard game|\bchess\b'),
        ('fitness_wellness', r'\byoga\b|\bworkout\b|\bfitness\b'),
        ('markets_shopping', r'\bmarket\b'), ('science_technology', r'\brobot|\bplanetarium|\bscience\b')) if re.search(pattern, text)]
    row['categories'] = raw.get('_categories') or (source.get('categories') if source.get('offering') else None) or subjects or [fallback.get(row['type'], 'community_social')]
    row['category_inferred'] = not bool(raw.get('_categories'))
    row['schedule'] = schedule_model(raw, row.get('start'), row.get('end'))
    if source.get('offering'):
        row['schedule'] = schedule_model({'_schedule': source['offering']['schedule']}, row.get('start'), row.get('end'))
    row['registration'] = raw.get('_registration') or {
        'status': 'unknown', 'opens_at': None, 'deadline': row.get('deadline'),
        'url': None, 'note': 'Event being listed does not confirm registration or ticket availability.'}
    row['commitment'] = raw.get('_commitment') or {'attendance': 'unknown', 'duration': None,
        'equipment': None, 'note': 'Check whether this is drop-in, a single session or a full-season commitment.'}
    return attach_place(row, raw)


def in_horizon(row, first, last):
    s = row['schedule']
    if s['kind'] in ('evergreen', 'program_catalog'): return True
    low, high = s['start_date'], s['end_date']
    if low and low > last: return False
    if high and high < first: return False
    # Missing dates are unresolved opportunities, never automatically "today".
    return True


def coverage_matrix(registry, taxonomy, health=None):
    health = {h['id']: h for h in health or []}
    cells = []
    for region in taxonomy['regions']:
        for category in taxonomy['categories']:
            routes = [s for s in registry if region in s.get('coverage_regions', [s['region']])
                      and category['id'] in s.get('categories', [])]
            collected = [s['id'] for s in routes if health.get(s['id'], {}).get('category_counts', {}).get(category['id'], 0) > 0]
            cells.append({'region': region, 'category': category['id'], 'routes': [s['id'] for s in routes],
                          'collecting_routes': collected, 'status': 'collecting' if collected else 'route_only' if routes else 'gap',
                          'next_search': f"{region} {category['search_terms']} official programs calendar registration"})
    forms = [{'kind': kind, 'routes': [s['id'] for s in registry if kind in s.get('activity_kinds', [])],
              'collecting_routes': [s['id'] for s in registry if health.get(s['id'], {}).get('kind_counts', {}).get(kind, 0) > 0]}
             for kind in KINDS if kind != 'date_range_unknown']
    return {'category_by_region': cells, 'activity_kinds': forms,
            'note': 'A route is a research lead, not proof that every program has been collected. Gaps are explicit; this matrix is not an exhaustiveness claim.'}
