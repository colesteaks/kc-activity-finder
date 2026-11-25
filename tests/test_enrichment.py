import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from activity_model import coverage_matrix, enrich
from enrichment import build_hints, is_promo_listing
from geo_model import geo_metadata
from geocode_places import geocode_address, geocode_places_file


class EnrichmentAndGeoTest(unittest.TestCase):
    def test_geo_metadata_subregions_drive_bands_and_amtrak(self):
        op = geo_metadata({'city': 'Overland Park', 'region': 'Kansas City metro'})
        self.assertEqual(op['corridor'], 'Kansas City metro')
        self.assertEqual(op['subregion'], 'Johnson County, KS')
        self.assertEqual(op['drive_band'], '0-30m')
        self.assertFalse(op['amtrak_accessible'])

        hermann = geo_metadata({'city': 'Hermann', 'region': 'Columbia'})
        self.assertEqual(hermann['corridor'], 'Mid-Missouri / Columbia')
        self.assertEqual(hermann['drive_band'], '2-3.5h')
        self.assertTrue(hermann['amtrak_accessible'])

        topeka = geo_metadata({'city': 'Topeka', 'region': 'Topeka & Flint Hills'})
        self.assertEqual(topeka['corridor'], 'Topeka & Flint Hills')
        self.assertEqual(topeka['drive_band'], '1-2h')

        omaha = geo_metadata({'city': 'Omaha', 'region': 'Omaha'})
        self.assertEqual(omaha['corridor'], 'Omaha')
        self.assertEqual(omaha['drive_band'], '2-3.5h')

    def test_promo_detection_and_rescues(self):
        self.assertTrue(is_promo_listing({'title': 'Happy Hour Refresh at Bar X', 'venue': 'Bar X'}))
        self.assertTrue(is_promo_listing({'title': 'Taco Tuesday', 'venue': 'Local Grill'}))
        self.assertTrue(is_promo_listing({'title': "Christmas at Minsky's!", 'venue': "Minsky's Pizza"}))
        self.assertFalse(is_promo_listing({'title': 'Holiday Pottery Class', 'venue': 'Belger Crane Yard'}))
        self.assertFalse(is_promo_listing({'title': 'Bourbon Tasting Workshop', 'venue': 'J. Rieger'}))

    def test_two_layer_hints_never_mutate_verified_fields(self):
        symphony = {
            'id': 'sym-1',
            'title': 'Kansas City Symphony: Mahler Symphony No. 5',
            'description': 'Annual spring orchestra concert at Helzberg Hall.',
            'venue': 'Kauffman Center',
            'city': 'Kansas City',
            'region': 'Kansas City metro',
            'source_id': 'kauffman',
            'source_kind': 'organizer',
            'source_name': 'Kauffman Center',
            'type': 'Music & performance',
            'categories': ['music_performance'],
            'url': 'https://kauffmancenter.org/events/mahler-5',
            'start': '2026-12-05T19:30:00-06:00',
            'all_day': False,
            'ages': {'all_ages': False, 'min': None, 'max': None, 'raw': None, 'note': 'Not verified'},
            'price': None,
            'registration': {'status': 'open', 'deadline': None},
            'geo': {'lat': 39.09, 'lng': -94.58},
        }
        promo = {
            'id': 'bar-1',
            'title': 'Happy Hour Refresh',
            'description': 'Half-price appetizers and drinks.',
            'venue': 'Iron Horse Bar & Grill',
            'city': 'Lee’s Summit',
            'region': 'Kansas City metro',
            'source_id': 'visitkc',
            'source_kind': 'official-calendar',
            'source_name': 'Visit KC',
            'type': 'Food & markets',
            'categories': ['food_drink'],
            'url': 'https://visitkc.com/events/happy-hour-refresh',
            'start': '2026-12-05T16:00:00-06:00',
            'all_day': False,
            'schedule': {'kind': 'one_off'},
            'ages': {'all_ages': False, 'min': None, 'max': None, 'raw': None},
            'price': None,
        }
        sym_hints = build_hints(symphony)
        promo_hints = build_hints(promo)
        self.assertTrue(sym_hints['labeled_estimate'])
        self.assertIsNone(symphony['ages']['min'])
        self.assertIsNone(symphony['price'])
        self.assertEqual(sym_hints['novelty'], 'signature_event')
        self.assertEqual(sym_hints['indoor_outdoor'], 'indoor')
        self.assertEqual(sym_hints['time_of_day'], 'evening')
        self.assertTrue(promo_hints['is_promo'])
        self.assertGreater(sym_hints['standout_score'], promo_hints['standout_score'] + 25)

    def test_enrich_adds_geo_meta_and_hints(self):
        row = {
            'id': 'x1',
            'title': 'Botanical Trail Walk',
            'description': 'Free admission guided hike.',
            'venue': 'Overland Park Arboretum',
            'city': 'Overland Park',
            'region': 'Kansas City metro',
            'source_id': 'op-arboretum',
            'source_kind': 'organizer',
            'type': 'Nature & animals',
            'url': 'https://opkansas.org/arboretum/walk',
            'start': '2026-12-06T09:00:00-06:00',
            'all_day': False,
            'ages': {'all_ages': False, 'min': None, 'max': None, 'raw': None},
            'price': None,
        }
        enrich(row)
        self.assertEqual(row['geo_meta']['subregion'], 'Johnson County, KS')
        self.assertTrue(row['hints']['free_likely'])
        self.assertEqual(row['hints']['time_of_day'], 'morning')

    def test_coverage_matrix_depth_tiers_and_summary_metrics(self):
        taxonomy = {
            'regions': ['Kansas City metro', 'Lawrence'],
            'categories': [
                {'id': 'arts_exhibits', 'search_terms': 'art museum'},
                {'id': 'camps', 'search_terms': 'summer camps'},
            ],
        }
        registry = [
            {'id': 'nelson', 'region': 'Kansas City metro', 'categories': ['arts_exhibits'], 'format': 'tnew', 'kind': 'organizer'},
            {'id': 'kc-static', 'region': 'Kansas City metro', 'categories': ['camps'], 'format': 'offering', 'kind': 'organizer'},
        ]
        health = [
            {'id': 'nelson', 'category_counts': {'arts_exhibits': 18}, 'kind_counts': {'one_off': 18}},
            {'id': 'kc-static', 'category_counts': {'camps': 1}, 'kind_counts': {'camp': 1}},
        ]
        activities = [
            {
                'id': f'n-{i}',
                'offering_id': f'oid-{i}',
                'source_id': 'nelson',
                'source_kind': 'organizer',
                'region': 'Kansas City metro',
                'categories': ['arts_exhibits'],
                'ages': {'all_ages': True},
                'hints': {'audience': ['all_ages']},
                'geo': {'lat': 39.04, 'lng': -94.58},
                'stale': False,
            }
            for i in range(15)
        ] + [
            {
                'id': 'c-1',
                'offering_id': 'oid-c1',
                'source_id': 'kc-static',
                'source_kind': 'organizer',
                'region': 'Kansas City metro',
                'categories': ['camps'],
                'ages': {'all_ages': False, 'min': None},
                'hints': {'audience': ['kids']},
                'stale': False,
            }
        ]
        matrix = coverage_matrix(registry, taxonomy, health, activities)
        by_key = {(c['region'], c['category']): c for c in matrix['category_by_region']}
        self.assertEqual(by_key[('Kansas City metro', 'arts_exhibits')]['depth_tier'], 'strong')
        self.assertEqual(by_key[('Kansas City metro', 'camps')]['depth_tier'], 'thin')
        self.assertEqual(by_key[('Lawrence', 'arts_exhibits')]['depth_tier'], 'gap')
        self.assertEqual(matrix['summary_metrics']['distinct_offerings'], 16)
        self.assertEqual(matrix['summary_metrics']['concentration_top3_share'], 1.0)

    def test_census_geocoder_with_mock_response(self):
        payload = json.dumps({
            'result': {
                'addressMatches': [
                    {'coordinates': {'x': -94.5809, 'y': 39.0451}}
                ]
            }
        })
        geo = geocode_address(
            '4525 Oak St, Kansas City, MO 64111',
            fetch_fn=lambda _url: payload,
            observed_at='2026-11-24T12:00:00-06:00',
        )
        self.assertEqual(geo['precision'], 'address')
        self.assertAlmostEqual(geo['lat'], 39.0451)
        self.assertAlmostEqual(geo['lng'], -94.5809)

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'places.json'
            p.write_text(json.dumps({
                'places': [
                    {'id': 'existing', 'address': '100 Main St', 'geo': {'lat': 39.1, 'lng': -94.5}},
                    {'id': 'needs-geo', 'address': '4525 Oak St, Kansas City, MO 64111'},
                ]
            }))
            attempted, updated = geocode_places_file(p, fetch_fn=lambda _url: payload)
            self.assertEqual((attempted, updated), (1, 1))
            saved = json.loads(p.read_text())
            self.assertEqual(saved['places'][1]['geo']['precision'], 'address')


if __name__ == '__main__':
    unittest.main()
