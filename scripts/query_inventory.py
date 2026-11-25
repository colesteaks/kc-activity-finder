#!/usr/bin/env python3
"""Index-first lookup against the collected snapshot.

This does not perform the eight-stage research ledger. It answers what the
current inventory already contains. Recommendations still require source
review, fit ranking, and adversarial checks.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_inventory(root: Path = ROOT) -> dict:
    bundle = root / 'web' / 'bundle.min.json'
    activities = root / 'web' / 'activities.json'
    path = bundle if bundle.exists() else activities
    return json.loads(path.read_text())


def matches(row: dict, args) -> bool:
    if args.region and row.get('region') != args.region:
        return False
    if args.city and (row.get('city') or '').casefold() != args.city.casefold():
        return False
    if args.q:
        blob = ' '.join(str(row.get(key) or '') for key in ('title', 'venue', 'city', 'description', 'type')).casefold()
        if args.q.casefold() not in blob:
            return False
    if args.audience:
        audience = ((row.get('hints') or {}).get('audience') or [])
        if args.audience not in audience:
            return False
    if args.free:
        if (row.get('hints') or {}).get('free_likely') is not True:
            return False
    if args.drive_band and (row.get('geo_meta') or {}).get('drive_band') != args.drive_band:
        return False
    if args.min_standout:
        if (row.get('hints') or {}).get('standout_score', 0) < args.min_standout:
            return False
    if args.date_from:
        high = row.get('end_date') or row.get('date')
        if high and high < args.date_from:
            return False
    if args.date_to and row.get('date') and row['date'] > args.date_to:
        return False
    return True


def project(row: dict) -> dict:
    hints = row.get('hints') or {}
    return {
        'id': row.get('offering_id') or row.get('id'),
        'title': row.get('title'),
        'date': row.get('date'),
        'city': row.get('city'),
        'region': row.get('region'),
        'venue': row.get('venue'),
        'url': row.get('url'),
        'audience': hints.get('audience'),
        'standout_score': hints.get('standout_score'),
        'drive_band': (row.get('geo_meta') or {}).get('drive_band'),
    }


def query(data: dict, args) -> list[dict]:
    rows = [project(row) for row in data.get('activities') or [] if matches(row, args)]
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
    parser.add_argument('--q')
    parser.add_argument('--audience', choices=['kids', 'family', 'teens', 'adults', 'all_ages'])
    parser.add_argument('--free', action='store_true')
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
