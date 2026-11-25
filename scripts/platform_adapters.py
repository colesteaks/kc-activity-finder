"""Reusable platform-class calendar and schedule adapters (zero-LLM, explicit-date only)."""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from dateutil.parser import isoparse, parse
from dateutil.rrule import rrulestr

TZ = ZoneInfo('America/Chicago')
FULL_DATE = r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d\d'
ISO_DATE = r'\b20\d\d-\d{2}-\d{2}\b'

_CATEGORY_KEYWORDS = (
    ('outdoor_recreation', r'\bhik(?:e|ing)\b|\btrail\b|\bpaddl|\bcanoe|\bkayak|\bcamp(?:ing)?\b|\bfish(?:ing)?\b|\bbird(?:ing)?\b|\barchery\b|\bconservat'),
    ('nature_animals', r'\bnature\b|\bwildlife\b|\bconservation\b|\bplant|\bgarden\b|\bbutterfly|\bzoo\b|\bbird'),
    ('sports_participation', r'\bleague\b|\btournament\b|\bswim|\bathletic|\bsoccer\b|\bpickleball\b|\b5k\b|\bmarathon\b|\brun\b'),
    ('sports_spectating', r'\bbaseball\b|\bhockey\b|\bfootball\b|\bbasketball\b|\bsoccer\b|\bvs\.?\b|\bat\b'),
    ('arts_exhibits', r'\bart\b|\bexhibit|\bgallery\b|\bmuseum\b|\bpaint|\bceramics\b|\bsculpt'),
    ('music_performance', r'\bconcert\b|\bmusic\b|\bsymphony\b|\bopera\b|\btheat(?:er|re)\b|\bcomedy\b|\bdance\b|\bjazz\b|\bband\b'),
    ('film_literature', r'\bfilm\b|\bcinema\b|\bmovie\b|\bbook\b|\bauthor\b|\bpoetry\b|\breading\b'),
    ('libraries_learning', r'\blibrary\b|\bstorytime\b|\bstory\s*time\b|\bhomework\b|\bliteracy\b'),
    ('science_technology', r'\bscience\b|\bplanetarium\b|\bastronomy\b|\bstem\b|\brobot|\bcoding\b|\bmaker'),
    ('classes_skills', r'\bclass\b|\bworkshop\b|\blesson\b|\blecture\b|\bseminar\b|\btraining\b'),
    ('food_drink', r'\bfood\b|\btasting\b|\bcooking\b|\bculinary\b|\bbrew|\bwine\b|\bfarmers\s*market'),
    ('markets_shopping', r'\bmarket\b|\bcraft\s*fair\b|\bvendor\b|\bflea\b'),
    ('festivals_seasonal', r'\bfestival\b|\bfest\b|\bparade\b|\bholiday\b|\bhalloween\b|\bchristmas\b'),
    ('games_hobbies', r'\bboard\s*game|\bchess\b|\btrivia\b|\bd&d\b|\bknitting\b|\bcrochet'),
    ('volunteering', r'\bvolunteer\b|\bcleanup\b|\bstewardship\b'),
    ('adaptive_inclusive', r'\badaptive\b|\bsensory[- ]friendly\b|\binclusive\b|\basl\b|\bwheelchair\b'),
    ('history_culture', r'\bhistory\b|\bhistoric\b|\bheritage\b|\bcultural\b'),
    ('travel_exploration', r'\bwalking\s*tour\b|\btour\b'),
)


def _text(node) -> str:
    return node.get_text(' ', strip=True) if node is not None else ''


def _infer_cats(*parts: str) -> list[str]:
    blob = ' '.join(str(p or '') for p in parts).lower()
    found = [cid for cid, pat in _CATEGORY_KEYWORDS if re.search(pat, blob)]
    return found


def _explicit_date_from_text(blob: str) -> str | None:
    m = re.search(FULL_DATE, blob)
    if m:
        try:
            return parse(m[0], fuzzy=False).date().isoformat()
        except (ValueError, OverflowError):
            pass
    m2 = re.search(ISO_DATE, blob)
    if m2:
        return m2[0]
    return None


def _unescape_ics(value: str) -> str:
    return (
        value.replace('\\n', '\n')
        .replace('\\N', '\n')
        .replace('\\,', ',')
        .replace('\\;', ';')
        .replace('\\\\', '\\')
    )


def _parse_ics_dt(raw_val: str, tzid: str | None = None) -> tuple[str | None, bool, datetime | None]:
    val = raw_val.strip()
    if re.fullmatch(r'20\d{6}', val):
        dt = datetime.strptime(val, '%Y%m%d')
        return dt.date().isoformat(), True, dt.replace(tzinfo=TZ)
    m = re.fullmatch(r'(20\d{6})T(\d{6})(Z?)', val)
    if not m:
        return None, False, None
    naive = datetime.strptime(m[1] + m[2], '%Y%m%d%H%M%S')
    if m[3] == 'Z':
        aware = naive.replace(tzinfo=ZoneInfo('UTC')).astimezone(TZ)
        return aware.isoformat(), False, aware
    zone = TZ
    if tzid:
        try:
            zone = ZoneInfo(tzid)
        except Exception:
            zone = TZ
    aware = naive.replace(tzinfo=zone).astimezone(TZ)
    return aware.isoformat(), False, aware


def ics_events(
    body: str,
    source: dict,
    page: str,
    start_date: date | None = None,
    end_date: date | None = None,
    max_instances: int = 60,
) -> list[dict]:
    """Parse RFC 5545 iCalendar (.ics) feeds, including explicit RRULE and EXDATE."""
    unfolded = re.sub(r'\r?\n[ \t]', '', body)
    lines = unfolded.splitlines()
    rows: list[dict] = []
    current: dict | None = None

    for line in lines:
        stripped = line.strip()
        if stripped == 'BEGIN:VEVENT':
            current = {'exdates': []}
            continue
        if stripped == 'END:VEVENT':
            if current is not None:
                rows.extend(_materialize_vevent(current, source, page, start_date, end_date, max_instances))
            current = None
            continue
        if current is None or ':' not in line:
            continue
        key_part, val = line.split(':', 1)
        parts = key_part.split(';')
        prop = parts[0].upper()
        params = {}
        for p in parts[1:]:
            if '=' in p:
                pk, pv = p.split('=', 1)
                params[pk.upper()] = pv.strip('"')
        if prop == 'EXDATE':
            for item in val.split(','):
                iso, _, _ = _parse_ics_dt(item, params.get('TZID'))
                if iso:
                    current['exdates'].append(iso)
        else:
            current[prop] = (val, params)

    return rows


