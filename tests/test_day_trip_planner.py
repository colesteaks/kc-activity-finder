import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from day_trip_planner import evaluate


def research():
    return json.loads((ROOT/'examples/day-trip-research.json').read_text())


class DayTripTests(unittest.TestCase):
    def test_fixture_checks_limits_and_full_itinerary(self):
        result=evaluate(research())
        self.assertEqual(result['route_checks']['river-town']['status'],'within_limit')
        self.assertEqual(result['route_checks']['far-town']['status'],'over_limit')
        self.assertEqual(result['itinerary_check']['status'],'mechanically_feasible')
        self.assertEqual(result['itinerary_check']['total_driving_minutes'],200)
        self.assertTrue(result['source_graph_digest'])

    def test_discovery_needs_no_date_or_invented_event_times(self):
        data=research();data['request'].update(date=None,depart_at=None,return_by=None);data['itinerary']=None
        data['destinations'][0]['anchors'][0]['open_windows']=[]
        result=evaluate(data)
        self.assertEqual(result['itinerary_check']['status'],'not_requested')
        self.assertEqual(result['route_checks']['river-town']['status'],'within_limit')

    def test_one_way_and_round_trip_are_not_interchangeable(self):
        data=research();data['request']['drive_limit_basis']='round_trip'
        self.assertEqual(evaluate(data)['route_checks']['river-town']['status'],'over_limit')
        data['request']['max_drive_minutes']=190
        self.assertEqual(evaluate(data)['route_checks']['river-town']['status'],'within_limit')

    def test_return_drive_must_also_fit_one_way_limit(self):
        data=research();data['destinations'][0]['route']['return_max_minutes']=121
        self.assertEqual(evaluate(data)['route_checks']['river-town']['status'],'over_limit')

    def test_missing_rough_stale_future_or_wrong_origin_routes_unverified(self):
        for defect in ('missing','rough','stale','future','origin','destination','return'):
            with self.subTest(defect=defect):
                data=research();route=data['destinations'][0]['route']
                if defect=='missing':data['destinations'][0]['route']=None
                if defect=='rough':route['method']='rough_estimate'
                if defect=='stale':route['checked_at']='2030-06-01T12:00:00-05:00'
                if defect=='future':route['checked_at']='2030-06-15T12:00:00-05:00'
                if defect=='origin':route['origin']='Different suburb'
                if defect=='destination':route['destination']='Different town'
                if defect=='return':route['return_max_minutes']=None
                result=evaluate(data)
                self.assertEqual(result['route_checks']['river-town']['status'],'unverified')
                self.assertEqual(result['itinerary_check']['status'],'blocked')

    def test_itinerary_requires_date_and_return_leg(self):
        for defect in ('date','return'):
            data=research()
            if defect=='date':data['request']['date']=None
            if defect=='return':data['itinerary']['steps'].pop()
            self.assertEqual(evaluate(data)['itinerary_check']['status'],'blocked')

    def test_overlap_late_return_and_wrong_local_day_are_blocked(self):
        for defect in ('overlap','late','day'):
            data=research()
            if defect=='overlap':data['itinerary']['steps'][2]['start']='2030-06-15T09:50:00-05:00'
            if defect=='late':data['request']['return_by']='2030-06-15T14:00:00-05:00'
            if defect=='day':data['request']['date']='2030-06-16'
            self.assertEqual(evaluate(data)['itinerary_check']['status'],'blocked')

    def test_local_driving_counts_toward_total_budget(self):
        data=research();data['request']['max_total_driving_minutes']=200
        data['itinerary']['steps'][3].update(kind='drive',drive_role='local',travel_minutes=15)
        result=evaluate(data)
        self.assertEqual(result['route_checks']['river-town']['status'],'within_limit')
        self.assertEqual(result['itinerary_check']['total_driving_minutes'],215)
        self.assertEqual(result['itinerary_check']['status'],'blocked')

    def test_transfer_cannot_be_omitted_between_stops(self):
        data=research();data['itinerary']['steps'][3].update(kind='buffer',travel_minutes=None,route_source_url=None,note='Walking mentioned in prose is not a transfer record')
        self.assertEqual(evaluate(data)['itinerary_check']['status'],'blocked')

    def test_round_trip_limit_includes_local_driving_and_allocated_drive_time(self):
        data=research();data['request'].update(drive_limit_basis='round_trip',max_drive_minutes=200)
        data['itinerary']['steps'][3].update(kind='drive',drive_role='local',travel_minutes=15)
        result=evaluate(data)
        self.assertEqual(result['route_checks']['river-town']['status'],'within_limit')
        self.assertEqual(result['itinerary_check']['status'],'blocked')
        self.assertTrue(any('round-trip' in reason for reason in result['itinerary_check']['errors']))

    def test_activity_needs_hours_duration_freshness_and_booking(self):
        for defect in ('hours','duration','stale','booking','sold_out','registration'):
            with self.subTest(defect=defect):
                data=research();anchor=data['destinations'][0]['anchors'][0]
                if defect=='hours':anchor['open_windows']=[]
                if defect=='duration':anchor['duration_minutes']=120
                if defect=='stale':anchor['checked_at']='2030-06-10T12:00:00-05:00'
                if defect=='booking':anchor['booking_status']='needed'
                if defect=='sold_out':anchor['availability']='sold_out'
                if defect=='registration':anchor['availability']='registration_required'
                self.assertEqual(evaluate(data)['itinerary_check']['status'],'blocked')

    def test_drive_duration_cannot_understate_route_evidence(self):
        data=research();data['itinerary']['steps'][0]['travel_minutes']=20
        self.assertEqual(evaluate(data)['itinerary_check']['status'],'blocked')
        data=research();data['itinerary']['steps'][0]['end']='2030-06-15T09:00:00-05:00'
        self.assertEqual(evaluate(data)['itinerary_check']['status'],'blocked')

    def test_duplicate_ids_and_unsafe_evidence_are_rejected(self):
        data=research();data['destinations'].append(copy.deepcopy(data['destinations'][0]))
        with self.assertRaisesRegex(ValueError,'Duplicate'):evaluate(data)
        data=research();data['destinations'][0]['anchors'][0]['url']='javascript:alert(1)'
        with self.assertRaises(ValueError):evaluate(data)

    def test_live_clock_cannot_reuse_fictional_future_research(self):
        data=research();data['fixture']=False
        with self.assertRaisesRegex(ValueError,'Live research clock'):evaluate(data)

    def test_cli_reports_blocked_itinerary_with_nonzero_exit(self):
        data=research();data['request']['return_by']='2030-06-15T10:00:00-05:00'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trip.json';path.write_text(json.dumps(data))
            result=subprocess.run([sys.executable,str(ROOT/'scripts/day_trip_planner.py'),str(path)],capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertEqual(json.loads(result.stdout)['itinerary_check']['status'],'blocked')


if __name__=='__main__':unittest.main()
