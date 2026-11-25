import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from calendar_adapters import downtown_events
from collect_activities import collect_source,normalize

PAGE='https://downtownbentonville.org/events/calendar'
OBSERVED='2026-11-23T09:00:00-06:00'
SOURCE=next(s for s in json.loads((ROOT/'data/collection-sources.json').read_text())['sources'] if s['id']=='bentonville-downtown')
FIXTURE=(ROOT/'tests/fixtures/bentonville-downtown-calendar.html').read_text()

class DowntownCalendarTests(unittest.TestCase):
    def test_actual_visible_cards_preserve_separate_dates_and_offerings(self):
        rows=downtown_events(FIXTURE,PAGE)
        self.assertEqual(len(rows),10)
        self.assertEqual(len({r['url'] for r in rows}),4)
        markets=[r for r in rows if 'Farmers Market' in r['name']]
        self.assertEqual(len(markets),7)
        self.assertEqual(markets[0]['startDate'],'2026-11-28T09:00:00-06:00')
        self.assertEqual(markets[0]['endDate'],'2026-11-28T12:00:00-06:00')
        self.assertEqual(markets[-1]['startDate'],'2027-01-16T09:00:00-06:00')
        self.assertTrue(all(r['location']['name']=='Record' for r in markets))

    def test_overnight_party_ends_in_next_year_without_guessing_age_policy(self):
        raw=next(r for r in downtown_events(FIXTURE,PAGE) if r['name'].startswith("New Year's"))
        self.assertEqual(raw['startDate'],'2026-12-31T20:00:00-06:00')
        self.assertEqual(raw['endDate'],'2027-01-01T01:00:00-06:00')
        row=normalize(raw,SOURCE,OBSERVED,PAGE)
        self.assertEqual(row['schedule']['kind'],'one_off')
        self.assertIsNone(row['ages']['min']);self.assertIsNone(row['ages']['max'])
        self.assertEqual(row['registration']['status'],'unknown')
        self.assertIsNone(row['price'])

    def test_no_year_or_ambiguous_clock_is_not_invented(self):
        self.assertEqual(downtown_events(FIXTURE.replace(', 2026','').replace(', 2027',''),PAGE),[])
        changed=FIXTURE.replace('9am - 12pm','9 - noon')
        self.assertEqual(len(downtown_events(changed,PAGE)),3)

    def test_missing_time_keeps_date_only_and_missing_end_stays_unknown(self):
        rows=downtown_events(FIXTURE.replace('9am - 12pm',''),PAGE)
        first=rows[0];self.assertEqual(first['startDate'],'2026-11-28');self.assertTrue(first['_all_day'])
        parade=next(r for r in rows if 'Parade' in r['name'])
        self.assertIsNone(parade['endDate'])

    def test_external_or_credential_links_are_not_collected(self):
        for target in ['https://elsewhere.test/do/x','https://user:pass@downtownbentonville.org/do/x','https://downtownbentonville.org:8443/do/x','javascript:alert(1)']:
            changed=FIXTURE.replace('/do/bentonville-farmers-market-indoor-season-1',target)
            self.assertEqual(len(downtown_events(changed,PAGE)),3)

    def test_conflicting_weekday_is_skipped_and_cancellation_is_preserved(self):
        rows=downtown_events(FIXTURE.replace('Saturday, Nov 28, 2026','Sunday, Nov 28, 2026'),PAGE)
        self.assertEqual(len(rows),9)
        raw=next(r for r in downtown_events(FIXTURE.replace('Holiday Market','Canceled: Holiday Market'),PAGE) if r['name'].startswith('Canceled:'))
        self.assertEqual(normalize(raw,SOURCE,OBSERVED,PAGE)['status'],'canceled')

    def test_live_source_path_stays_partial_and_does_not_fetch_extra_details(self):
        with tempfile.TemporaryDirectory() as tmp,patch('collect_activities.Fetcher.fetch',return_value=FIXTURE) as fetch:
            rows,health=collect_source(SOURCE,date(2026,11,23),date(2027,6,23),OBSERVED,Path(tmp))
        self.assertEqual(len(rows),10);self.assertEqual(fetch.call_count,1)
        self.assertEqual(health['status'],'partial');self.assertTrue(health['truncated'])
        self.assertIn('Visible calendar cards only',health['horizon_note'])
        self.assertEqual(health['errors'],[])

if __name__=='__main__':unittest.main()
