import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from activity_model import schedule_model,coverage_matrix,in_horizon
from collect_activities import normalize
from validate_public_data import validate_public
SOURCE={'id':'official','name':'Official','city':'Kansas City','region':'Kansas City metro','kind':'organizer','format':'jsonld'}
OBSERVED='2026-11-07T10:00:00-06:00'

class ActivityModelTests(unittest.TestCase):
    def test_evergreen_has_no_fabricated_event_date(self):
        row=normalize({'name':'Hiking trail','_schedule':{'kind':'evergreen'}},SOURCE,OBSERVED,'https://example.test/trail')
        self.assertIsNone(row['start']);self.assertIsNone(row['date']);self.assertTrue(in_horizon(row,'2027-01-01','2027-06-01'));self.assertEqual(row['status'],'listed')
    def test_missing_date_without_explicit_offering_is_unresolved(self):
        self.assertIsNone(normalize({'name':'News article'},SOURCE,OBSERVED,'https://example.test'))
    def test_season_and_signup_window_are_independent(self):
        raw={'name':'Fixture: spring league','startDate':'2027-03-01','endDate':'2027-05-30','_schedule':{'kind':'sports_season'},'_registration':{'status':'open','opens_at':'2026-11-01','deadline':'2027-02-01','url':'https://example.test/signup','note':'Fixture only'},'_commitment':{'attendance':'team_season','duration':'12 weeks','equipment':None,'note':'Fixture only'}}
        row=normalize(raw,SOURCE,OBSERVED,'https://example.test/season');self.assertEqual(row['schedule']['start_date'],'2027-03-01');self.assertEqual(row['registration']['deadline'],'2027-02-01');self.assertEqual(row['commitment']['attendance'],'team_season');self.assertFalse(in_horizon(row,'2026-11-01','2026-12-01'))
    def test_exhibit_window_is_not_daily_opening_hours(self):
        s=schedule_model({'@type':'ExhibitionEvent'},'2026-10-01T09:00:00-05:00','2027-02-01T18:00:00-06:00');self.assertEqual(s['kind'],'exhibit');self.assertIsNone(s['operating_hours']);self.assertEqual(s['sessions'],[])
    def test_ambiguous_multiday_not_inferred_as_league_or_exhibit(self):
        self.assertEqual(schedule_model({'name':'Registration announcement'},'2026-11-01','2027-05-01')['kind'],'date_range_unknown')
    def test_registration_title_does_not_create_a_season(self):
        self.assertEqual(schedule_model({'name':'Soccer registration'},'2026-11-01',None)['kind'],'one_off')
    def test_unknown_program_dates_are_preserved(self):
        row=normalize({'name':'Soccer program','_schedule':{'kind':'recurring_program'}},SOURCE,OBSERVED,'https://example.test/program');self.assertEqual(row['schedule']['kind'],'recurring_program');self.assertIsNone(row['schedule']['end_date'])
    def test_stable_offering_id_across_sessions(self):
        a=normalize({'name':'Pottery','startDate':'2027-01-01'},SOURCE,OBSERVED,'https://example.test/course');b=normalize({'name':'Pottery','startDate':'2027-01-08'},SOURCE,OBSERVED,'https://example.test/course');self.assertNotEqual(a['id'],b['id']);self.assertEqual(a['offering_id'],b['offering_id'])
    def test_every_category_region_pair_is_audited(self):
        registry=json.loads((ROOT/'data/collection-sources.json').read_text())['sources'];tax=json.loads((ROOT/'data/activity-taxonomy.json').read_text());matrix=coverage_matrix(registry,tax);self.assertEqual(len(matrix['category_by_region']),len(tax['categories'])*len(tax['regions']));self.assertTrue(any(c['status']=='gap' for c in matrix['category_by_region']))
        for kind in ('sports_season','evergreen','exhibit'):self.assertTrue(next(c for c in matrix['activity_kinds'] if c['kind']==kind)['routes'])
    def test_registry_categories_are_known(self):
        known={c['id'] for c in json.loads((ROOT/'data/activity-taxonomy.json').read_text())['categories']}
        for s in json.loads((ROOT/'data/collection-sources.json').read_text())['sources']:self.assertTrue(set(s['categories'])<=known);self.assertTrue(s['activity_kinds'])
    def test_orphan_parent_rejected(self):
        d=json.loads((ROOT/'web/activities.json').read_text());d['activities'][0]['parent_id']='missing-parent'
        with self.assertRaises(AssertionError):validate_public(d)
if __name__=='__main__':unittest.main()
