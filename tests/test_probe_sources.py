import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from probe_sources import (
    addresses_from_proposals,
    apply_probe,
    classify_response,
    place_record,
    postal_addresses,
    tier_for_region,
)


class ProbeTests(unittest.TestCase):
    def test_tiers_follow_taxonomy_corridors(self):
        self.assertEqual(tier_for_region('Lawrence'), 'tier1_backyard')
        self.assertEqual(tier_for_region('Topeka & Flint Hills'), 'tier2_day_trip')
        self.assertEqual(tier_for_region('Omaha'), 'tier3_weekend')
        self.assertEqual(tier_for_region(None), 'unassigned')

    def test_rss_fixture_is_a_verified_parser_and_blocks_are_not_parsed(self):
        body = (ROOT / 'tests/fixtures/platforms/sample.rss').read_text()
        verified = classify_response('https://example.test/events/feed', 200, body, 'application/rss+xml')
        self.assertEqual(verified['classification'], 'verified_parser')
        self.assertEqual(verified['format'], 'rss')
        self.assertEqual(verified['event_count'], 1)
        blocked = classify_response('https://example.test/events/feed', 403, body, 'text/html')
        self.assertEqual(blocked['classification'], 'blocked')
        self.assertEqual(blocked['event_count'], 0)

    def test_promotion_keeps_the_provided_seed_and_skips_unknown_regions(self):
        seed = {
            'id': 'kc-daily',
            'provenance': {'kind': 'provided-seed', 'raw_value': 'KC daily', 'seed_line': 1},
            'canonical_url': 'https://www.kcdaily.com/',
        }
        graph = {'last_reviewed': '2026-11-07', 'nodes': [json.loads(json.dumps(seed))]}
        registry = {'sources': []}
        probes = [
            {'url': 'https://lawrenceartscenter.org/events/feed', 'classification': 'verified_parser', 'format': 'rss', 'event_count': 2, 'error': None},
            {'url': 'https://example.test/comments/feed', 'classification': 'verified_parser', 'format': 'rss', 'event_count': 4, 'error': None},
            {'url': 'https://unknown.example/events/feed', 'classification': 'verified_parser', 'format': 'rss', 'event_count': 3, 'error': None},
            {'url': 'https://kcconvention.com/events/feed', 'classification': 'blocked', 'format': None, 'event_count': 0, 'error': 'HTTP 403'},
        ]
        candidates = [
            {'url': probes[0]['url'], 'label': 'Lawrence Arts Center events', 'region': 'Lawrence', 'skip_promotion': False},
            {'url': probes[1]['url'], 'label': 'Comments', 'region': 'Lawrence', 'skip_promotion': True},
            {'url': probes[2]['url'], 'label': 'Unknown', 'region': None, 'skip_promotion': False},
            {'url': probes[3]['url'], 'label': 'Convention', 'region': 'Kansas City metro', 'skip_promotion': False},
        ]
        result = apply_probe(registry, graph, probes, candidates, '2026-11-24')
        self.assertEqual([item['format'] for item in result['promoted']], ['rss'])
        self.assertEqual(graph['nodes'][0], seed)
        self.assertEqual(graph['nodes'][0]['provenance']['kind'], 'provided-seed')
        self.assertEqual(registry['sources'][0]['region'], 'Lawrence')
        self.assertTrue(any(item['reason'] == 'region not tied to a reviewed host' for item in result['withheld']))

    def test_jsonld_and_proposal_addresses_stay_explicit(self):
        html = '''<script type="application/ld+json">
        {"@type":"Museum","name":"Example Museum","address":{"streetAddress":"100 Main St","addressLocality":"Lawrence","addressRegion":"KS","postalCode":"66044"}}
        </script>'''
        found = postal_addresses(html, 'https://example.test/visit')
        self.assertEqual(found[0]['address'], '100 Main St, Lawrence, KS 66044')
        proposals = [
            {'url': 'https://www.opkansas.org/recreation-fun/deanna-rose-childrens-farmstead', 'label': 'Deanna Rose Children’s Farmstead 13800 Switzer Rd, Overland Park, KS 66221'},
            {'url': 'https://www.google.com/maps/place/Example', 'label': '10695 Roe Ave, Overland Park, KS 66207'},
            {'url': 'http://insecure.example/place', 'label': '100 Main St, Lawrence, KS 66044'},
        ]
        rows = addresses_from_proposals(proposals)
        self.assertEqual(len(rows), 1)
        self.assertIn('13800 Switzer', rows[0]['address'])
        with self.assertRaises(ValueError):
            place_record(rows[0], None)


if __name__ == '__main__':
    unittest.main()
