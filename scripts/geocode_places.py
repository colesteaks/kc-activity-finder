#!/usr/bin/env python3
"""Batch-geocode missing coordinates in data/places.json via the free US Census Geocoder."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from place_model import valid_coordinates

TZ = ZoneInfo('America/Chicago')
CENSUS_ENDPOINT = 'https://geocoding.geo.census.gov/geocoder/locations/onelineaddress'
AGENT = 'KCActivityFinder/1.0 (+https://github.com/colesteaks/kc-activity-finder)'


def geocode_address(address: str, fetch_fn=None, observed_at: str | None = None) -> dict | None:
    """Resolve one street address through the US Census Geocoder with provenance."""
    if not address or not address.strip():
        return None
    query_url = CENSUS_ENDPOINT + '?' + urlencode({
        'address': address.strip(),
        'benchmark': 'Public_AR_Current',
        'format': 'json',
    })
    if fetch_fn is None:
        req = urllib.request.Request(query_url, headers={'User-Agent': AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    else:
        payload = json.loads(fetch_fn(query_url))
    matches = ((payload.get('result') or {}).get('addressMatches') or [])
    if not matches:
        return None
    coords = matches[0].get('coordinates') or {}
    try:
        lat = float(coords['y'])
        lng = float(coords['x'])
    except (KeyError, TypeError, ValueError):
        return None
    if not valid_coordinates(lat, lng):
        return None
    return {
        'lat': lat,
        'lng': lng,
        'precision': 'address',
        'source_url': query_url,
        'checked_at': observed_at or datetime.now(TZ).isoformat(),
        'note': 'US Census street-address match; approximate venue location, not a verified entrance.',
    }


def geocode_places_file(path: Path, force: bool = False, dry_run: bool = False, fetch_fn=None) -> tuple[int, int]:
    """Populate missing coordinates in data/places.json; returns (attempted, updated)."""
    data = json.loads(path.read_text(encoding='utf-8'))
    attempted = 0
    updated = 0
    now = datetime.now(TZ).isoformat()
    for place in data.get('places', []):
        if place.get('geo') and not force:
            continue
        addr = place.get('address') or ''
        if not addr:
            continue
        attempted += 1
        try:
            geo = geocode_address(addr, fetch_fn=fetch_fn, observed_at=now)
        except Exception as exc:
            print(f"WARN {place['id']}: {exc}", file=sys.stderr)
            continue
        if geo:
            place['geo'] = geo
            updated += 1
            print(f"GEOCODED {place['id']}: {geo['lat']}, {geo['lng']}")
        else:
            print(f"NO MATCH {place['id']}: {addr}")
    if updated and not dry_run:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return attempted, updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--places', type=Path, default=ROOT / 'data/places.json')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    attempted, updated = geocode_places_file(args.places, force=args.force, dry_run=args.dry_run)
    print(f'Attempted {attempted}, updated {updated}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
