"""Two-layer transparent enrichment: labeled discovery hints separate from verified organizer policies."""
from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo('America/Chicago')

_PROMO_RE = re.compile(
    r'happy hour refresh|half[- ]price happy hour|new .+ drinks|back at minsky|is back at minsky'
    r'|\bhappy hour\b|\bdrink specials?\b|\b12-step\b|\brecovery group\b|\brooftop igloos?\b'
    r'|\bhalf[- ]price\b|\btaco tuesday\b|\bdaily specials?\b|\bbrunch specials?\b',
    re.I,
)
_PROMO_RESCUE_RE = re.compile(
    r'workshop|\bclass\b|tasting|live music|concert|pottery|\btour\b|festival|comedy|trivia',
    re.I,
)


def is_promo_listing(row: dict) -> bool:
    """Generalized promo / recurring bar-special / recovery-meeting detector."""
    title = str(row.get('title') or '')
    if _PROMO_RESCUE_RE.search(title):
        return False
    venue = str(row.get('venue') or '')
    if _PROMO_RE.search(title):
        return True
    # Pure restaurant/bar recurring menu listings with no event keyword
    if re.search(r"minsky[’']s pizza|iron horse bar & grill|hammers dueling piano bar", venue, re.I) and re.search(
        r'christmas at|happy hour|igloo|special|menu', title, re.I
    ):
        return True
    return False


def _infer_audience(row: dict, text: str) -> list[str]:
    ages = row.get('ages') or {}
    if ages.get('all_ages'):
        return ['all_ages', 'family']
    low, high = ages.get('min'), ages.get('max')
    if low is not None or high is not None:
        tags = []
        if (low is None or low <= 12) and (high is None or high >= 2):
            tags.extend(['kids', 'family'])
        if (low is None or low <= 17) and (high is None or high >= 12):
            tags.append('teens')
        if high is None or high >= 18:
            tags.append('adults')
        if tags:
            return list(dict.fromkeys(tags))

    if re.search(r'\b(21\+|18\+|bar|brewery|pub|cocktail|wine|bourbon|happy hour|date night|speakeasy|burlesque|comedy club)\b', text, re.I):
        return ['adults']
    if re.search(r'\b(storytime|story time|toddler|preschool|kindergarten|kids|children|little ones|wonderscope|deanna rose|rabbit hole|legoland|sea life)\b', text, re.I):
        return ['kids', 'family']
    if re.search(r'\b(teen|high school|middle school|youth)\b', text, re.I):
        return ['teens', 'family']
    if re.search(r'\b(family|all ages|zoo|aquarium|festival|parade|farmers market|state park|nature center|arboretum|miniature golf|planetarium)\b', text, re.I):
        return ['all_ages', 'family']
    if row.get('source_id') in ('kc-library', 'lawrence-library', 'bpl-books-on-main') and re.search(r'\badult|book club|genealogy|finance|career\b', text, re.I):
        return ['adults']
    if 'libraries_learning' in (row.get('categories') or []):
        return ['all_ages', 'family']
    if re.search(r'\b(symphony|opera|lecture|gallery|exhibit|museum|concert|theater|theatre)\b', text, re.I):
        return ['adults', 'family']
    return ['all_ages', 'adults']


def _infer_free_likely(row: dict, text: str) -> bool | None:
    price = row.get('price')
    if price is not None:
        try:
            return float(str(price).replace('$', '').strip()) == 0.0
        except ValueError:
            if str(price).strip().lower() in ('free', '0', '0.00'):
                return True
    if re.search(r'\bfree\b|\bno cost\b|\bno charge\b|\bfree admission\b|\bcomplimentary\b', text, re.I):
        return True
    if row.get('source_id') in ('kc-library', 'lawrence-library', 'nelson', 'crystal-bridges', 'crystal-trails', 'kc-parks', 'rock-bridge-state-park', 'weston-bend', 'clinton-state-park', 'ku-astronomy', 'shsmo-tom-sawyer', 'shsmo-indigenous-identities'):
        if not re.search(r'\$\d+|\bticket|\bfee\b|\bpaid\b', text, re.I):
            return True
    if re.search(r'\$\d+|\btickets?\b|\badmission\b', text, re.I) and row.get('source_id') in ('tmobile', 'midland', 'truman', 'kcopera', 'kc-zoo', 'mavericks', 'science-city'):
        return False
    return None


