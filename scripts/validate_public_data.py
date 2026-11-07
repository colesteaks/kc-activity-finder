#!/usr/bin/env python3
"""Validate the public activity file before publishing."""
import json
from pathlib import Path
from dateutil.parser import isoparse
from dateutil.relativedelta import relativedelta
from collect_activities import ROOT, safe_url
from jsonschema import Draft202012Validator, FormatChecker


def validate_public(data):
    assert data['version'] == 1 and data['timezone'] == 'America/Chicago'
    assert isoparse(data['updated_at']).utcoffset() is not None
    assert isoparse(data['horizon_end']).date() >= isoparse(data['horizon_start']).date() + relativedelta(months=6)
    ids = [r['id'] for r in data['activities']]
    assert len(ids) == len(set(ids)), 'Duplicate activity IDs'
    validator = Draft202012Validator(json.loads((ROOT / 'schemas/activity.schema.json').read_text()), format_checker=FormatChecker())
    by_id = {a['id']: a for a in data['activities']}
    categories = {c['id'] for c in data['taxonomy']['categories']}
    for a in data['activities']:
        validator.validate(a)
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
