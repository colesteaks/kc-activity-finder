"""Two-tier regional hierarchy, drive bands, and Amtrak River Runner tagging."""
from __future__ import annotations

import re

AMTRAK_RIVER_RUNNER_CITIES = {
    'kansas city',
    'independence',
    "lee's summit",
    'lee’s summit',
    'warrensburg',
    'sedalia',
    'jefferson city',
    'hermann',
    'washington',
    'kirkwood',
    'st. louis',
}

_SUBREGION_BY_CITY = {
    # Kansas City MO core
    'kansas city': ('Kansas City metro', 'Kansas City, MO', '0-30m'),
    'kansas city, mo': ('Kansas City metro', 'Kansas City, MO', '0-30m'),
    # Johnson County, KS
    'overland park': ('Kansas City metro', 'Johnson County, KS', '0-30m'),
    'leawood': ('Kansas City metro', 'Johnson County, KS', '0-30m'),
    'lenexa': ('Kansas City metro', 'Johnson County, KS', '0-30m'),
    'olathe': ('Kansas City metro', 'Johnson County, KS', '0-30m'),
    'shawnee': ('Kansas City metro', 'Johnson County, KS', '0-30m'),
    'prairie village': ('Kansas City metro', 'Johnson County, KS', '0-30m'),
    'mission': ('Kansas City metro', 'Johnson County, KS', '0-30m'),
    'merriam': ('Kansas City metro', 'Johnson County, KS', '0-30m'),
    'roeland park': ('Kansas City metro', 'Johnson County, KS', '0-30m'),
    'johnson county': ('Kansas City metro', 'Johnson County, KS', '0-30m'),
    'gardner': ('Kansas City metro', 'Johnson County, KS', '30-60m'),
    'de soto': ('Kansas City metro', 'Johnson County, KS', '30-60m'),
    # Wyandotte County / KCK
    'kansas city, ks': ('Kansas City metro', 'Wyandotte County / KCK', '0-30m'),
    'edwardsville': ('Kansas City metro', 'Wyandotte County / KCK', '0-30m'),
    'bonner springs': ('Kansas City metro', 'Wyandotte County / KCK', '30-60m'),
    # KC Northland
    'north kansas city': ('Kansas City metro', 'KC Northland', '0-30m'),
    'gladstone': ('Kansas City metro', 'KC Northland', '0-30m'),
    'riverside': ('Kansas City metro', 'KC Northland', '0-30m'),
    'parkville': ('Kansas City metro', 'KC Northland', '0-30m'),
    'liberty': ('Kansas City metro', 'KC Northland', '0-30m'),
    'smithville': ('Kansas City metro', 'KC Northland', '30-60m'),
    'platte city': ('Kansas City metro', 'KC Northland', '30-60m'),
    'weston': ('Kansas City metro', 'KC Northland', '30-60m'),
    'excelsior springs': ('Kansas City metro', 'KC Northland', '30-60m'),
    # Eastern Jackson & Cass
    'independence': ('Kansas City metro', 'Eastern Jackson & Cass', '0-30m'),
    "lee's summit": ('Kansas City metro', 'Eastern Jackson & Cass', '0-30m'),
    'lee’s summit': ('Kansas City metro', 'Eastern Jackson & Cass', '0-30m'),
    'blue springs': ('Kansas City metro', 'Eastern Jackson & Cass', '0-30m'),
    'raytown': ('Kansas City metro', 'Eastern Jackson & Cass', '0-30m'),
    'grandview': ('Kansas City metro', 'Eastern Jackson & Cass', '0-30m'),
    'belton': ('Kansas City metro', 'Eastern Jackson & Cass', '0-30m'),
    'kingsville': ('Kansas City metro', 'Eastern Jackson & Cass', '30-60m'),
    # Lawrence / Douglas County
    'lawrence': ('Lawrence', 'Douglas County, KS', '30-60m'),
    'baldwin city': ('Lawrence', 'Douglas County, KS', '30-60m'),
    'eudora': ('Lawrence', 'Douglas County, KS', '30-60m'),
    'lecompton': ('Lawrence', 'Douglas County, KS', '30-60m'),
    # Mid-Missouri / Columbia corridor
    'columbia': ('Mid-Missouri / Columbia', 'Boone County, MO', '1-2h'),
    'rocheport': ('Mid-Missouri / Columbia', 'Katy Trail & Mid-MO', '1-2h'),
    'arrow rock': ('Mid-Missouri / Columbia', 'Katy Trail & Mid-MO', '1-2h'),
    'boonville': ('Mid-Missouri / Columbia', 'Katy Trail & Mid-MO', '1-2h'),
    'warrensburg': ('Mid-Missouri / Columbia', 'West-Central MO', '1-2h'),
    'sedalia': ('Mid-Missouri / Columbia', 'Sedalia & Katy Trail', '1-2h'),
    'jefferson city': ('Mid-Missouri / Columbia', 'Capitol & River Corridor', '2-3.5h'),
    'hermann': ('Mid-Missouri / Columbia', 'Missouri Wine Country', '2-3.5h'),
    'washington': ('Mid-Missouri / Columbia', 'Missouri Wine Country', '2-3.5h'),
    # Northwest Arkansas
    'bentonville': ('Northwest Arkansas', 'Bentonville & Bella Vista', '2-3.5h'),
    'bella vista': ('Northwest Arkansas', 'Bentonville & Bella Vista', '2-3.5h'),
    'rogers': ('Northwest Arkansas', 'Rogers & Beaver Lake', '2-3.5h'),
    'springdale': ('Northwest Arkansas', 'Springdale', '2-3.5h'),
    'fayetteville': ('Northwest Arkansas', 'Fayetteville & U of A', '2-3.5h'),
    'eureka springs': ('Northwest Arkansas', 'Eureka Springs & Ozarks', '2-3.5h'),
    # Tier 2 Day Trips
    'topeka': ('Topeka & Flint Hills', 'Topeka, KS', '1-2h'),
    'manhattan': ('Topeka & Flint Hills', 'Flint Hills & Manhattan', '1-2h'),
    'strong city': ('Topeka & Flint Hills', 'Tallgrass Prairie', '1-2h'),
    'cottonwood falls': ('Topeka & Flint Hills', 'Tallgrass Prairie', '1-2h'),
    'council grove': ('Topeka & Flint Hills', 'Santa Fe Trail & Flint Hills', '1-2h'),
    'st. joseph': ('St. Joseph & Pony Express', 'St. Joseph, MO', '30-60m'),
    'saint joseph': ('St. Joseph & Pony Express', 'St. Joseph, MO', '30-60m'),
    'mound city': ('St. Joseph & Pony Express', 'Loess Bluffs Corridor', '1-2h'),
    'atchison': ('surrounding areas', 'Atchison & Leavenworth River', '30-60m'),
    'leavenworth': ('surrounding areas', 'Atchison & Leavenworth River', '30-60m'),
    'louisburg': ('surrounding areas', 'Miami County & SE Kansas', '30-60m'),
    'fort scott': ('surrounding areas', 'Miami County & SE Kansas', '1-2h'),
    # Tier 3 Weekend Powerhouses
    'omaha': ('Omaha', 'Omaha Metro, NE', '2-3.5h'),
    'council bluffs': ('Omaha', 'Omaha Metro, NE', '2-3.5h'),
    'des moines': ('Des Moines', 'Des Moines Metro, IA', '2-3.5h'),
    'west des moines': ('Des Moines', 'Des Moines Metro, IA', '2-3.5h'),
    'madrid': ('Des Moines', 'High Trestle / Central IA', '2-3.5h'),
    'springfield': ('Springfield & Ozarks', 'Springfield, MO', '2-3.5h'),
    'branson': ('Springfield & Ozarks', 'Branson & Table Rock', '2-3.5h'),
    'camdenton': ('Springfield & Ozarks', 'Lake of the Ozarks', '2-3.5h'),
    'wichita': ('Wichita & Hutchinson', 'Wichita, KS', '2-3.5h'),
    'hutchinson': ('Wichita & Hutchinson', 'Hutchinson, KS', '2-3.5h'),
}