def _materialize_vevent(
    ev: dict,
    source: dict,
    page: str,
    start_date: date | None,
    end_date: date | None,
    max_instances: int,
) -> list[dict]:
    summary_raw = ev.get('SUMMARY', ('', {}))[0]
    title = _unescape_ics(summary_raw).strip()
    if not title or 'DTSTART' not in ev:
        return []
    dtstart_val, dtstart_params = ev['DTSTART']
    start_iso, all_day, start_dt = _parse_ics_dt(dtstart_val, dtstart_params.get('TZID'))
    if not start_iso or start_dt is None:
        return []
    end_iso, end_dt = None, None
    if 'DTEND' in ev:
        dtend_val, dtend_params = ev['DTEND']
        end_iso, _, end_dt = _parse_ics_dt(dtend_val, dtend_params.get('TZID'))
        if end_dt and end_dt < start_dt:
            end_iso, end_dt = None, None

    url_val = ev.get('URL', ('', {}))[0].strip() or page
    url = urljoin(page, url_val)
    loc_name = _unescape_ics(ev.get('LOCATION', ('', {}))[0]).strip() or source['name']
    desc = _unescape_ics(ev.get('DESCRIPTION', ('', {}))[0]).strip()
    status_val = ev.get('STATUS', ('', {}))[0].strip().upper()
    ev_status = 'EventCancelled' if status_val == 'CANCELLED' else 'EventScheduled'
    cats_raw = _unescape_ics(ev.get('CATEGORIES', ('', {}))[0])
    geo_dict = None
    if 'GEO' in ev:
        geo_parts = ev['GEO'][0].split(';')
        if len(geo_parts) == 2:
            try:
                geo_dict = {'latitude': float(geo_parts[0]), 'longitude': float(geo_parts[1])}
            except ValueError:
                geo_dict = None

    loc_obj: dict = {'name': loc_name}
    if geo_dict:
        loc_obj['geo'] = geo_dict

    cats = _infer_cats(title, cats_raw, desc)
    rrule_val = ev.get('RRULE', ('', {}))[0].strip()
    exdates = ev.get('exdates', [])

    base_row: dict = {
        'name': title,
        'startDate': start_iso,
        'endDate': end_iso,
        'url': url,
        'location': loc_obj,
        'description': desc,
        'keywords': cats_raw,
        'eventStatus': ev_status,
        '_all_day': all_day,
        '_evidence_quote': f'ICS {dtstart_val}' + (f' ({rrule_val})' if rrule_val else ''),
    }
    if cats:
        base_row['_categories'] = cats

    if not rrule_val or not rrule_val.upper().startswith('FREQ='):
        return [base_row]

    # Expand bounded occurrences from explicit RRULE, preserving recurrence metadata.
    ex_dates_only = {x[:10] for x in exdates}
    duration = (end_dt - start_dt) if end_dt else None
    w_start = start_date or start_dt.date()
    w_end = end_date or (w_start + timedelta(days=210))
    try:
        # Use naive local dtstart and naive UNTIL so dateutil.rrule avoids mixed naive/aware errors.
        rrule_clean = re.sub(
            r'UNTIL=(\d{8})T(\d{6})Z',
            lambda m: 'UNTIL=' + datetime.strptime(m[1] + m[2], '%Y%m%d%H%M%S')
            .replace(tzinfo=ZoneInfo('UTC'))
            .astimezone(TZ)
            .strftime('%Y%m%dT%H%M%S'),
            rrule_val,
        )
        rule = rrulestr(rrule_clean, dtstart=start_dt.replace(tzinfo=None))
        win_start_dt = datetime.combine(w_start, datetime.min.time())
        win_end_dt = datetime.combine(w_end, datetime.max.time())
        occurrences = []
        for occ in rule.between(win_start_dt, win_end_dt, inc=True):
            occ_aware = occ.replace(tzinfo=TZ)
            if occ_aware.date().isoformat() in ex_dates_only:
                continue
            occ_start = occ_aware.date().isoformat() if all_day else occ_aware.isoformat()
            occ_end = None
            if duration is not None:
                end_occ = occ_aware + duration
                occ_end = end_occ.date().isoformat() if all_day else end_occ.isoformat()
            item = dict(base_row)
            item['startDate'] = occ_start
            item['endDate'] = occ_end
            item['_schedule'] = {
                'kind': 'recurring_program',
                'start_date': occ_aware.date().isoformat(),
                'end_date': (occ_aware + duration).date().isoformat() if duration else occ_aware.date().isoformat(),
                'recurrence': {'rrule': rrule_val, 'timezone': 'America/Chicago', 'exdates': exdates},
                'note': 'Expanded from official iCalendar RRULE within collection horizon.',
            }
            occurrences.append(item)
            if len(occurrences) >= max_instances:
                break
        if occurrences:
            return occurrences
    except Exception:
        pass

    base_row['_schedule'] = {
        'kind': 'recurring_program',
        'start_date': start_dt.date().isoformat(),
        'end_date': end_dt.date().isoformat() if end_dt else None,
        'recurrence': {'rrule': rrule_val, 'timezone': 'America/Chicago', 'exdates': exdates},
        'note': 'Official iCalendar RRULE entry; confirm individual session dates with organizer.',
    }
    return [base_row]


def _xml_child_text(node, names: tuple[str, ...]) -> str:
    for child in node:
        local = child.tag.split('}')[-1].lower()
        if local in names:
            return ''.join(child.itertext()).strip()
    return ''


