"""Reviewed place identities, geospatial provenance and persistent offerings."""
import copy
import json
import math
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def places():
    return json.loads((ROOT / 'data/places.json').read_text())['places']


def valid_coordinates(lat, lng):
    return (type(lat) in (int,float) and type(lng) in (int,float)
            and math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180)


def normalized(value):
    return re.sub(r'\W+', '', value.casefold())


def attach_place(row, raw=None):
    raw = raw or {}
    row['place_id'] = None
    row['geo'] = None
    for p in places():
        if row['source_id'] not in p['match']['source_ids']: continue
        names = {normalized(n) for n in p['match']['venue_aliases']}
        if normalized(row['venue']) not in names: continue
        row['place_id'] = p['id']
        row['geo'] = copy.deepcopy(p['geo'])
        break
    location = raw.get('location') or {}
    if isinstance(location, list): location = next((x for x in location if isinstance(x, dict)), {})
    if isinstance(location, dict):
        geo = location.get('geo') or {}
        if not isinstance(geo, dict) or any(isinstance(geo.get(k),bool) for k in ('latitude','longitude')): return row
        try: lat,lng = float(geo.get('latitude')),float(geo.get('longitude'))
        except (TypeError,ValueError,AttributeError): return row
        if valid_coordinates(lat,lng):
            row['geo'] = {'lat':lat,'lng':lng,'precision':'source_point',
                          'source_url':row['evidence']['url'],'checked_at':row['checked_at'],
                          'note':'Coordinate published for this event location; confirm the entrance with the organizer.'}
    return row


def public_places():
    return [{k:copy.deepcopy(v) for k,v in p.items() if k!='match'} for p in places()]
