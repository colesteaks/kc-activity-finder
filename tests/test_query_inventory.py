import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from query_inventory import query


class QueryTests(unittest.TestCase):
    def test_index_filters_hints_without_dropping_other_rows_from_the_file(self):
        data = {'activities': [
            {
                'id': 'a', 'offering_id': 'a', 'title': 'Family storytime', 'date': '2026-12-01',
                'end_date': '2026-12-01', 'city': 'Lawrence', 'region': 'Lawrence', 'venue': 'Library',
                'url': 'https://example.test/a',
                'hints': {'audience': ['kids', 'family'], 'standout_score': 40, 'free_likely': True},
                'geo_meta': {'drive_band': '30-60m'},
            },
            {
                'id': 'b', 'offering_id': 'b', 'title': 'Late concert', 'date': '2026-12-20',
                'end_date': '2026-12-20', 'city': 'Kansas City', 'region': 'Kansas City metro',
                'venue': 'Hall', 'url': 'https://example.test/b',
                'hints': {'audience': ['adults'], 'standout_score': 90, 'free_likely': False},
                'geo_meta': {'drive_band': '0-30m'},
            },
        ]}

        class Args:
            region = 'Lawrence'
            city = None
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


if __name__ == '__main__':
    unittest.main()