def rss_events(body: str, source: dict, page: str) -> list[dict]:
    """Parse RSS 2.0 / Atom feeds with explicit event dates (never inventing missing years)."""
    try:
        root = ET.fromstring(body.strip())
    except ET.ParseError:
        return []
    rows: list[dict] = []
    root_local = root.tag.split('}')[-1].lower()
    if root_local == 'feed':
        items = [c for c in root if c.tag.split('}')[-1].lower() == 'entry']
    else:
        channel = next((c for c in root if c.tag.split('}')[-1].lower() == 'channel'), root)
        items = [c for c in channel if c.tag.split('}')[-1].lower() == 'item']

    for item in items:
        title = _xml_child_text(item, ('title',))
        if not title:
            continue
        link = _xml_child_text(item, ('link',))
        if not link:
            for c in item:
                if c.tag.split('}')[-1].lower() == 'link' and c.get('href'):
                    link = c.get('href', '')
                    break
        desc = _xml_child_text(item, ('description', 'summary', 'content'))
        ev_start = _xml_child_text(item, ('startdate', 'start_date', 'eventdate', 'dtstart'))
        ev_end = _xml_child_text(item, ('enddate', 'end_date', 'dtend'))
        if not ev_start:
            # Check explicit year-bearing date in title/description (never pubDate alone, which is post publish time).
            ev_start = _explicit_date_from_text(title + ' ' + desc)
        if not ev_start or not re.search(r'\b20\d\d\b', ev_start):
            continue
        try:
            if re.fullmatch(ISO_DATE, ev_start):
                start_iso = ev_start
                all_day = True
            else:
                parsed = parse(ev_start)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=TZ)
                start_iso = parsed.astimezone(TZ).isoformat()
                all_day = False
        except (ValueError, OverflowError):
            continue

        end_iso = None
        if ev_end and re.search(r'\b20\d\d\b', ev_end):
            try:
                if re.fullmatch(ISO_DATE, ev_end):
                    end_iso = ev_end
                else:
                    pe = parse(ev_end)
                    if pe.tzinfo is None:
                        pe = pe.replace(tzinfo=TZ)
                    end_iso = pe.astimezone(TZ).isoformat()
            except (ValueError, OverflowError):
                end_iso = None

        venue_text = _xml_child_text(item, ('location', 'venue')) or source['name']
        cats_text = ' '.join(
            ''.join(c.itertext()).strip()
            for c in item
            if c.tag.split('}')[-1].lower() == 'category'
        )
        row: dict = {
            'name': title,
            'startDate': start_iso,
            'endDate': end_iso,
            'url': urljoin(page, link or page),
            'location': {'name': venue_text},
            'description': BeautifulSoup(desc, 'html.parser').get_text(' ', strip=True) if '<' in desc else desc,
            'keywords': cats_text,
            '_all_day': all_day,
            '_evidence_quote': f'RSS {ev_start}',
        }
        cats = _infer_cats(title, cats_text, desc)
        if cats:
            row['_categories'] = cats
        rows.append(row)
    return rows


def localist_events(data: dict, source: dict, page: str) -> list[dict]:
    """Parse Concept3D / Localist /api/2/events JSON payloads."""
    rows: list[dict] = []
    for wrapper in data.get('events', []):
        ev = wrapper.get('event', wrapper) if isinstance(wrapper, dict) else None
        if not isinstance(ev, dict):
            continue
        title = str(ev.get('title') or '').strip()
        if not title:
            continue
        url = ev.get('localist_url') or ev.get('url') or page
        desc = ev.get('description_text') or ev.get('description') or ''
        venue = ev.get('location_name') or ev.get('location') or source['name']
        addr = ev.get('address') or ''
        loc: dict = {'name': venue}
        if addr:
            loc['address'] = addr
        geo = ev.get('geo') or {}
        if geo.get('latitude') is not None and geo.get('longitude') is not None:
            loc['geo'] = {'latitude': geo['latitude'], 'longitude': geo['longitude']}

        offers = None
        if ev.get('free') is True:
            offers = {'price': '0', 'priceCurrency': 'USD'}
        elif ev.get('ticket_cost'):
            m = re.search(r'\$?\s*(\d+(?:\.\d{2})?)', str(ev['ticket_cost']))
            if m:
                offers = {'price': m[1], 'priceCurrency': 'USD'}

        filters = ev.get('filters') or {}
        filter_names = []
        audience_names = []
        for fkey, flist in filters.items():
            if not isinstance(flist, list):
                continue
            for entry in flist:
                name = entry.get('name', '') if isinstance(entry, dict) else str(entry)
                if name:
                    filter_names.append(name)
                    if 'audience' in fkey.lower():
                        audience_names.append(name)

        age_range = None
        for aud in audience_names:
            if re.search(r'\ball\s*ages\b', aud, re.I):
                age_range = 'All ages'
                break
            m_age = re.search(r'\b(\d{1,2}\s*[-–]\s*\d{1,2}|\d{1,2}\+)\b', aud)
            if m_age:
                age_range = m_age[1]
                break

        ev_status = 'EventCancelled' if ev.get('canceled') or str(ev.get('status', '')).lower() == 'canceled' else 'EventScheduled'
        cats = _infer_cats(title, ' '.join(filter_names), desc)
        instances = ev.get('event_instances') or []
        for inst_wrap in instances:
            inst = inst_wrap.get('event_instance', inst_wrap) if isinstance(inst_wrap, dict) else None
            if not isinstance(inst, dict) or not inst.get('start'):
                continue
            row: dict = {
                'name': title,
                'startDate': inst['start'],
                'endDate': inst.get('end'),
                'url': url,
                'location': loc,
                'description': desc,
                'keywords': ' '.join(filter_names),
                'eventStatus': ev_status,
                '_all_day': bool(inst.get('all_day', False)),
                '_evidence_quote': f"Localist {inst['start']}",
            }
            if offers:
                row['offers'] = offers
            if age_range:
                row['typicalAgeRange'] = age_range
            if cats:
                row['_categories'] = cats
            rows.append(row)
    return rows


def simpleview_events(body_or_data, source: dict, page: str) -> list[dict]:
    """Parse Simpleview CMS JSON feeds, RSS feeds, or explicit-date event cards."""
    if isinstance(body_or_data, str):
        stripped = body_or_data.lstrip()
        if stripped.startswith('{') or stripped.startswith('['):
            try:
                body_or_data = json.loads(stripped)
            except ValueError:
                return []
        elif '<rss' in stripped[:500].lower() or '<feed' in stripped[:500].lower():
            return rss_events(body_or_data, source, page)
        else:
            return _simpleview_html_events(body_or_data, source, page)

    items = []
    if isinstance(body_or_data, list):
        items = body_or_data
    elif isinstance(body_or_data, dict):
        items = body_or_data.get('docs') or body_or_data.get('events') or body_or_data.get('results') or body_or_data.get('data') or []

    rows: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get('title') or item.get('name') or '').strip()
        start_raw = item.get('startDate') or item.get('start_date') or item.get('date') or item.get('start')
        if not title or not start_raw or not re.search(r'\b20\d\d\b', str(start_raw)):
            continue
        end_raw = item.get('endDate') or item.get('end_date') or item.get('end')
        url = urljoin(page, str(item.get('url') or item.get('link') or page))
        loc: dict = {'name': str(item.get('venue') or item.get('location') or item.get('address1') or source['name'])}
        city = item.get('city') or source.get('city')
        if city:
            loc['address'] = {'addressLocality': city}
        lat = item.get('latitude') or item.get('lat')
        lng = item.get('longitude') or item.get('lng') or item.get('lon')
        if lat is not None and lng is not None:
            loc['geo'] = {'latitude': lat, 'longitude': lng}
        desc = str(item.get('description') or item.get('summary') or '')
        cats_raw = ' '.join(item.get('categories', [])) if isinstance(item.get('categories'), list) else str(item.get('category') or '')
        row: dict = {
            'name': title,
            'startDate': str(start_raw),
            'endDate': str(end_raw) if end_raw else None,
            'url': url,
            'location': loc,
            'description': desc,
            'keywords': cats_raw,
            '_all_day': len(str(start_raw).strip()) == 10,
            '_evidence_quote': f'Simpleview {start_raw}',
        }
        cats = _infer_cats(title, cats_raw, desc)
        if cats:
            row['_categories'] = cats
        rows.append(row)
    return rows


