import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from weekly_discovery_brief import build,eligible,public_url


class WeeklyDiscoveryTests(unittest.TestCase):
    def test_tracking_normalized_without_losing_program_parameters(self):
        self.assertEqual(public_url('https://example.com/events?program=42&utm_source=news#top'),'https://example.com/events?program=42')
    def test_private_and_unsafe_urls_rejected(self):
        for url in ('file:///etc/passwd','javascript:alert(1)','http://localhost/events','http://127.0.0.1/events','http://10.0.0.1/events','https://user:pass@example.com','https://[broken'):
            self.assertIsNone(public_url(url))
    def test_review_cooldowns(self):
        today=date(2026,11,7)
        self.assertFalse(eligible({'status':'accepted'},today));self.assertFalse(eligible({'status':'rejected'},today))
        self.assertFalse(eligible({'status':'deferred','next_review_after':'2026-11-08'},today))
        self.assertTrue(eligible({'status':'deferred','next_review_after':'2026-11-07'},today))
        self.assertFalse(eligible({'status':'adapter_needed'},today))
    def test_real_brief_bounded_and_spans_regions(self):
        b=build(today=date(2026,11,7))
        self.assertLessEqual(len(b['candidates']),b['budgets']['candidate_links'])
        self.assertEqual(len(b['gap_searches']),b['budgets']['gap_searches'])
        self.assertEqual(len({c['region'] for c in b['gap_searches']}),5)
        self.assertIn('unique_offerings',b['baseline'])
    def test_deterministic_same_week_and_rotating_searches(self):
        a=build(today=date(2026,11,7));b=build(today=date(2026,11,7));c=build(today=date(2026,11,14))
        self.assertEqual(a,b);self.assertNotEqual(a['gap_searches'],c['gap_searches'])
    def test_no_duplicate_candidates_or_excess_host_repetition(self):
        from collections import Counter
        from urllib.parse import urlsplit
        b=build();urls=[c['url'] for c in b['candidates']]
        self.assertEqual(len(urls),len(set(urls)))
        self.assertTrue(all(n<=b['budgets']['links_per_host'] for n in Counter(urlsplit(u).hostname for u in urls).values()))
    def test_accepted_proposal_excluded_from_next_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for path in ('data/weekly-discovery-policy.json','data/source-review-ledger.json','data/collection-sources.json','web/activities.json','data/source-proposals.json','data/activity-taxonomy.json'):
                p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text((ROOT/path).read_text())
            first=build(root);target=first['candidates'][0]['url']
            (root/'data/source-review-ledger.json').write_text(json.dumps({'reviews':[{'url':target,'status':'accepted'}],'runs':[]}))
            self.assertNotIn(target,[c['url'] for c in build(root)['candidates']])


if __name__=='__main__':unittest.main()
