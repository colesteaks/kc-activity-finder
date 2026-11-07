import copy
import sys
import unittest
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from activity_pipeline import (CHECKS, EXPECTED_STAGES, complete, exclusions, initialize,
                               load, merge, rank, report, timestamp, validate_candidate)


def ready(mode='weekend'):
    graph = load(ROOT / 'data/source-graph.json')
    run = initialize(load(ROOT / f'examples/{mode}-request.json'), graph, True)
    run['candidates'] = load(ROOT / f'examples/{mode}-candidates.json')['candidates']
    run['coverage'][0].update(status='checked', observed_at=run['request']['as_of'],
                              visited_urls=['https://example.test/seed'], notes='Synthetic sweep only')
    run['searches'] = [{'region': region, 'query': 'Fictional search', 'outcome': 'Synthetic fixture; no live search',
                        'observed_at': run['request']['as_of']} for region in
                       ['Kansas City metro', 'Lawrence', 'Columbia', 'Bentonville', 'surrounding areas']]
    for stage in EXPECTED_STAGES[:6]: complete(run, stage, graph)
    run['review'] = {'reviewer': 'Synthetic test reviewer', 'blocking_findings': [], 'candidates': {
        c['candidate_id']: [{'id': k, 'status': 'pass', 'notes': 'Synthetic check'} for k in sorted(CHECKS)]
        for c in run['candidates']}}
    complete(run, 'adversarial-review', graph)
    return run, graph


class PipelineTests(unittest.TestCase):
    def test_both_modes_end_to_end(self):
        for mode in ('weekend', 'signup'):
            run, graph = ready(mode)
            self.assertTrue(any(not r['exclusions'] for r in run['ranking']))
            self.assertIn('FICTIONAL DEMO', report(run, graph))

    def test_age_filter_does_not_destroy_inventory(self):
        run, _ = ready(); run['request']['party']['ages'] = [2, 35]
        run['candidates'][0]['audience']['min_age'] = 18
        self.assertIn('age-ineligible', exclusions(run['candidates'][0], run['request']))
        self.assertEqual(len(rank(run)), len(run['candidates']))

    def test_unknown_age_is_not_inferred_from_family_friendly(self):
        run, _ = ready(); c = run['candidates'][0]; c['audience']['min_age'] = None
        self.assertIn('age-eligibility-unknown', exclusions(c, run['request']))

    def test_sensor_only_cannot_recommend(self):
        run, _ = ready(); c = run['candidates'][0]
        for p in c['verification']: p['evidence_type'] = 'editorial'
        self.assertTrue(any(x.startswith('missing-fresh-official') for x in exclusions(c, run['request'])))

    def test_stale_and_future_evidence_rejected(self):
        for days in (-4, 1):
            run, _ = ready(); c = run['candidates'][0]
            c['verification'][0]['observed_at'] = (timestamp(run['request']['as_of']) + timedelta(days=days)).isoformat()
            self.assertTrue(any(x.startswith('missing-fresh-official') for x in exclusions(c, run['request'])))

    def test_unavailable_preserved(self):
        for state in ('sold-out', 'cancelled', 'closed', 'unknown', 'waitlist', 'not-open'):
            run, _ = ready(); c = run['candidates'][0]; c['availability']['status'] = state
            self.assertIn('availability-' + state, exclusions(c, run['request']))

    def test_merge_preserves_conflict_and_original(self):
        run, _ = ready(); c = run['candidates'][0]; other = copy.deepcopy(c)
        other['candidate_id'] = 'duplicate'; other['cost']['max'] = 999
        rows, log = merge([c, other]); self.assertEqual(len(rows), 1)
        self.assertEqual(log[0]['original']['cost']['max'], 999)
        self.assertIn('unresolved-conflict', exclusions(rows[0], run['request']))

    def test_different_occurrences_never_merge(self):
        run, _ = ready(); c = run['candidates'][0]; other = copy.deepcopy(c)
        other['candidate_id'] = 'tomorrow'; other['timing']['start'] = (timestamp(c['timing']['start']) + timedelta(days=1)).isoformat()
        other['timing']['end'] = None
        self.assertEqual(len(merge([c, other])[0]), 2)

    def test_unknown_time_is_retained(self):
        run, _ = ready(); c = run['candidates'][0]; c['timing'].update(start=None, end=None)
        validate_candidate(c); self.assertIn('unknown-time', exclusions(c, run['request']))

    def test_changes_invalidate_review(self):
        run, graph = ready(); run['candidates'][0]['title'] += ' changed'
        with self.assertRaisesRegex(ValueError, 'stale'): report(run, graph)

    def test_review_checks_cannot_be_removed_after_signoff(self):
        run, graph = ready(); run['review']['candidates'] = {}
        with self.assertRaises(ValueError): report(run, graph)

    def test_stage_order_enforced(self):
        run, graph = ready(); run['completed'] = []
        with self.assertRaises(ValueError): complete(run, 'merge', graph)

    def test_orphan_parent_rejected(self):
        run, graph = ready(); run['candidates'][0]['parent_event_id'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'Orphan'): report(run, graph)

    def test_strict_budget_and_travel_filters(self):
        run, _ = ready(); c = run['candidates'][0]
        run['request']['filters'] = {'max_price_per_person': 1, 'max_travel_minutes': 5}
        c['cost']['fees_unknown'] = True
        reasons = exclusions(c, run['request'])
        self.assertIn('budget-exceeded-or-unverified', reasons)
        self.assertIn('travel-exceeded-or-unverified', reasons)

    def test_local_calendar_window_uses_chicago(self):
        run, _ = ready(); c = run['candidates'][0]
        c['timing'].update(start='2030-09-07T02:00:00+00:00', end=None)
        run['request']['window'] = {'start': '2030-09-06', 'end': '2030-09-06'}
        self.assertNotIn('outside-window', exclusions(c, run['request']))

    def test_schema_rejects_out_of_range_fit(self):
        run, _ = ready(); c = run['candidates'][0]; c['fit']['movement']['score'] = 6
        with self.assertRaises(Exception): validate_candidate(c)

    def test_missing_region_search_blocks_completion(self):
        run, graph = ready(); run['completed'] = EXPECTED_STAGES[:3]; run['searches'] = []
        with self.assertRaises(ValueError): complete(run, 'broader-web-search', graph)

    def test_deadline_is_exact_instant(self):
        run, _ = ready('signup'); c = run['candidates'][0]
        c['availability']['deadline'] = (timestamp(run['request']['as_of']) - timedelta(seconds=1)).isoformat()
        self.assertIn('deadline-passed', exclusions(c, run['request']))


if __name__ == '__main__': unittest.main()