def _simpleview_html_events(body: str, source: dict, page: str) -> list[dict]:
    soup = BeautifulSoup(body, 'html.parser')
    rows: list[dict] = []
    for card in soup.select('article, .item, .event-item, .views-row'):
        title_el = card.select_one('h2 a[href], h3 a[href], .title a[href], a.title[href]')
        if not title_el:
            continue
        title = _text(title_el)
        time_el = card.select_one('time[datetime]')
        date_iso = None
        if time_el and re.search(r'^20\d\d-\d{2}-\d{2}', time_el.get('datetime', '')):
            date_iso = time_el['datetime']
        else:
            date_iso = _explicit_date_from_text(_text(card))
        if not title or not date_iso:
            continue
        venue = _text(card.select_one('.venue, .location, .address')) or source['name']
        rows.append({
            'name': title,
            'startDate': date_iso,
            'url': urljoin(page, title_el['href']),
            'location': {'name': venue},
            'description': _text(card.select_one('p, .summary, .description')),
            '_all_day': len(date_iso) == 10,
            '_evidence_quote': f'Simpleview HTML {date_iso}',
        })
    return rows


def bibliocommons_events(body_or_data, source: dict, page: str) -> list[dict]:
    """Parse BiblioCommons events API JSON or embedded state JSON."""
    data = body_or_data
    if isinstance(body_or_data, str):
        stripped = body_or_data.lstrip()
        if stripped.startswith('{') or stripped.startswith('['):
            try:
                data = json.loads(stripped)
            except ValueError:
                return []
        else:
            soup = BeautifulSoup(body_or_data, 'html.parser')
            state_node = soup.select_one('script#__NEXT_DATA__, script[data-iso-serialized]')
            if not state_node:
                return []
            try:
                data = json.loads(state_node.get_text())
            except ValueError:
                return []

    events_list: list[dict] = []
    locations_map: dict = {}
    audiences_map: dict = {}
    places_map: dict = {}
    if isinstance(data, dict):
        entities = data.get('entities') or {}
        if isinstance(entities.get('locations'), dict):
            locations_map = entities['locations']
        if isinstance(entities.get('eventAudiences'), dict):
            audiences_map = entities['eventAudiences']
        if isinstance(entities.get('places'), dict):
            places_map = entities['places']
        if isinstance(entities.get('events'), dict):
            events_list = list(entities['events'].values())
        elif isinstance(data.get('events'), dict) and isinstance(data['events'].get('items'), list):
            events_list = data['events']['items']
        elif isinstance(data.get('items'), list):
            events_list = data['items']
        elif isinstance(data.get('events'), list):
            events_list = data['events']

    _bc_city_hints = (
        ('overland park', 'Overland Park'),
        ('central resource', 'Overland Park'),
        ('oak park', 'Overland Park'),
        ('blue valley', 'Overland Park'),
        ('antioch', 'Merriam'),
        ('merriam', 'Merriam'),
        ('corinth', 'Prairie Village'),
        ('prairie village', 'Prairie Village'),
        ('cedar roe', 'Roeland Park'),
        ('roeland park', 'Roeland Park'),
        ('shawnee', 'Shawnee'),
        ('monticello', 'Shawnee'),
        ('lenexa', 'Lenexa'),
        ('lackman', 'Lenexa'),
        ('gardner', 'Gardner'),
        ('de soto', 'De Soto'),
        ('edgerton', 'Edgerton'),
        ('spring hill', 'Spring Hill'),
        ('olathe', 'Olathe'),
        ('lawrence', 'Lawrence'),
    )
    public_base = (source.get('public_base_url') or page).rstrip('/') + '/'

    rows: list[dict] = []
    for ev in events_list:
        if not isinstance(ev, dict):
            continue
        defn = ev.get('definition', ev)
        title = str(defn.get('title') or ev.get('title') or '').strip()
        start_raw = defn.get('start') or ev.get('start') or defn.get('startDate')
        if not title or not start_raw or not re.search(r'\b20\d\d\b', str(start_raw)):
            continue
        end_raw = defn.get('end') or ev.get('end') or defn.get('endDate')
        loc_id = str(defn.get('branchLocationId') or ev.get('branchLocationId') or '')
        loc_obj = locations_map.get(loc_id, {}) if loc_id else {}
        place_id = str(defn.get('placeId') or ev.get('placeId') or '')
        place_obj = places_map.get(place_id, {}) if place_id else {}
        branch_name = (
            (defn.get('location') or {}).get('name')
            if isinstance(defn.get('location'), dict)
            else defn.get('locationName') or loc_obj.get('name') or place_obj.get('name') or source['name']
        )
        city = loc_obj.get('city') or (place_obj.get('address') or {}).get('city')
        if not city and branch_name:
            bn_low = str(branch_name).lower()
            city = next((c for k, c in _bc_city_hints if k in bn_low), None)
        city = city or source.get('city')
        loc: dict = {'name': str(branch_name)}
        if city:
            loc['address'] = {'addressLocality': str(city)}
        lat = loc_obj.get('lat') or (place_obj.get('coordinates') or {}).get('lat')
        lng = loc_obj.get('lng') or (place_obj.get('coordinates') or {}).get('lng')
        if lat is not None and lng is not None:
            loc['geo'] = {'latitude': lat, 'longitude': lng}

        ev_id = ev.get('id') or defn.get('id')
        link = defn.get('url') or ev.get('url') or (urljoin(public_base, f'events/{ev_id}') if ev_id else page)
        desc = BeautifulSoup(str(defn.get('description') or ''), 'html.parser').get_text(' ', strip=True)
        aud_labels = []
        for a in defn.get('audiences', []) or []:
            if isinstance(a, dict) and a.get('name'):
                aud_labels.append(a['name'])
            elif isinstance(a, str):
                aud_labels.append(a)
        for aid in defn.get('audienceIds', []) or []:
            aobj = audiences_map.get(str(aid))
            if isinstance(aobj, dict) and aobj.get('name'):
                aud_labels.append(aobj['name'])
        aud_labels = list(dict.fromkeys(aud_labels))
        age_range = None
        for aud in aud_labels:
            if re.search(r'\ball\s*ages\b', aud, re.I):
                age_range = 'All ages'
                break
            if re.search(r'\bbirth\s*(?:to|[-–])\s*(?:five|5)\b', aud, re.I):
                age_range = '0–5'
                break
            if re.search(r'\bbirth\s*(?:to|[-–])\s*(?:six|6)\b', aud, re.I):
                age_range = '0–6'
                break
            m_age = re.search(r'(\d{1,2})\s*[-–]\s*(\d{1,2})', aud)
            if m_age:
                age_range = f'{m_age[1]}–{m_age[2]}'
                break
            m_plus = re.search(r'\b(18|21)\+\b', aud)
            if m_plus:
                age_range = m_plus[1] + '+'
                break

        reg_info = defn.get('registration') or ev.get('registration') or {}
        is_full = bool(reg_info.get('isFull') or ev.get('is_full'))
        has_waitlist = bool(reg_info.get('waitlistAvailable') or ev.get('waitlist'))
        reg_status = 'waitlist' if (is_full and has_waitlist) else 'sold_out' if is_full else 'open' if reg_info.get('required') else 'unknown'
        canceled = bool(defn.get('isCancelled') or ev.get('isCancelled'))
        cats = list(dict.fromkeys(['libraries_learning'] + _infer_cats(title, ' '.join(aud_labels), desc)))

        row: dict = {
            'name': title,
            'startDate': str(start_raw),
            'endDate': str(end_raw) if end_raw else None,
            'url': urljoin(public_base, str(link)),
            'location': loc,
            'description': desc,
            'keywords': ' '.join(aud_labels),
            'offers': {'price': '0', 'priceCurrency': 'USD'},
            'eventStatus': 'EventCancelled' if canceled else 'EventScheduled',
            '_categories': cats,
            '_evidence_quote': f'BiblioCommons {start_raw}',
            '_registration': {
                'status': reg_status,
                'opens_at': None,
                'deadline': None,
                'url': urljoin(public_base, str(link)) if reg_info.get('required') else None,
                'note': 'Public library listing; verify registration and seating with branch.',
            },
        }
        if age_range:
            row['typicalAgeRange'] = age_range
        rows.append(row)
    return rows


