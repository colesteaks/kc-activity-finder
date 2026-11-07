#!/usr/bin/env python3
"""Validate the public activity file before publishing."""
import json
from datetime import datetime
from pathlib import Path
from dateutil.parser import isoparse
from dateutil.relativedelta import relativedelta
from collect_activities import ROOT, safe_url
from jsonschema import Draft202012Validator, FormatChecker
from place_model import valid_coordinates


def validate_public(data):
    assert data['version'] == 1 and data['timezone'] == 'America/Chicago'
    assert isoparse(data['updated_at']).utcoffset() is not None
    assert isoparse(data['horizon_end']).date() >= isoparse(data['horizon_start']).date() + relativedelta(months=6)
    ids = [r['id'] for r in data['activities']]
    assert len(ids) == len(set(ids)), 'Duplicate activity IDs'
    validator = Draft202012Validator(json.loads((ROOT / 'schemas/activity.schema.json').read_text()), format_checker=FormatChecker())
    by_id = {a['id']: a for a in data['activities']}
    categories = {c['id'] for c in data['taxonomy']['categories']}
    place_validator = Draft202012Validator(json.loads((ROOT / 'schemas/place.schema.json').read_text()), format_checker=FormatChecker())
    places = {p['id']:p for p in data['places']}
    assert len(places)==len(data['places']), 'Duplicate place IDs'
    for p in places.values():
        place_validator.validate(p)
        if p['geo']:
            assert valid_coordinates(p['geo']['lat'],p['geo']['lng'])
            assert safe_url(p['geo']['source_url'])
        assert safe_url(p['source_url'])
        assert len({a['id'] for a in p['activities']}) == len(p['activities']), 'Duplicate amenity IDs'
        for hours in [p['hours']] + [a['hours'] for a in p['activities']]:
            if not hours: continue
            rules = hours['rules'] + [r for e in hours['exceptions'] for r in e.get('rules',[])]
            assert len({e['date'] for e in hours['exceptions']}) == len(hours['exceptions']), 'Duplicate closure dates'
            for rule in rules:
                assert set(rule['days']) <= set(range(7))
                for key in ('season_start','season_end'):
                    if key in rule: datetime.strptime('2000-'+rule[key],'%Y-%m-%d')
                assert rule['opens'] != rule['closes'], 'Use 00:00–24:00 for an explicitly published full day'
            assert safe_url(hours['source_url'])
        for amenity in p['activities']: assert safe_url(amenity['source_url'])
    for a in data['activities']:
        validator.validate(a)
        assert a['place_id'] is None or a['place_id'] in places
        if a['geo']:
            assert valid_coordinates(a['geo']['lat'],a['geo']['lng']) and safe_url(a['geo']['source_url'])
        assert set(a['categories']) <= categories, 'Unknown activity subject'
        assert a['title'] and safe_url(a['url']) and safe_url(a['evidence']['url'])
        assert a['start'] is None or isoparse(a['start']).utcoffset() is not None
        assert isoparse(a['checked_at']).utcoffset() is not None
        assert a['end'] is None or (a['start'] and isoparse(a['end']) >= isoparse(a['start']))
        assert a['date'] is None or a['end_date'] is None or a['date'] <= a['end_date']
        s = a['schedule']
        assert not (s['start_date'] and s['end_date']) or s['start_date'] <= s['end_date']
        for session in s['sessions']:
            assert isoparse(session['start']).utcoffset() is not None
            assert not session['end'] or isoparse(session['end']) >= isoparse(session['start'])
        if s['recurrence']:
            assert s['recurrence']['rrule'].startswith('FREQ='), 'Recurrence must be an explicit source rule'
        for field in ('opens_at', 'deadline'):
            if a['registration'][field]: isoparse(a['registration'][field])
        seen = {a['id']}; parent = a['parent_id']
        while parent:
            assert parent in by_id and parent not in seen, 'Orphan or cyclic parent activity'
            seen.add(parent); parent = by_id[parent]['parent_id']
        assert a['ages']['min'] is None or a['ages']['min'] >= 0
        assert a['ages']['max'] is None or a['ages']['min'] is None or a['ages']['max'] >= a['ages']['min']
        assert a['source_kind'] in ('organizer', 'official-calendar', 'sensor')
        assert isinstance(a['stale'], bool) and isinstance(a['conflicts'], list)
    assert data['sources'], 'Coverage ledger is required'
    return len(ids)


if __name__ == '__main__':
    count = validate_public(json.loads((ROOT / 'web/activities.json').read_text()))
    print(f'Public data valid: {count} activities')