_REGION_DEFAULTS = {
    'Kansas City metro': ('Kansas City metro', 'Kansas City, MO', '0-30m'),
    'Lawrence': ('Lawrence', 'Douglas County, KS', '30-60m'),
    'Columbia': ('Mid-Missouri / Columbia', 'Boone County, MO', '1-2h'),
    'Bentonville': ('Northwest Arkansas', 'Bentonville & NWA', '2-3.5h'),
    'surrounding areas': ('surrounding areas', 'Regional Day Trips', '1-2h'),
    'Topeka & Flint Hills': ('Topeka & Flint Hills', 'Topeka & Flint Hills', '1-2h'),
    'St. Joseph & Pony Express': ('St. Joseph & Pony Express', 'St. Joseph & Loess Bluffs', '1-2h'),
    'Omaha': ('Omaha', 'Omaha Metro, NE', '2-3.5h'),
    'Des Moines': ('Des Moines', 'Des Moines Metro, IA', '2-3.5h'),
    'Springfield & Ozarks': ('Springfield & Ozarks', 'Springfield & Ozarks', '2-3.5h'),
    'Wichita & Hutchinson': ('Wichita & Hutchinson', 'Wichita & Hutchinson', '2-3.5h'),
}


def geo_metadata(row: dict) -> dict:
    """Return 2-tier corridor/subregion/drive-band metadata without altering source region."""
    city = str(row.get('city') or '').strip()
    region = str(row.get('region') or '').strip()
    norm_city = re.sub(r'\s+', ' ', city).casefold()
    if norm_city in _SUBREGION_BY_CITY:
        corridor, subregion, drive_band = _SUBREGION_BY_CITY[norm_city]
    else:
        corridor, subregion, drive_band = _REGION_DEFAULTS.get(
            region, (region or 'surrounding areas', city or 'Regional', '1-2h')
        )
    return {
        'corridor': corridor,
        'subregion': subregion,
        'municipality': city or subregion,
        'drive_band': drive_band,
        'amtrak_accessible': norm_city in AMTRAK_RIVER_RUNNER_CITIES,
    }