def libcal_events(body_or_data, source: dict, page: str) -> list[dict]:
    """Parse Springshare LibCal / LibNet JSON APIs or RSS/iCal feeds."""
    if isinstance(body_or_data, str):
        stripped = body_or_data.lstrip()
        if stripped.startswith('BEGIN:VCALENDAR'):
            return ics_events(body_or_data, source, page)
        if '<rss' in stripped[:500].lower() or '<feed' in stripped[:500].lower():
            return rss_events(body_or_data, source, page)
        if stripped.startswith('{') or stripped.startswith('['):
            try:
                body_or_data = json.loads(stripped)
            except ValueError:
                return []
        else:
            return []

    events_list = body_or_data if isinstance(body_or_data, list) else body_or_data.get('events') or body_or_data.get('results') or []
    rows: list[dict] = []
    for ev in events_list:
        if not isinstance(ev, dict):
            continue
        title = str(ev.get('title') or ev.get('name') or '').strip()
        start_raw = ev.get('start') or ev.get('startDate') or ev.get('startdt')
        if not title or not start_raw or not re.search(r'\b20\d\d\b', str(start_raw)):
            continue
        end_raw = ev.get('end') or ev.get('endDate') or ev.get('enddt')
        link = urljoin(page, str((ev.get('url') or {}).get('public') if isinstance(ev.get('url'), dict) else ev.get('url') or page))
        loc_data = ev.get('location') or ev.get('campus') or {}
        venue = loc_data.get('name') if isinstance(loc_data, dict) else str(loc_data or source['name'])
        desc = BeautifulSoup(str(ev.get('description') or ''), 'html.parser').get_text(' ', strip=True)
        aud = ' '.join(a.get('name', '') if isinstance(a, dict) else str(a) for a in (ev.get('audience') or []))
        seats = ev.get('seats')
        taken = ev.get('seats_taken')
        reg_req = bool(ev.get('registration') or seats)
        if reg_req and seats is not None and taken is not None and taken >= seats:
            reg_status = 'waitlist' if ev.get('waitlist') else 'sold_out'
        elif reg_req:
            reg_status = 'open'
        else:
            reg_status = 'unknown'

        cats = list(dict.fromkeys(['libraries_learning'] + _infer_cats(title, aud, desc)))
        row: dict = {
            'name': title,
            'startDate': str(start_raw),
            'endDate': str(end_raw) if end_raw else None,
            'url': link,
            'location': {'name': venue or source['name']},
            'description': desc,
            'offers': {'price': '0', 'priceCurrency': 'USD'},
            '_categories': cats,
            '_evidence_quote': f'LibCal {start_raw}',
            '_registration': {
                'status': reg_status,
                'opens_at': None,
                'deadline': None,
                'url': link if reg_req else None,
                'note': 'Public library calendar; check branch availability and registration.',
            },
        }
        m_age = re.search(r'(\d{1,2})\s*[-–]\s*(\d{1,2})', aud)
        if re.search(r'\ball\s*ages\b', aud, re.I):
            row['typicalAgeRange'] = 'All ages'
        elif m_age:
            row['typicalAgeRange'] = f'{m_age[1]}–{m_age[2]}'
        rows.append(row)
    return rows


