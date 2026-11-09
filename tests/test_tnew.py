"""Regression coverage for the museum's selected public ticket performance."""
import json
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from calendar_adapters import tnew_events
from collect_activities import collect_source, normalize
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/tnew'
TOUR = 'https://cart.nelson-atkins.org/51930/53441'
FILM = 'https://cart.nelson-atkins.org/50445/53356'
SOURCE = {'id': 'nelson', 'name': 'Nelson-Atkins Museum of Art',
          'url': 'https://nelson-atkins.org/events/', 'region': 'Kansas City metro',
          'city': 'Kansas City', 'kind': 'organizer', 'format': 'tnew',
          'pattern': r'^/\d+/\d+/?$', 'detail_hosts': ['cart.nelson-atkins.org'],
          'max_details': 24, 'categories': ['arts_exhibits'], 'activity_kinds': ['one_off']}
NOW = datetime(2026, 11, 9, 9, tzinfo=ZoneInfo('America/Chicago'))


class TnewTests(unittest.TestCase):
    def test_selected_performance_never_clones_more_dates_or_other_film_titles(self):
        rows = tnew_events((FIXTURES / 'cinema.html').read_text(), FILM)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name'], 'Cinema Paradiso')
        self.assertEqual(rows[0]['startDate'], '2026-11-13T19:00:00-06:00')
        self.assertEqual(rows[0]['url'], FILM)
        self.assertEqual(rows[0]['_categories'], ['film_literature'])
        self.assertNotIn('endDate', rows[0])

    def test_sold_out_and_material_audience_survive_normalization(self):
        raw = tnew_events((FIXTURES / 'sold-out-tour.html').read_text(), TOUR)[0]
        row = normalize(raw, SOURCE, NOW.isoformat(), TOUR)
        self.assertEqual(row['ticket_status'], 'SoldOut')
        self.assertEqual(row['registration']['status'], 'sold_out')
        self.assertIn('people with memory loss and their care partners', row['description'])
        self.assertIsNone(row['ages']['min'])
        self.assertIsNone(row['price'])
        self.assertEqual(row['venue'], 'Bloch Lobby')
        self.assertEqual(row['date'], '2026-11-12')

    def test_no_year_or_ambiguous_clock_is_not_guessed(self):
        body = (FIXTURES / 'cinema.html').read_text()
        for modified in (body.replace('2026', ''), body.replace('7:00PM', 'TBA'),
                         body.replace('7:00PM', '7:00PM–9:00PM')):
            self.assertEqual(tnew_events(modified, FILM), [])

    def test_disabled_purchase_button_or_unavailable_text_never_implies_open(self):
        body = (FIXTURES / 'cinema.html').read_text()
        row = tnew_events(body.replace('id="tn-add-to-cart-button"',
                                      'disabled id="tn-add-to-cart-button"'), FILM)[0]
        self.assertEqual(row['_registration']['status'], 'unknown')
        self.assertEqual(row['offers']['availability'], 'unknown')
        self.assertEqual(tnew_events('<h1>Calendar with no selected performance</h1>', FILM), [])

    def test_explicit_host_delegation_collects_only_reviewed_ticket_links(self):
        index = ''.join(f'<a href="{u}">Ticket</a>' for u in [TOUR, FILM,
                     'https://evil.test/51930/53441',
                     'https://cart.nelson-atkins.org.evil.test/51930/53441',
                     'http://cart.nelson-atkins.org/51930/53441',
                     'https://user:password@cart.nelson-atkins.org/51930/53441'])
        fetched = []
        def fetch(_self, url):
            fetched.append(url)
            if url == SOURCE['url']: return index
            return (FIXTURES / ('cinema.html' if url == FILM else 'sold-out-tour.html')).read_text()
        with tempfile.TemporaryDirectory() as tmp, patch('collect_activities.Fetcher.fetch', fetch):
            rows, health = collect_source(SOURCE, date(2026,11,9), date(2027,6,9), NOW.isoformat(), Path(tmp))
        self.assertEqual(set(fetched), {SOURCE['url'], TOUR, FILM})
        self.assertEqual(len(rows), 2)
        self.assertEqual(health['status'], 'checked')
        validator = Draft202012Validator(json.loads((ROOT/'schemas/activity.schema.json').read_text()),
                                         format_checker=FormatChecker())
        for row in rows: validator.validate(row)

    def test_delegation_is_opt_in_and_existing_identity_formula_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp, patch('collect_activities.Fetcher.fetch',
                return_value=f'<a href="{TOUR}">Ticket</a>'):
            rows, health = collect_source(dict(SOURCE, detail_hosts=[]), date(2026,11,9),
                                          date(2027,6,9), NOW.isoformat(), Path(tmp))
        self.assertEqual(rows, [])
        self.assertEqual(health['visited_count'], 1)
        raw = tnew_events((FIXTURES/'cinema.html').read_text(), FILM)[0]
        first = normalize(raw, SOURCE, NOW.isoformat(), FILM)
        second = normalize(raw, dict(SOURCE, format='jsonld'), NOW.isoformat(), FILM)
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(first['offering_id'], second['offering_id'])


if __name__ == '__main__': unittest.main()