def _infer_indoor_outdoor(row: dict, text: str) -> str:
    cats = set(row.get('categories') or [])
    if re.search(r'\bindoor\b|\bmuseum\b|\bgallery\b|\blibrary\b|\bplanetarium\b|\bcinema\b|\btheatre\b|\btheater\b|\baquarium\b|\bauditorium\b|\bsymphony\b|\bopera\b', text, re.I):
        if re.search(r'\btrail\b|\bgarden\b|\boutdoor\b|\bzoo\b|\bpark\b', text, re.I):
            return 'mixed'
        return 'indoor'
    if re.search(r'\boutdoor\b|\btrail\b|\bhike\b|\bhiking\b|\bpark\b|\bstate park\b|\bgarden\b|\bpaddl|\bcamping\b|\bparade\b|\bfarmers market\b|\bminiature golf\b|\bzoo\b', text, re.I):
        return 'outdoor'
    if 'outdoor_recreation' in cats:
        return 'outdoor'
    if cats & {'arts_exhibits', 'libraries_learning', 'film_literature', 'music_performance', 'science_technology'}:
        return 'indoor'
    return 'unknown'


def _infer_time_of_day(row: dict) -> str:
    kind = (row.get('schedule') or {}).get('kind')
    if kind in ('evergreen', 'program_catalog') or not row.get('start'):
        return 'flexible'
    if row.get('all_day'):
        return 'all_day'
    try:
        dt = datetime.fromisoformat(row['start'].replace('Z', '+00:00')).astimezone(TZ)
        hour = dt.hour
        if hour < 12:
            return 'morning'
        if hour < 17:
            return 'afternoon'
        if hour < 21:
            return 'evening'
        return 'night'
    except (ValueError, TypeError):
        return 'flexible'


def _infer_novelty(row: dict, promo: bool, text: str) -> str:
    if promo:
        return 'promo_or_routine'
    kind = (row.get('schedule') or {}).get('kind')
    if kind == 'evergreen':
        return 'ongoing_place'
    if kind == 'exhibit':
        return 'exhibit_run'
    if kind in ('recurring_program', 'program_catalog', 'course', 'camp', 'sports_season'):
        return 'recurring_program'
    if re.search(r'\bfestival\b|\bfair\b|\bsymphony\b|\bopera\b|\bworld cup\b|\bchampionship\b|\bgala\b|\bannual\b|\bmatsuri\b|\bparade\b|\bconcert\b|\bholiday reflections\b', text, re.I):
        return 'signature_event'
    if row.get('source_kind') == 'organizer' and not re.search(r'\b12-step\b|\bstudy group\b|\bopen lab\b', text, re.I):
        return 'special_event'
    return 'special_event' if kind == 'one_off' else 'recurring_program'


def build_hints(row: dict, source: dict | None = None) -> dict:
    """Produce transparently labeled discovery hints without mutating verified fields."""
    text = ' '.join([
        str(row.get('title') or ''),
        str(row.get('description') or ''),
        str(row.get('venue') or ''),
        str(row.get('source_name') or ''),
    ])
    promo = is_promo_listing(row)
    audience = _infer_audience(row, text)
    free_likely = _infer_free_likely(row, text)
    indoor_outdoor = _infer_indoor_outdoor(row, text)
    time_of_day = _infer_time_of_day(row)
    novelty = _infer_novelty(row, promo, text)

    score = 50
    if novelty == 'signature_event':
        score += 20
    elif novelty in ('special_event', 'exhibit_run'):
        score += 10
    elif novelty == 'ongoing_place':
        score += 6
    if row.get('source_kind') == 'organizer':
        score += 12
    if not row.get('all_day') and row.get('start'):
        score += 8
    reg = row.get('registration') or {}
    if reg.get('status') == 'open' or reg.get('deadline'):
        score += 6
    if row.get('geo'):
        score += 4
    if free_likely is True:
        score += 4
    if promo:
        score -= 28
    if row.get('stale') or row.get('disappeared') or row.get('status') in ('canceled', 'postponed'):
        score -= 20
    if (row.get('schedule') or {}).get('kind') == 'date_range_unknown':
        score -= 8
    score = max(0, min(100, score))

    return {
        'labeled_estimate': True,
        'audience': audience,
        'free_likely': free_likely,
        'indoor_outdoor': indoor_outdoor,
        'time_of_day': time_of_day,
        'is_promo': promo,
        'novelty': novelty,
        'standout_score': score,
    }