def civicplus_events(body: str, source: dict, page: str) -> list[dict]:
    """Parse CivicPlus / CivicEngage municipal iCal, RSS, or HTML calendar pages."""
    stripped = body.lstrip()
    if stripped.startswith('BEGIN:VCALENDAR'):
        return ics_events(body, source, page)
    if '<rss' in stripped[:500].lower() or '<feed' in stripped[:500].lower():
        return rss_events(body, source, page)
    soup = BeautifulSoup(body, 'html.parser')
    rows: list[dict] = []
    for card in soup.select('.calendarEvent, .catItem, .cp-event, li.event, tr.calendar-row'):
        link_el = card.select_one('h3 a[href], h2 a[href], a[href]')
        if not link_el:
            continue
        title = _text(link_el)
        blob = _text(card)
        date_iso = _explicit_date_from_text(blob)
        if not date_iso:
            m_us = re.search(r'\b(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])/(20\d\d)\b', blob)
            if m_us:
                date_iso = f"{m_us[3]}-{int(m_us[1]):02d}-{int(m_us[2]):02d}"
        if not title or not date_iso:
            continue
        rows.append({
            'name': title,
            'startDate': date_iso,
            'url': urljoin(page, link_el['href']),
            'location': {'name': _text(card.select_one('.location, .venue')) or source['name']},
            'description': _text(card.select_one('p, .description')),
            '_all_day': True,
            '_evidence_quote': f'CivicPlus {date_iso}',
        })
    return rows


def mlb_schedule_events(data: dict, source: dict, page: str) -> list[dict]:
    """Parse official MLB / MiLB Stats API schedule JSON."""
    rows: list[dict] = []
    team_id = source.get('team_id')
    home_only = source.get('home_only', True)
    for day_entry in data.get('dates', []):
        for game in day_entry.get('games', []):
            teams = game.get('teams') or {}
            home = (teams.get('home') or {}).get('team') or {}
            away = (teams.get('away') or {}).get('team') or {}
            if home_only and team_id and home.get('id') != team_id:
                continue
            game_dt = game.get('gameDate')
            if not game_dt:
                continue
            away_name = away.get('name') or 'Opponent'
            home_name = home.get('name') or source['name']
            title = f'{away_name} at {home_name}'
            venue = (game.get('venue') or {}).get('name') or source['name']
            state = ((game.get('status') or {}).get('detailedState') or '').lower()
            ev_status = 'EventCancelled' if 'cancel' in state else 'EventPostponed' if 'postpon' in state else 'EventScheduled'
            rows.append({
                'name': title,
                'startDate': game_dt,
                'url': source.get('public_url') or source.get('tickets_url') or source.get('url') or page,
                'location': {'name': venue, 'address': {'addressLocality': source['city']}},
                'description': f"Official schedule listing: {title} at {venue}. Check official tickets and game-time updates.",
                'eventStatus': ev_status,
                '_categories': ['sports_spectating'],
                '_evidence_quote': f'MLB Stats API {game_dt}',
            })
    return rows


_MDC_VENUE_MAP = (
    ('burr oak woods', ('Blue Springs', 'Kansas City metro')),
    ('anita b. gorman', ('Kansas City', 'Kansas City metro')),
    ('discovery center', ('Kansas City', 'Kansas City metro')),
    ('parma woods', ('Parkville', 'Kansas City metro')),
    ('james a. reed', ('Lee’s Summit', 'Kansas City metro')),
    ('runge', ('Jefferson City', 'Columbia')),
    ('rock bridge', ('Columbia', 'Columbia')),
    ('boone county', ('Columbia', 'Columbia')),
    ('pony express', ('Maysville', 'St. Joseph & Pony Express')),
    ('st. joseph', ('St. Joseph', 'St. Joseph & Pony Express')),
    ('northwest regional', ('St. Joseph', 'St. Joseph & Pony Express')),
    ('springfield conservation', ('Springfield', 'Springfield & Ozarks')),
    ('andy dalton', ('Ash Grove', 'Springfield & Ozarks')),
    ('shoal creek', ('Joplin', 'Springfield & Ozarks')),
    ('shepherd of the hills', ('Branson', 'Springfield & Ozarks')),
    ('lost valley', ('Warsaw', 'surrounding areas')),
    ('knob noster', ('Knob Noster', 'surrounding areas')),
    ('sedalia', ('Sedalia', 'surrounding areas')),
)
_MDC_EXCLUDE = (
    'powder valley', 'columbia bottom', 'august a. busch', 'cape girardeau',
    'twin pines', 'kirksville', 'hannibal', 'st. louis', 'st. charles', 'southeast regional',
)


def mdc_events(body: str, source: dict, page: str) -> list[dict]:
    """Parse Missouri Dept. of Conservation (/events) calendar cards."""
    soup = BeautifulSoup(body, 'html.parser')
    rows: list[dict] = []
    for card in soup.select('.views-row, article.event, .node--type-event'):
        link_el = card.select_one(
            '.views-field-field-event-registration-link a[href], '
            'h2 a[href], h3 a[href], .field--name-title a[href], a[href*="/events/"]'
        )
        if not link_el:
            continue
        title = _text(link_el)
        date_el = card.select_one('.views-field-field-event-begin-date .field-content, .date-display-single')
        date_blob = _text(date_el) or _text(card)
        blob = _text(card)
        venue = (
            _text(card.select_one('.views-field-views-conditional-field .field-content'))
            or _text(card.select_one('.views-field-field-location .field-content, .field--name-field-location, .location, .event-location'))
            or source['name']
        )
        v_low = venue.lower()
        if any(ex in v_low for ex in _MDC_EXCLUDE):
            continue

        start_val = None
        end_val = None
        all_day = True
        if ' - ' in date_blob and date_el is not None:
            parts = [p.strip() for p in date_blob.split(' - ', 1)]
            if re.search(r'\b20\d\d\b', parts[0]):
                try:
                    dt_start = parse(parts[0], fuzzy=False)
                    if dt_start.tzinfo is None:
                        dt_start = dt_start.replace(tzinfo=TZ)
                    start_val = dt_start.isoformat()
                    all_day = bool(re.fullmatch(r'[^0-9:]+20\d\d', parts[0]))
                    if len(parts) > 1 and re.search(r'\b20\d\d\b', parts[1]):
                        dt_end = parse(parts[1], fuzzy=False)
                        if dt_end.tzinfo is None:
                            dt_end = dt_end.replace(tzinfo=TZ)
                        if dt_end >= dt_start:
                            end_val = dt_end.isoformat()
                except (ValueError, OverflowError):
                    start_val = None
        if not start_val:
            date_iso = _explicit_date_from_text(date_blob)
            if not date_iso:
                m_us = re.search(r'\b(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])/(20\d\d)\b', date_blob)
                if m_us:
                    date_iso = f"{m_us[3]}-{int(m_us[1]):02d}-{int(m_us[2]):02d}"
            if not date_iso:
                continue
            time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?)', date_blob, re.I)
            start_val = date_iso
            if time_match:
                try:
                    day = parse(date_iso)
                    clock_str = time_match[1].replace('.', '')
                    start_val = parse(clock_str, default=day).replace(tzinfo=TZ).isoformat()
                    all_day = False
                except (ValueError, OverflowError):
                    start_val = date_iso

        if not title or not start_val:
            continue
        desc = _text(card.select_one('.views-field-body .field-content, .field--name-body, .summary, p'))
        cats = list(dict.fromkeys(['nature_animals', 'outdoor_recreation'] + _infer_cats(title, desc)))
        mapped = next((val for key, val in _MDC_VENUE_MAP if key in v_low), None)
        city = mapped[0] if mapped else ('St. Joseph' if 'st. joseph' in blob.lower() else source.get('city'))
        loc: dict = {'name': venue}
        if city:
            loc['address'] = {'addressLocality': city}
        row: dict = {
            'name': title,
            'startDate': start_val,
            'endDate': end_val,
            'url': urljoin(page, link_el['href']),
            'location': loc,
            'description': desc,
            '_all_day': all_day,
            '_categories': cats,
            '_evidence_quote': f'MDC {date_blob[:60]}',
        }
        if mapped:
            row['_region'] = mapped[1]
        elif source.get('id') == 'mdc-events':
            row['_region'] = 'surrounding areas'
        if re.search(r'\bfree\b', blob, re.I):
            row['offers'] = {'price': '0', 'priceCurrency': 'USD'}
        rows.append(row)
    return rows


