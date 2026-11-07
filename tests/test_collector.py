import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from collect_activities import (TZ, age_rules, jsonld_events, normalize, reconcile,
                                structured_events, run, safe_url, columbia_event, explicit_age_guidance)
from validate_public_data import validate_public

SOURCE = {'id':'test','name':'Test','region':'Lawrence','city':'Lawrence','kind':'organizer','format':'jsonld','url':'https://example.test/events/'}
NOW = datetime(2026,11,7,10,tzinfo=TZ)


class CollectorTests(unittest.TestCase):
    def row(self):
        return normalize({'name':'Real &amp; Clear','startDate':'2026-11-08T13:00:00-06:00','url':'https://example.test/event/one'}, SOURCE,NOW.isoformat(),'https://example.test/event/one')

    def test_unknown_ages_never_inferred(self):
        self.assertEqual(age_rules('Family fun')['min'],None)
        self.assertTrue(age_rules('All ages')['all_ages'])
        self.assertEqual(age_rules('21+')['min'],21)
        self.assertEqual(age_rules('3–7')['max'],7)

    def test_explicit_audience_text_only(self):
        self.assertEqual(explicit_age_guidance('Workshop','For ages 6 to 12.')['min'],6)
        self.assertEqual(explicit_age_guidance('Concert 21+','')['min'],21)
        self.assertTrue(explicit_age_guidance('Art','Open to all ages')['all_ages'])
        self.assertIsNone(explicit_age_guidance('Exhibition','Artists of all ages contribute')['min'])
        self.assertIsNone(explicit_age_guidance('Exhibition','Featuring 20+ local artists')['min'])
        self.assertIsNone(explicit_age_guidance('Holiday visit','Children ages 3 to 9 pay $5. Adults pay $10.')['min'])

    def test_jsonld_graph_and_multiline_strings(self):
        body='<script type="application/ld+json">{"@graph":[{"@type":"MusicEvent","name":"Live\nMusic","startDate":"2026-11-08"}]}</script>'
        self.assertEqual(len(jsonld_events(body)),1)

    def test_date_only_preserves_all_day(self):
        row=normalize({'name':'Open studio','startDate':'2026-11-08'},SOURCE,NOW.isoformat(),'https://example.test/event')
        self.assertTrue(row['all_day']);self.assertEqual(row['ages']['min'],None)

    def test_bad_end_is_quarantined(self):
        with self.assertRaises(ValueError):normalize({'name':'Bad','startDate':'2026-11-08','endDate':'2026-11-07'},SOURCE,NOW.isoformat(),'https://example.test/event')

    def test_missing_events_stale_not_deleted(self):
        row=self.row();result=reconcile([row],[],[],NOW)
        self.assertTrue(result[0]['stale']);self.assertTrue(result[0]['disappeared']);self.assertEqual(result[0]['checked_at'],row['checked_at'])

    def test_expired_events_removed(self):
        row=self.row();row['schedule'].update(start_date='2026-11-01',end_date='2026-11-01')
        row.update(start='2026-11-01T13:00:00-06:00',date='2026-11-01',end_date='2026-11-01')
        self.assertEqual(reconcile([row],[],[],NOW),[])

    def test_cancelation_survives(self):
        row=self.row();fresh=dict(row,status='canceled');result=reconcile([row],[fresh],[],NOW)
        self.assertEqual(result[0]['status'],'canceled')

    def test_cancelled_title_overrides_schema_default(self):
        row=normalize({'name':'CANCELLED | Concert','startDate':'2026-11-08','eventStatus':'EventScheduled'},SOURCE,NOW.isoformat(),'https://example.test/event')
        self.assertEqual(row['status'],'canceled')

    def test_no_year_is_not_assigned_to_today(self):
        self.assertEqual(columbia_event('<h1>A party</h1><div class="event_date">November 7</div>','https://example.test'),[])

    def test_nextjs_data_decoded_without_eval(self):
        obj={'type':'special_event','uid':'walk','data':{'title':[{'text':'Penguin walk'}],'activity_time':[{'start_time':'2026-11-08T17:00:00+0000'}]}}
        payload='1:'+json.dumps(obj)
        body='<script>self.__next_f.push('+json.dumps([1,payload])+')</script>'
        rows=structured_events(body,dict(SOURCE,id='kc-zoo'))
        self.assertEqual(rows[0]['name'],'Penguin walk')

    def test_cross_scheme_links_rejected(self):
        self.assertIsNone(safe_url('javascript:alert(1)'));self.assertIsNone(safe_url('https://user:pass@example.test'))

    def test_failed_run_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);registry=r/'sources.json';out=r/'activities.json';registry.write_text(json.dumps({'sources':[SOURCE]}));out.write_text('{"activities":[]}')
            with patch('collect_activities.collect_source',return_value=([],{'visited_count':0,'events':0,'id':'test','status':'failed'})):
                with self.assertRaises(RuntimeError):run(registry,out,r/'cache',NOW)
            self.assertEqual(out.read_text(),'{"activities":[]}')

    def test_public_dataset(self):
        if (ROOT/'web/activities.json').exists():validate_public(json.loads((ROOT/'web/activities.json').read_text()))


if __name__=='__main__':unittest.main()
