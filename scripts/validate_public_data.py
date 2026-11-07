#!/usr/bin/env python3
"""Validate the public activity file before publishing."""
import json
from pathlib import Path
from dateutil.parser import isoparse
from dateutil.relativedelta import relativedelta
from collect_activities import ROOT, safe_url


def validate_public(data):
    assert data['version'] == 1 and data['timezone'] == 'America/Chicago'
    assert isoparse(data['updated_at']).utcoffset() is not None
    assert isoparse(data['horizon_end']).date() >= isoparse(data['horizon_start']).date() + relativedelta(months=6)
    ids = [r['id'] for r in data['activities']]
    assert len(ids) == len(set(ids)), 'Duplicate activity IDs'
    for a in data['activities']:
        assert a['title'] and safe_url(a['url']) and safe_url(a['evidence']['url'])
        assert isoparse(a['start']).utcoffset() is not None
        assert isoparse(a['checked_at']).utcoffset() is not None
        assert a['end'] is None or isoparse(a['end']) >= isoparse(a['start'])
        assert a['date'] <= a['end_date']
        assert a['ages']['min'] is None or a['ages']['min'] >= 0
        assert a['ages']['max'] is None or a['ages']['min'] is None or a['ages']['max'] >= a['ages']['min']
        assert a['source_kind'] in ('organizer', 'official-calendar', 'sensor')
        assert isinstance(a['stale'], bool) and isinstance(a['conflicts'], list)
    assert data['sources'], 'Coverage ledger is required'
    return len(ids)


if __name__ == '__main__':
    count = validate_public(json.loads((ROOT / 'web/activities.json').read_text()))
    print(f'Public data valid: {count} activities')