def _is_truthy(val) -> bool:
    if isinstance(val, bool):
        return val
    return str(val or '').strip().lower() in ('1', 'true', 'yes')


def _safe_int(val) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def libnet_events(body_or_data, source: dict, page: str) -> list[dict]:
    """Parse Communico / LibNet /eeventcaldata JSON arrays."""
    data = body_or_data
    if isinstance(body_or_data, str):
        try:
            data = json.loads(body_or_data.lstrip())
        except ValueError:
            return []
    if isinstance(data, dict):
        data = data.get('events') or data.get('data') or []
    if not isinstance(data, list):
        return []

    rows: list[dict] = []
    for item in data:
        if not isinstance(item, dict) or _is_truthy(item.get('private_event')):
            continue
        title = str(item.get('title') or '').strip()
        start_raw = str(item.get('event_start') or item.get('start_time') or '').strip()
        if not title or not start_raw or not re.search(r'\b20\d\d\b', start_raw):
            continue
        end_raw = str(item.get('event_end') or item.get('end_time') or '').strip() or None
        try:
            dt_start = parse(start_raw)
            if dt_start.tzinfo is None:
                dt_start = dt_start.replace(tzinfo=TZ)
        except (ValueError, OverflowError):
            continue
        all_day = dt_start.hour == 0 and dt_start.minute == 0 and (
            not end_raw or '23:59' in end_raw or '00:00:00' in end_raw
        )
        start_val = dt_start.date().isoformat() if all_day else dt_start.isoformat()
        end_val = None
        if end_raw and re.search(r'\b20\d\d\b', end_raw):
            try:
                dt_end = parse(end_raw)
                if dt_end.tzinfo is None:
                    dt_end = dt_end.replace(tzinfo=TZ)
                if dt_end > dt_start and not (all_day and dt_end.date() == dt_start.date()):
                    end_val = dt_end.date().isoformat() if all_day else dt_end.isoformat()
            except (ValueError, OverflowError):
                end_val = None

        venue = str(item.get('location') or item.get('venue_name') or item.get('library') or source['name']).strip()
        loc: dict = {'name': venue}
        if source.get('city'):
            loc['address'] = {'addressLocality': source['city']}
        desc_raw = item.get('long_description') or item.get('description') or ''
        desc = BeautifulSoup(str(desc_raw), 'html.parser').get_text(' ', strip=True) if '<' in str(desc_raw) else str(desc_raw)

        ages_text = str(item.get('ages') or '')
        ages_arr = [str(x) for x in (item.get('agesArray') or []) if x]
        tags_arr = [str(x) for x in (item.get('tagsArray') or []) if x]
        ev_type = str(item.get('event_type') or '')
        keywords = ' '.join(x for x in [ages_text, *ages_arr, *tags_arr, ev_type] if x)

        cleaned_age_src = re.sub(r'\bgrades?\s+\d+\s*[-–to]+\s*\d+\b', '', ages_text, flags=re.I)
        age_range = None
        if re.search(r'\ball\s*ages\b', ages_text, re.I):
            age_range = 'All ages'
        elif re.search(r'\bbirth\s*(?:to|[-–])\s*(?:five|5)\b', ages_text, re.I):
            age_range = '0–5'
        elif re.search(r'\bbirth\s*(?:to|[-–])\s*(?:six|6)\b', ages_text, re.I):
            age_range = '0–6'
        else:
            m_age = re.search(r'\b(?:ages?\s*)?(\d{1,2})\s*(?:[-–]|to)\s*(\d{1,2})\b', cleaned_age_src, re.I)
            if m_age:
                age_range = f'{m_age[1]}–{m_age[2]}'
            else:
                m_plus = re.search(r'\b(18|21)\+\b', ages_text)
                if m_plus:
                    age_range = m_plus[1] + '+'

        changed = str(item.get('changed') or item.get('changed_reason') or '').lower()
        ev_status = 'EventCancelled' if 'cancel' in changed else 'EventScheduled'

        reg_cost = item.get('registration_cost')
        billing_on = _is_truthy(item.get('enable_billing'))
        offers = None
        if reg_cost is not None and str(reg_cost).strip():
            if 'free' in str(reg_cost).lower():
                offers = {'price': '0', 'priceCurrency': 'USD'}
            else:
                m_p = re.search(r'(\d+(?:\.\d{1,2})?)', str(reg_cost))
                if m_p:
                    offers = {'price': m_p[1], 'priceCurrency': 'USD'}
        elif not billing_on:
            offers = {'price': '0', 'priceCurrency': 'USD'}

        reg_open = _is_truthy(item.get('allow_reg'))
        max_att = _safe_int(item.get('max_attendee'))
        tot_reg = _safe_int(item.get('total_registrants'))
        if reg_open and max_att > 0 and tot_reg >= max_att:
            reg_status = 'waitlist' if _is_truthy(item.get('allow_waitlist')) else 'sold_out'
        elif reg_open:
            reg_status = 'open'
        else:
            reg_status = 'unknown'

        rc_raw = str(item.get('registration_close') or '').strip()
        deadline = rc_raw if re.search(r'\b20\d\d\b', rc_raw) else None
        link = str(item.get('url') or '').strip() or page
        cats = list(dict.fromkeys(['libraries_learning'] + _infer_cats(title, keywords, desc)))
        row: dict = {
            'name': title,
            'startDate': start_val,
            'endDate': end_val,
            'url': urljoin(page, link),
            'location': loc,
            'description': desc,
            'keywords': keywords,
            'eventStatus': ev_status,
            '_all_day': all_day,
            '_categories': cats,
            '_evidence_quote': f'LibNet {start_raw}',
            '_registration': {
                'status': reg_status,
                'opens_at': None,
                'deadline': deadline,
                'url': urljoin(page, str(item.get('reg_url') or link)) if reg_open else None,
                'note': 'Public library calendar; check registration and branch hours.',
            },
        }
        if offers:
            row['offers'] = offers
        if age_range:
            row['typicalAgeRange'] = age_range
        rows.append(row)
    return rows


