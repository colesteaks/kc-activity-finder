#!/usr/bin/env python3
"""Index-first lookup against the collected snapshot (supports flat or relational bundles).

This does not perform the eight-stage research ledger. It answers what the
current inventory already contains. Recommendations still require source
review, fit ranking, and adversarial checks.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_TIME_OFF_RE = re.compile(r'^(\d{2}:\d{2})([+-]\d{2})$')


def _decode_start(date_val: str | None, time_part: str) -> str | None:
    if not time_part:
        return None
    m = _TIME_OFF_RE.match(time_part)
    if m and date_val:
        return f'{date_val}T{m[1]}:00{m[2]}:00'
    return time_part


def _decode_ages(age_tuple) -> dict:
    if not age_tuple:
        return {'min': None, 'max': None, 'all_ages': False}
    if age_tuple[0]:
        return {'min': 0, 'max': None, 'all_ages': True}
    return {
        'min': age_tuple[1] if len(age_tuple) > 1 else None,
        'max': age_tuple[2] if len(age_tuple) > 2 else None,
        'all_ages': False,
    }


def _at(tbl: list[str], idx):
    return tbl[idx] if isinstance(idx, int) and 0 <= idx < len(tbl) else None


def hydrate_bundle(data: dict) -> dict:
    """Hydrate v2 columnar or v1 relational bundle into flat activity rows."""
    if 'activities' in data or not isinstance(data.get('occurrences'), list):
        return data

    source_names = {s['id']: s.get('name') for s in (data.get('sources') or []) if isinstance(s, dict) and s.get('id')}
    raw_offers = data.get('offerings') or []
    tables = data.get('tables')

    if data.get('version') == 2 and isinstance(tables, dict):
        decoded_offers = []
        for row in raw_offers:
            def get(i, default=None):
                return row[i] if i < len(row) and row[i] is not None else default

            sk_code = get(7, 0)
            sk = 'organizer' if sk_code == 1 else ('official-calendar' if sk_code == 2 else 'sensor')
            free_code = get(13)
            free_likely = True if free_code == 1 else (False if free_code == 0 else None)
            ranged = get(23)
            kind = _at(tables.get('kinds', []), get(10)) or 'one_off'
            geo_pt = get(19)
            src_id = _at(tables.get('sources', []), get(6))
            decoded_offers.append({
                'offering_id': get(0),
                'title': get(1),
                'url': get(2),
                'venue': _at(tables.get('venues', []), get(3)) or '',
                'city': _at(tables.get('cities', []), get(4)) or '',
                'region': _at(tables.get('regions', []), get(5)) or '',
                'source_id': src_id,
                'source_name': source_names.get(src_id, src_id),
                'source_kind': sk,
                'categories': [_at(tables.get('categories', []), i) for i in get(8, []) if _at(tables.get('categories', []), i)],
                'type': _at(tables.get('types', []), get(9)),
                'schedule': {
                    'kind': kind,
                    'start_date': ranged[0] if isinstance(ranged, list) and len(ranged) > 0 else None,
                    'end_date': ranged[1] if isinstance(ranged, list) and len(ranged) > 1 else None,
                },
                'hints': {
                    'standout_score': get(11, 0),
                    'audience': [_at(tables.get('audiences', []), i) for i in get(12, []) if _at(tables.get('audiences', []), i)],
                    'free_likely': free_likely,
                    'indoor_outdoor': _at(tables.get('io', []), get(14)),
                },
                'geo_meta': {
                    'drive_band': _at(tables.get('bands', []), get(15)),
                    'corridor': _at(tables.get('corridors', []), get(16)),
                    'amtrak_accessible': bool(get(17, 0)),
                },
                'first_seen': get(18, ''),
                'geo': {'lat': geo_pt[0], 'lng': geo_pt[1]} if isinstance(geo_pt, list) and len(geo_pt) >= 2 else None,
                'ages': _decode_ages(get(20)),
                'place_id': get(21),
                'price': get(22),
            })
        offerings = decoded_offers
    else:
        offerings = raw_offers

    activities = []
    for occ in data['occurrences']:
        offer_idx = occ[0]
        offer = offerings[offer_idx] if isinstance(offer_idx, int) and offer_idx < len(offerings) else {}
        date_val = occ[1] if len(occ) > 1 and occ[1] else None
        end_date = occ[2] if len(occ) > 2 and occ[2] else date_val
        time_part = occ[3] if len(occ) > 3 and occ[3] else ''
        if data.get('version') == 2:
            start_val = _decode_start(date_val, time_part)
        else:
            start_val = time_part or None
        status = occ[4] if len(occ) > 4 and occ[4] else 'scheduled'
        stale = bool(occ[5]) if len(occ) > 5 else False
        row = dict(offer)
        sched = dict(offer.get('schedule') or {})
        kind = sched.get('kind') or 'one_off'
        sched.setdefault('start_date', date_val if kind == 'one_off' else (sched.get('start_date') or date_val))
        sched.setdefault('end_date', end_date if kind == 'one_off' else (sched.get('end_date') or end_date))
        row.update({
            'id': f"{offer.get('offering_id') or offer_idx}:{date_val or 'undated'}",
            'date': date_val,
            'end_date': end_date,
            'start': start_val,
            'all_day': not bool(start_val),
            'status': status,
            'stale': stale,
            'schedule': sched,
            'source_name': offer.get('source_name') or source_names.get(offer.get('source_id'), offer.get('source_id')),
        })
        activities.append(row)

    hydrated = dict(data)
    hydrated['activities'] = activities
    return hydrated


def load_inventory(root: Path = ROOT) -> dict:
    bundle = root / 'web' / 'bundle.min.json'
    activities = root / 'web' / 'activities.json'
    path = bundle if bundle.exists() else activities
    return hydrate_bundle(json.loads(path.read_text()))


def matches(row: dict, args) -> bool:
    if not getattr(args, 'include_stale', False) and row.get('stale'):
        return False
    if getattr(args, 'region', None) and row.get('region') != args.region:
        return False
    if getattr(args, 'city', None) and (row.get('city') or '').casefold() != args.city.casefold():
        return False
    if getattr(args, 'corridor', None) and (row.get('geo_meta') or {}).get('corridor') != args.corridor:
        return False
    if getattr(args, 'amtrak', False) and not (row.get('geo_meta') or {}).get('amtrak_accessible'):
        return False
    if getattr(args, 'q', None):
        blob = ' '.join(str(row.get(key) or '') for key in ('title', 'venue', 'city', 'description', 'type')).casefold()
        if args.q.casefold() not in blob:
            return False
    if getattr(args, 'audience', None):
        audience = ((row.get('hints') or {}).get('audience') or [])
        if args.audience not in audience:
            return False
    if getattr(args, 'free', False):
        if (row.get('hints') or {}).get('free_likely') is not True:
            return False
    if getattr(args, 'drive_band', None) and (row.get('geo_meta') or {}).get('drive_band') != args.drive_band:
        return False
    if getattr(args, 'min_standout', 0):
        if (row.get('hints') or {}).get('standout_score', 0) < args.min_standout:
            return False
    if getattr(args, 'date_from', None):
        high = row.get('end_date') or row.get('date')
        if high and high < args.date_from:
            return False
    if getattr(args, 'date_to', None) and row.get('date') and row['date'] > args.date_to:
        return False
    return True


def project(row: dict) -> dict:
    hints = row.get('hints') or {}
    geo_meta = row.get('geo_meta') or {}
    return {
        'id': row.get('offering_id') or row.get('id'),
        'title': row.get('title'),
        'date': row.get('date'),
        'start': row.get('start'),
        'city': row.get('city'),
        'region': row.get('region'),
        'corridor': geo_meta.get('corridor'),
        'amtrak_accessible': bool(geo_meta.get('amtrak_accessible')),
        'venue': row.get('venue'),
        'url': row.get('url'),
        'audience': hints.get('audience'),
        'standout_score': hints.get('standout_score'),
        'drive_band': geo_meta.get('drive_band'),
    }


def query(data: dict, args) -> list[dict]:
    hydrated = hydrate_bundle(data)
    rows = [project(row) for row in hydrated.get('activities') or [] if matches(row, args)]
    rows.sort(key=lambda row: (-(row.get('standout_score') or 0), row.get('date') or '9999', row.get('title') or ''))
    seen = set()
    distinct = []
    for row in rows:
        if row['id'] in seen:
            continue
        seen.add(row['id'])
        distinct.append(row)
        if len(distinct) >= args.limit:
            break
    return distinct


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--region')
    parser.add_argument('--city')
    parser.add_argument('--corridor')
    parser.add_argument('--q')
    parser.add_argument('--audience', choices=['kids', 'family', 'teens', 'adults', 'all_ages'])
    parser.add_argument('--free', action='store_true')
    parser.add_argument('--amtrak', action='store_true')
    parser.add_argument('--include-stale', action='store_true')
    parser.add_argument('--drive-band', choices=['0-30m', '30-60m', '1-2h', '2-3.5h'])
    parser.add_argument('--min-standout', type=int, default=0)
    parser.add_argument('--date-from')
    parser.add_argument('--date-to')
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    rows = query(load_inventory(args.root), args)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            print(f"{row['date'] or 'undated':10}  {row['standout_score'] or '-':>3}  {row['title']}  [{row['city']}]  {row['url']}")
        if not rows:
            print('No inventory rows matched. This is the collected snapshot, not a live search.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
