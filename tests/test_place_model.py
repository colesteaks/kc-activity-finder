import copy
import json
import sys
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from place_model import attach_place, places, public_places, valid_coordinates, normalized
from refresh_sources import add_place_leaves
from validate_public_data import validate_public


class PlaceTests(unittest.TestCase):
    def row(self, source='weston-bend', venue='Weston Bend State Park'):
        return {'source_id':source,'venue':venue,'evidence':{'url':'https://example.test/event'},'checked_at':'2026-11-07T12:00:00Z'}

    def test_source_and_venue_both_required(self):
        self.assertEqual(attach_place(self.row())['place_id'],'weston-bend')
        self.assertIsNone(attach_place(self.row(venue='Offsite brewery'))['geo'])
        self.assertIsNone(attach_place(self.row(source='unrelated'))['geo'])

    def test_museum_hours_do_not_inherit_trail_hours(self):
        row=attach_place(self.row('crystal-bridges','Great Hall'))
        self.assertEqual(row['place_id'],'crystal-museum')
        self.assertIsNone(next(p for p in places() if p['id']==row['place_id'])['hours'])

    def test_event_location_coordinate_precedence_and_provenance(self):
        raw={'location':{'geo':{'latitude':'39.4','longitude':'-94.8'}}}
        row=attach_place(self.row(),raw)
        self.assertEqual(row['geo']['lat'],39.4)
        self.assertEqual(row['geo']['precision'],'source_point')
        self.assertEqual(row['geo']['source_url'],row['evidence']['url'])

    def test_invalid_coordinates_never_become_pins(self):
        for lat,lng in ((True,0),(float('nan'),1),(0,float('inf')),(91,0),(0,181)):
            self.assertFalse(valid_coordinates(lat,lng))
            self.assertIsNone(attach_place(self.row('unmapped'),{'location':{'geo':{'latitude':lat,'longitude':lng}}})['geo'])

    def test_unique_identity_aliases_and_schema(self):
        identities=set()
        validator=Draft202012Validator(json.loads((ROOT/'schemas/place.schema.json').read_text()),format_checker=FormatChecker())
        for p in places():
            for source in p['match']['source_ids']:
                for alias in p['match']['venue_aliases']:
                    identity=(source,normalized(alias))
                    self.assertNotIn(identity,identities);identities.add(identity)
        for p in public_places(): validator.validate(p)

    def test_registry_is_not_mutated_by_attachment(self):
        row=attach_place(self.row());row['geo']['lat']=0
        self.assertNotEqual(attach_place(self.row())['geo']['lat'],0)
        self.assertNotIn('match',public_places()[0])

    def test_graph_keeps_official_hours_and_offering_leaves(self):
        graph={'nodes':[{'id':'weston-bend'}]};add_place_leaves(graph)
        self.assertEqual(graph['nodes'][0]['place_ids'],['weston-bend'])
        leaf=next(p for p in graph['place_leaves'] if p['id']=='weston-bend')
        self.assertIn('/hours/',leaf['hours_source']);self.assertTrue(leaf['offering_sources'])

    def test_public_validator_rejects_invalid_hours_and_orphan_places(self):
        original=json.loads((ROOT/'web/activities.json').read_text())
        for defect in ('clock','season','orphan'):
            data=copy.deepcopy(original)
            if defect=='clock':data['places'][0]['hours']['rules'][0]['opens']='29:00'
            if defect=='season':data['places'][0]['hours']['rules'][1]['season_start']='02-30'
            if defect=='orphan':data['activities'][0]['place_id']='not-a-place'
            with self.assertRaises(Exception):validate_public(data)


if __name__=='__main__':unittest.main()