def livewhale_events(body_or_data, source: dict, page: str) -> list[dict]:
    """Parse LiveWhale /live/json/events API payloads (e.g., University of Missouri)."""
    data = body_or_data
    if isinstance(body_or_data, str):
        try:
            data = json.loads(body_or_data.lstrip())
        except ValueError:
            return []
    events_list = data if isinstance(data, list) else (data.get('data') or data.get('events') or []) if isinstance(data, dict) else []
    rows: list[dict] = []
    for ev in events_list:
        if not isinstance(ev, dict):
            continue
        title = str(ev.get('title') or '').strip()
        start_raw = ev.get('date_iso') or (ev.get('date_utc') + '+00:00' if ev.get('date_utc') else None)
        if not title or not start_raw or not re.search(r'\b20\d\d\b', str(start_raw)):
            continue
        end_raw = ev.get('date2_iso') or (ev.get('date2_utc') + '+00:00' if ev.get('date2_utc') else None)
        try:
            dt_s = isoparse(str(start_raw))
            if end_raw:
                dt_e = isoparse(str(end_raw))
                if dt_e < dt_s:
                    end_raw = None
        except (ValueError, TypeError):
            end_raw = None

        loc_val = ev.get('location')
        venue = loc_val.get('name') if isinstance(loc_val, dict) else (str(loc_val).strip() if loc_val else source['name'])
        loc: dict = {'name': venue or source['name']}
        if source.get('city'):
            loc['address'] = {'addressLocality': source['city']}
        lat, lng = ev.get('latitude'), ev.get('longitude')
        if lat is not None and lng is not None:
            try:
                loc['geo'] = {'latitude': float(lat), 'longitude': float(lng)}
            except (TypeError, ValueError):
                pass

        desc_raw = ev.get('summary') or ev.get('description') or ''
        desc = BeautifulSoup(str(desc_raw), 'html.parser').get_text(' ', strip=True) if '<' in str(desc_raw) else str(desc_raw)
        types = ' '.join(str(t) for t in (ev.get('event_types') or []) if t)
        cost = str(ev.get('cost') or '')
        offers = None
        if ev.get('is_free') or re.search(r'\bfree\b', cost, re.I):
            offers = {'price': '0', 'priceCurrency': 'USD'}
        else:
            m_cost = re.search(r'\$?\s*(\d+(?:\.\d{2})?)', cost)
            if m_cost:
                offers = {'price': m_cost[1], 'priceCurrency': 'USD'}
        ev_status = 'EventCancelled' if ev.get('is_canceled') or str(ev.get('status') or '').lower() == 'canceled' else 'EventScheduled'
        cats = _infer_cats(title, types, desc)
        row: dict = {
            'name': title,
            'startDate': str(start_raw),
            'endDate': str(end_raw) if end_raw else None,
            'url': urljoin(page, str(ev.get('url') or page)),
            'location': loc,
            'description': desc,
            'keywords': types,
            'eventStatus': ev_status,
            '_all_day': bool(ev.get('is_all_day')),
            '_evidence_quote': f'LiveWhale {start_raw}',
        }
        if offers:
            row['offers'] = offers
        if cats:
            row['_categories'] = cats
        rows.append(row)
    return rows


def ticketmaster_events(data: dict, source: dict, page: str) -> list[dict]:
    """Parse Ticketmaster Discovery API v2 responses (used when API key is configured)."""
    rows: list[dict] = []
    for ev in (data.get('_embedded') or {}).get('events', []):
        title = str(ev.get('name') or '').strip()
        dates = ev.get('dates') or {}
        start_obj = dates.get('start') or {}
        start_raw = start_obj.get('dateTime') or start_obj.get('localDate')
        if not title or not start_raw:
            continue
        venues = ((ev.get('_embedded') or {}).get('venues') or [])
        v = venues[0] if venues else {}
        loc: dict = {'name': v.get('name') or source['name']}
        city = (v.get('city') or {}).get('name')
        if city:
            loc['address'] = {'addressLocality': city}
        v_loc = v.get('location') or {}
        if v_loc.get('latitude') and v_loc.get('longitude'):
            loc['geo'] = {'latitude': v_loc['latitude'], 'longitude': v_loc['longitude']}
        pr = (ev.get('priceRanges') or [{}])[0]
        offers = None
        if pr.get('min') is not None:
            offers = {'price': str(pr['min']), 'priceCurrency': pr.get('currency') or 'USD'}
        code = ((dates.get('status') or {}).get('code') or '').lower()
        ev_status = 'EventCancelled' if code == 'cancelled' else 'EventPostponed' if code == 'postponed' else 'EventRescheduled' if code == 'rescheduled' else 'EventScheduled'
        classes = ' '.join(
            (c.get(k) or {}).get('name', '')
            for c in ev.get('classifications', [])
            for k in ('segment', 'genre', 'subGenre')
        )
        row: dict = {
            'name': title,
            'startDate': start_raw,
            'url': ev.get('url') or page,
            'location': loc,
            'description': ev.get('info') or ev.get('pleaseNote') or '',
            'keywords': classes,
            'eventStatus': ev_status,
            '_all_day': 'dateTime' not in start_obj,
            '_evidence_quote': f'Ticketmaster {start_raw}',
        }
        if offers:
            row['offers'] = offers
        cats = _infer_cats(title, classes)
        if cats:
            row['_categories'] = cats
        rows.append(row)
    return rows
