import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from build_web_bundle import build_bundle
from query_inventory import load_inventory, query


class QueryTests(unittest.TestCase):
    def test_index_filters_hints_without_dropping_other_rows_from_the_file(self):
        data = {'activities': [
            {
                'id': 'a', 'offering_id': 'a', 'title': 'Family storytime', 'date': '2026-12-01',
                'end_date': '2026-12-01', 'city': 'Lawrence', 'region': 'Lawrence', 'venue': 'Library',
                'url': 'https://example.test/a', 'stale': False,
                'hints': {'audience': ['kids', 'family'], 'standout_score': 40, 'free_likely': True},
                'geo_meta': {'drive_band': '30-60m', 'corridor': 'Lawrence', 'amtrak_accessible': False},
            },
            {
                'id': 'b', 'offering_id': 'b', 'title': 'Late concert', 'date': '2026-12-20',
                'end_date': '2026-12-20', 'city': 'Hermann', 'region': 'Columbia', 'venue': 'Hall',
                'url': 'https://example.test/b', 'stale': False,
                'hints': {'audience': ['adults'], 'standout_score': 90, 'free_likely': False},
                'geo_meta': {'drive_band': '2-3.5h', 'corridor': 'Mid-Missouri / Columbia', 'amtrak_accessible': True},
            },
        ]}

        class Args:
            region = 'Lawrence'
            city = None
            corridor = None
            amtrak = False
            include_stale = False
            q = 'story'
            audience = 'kids'
            free = True
            drive_band = '30-60m'
            min_standout = 0
            date_from = '2026-12-01'
            date_to = '2026-12-15'
            limit = 10

        rows = query(data, Args)
        self.assertEqual([row['id'] for row in rows], ['a'])
        self.assertEqual(len(data['activities']), 2)

    def test_query_hydrates_v2_bundle_and_filters_amtrak_and_stale(self):
        raw = {
            'updated_at': '2026-11-25T10:00:00-06:00',
            'sources': [{'id': 'src1', 'name': 'Source 1', 'region': 'Columbia', 'url': 'https://example.test'}],
            'places': [],
            'coverage_matrix': {'summary_metrics': {}, 'category_by_region': []},
            'activities': [
                {
                    'id': 'r1', 'offering_id': 'o1', 'title': 'River Runner Holiday', 'venue': 'Depot',
                    'city': 'Hermann', 'region': 'Columbia', 'categories': ['festivals_seasonal'],
                    'type': 'Festivals & seasonal', 'date': '2026-12-06', 'end_date': '2026-12-06',
                    'start': '2026-12-06T10:00:00-06:00', 'all_day': False, 'status': 'scheduled',
                    'stale': False, 'url': 'https://example.test/1', 'source_id': 'src1', 'source_kind': 'organizer',
                    'schedule': {'kind': 'one_off'}, 'ages': {'all_ages': True},
                    'hints': {'audience': ['all_ages', 'family'], 'free_likely': True, 'standout_score': 88},
                    'geo_meta': {'drive_band': '2-3.5h', 'corridor': 'Mid-Missouri / Columbia', 'amtrak_accessible': True},
                },
                {
                    'id': 'r2', 'offering_id': 'o2', 'title': 'Old Ghost Event', 'venue': 'Depot',
                    'city': 'Hermann', 'region': 'Columbia', 'categories': ['festivals_seasonal'],
                    'type': 'Festivals & seasonal', 'date': '2026-12-07', 'end_date': '2026-12-07',
                    'start': None, 'all_day': True, 'status': 'scheduled', 'stale': True,
                    'url': 'https://example.test/2', 'source_id': 'src1', 'source_kind': 'organizer',
                    'schedule': {'kind': 'one_off'}, 'ages': {},
                    'hints': {'audience': ['all_ages'], 'standout_score': 50},
                    'geo_meta': {'drive_band': '2-3.5h', 'corridor': 'Mid-Missouri / Columbia', 'amtrak_accessible': True},
                },
            ],
        }
        bundle = build_bundle(raw)

        class AmtrakArgs:
            region = None
            city = None
            corridor = None
            amtrak = True
            include_stale = False
            q = None
            audience = None
            free = False
            drive_band = None
            min_standout = 0
            date_from = None
            date_to = None
            limit = 10

        rows = query(bundle, AmtrakArgs)
        self.assertEqual([r['id'] for r in rows], ['o1'])
        self.assertEqual(rows[0]['start'], '2026-12-06T10:00:00-06:00')

        AmtrakArgs.include_stale = True
        self.assertEqual([r['id'] for r in query(bundle, AmtrakArgs)], ['o1', 'o2'])

    def test_real_repo_inventory_returns_multi_region_rows(self):
        if not (ROOT / 'web' / 'bundle.min.json').exists():
            self.skipTest('bundle not present')
        inv = load_inventory(ROOT)
        self.assertGreater(len(inv['activities']), 3000)

        class RegArgs:
            city = None; corridor = None; amtrak = False; include_stale = False
            q = None; audience = None; free = False; drive_band = None; min_standout = 0
            date_from = None; date_to = None; limit = 3

        for region in ('Lawrence', 'Columbia', 'Omaha', 'Topeka & Flint Hills', 'Des Moines'):
            RegArgs.region = region
            self.assertGreater(len(query(inv, RegArgs)), 0, f'Expected rows in {region}')


if __name__ == '__main__':
    unittest.main()
