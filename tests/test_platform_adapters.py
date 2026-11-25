import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from collect_activities import TZ, collect_source, normalize, reconcile
from platform_adapters import (
    bibliocommons_events,
    civicplus_events,
    ics_events,
    libcal_events,
    localist_events,
    mdc_events,
    mlb_schedule_events,
    rss_events,
    simpleview_events,
    ticketmaster_events,
)

FIXTURES = ROOT / 'tests/fixtures/platforms'
NOW = datetime(2026, 11, 24, 10, tzinfo=TZ)
BASE_SRC = {
    'id': 'plat-test',
    'name': 'Platform Test',
    'region': 'Kansas City metro',
    'city': 'Kansas City',
    'kind': 'organizer',
    'format': 'ics',
    'url': 'https://example.test/events',
}


class PlatformAdapterTests(unittest.TestCase):
    def test_ics_rrule_exdate_and_canceled(self):
        body = (FIXTURES / 'sample.ics').read_text()
        rows = ics_events(body, BASE_SRC, BASE_SRC['url'], date(2026, 12, 1), date(2027, 1, 15))
        # 4 weekly occurrences minus 1 EXDATE (Dec 12) + 1 canceled lecture = 4 rows
        self.assertEqual(len(rows), 4)
        walks = [r for r in rows if 'Trail Walk' in r['name']]
        self.assertEqual([w['startDate'][:10] for w in walks], ['2026-12-05', '2026-12-19', '2026-12-26'])
        self.assertEqual(walks[0]['_schedule']['recurrence']['rrule'], 'FREQ=WEEKLY;COUNT=4')
        self.assertEqual(walks[0]['location']['geo']['latitude'], 39.0268)
        canceled = next(r for r in rows if 'Canceled' in r['name'])
        norm_c = normalize(canceled, BASE_SRC, NOW.isoformat(), BASE_SRC['url'])
        self.assertEqual(norm_c['status'], 'canceled')

    def test_rss_parses_explicit_event_dates_and_skips_missing_year(self):
        rows = rss_events((FIXTURES / 'sample.rss').read_text(), BASE_SRC, BASE_SRC['url'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name'], 'Winter Jazz Night')
        self.assertEqual(rows[0]['startDate'], '2026-12-18T20:00:00-06:00')
        self.assertEqual(rows[0]['location']['name'], 'The Midland')

    def test_localist_api_v2_extracts_free_geo_and_ages(self):
        data = json.loads((FIXTURES / 'localist.json').read_text())
        rows = localist_events(data, dict(BASE_SRC, region='Lawrence', city='Lawrence'), 'https://calendar.ku.edu/api/2/events')
        self.assertEqual(len(rows), 1)
        norm = normalize(rows[0], dict(BASE_SRC, region='Lawrence', city='Lawrence', format='localist'), NOW.isoformat(), 'https://calendar.ku.edu/api/2/events')
        self.assertEqual(norm['price'], '0')
        self.assertTrue(norm['ages']['all_ages'])
        self.assertEqual(norm['geo']['lat'], 38.958)

    def test_simpleview_json_and_civicplus_html(self):
        sv_payload = json.dumps({'docs': [{'title': 'Holiday Market', 'startDate': '2026-12-12', 'venue': 'Union Station', 'city': 'Overland Park', 'url': '/event/hm'}]})
        sv_rows = simpleview_events(sv_payload, BASE_SRC, 'https://example.test/sv')
        self.assertEqual(sv_rows[0]['location']['address']['addressLocality'], 'Overland Park')
        cp_html = '<div class="calendarEvent"><h3><a href="/cal/1">Tree Lighting</a></h3><p>December 4, 2026</p><span class="location">Town Square</span></div>'
        cp_rows = civicplus_events(cp_html, BASE_SRC, 'https://example.test/cp')
        self.assertEqual(cp_rows[0]['startDate'], '2026-12-04')

    def test_bibliocommons_and_libcal_library_adapters(self):
        bc_json = json.dumps({
            'entities': {
                'locations': {'b1': {'name': 'Central Branch', 'city': 'Overland Park', 'lat': 38.98, 'lng': -94.67}},
                'events': {'e1': {'id': 'e1', 'definition': {'title': 'Toddler Storytime', 'start': '2026-12-03T10:00:00-06:00', 'branchLocationId': 'b1', 'audiences': [{'name': 'Ages 0-5'}], 'registration': {'required': True, 'isFull': False}}}},
            }
        })
        bc_rows = bibliocommons_events(bc_json, BASE_SRC, 'https://example.test/bc')
        self.assertEqual(bc_rows[0]['typicalAgeRange'], '0–5')
        self.assertEqual(bc_rows[0]['offers']['price'], '0')
        self.assertEqual(bc_rows[0]['_registration']['status'], 'open')

        lc_json = json.dumps({'events': [{'title': 'Teen Chess Club', 'start': '2026-12-09T16:00:00-06:00', 'url': 'https://example.test/lc/1', 'location': {'name': 'Columbia Public Library'}, 'audience': ['Ages 12-18'], 'seats': 10, 'seats_taken': 10, 'waitlist': True}]})
        lc_rows = libcal_events(lc_json, BASE_SRC, 'https://example.test/lc')
        self.assertEqual(lc_rows[0]['typicalAgeRange'], '12–18')
        self.assertEqual(lc_rows[0]['_registration']['status'], 'waitlist')

    def test_mlb_schedule_filters_home_games_only(self):
        payload = {'dates': [{'games': [
            {'gameDate': '2027-04-02T19:10:00Z', 'venue': {'name': 'Kauffman Stadium'}, 'status': {'detailedState': 'Scheduled'},
             'teams': {'home': {'team': {'id': 118, 'name': 'Kansas City Royals'}}, 'away': {'team': {'id': 142, 'name': 'Minnesota Twins'}}}},
            {'gameDate': '2027-04-05T18:10:00Z', 'venue': {'name': 'Target Field'}, 'status': {'detailedState': 'Scheduled'},
             'teams': {'home': {'team': {'id': 142, 'name': 'Minnesota Twins'}}, 'away': {'team': {'id': 118, 'name': 'Kansas City Royals'}}}},
        ]}]}
        src = dict(BASE_SRC, format='mlb_schedule', team_id=118, home_only=True, tickets_url='https://www.mlb.com/royals/schedule')
        rows = mlb_schedule_events(payload, src, 'https://statsapi.mlb.com/api/v1/schedule')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name'], 'Minnesota Twins at Kansas City Royals')

    def test_mdc_and_ticketmaster_adapters_and_missing_key_graceful(self):
        mdc_html = '<article class="node--type-event"><h2><a href="/events/eagle">Eagle Watch</a></h2><p>December 12, 2026 9:00 a.m. - Free</p><span class="location">Burr Oak Woods</span></article>'
        mdc_rows = mdc_events(mdc_html, BASE_SRC, 'https://mdc.mo.gov/events')
        self.assertEqual(mdc_rows[0]['offers']['price'], '0')
        self.assertEqual(mdc_rows[0]['startDate'], '2026-12-12T09:00:00-06:00')

        tm_src = dict(BASE_SRC, format='ticketmaster', url='https://app.ticketmaster.com/discovery/v2/events.json')
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=False):
            os.environ.pop('TICKETMASTER_API_KEY', None)
            rows, health = collect_source(tm_src, date(2026, 11, 24), date(2027, 6, 24), NOW.isoformat(), Path(tmp))
        self.assertEqual(rows, [])
        self.assertEqual(health['status'], 'discovery-only')

        tm_data = {'_embedded': {'events': [{'name': 'Symphony Gala', 'url': 'https://example.test/tm/1', 'dates': {'start': {'dateTime': '2027-01-15T20:00:00-06:00'}, 'status': {'code': 'onsale'}}, 'priceRanges': [{'min': 45, 'currency': 'USD'}], '_embedded': {'venues': [{'name': 'Helzberg Hall', 'city': {'name': 'Kansas City'}}]}}]}}
        self.assertEqual(ticketmaster_events(tm_data, tm_src, tm_src['url'])[0]['offers']['price'], '45')

    def test_fuzzy_cross_source_dedup_merges_unambiguous_match_only(self):
        org_src = dict(BASE_SRC, id='nelson', name='Nelson-Atkins', kind='organizer', format='tnew')
        cvb_src = dict(BASE_SRC, id='visitkc', name='Visit KC', kind='official-calendar', format='visitkc')
        org = normalize({'name': 'Cinema Paradiso Film Screening', 'startDate': '2026-12-04T19:00:00-06:00', 'location': {'name': 'The Nelson-Atkins Museum of Art'}, 'url': 'https://cart.nelson-atkins.org/1'}, org_src, NOW.isoformat(), 'https://nelson-atkins.org/events/')
        area = normalize({'name': 'Cinema Paradiso', 'startDate': '2026-12-04', '_all_day': True, 'location': {'name': 'Nelson-Atkins Museum of Art', 'geo': {'latitude': 39.045, 'longitude': -94.581}}, 'url': 'https://www.visitkc.com/events/cp'}, cvb_src, NOW.isoformat(), 'https://www.visitkc.com/events/')
        merged = reconcile([], [org, area], [], NOW)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['source_id'], 'nelson')
        self.assertEqual(len(merged[0]['sources']), 2)
        self.assertEqual(merged[0]['geo']['lat'], 39.045)

    def test_fuzzy_dedup_keeps_two_same_day_showtimes_separate_and_localist_collects(self):
        org_src = dict(BASE_SRC, id='nelson', name='Nelson-Atkins', kind='organizer', format='tnew')
        cvb_src = dict(BASE_SRC, id='visitkc', name='Visit KC', kind='official-calendar', format='visitkc')
        s1 = normalize({'name': 'Cinema Paradiso', 'startDate': '2026-12-04T15:00:00-06:00', 'location': {'name': 'The Nelson-Atkins Museum of Art'}, 'url': 'https://cart.nelson-atkins.org/1'}, org_src, NOW.isoformat(), 'https://nelson-atkins.org/events/')
        s2 = normalize({'name': 'Cinema Paradiso', 'startDate': '2026-12-04T19:00:00-06:00', 'location': {'name': 'The Nelson-Atkins Museum of Art'}, 'url': 'https://cart.nelson-atkins.org/2'}, org_src, NOW.isoformat(), 'https://nelson-atkins.org/events/')
        area = normalize({'name': 'Cinema Paradiso', 'startDate': '2026-12-04', '_all_day': True, 'location': {'name': 'Nelson-Atkins Museum of Art'}, 'url': 'https://www.visitkc.com/events/cp'}, cvb_src, NOW.isoformat(), 'https://www.visitkc.com/events/')
        self.assertEqual(len(reconcile([], [s1, s2, area], [], NOW)), 3)

        loc_src = dict(BASE_SRC, id='ku-cal', format='localist', region='Lawrence', city='Lawrence', url='https://calendar.ku.edu/api/2/events')
        payload = (FIXTURES / 'localist.json').read_text()
        with tempfile.TemporaryDirectory() as tmp, patch('collect_activities.Fetcher.fetch', return_value=payload):
            rows, health = collect_source(loc_src, date(2026, 11, 24), date(2027, 6, 24), NOW.isoformat(), Path(tmp))
        self.assertEqual(len(rows), 1)
        self.assertEqual(health['status'], 'checked')


if __name__ == '__main__':
    unittest.main()
