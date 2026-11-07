#!/usr/bin/env python3
"""Check researched driving limits and a proposed day-trip schedule, without API/model calls.

This is a feasibility checker, not a search service, booking service or live-hours oracle.
The skill performs first-party research, ranking and adversarial review separately.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from activity_pipeline import ROOT, graph_identity, load, timestamp, url, validate


def elapsed(start, end):
    return (timestamp(end) - timestamp(start)).total_seconds() / 60


def fresh(checked_at, as_of, hours):
    if checked_at is None:
        return False
    age = timestamp(as_of) - timestamp(checked_at)
    return timedelta(0) <= age <= timedelta(hours=hours)


def route_check(destination, request):
    route = destination['route']
    reasons = []
    if route is None:
        return {'status': 'unverified', 'reasons': ['Missing driving-route evidence']}
    if route['origin'].strip().casefold() != request['origin'].strip().casefold():
        reasons.append('Route origin does not match the requested origin')
    if route['destination'].strip().casefold() != destination['name'].strip().casefold():
        reasons.append('Route destination does not match this destination')
    if route['method'] != 'routing_estimate' or not route['source_url']:
        reasons.append('A rough estimate or straight-line distance cannot establish a driving limit')
    if not fresh(route['checked_at'], request['as_of'], 7 * 24):
        reasons.append('Route evidence is missing, future-dated or more than seven days old')
    out, back = route['outbound_max_minutes'], route['return_max_minutes']
    if out is None or back is None:
        reasons.append('Both directional driving estimates are needed')
    if reasons:
        return {'status': 'unverified', 'reasons': reasons}
    # A one-way limit applies in either direction, rather than allowing an over-limit return.
    duration = max(out, back) if request['drive_limit_basis'] == 'one_way' else out + back
    if duration > request['max_drive_minutes']:
        return {'status': 'over_limit', 'reasons': ['Conservative route estimate exceeds the requested driving limit']}
    if request['max_total_driving_minutes'] is not None and out + back > request['max_total_driving_minutes']:
        return {'status': 'over_limit', 'reasons': ['Out-and-back driving already exceeds the total driving budget']}
    return {'status': 'within_limit', 'reasons': [], 'outbound_max_minutes': out, 'return_max_minutes': back,
            'note': 'Routing estimate only; traffic, weather, stops and local travel may add time.'}


def check_itinerary(data, routes):
    itinerary, request = data['itinerary'], data['request']
    if itinerary is None:
        return {'status': 'not_requested', 'errors': [], 'note': 'Destination exploration is not a date-verified itinerary.'}
    errors = []
    destination = next((d for d in data['destinations'] if d['id'] == itinerary['destination_id']), None)
    if destination is None:
        return {'status': 'blocked', 'errors': ['Unknown itinerary destination']}
    if routes[destination['id']]['status'] != 'within_limit':
        errors.append('Destination has not passed the driving-limit check')
    if request['date'] is None or request['depart_at'] is None or request['return_by'] is None:
        errors.append('A dated plan needs an exact date, departure and latest return')
    anchors = {a['id']: a for a in destination['anchors']}
    steps = itinerary['steps']
    drives = [s for s in steps if s['kind'] == 'drive']
    if not steps or steps[0]['drive_role'] != 'outbound' or steps[-1]['drive_role'] != 'return':
        errors.append('Plan must include the outbound and return drive as its first and last steps')
    if sum(s['drive_role'] == 'outbound' for s in drives) != 1 or sum(s['drive_role'] == 'return' for s in drives) != 1:
        errors.append('Exactly one outbound and one return drive are required')
    if not any(s['kind'] == 'activity' for s in steps):
        errors.append('Plan needs at least one anchor activity')
    total_drive = 0
    previous = None
    previous_activity_index = None
    for index, step in enumerate(steps):
        start, end = timestamp(step['start']), timestamp(step['end'])
        prefix = f'Step {index + 1}: '
        if end <= start:
            errors.append(prefix + 'End must follow start')
        if previous and start < previous:
            errors.append(prefix + 'Overlaps the previous step')
        previous = end
        if request['date'] and (start.astimezone(ZoneInfo(request['timezone'])).date().isoformat() != request['date'] or end.astimezone(ZoneInfo(request['timezone'])).date().isoformat() != request['date']):
            errors.append(prefix + 'Falls outside the requested local day')
        if request['depart_at'] and start < timestamp(request['depart_at']):
            errors.append(prefix + 'Starts before departure')
        if request['return_by'] and end > timestamp(request['return_by']):
            errors.append(prefix + 'Exceeds the latest return')
        duration = elapsed(step['start'], step['end'])
        if step['kind'] == 'drive':
            if step['drive_role'] is None or step['travel_minutes'] is None or not step['route_source_url']:
                errors.append(prefix + 'Driving leg needs its role, estimate and route evidence')
            else:
                total_drive += max(duration, step['travel_minutes'])
                if duration < step['travel_minutes']:
                    errors.append(prefix + 'Insufficient time for the driving estimate')
                route = destination['route']
                required = route.get(step['drive_role'] + '_max_minutes') if route else None
                if step['drive_role'] in ('outbound', 'return') and (required is None or step['travel_minutes'] < required):
                    errors.append(prefix + 'Driving estimate understates the destination route')
            if step['activity_id'] is not None:
                errors.append(prefix + 'Driving cannot also be an activity visit')
        elif step['kind'] == 'walk':
            if step['drive_role'] is not None or step['travel_minutes'] is None or not step['route_source_url']:
                errors.append(prefix + 'Walking transfer needs its estimate and map/route evidence')
            elif duration < step['travel_minutes']:
                errors.append(prefix + 'Insufficient time for the walking transfer')
        elif step['drive_role'] is not None or step['travel_minutes'] is not None:
            errors.append(prefix + 'Non-driving steps cannot carry driving estimates')
        if step['kind'] == 'activity':
            if previous_activity_index is not None and not any(s['kind'] == 'walk' or (s['kind'] == 'drive' and s['drive_role'] == 'local') for s in steps[previous_activity_index + 1:index]):
                errors.append(prefix + 'Activity stops need an explicit walking or local-driving transfer between them')
            previous_activity_index = index
            anchor = anchors.get(step['activity_id'])
            if anchor is None:
                errors.append(prefix + 'Unknown anchor activity')
                continue
            if anchor['availability'] not in ('available', 'registration_required'):
                errors.append(prefix + 'Activity is unavailable or unresolved')
            if anchor['booking_status'] not in ('not_required', 'confirmed') or (anchor['availability'] == 'registration_required' and anchor['booking_status'] != 'confirmed'):
                errors.append(prefix + 'Booking still needs action or confirmation')
            if not fresh(anchor['checked_at'], request['as_of'], 48):
                errors.append(prefix + 'Activity evidence needs a fresh check')
            if anchor['duration_minutes'] is None or duration < anchor['duration_minutes']:
                errors.append(prefix + 'Visit duration is unknown or too short')
            if not any(timestamp(w['start']) <= start and end <= timestamp(w['end']) for w in anchor['open_windows']):
                errors.append(prefix + 'Visit does not fit a verified operating/session window')
        elif step['activity_id'] is not None:
            errors.append(prefix + 'Only activity visits can reference an anchor')
    if request['max_total_driving_minutes'] is not None and total_drive > request['max_total_driving_minutes']:
        errors.append('Driving including local transfers exceeds the total driving budget')
    if request['drive_limit_basis'] == 'round_trip' and total_drive > request['max_drive_minutes']:
        errors.append('Driving including local transfers exceeds the round-trip driving limit')
    return {'status': 'blocked' if errors else 'mechanically_feasible', 'errors': errors,
            'total_driving_minutes': total_drive,
            'note': 'Timing check only. The researcher must still verify party eligibility, costs, access, weather, route endpoints and bookings; this does not reserve anything.'}


def evaluate(data):
    validate(data, 'day-trip')
    request = data['request']
    ZoneInfo(request['timezone'])
    timestamp(request['as_of'])
    if not data['fixture'] and abs(datetime.now(timezone.utc) - timestamp(request['as_of'])) > timedelta(hours=24):
        raise ValueError('Live research clock must be within 24 hours; refresh research before use')
    for key in ('depart_at', 'return_by'):
        if request[key]: timestamp(request[key])
    if request['depart_at'] and request['return_by'] and timestamp(request['return_by']) <= timestamp(request['depart_at']):
        raise ValueError('Latest return must follow departure')
    ids = [d['id'] for d in data['destinations']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate destination IDs')
    for destination in data['destinations']:
        anchor_ids = [a['id'] for a in destination['anchors']]
        if len(anchor_ids) != len(set(anchor_ids)):
            raise ValueError('Duplicate anchor IDs within a destination')
        route = destination['route']
        if route and route['source_url']: url(route['source_url'])
        if route and route['checked_at']: timestamp(route['checked_at'])
        for anchor in destination['anchors']:
            url(anchor['url']); timestamp(anchor['checked_at'])
            for window in anchor['open_windows']:
                if timestamp(window['end']) <= timestamp(window['start']):
                    raise ValueError('Reversed activity operating window')
    if data['itinerary']:
        for step in data['itinerary']['steps']:
            if step['route_source_url']: url(step['route_source_url'])
    routes = {d['id']: route_check(d, request) for d in data['destinations']}
    return {'version': 1, 'fixture': data['fixture'], 'as_of': request['as_of'],
            'source_graph_digest': graph_identity(load(ROOT / 'data/source-graph.json')),
            'route_checks': routes, 'itinerary_check': check_itinerary(data, routes),
            'limitations': ['Does not browse, rank destination quality or prove source coverage/review.',
                            'A within-limit route is not a verified or bookable activity recommendation.',
                            'Retain the research inventory, sources and tradeoffs in the skill report.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('research', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = evaluate(load(args.research))
    output = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output: args.output.write_text(output, encoding='utf-8')
    else: print(output, end='')
    return 2 if result['itinerary_check']['status'] == 'blocked' else 0


if __name__ == '__main__':
    raise SystemExit(main())
