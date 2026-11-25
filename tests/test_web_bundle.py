import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from build_web_bundle import build_bundle, render_feed, write_outputs
from query_inventory import hydrate_bundle


def sample():
    return {
        'version': 1,
        'updated_at': '2026-11-24T12:00:00-06:00',
        'horizon_start': '2026-11-24',
        'horizon_end': '2027-06-24',
        'timezone': 'America/Chicago',
        'taxonomy': {'regions': ['Lawrence', 'Topeka & Flint Hills'], 'categories': []},
        'places': [],
        'sources': [{'id': 'arts', 'name': 'Arts', 'region': 'Lawrence', 'url': 'https://example.test/feed', 'events': 1, 'status': 'checked', 'visited_count': 1}],
        'coverage_matrix': {
            'summary_metrics': {'depth_tier_counts': {'active': 1}},
            'category_by_region': [{
                'region': 'Lawrence', 'category': 'music_performance', 'status': 'collecting',
                'depth_tier': 'active', 'distinct_offerings': 1, 'routes': ['arts'],
            }],
        },
        'activities': [{
            'id': 'jazz-1',
            'offering_id': 'jazz',
            'title': 'Winter Jazz Night',
            'venue': 'Hall',
            'city': 'Lawrence',
            'region': 'Lawrence',
            'categories': ['music_performance'],
            'type': 'Music',
            'date': '2026-12-18',
            'end_date': '2026-12-18',
            'start': '2026-12-18T20:00:00-06:00',
            'end': None,
            'all_day': False,
            'status': 'scheduled',
            'stale': False,
            'url': 'https://example.test/jazz',
            'source_id': 'arts',
            'source_name': 'Arts',
            'source_kind': 'organizer',
            'schedule': {'kind': 'one_off', 'start_date': '2026-12-18', 'end_date': '2026-12-18', 'sessions': [{'start': '2026-12-18T20:00:00-06:00', 'end': None}]},
            'ages': {'min': None, 'max': None, 'all_ages': False, 'label': 'Age not specified'},
            'hints': {'audience': ['adults'], 'standout_score': 80, 'is_promo': False},
            'geo_meta': {'drive_band': '30-60m', 'corridor': 'Lawrence', 'amtrak_accessible': False},
            'place_id': None,
            'description': 'A long description ' * 20,
            'evidence': {'url': 'https://example.test/jazz', 'format': 'rss', 'quote': 'not for the bundle'},
            'conflicts': [],
            'checked_at': '2026-11-24T12:00:00-06:00',
            'first_seen': '2026-11-24T12:00:00-06:00',
            'ticket_status': 'unknown',
            'price': None,
            'currency': None,
        }],
    }


class BundleTests(unittest.TestCase):
    def test_v2_bundle_drops_quotes_and_hydrates_cleanly(self):
        bundle = build_bundle(sample())
        self.assertEqual(bundle['version'], 2)
        self.assertNotIn('quote', json.dumps(bundle))
        self.assertNotIn('routes', json.dumps(bundle['coverage_matrix']))
        self.assertNotIn('activities', bundle)
        hydrated = hydrate_bundle(bundle)
        row = hydrated['activities'][0]
        self.assertEqual(row['title'], 'Winter Jazz Night')
        self.assertEqual(row['start'], '2026-12-18T20:00:00-06:00')
        self.assertEqual(row['hints']['standout_score'], 80)

        data_with_stale = sample()
        stale_row = dict(data_with_stale['activities'][0], id='stale-1', title='Stale Item', stale=True)
        data_with_stale['activities'].append(stale_row)
        feed = render_feed('Test', data_with_stale['activities'])
        self.assertIn('https://example.test/jazz', feed)
        self.assertIn('Winter Jazz Night', feed)
        self.assertNotIn('Stale Item', feed)
        self.assertNotIn('not for the bundle', feed)

    def test_write_outputs_cleans_slugs_minifies_and_stays_under_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feeds = root / 'web' / 'feeds'
            feeds.mkdir(parents=True)
            (feeds / 'topeka---flint-hills.xml').write_text('<old/>')
            stats = write_outputs(sample(), root)
            text = (root / 'web' / 'activities.json').read_text()
            self.assertNotIn('\n  "', text)
            self.assertLess(stats['bundle_bytes'], 1_000_000)
            self.assertTrue((feeds / 'lawrence.xml').exists())
            self.assertTrue((feeds / 'topeka-flint-hills.xml').exists())
            self.assertFalse((feeds / 'topeka---flint-hills.xml').exists())
            self.assertTrue((feeds / 'standouts.xml').exists())


if __name__ == '__main__':
    unittest.main()
