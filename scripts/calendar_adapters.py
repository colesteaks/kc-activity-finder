"""Explicit visible calendar formats that do not expose Event JSON-LD."""
import re
from datetime import datetime
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from html import escape
from dateutil.parser import parse

TZ=ZoneInfo('America/Chicago')
FULL_DATE=r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d\d'


def text(node):return node.get_text(' ',strip=True) if node else ''


def visitkc_categories(classes):
    mapping={'exhibits':'arts_exhibits','concerts':'music_performance','theatre':'music_performance',
             'festivals':'festivals_seasonal','holiday-activities':'festivals_seasonal','sports':'sports_spectating',
             'outdoors':'outdoor_recreation','markets':'markets_shopping','food-drink':'food_drink',
             'tours':'travel_exploration','classes':'classes_skills','workshops':'classes_skills'}
    return list(dict.fromkeys(mapping[c.removeprefix('event_category-')] for c in classes
                             if c.startswith('event_category-') and c.removeprefix('event_category-') in mapping))


def library_events(body,page):
    soup=BeautifulSoup(body,'html.parser');result=[]
    for card in soup.select('.views-row'):
        link=card.select_one('h3 a[href]');dates=card.select_one('.search-result__details__date')
        if not link or not dates:continue
        stamp=re.search(FULL_DATE,text(dates))
        if not stamp:continue
        time=card.select_one('.search-result__details__date .time')
        day=parse(stamp[0]);start=parse(text(time),default=day).replace(tzinfo=TZ).isoformat() if time else day.date().isoformat()
        result.append({'name':text(link),'startDate':start,'url':urljoin(page,link['href']),
            'location':{'name':text(card.select_one('.search-result__details__location'))},
            'description':text(card.select_one('.search-result__body__text')),
            '_all_day':time is None,'_evidence_quote':text(dates),'_categories':['libraries_learning']})
    return result


def carbonhouse_events(body,page,source):
    soup=BeautifulSoup(body,'html.parser');result=[]
    for card in soup.select('.entry'):
        title=card.select_one('h3 a[href]');day=card.select_one('.date-time-container .date');clock=card.select_one('.date-time-container .time')
        if not title or not day or not re.search(r'\b20\d\d\b',text(day)):continue
        date=parse(text(day));match=re.search(r'\d{1,2}(?::\d{2})?\s*[AP]M',text(clock),re.I)
        if not match:continue
        start=parse(match[0],default=date).replace(tzinfo=TZ)
        result.append({'name':text(title),'startDate':start.isoformat(),'url':urljoin(page,title['href']),
            'location':{'name':source['name']},'description':text(card.select_one('.tour,.supporting')),
            '_evidence_quote':text(day)+' '+text(clock),'_categories':['music_performance']})
    return result


def visitkc_events(body,page):
    soup=BeautifulSoup(body,'html.parser');result=[];day=None
    for node in soup.select('h2,.js-post.type-event'):
        if node.name=='h2':
            stamp=re.search(FULL_DATE,text(node));day=parse(stamp[0]).date().isoformat() if stamp else None
            continue
        if not day:continue  # Featured cards have no full dated grouping: never guess their year.
        link=node.select_one('.entry-title a[href]');venue=node.select_one('.card-text')
        if not link:continue
        result.append({'name':text(link),'startDate':day,'url':urljoin(page,link['href']),
            'location':{'name':text(venue)},'keywords':' '.join(node.get('class',[])),
            'description':'Listed on Visit KC for this date. Confirm event times, admission and availability with the organizer.',
            '_all_day':True,'_evidence_quote':day+' · '+text(link)})
        result[-1]['_source_post_id']=str(node.get('data-map-ids') or node.get('id','').removeprefix('post-')).split(',')[0]
        subjects=visitkc_categories(node.get('class',[]))
        if subjects:result[-1]['_categories']=subjects
    return result


def visitkc_api_events(data,page):
    if data.get('success') is not True:raise ValueError('Visit KC API did not return a successful result')
    fragments=[]
    for post in data.get('posts',[]):
        if post.get('type')=='header':fragments.append('<h2>'+escape(post.get('date',''))+'</h2>')
        elif post.get('type')=='event':fragments.append(post.get('content',''))
    records=visitkc_events(''.join(fragments),page)
    markers={str(m.get('postId')):m for m in data.get('markers',[])}
    for row in records:
        marker=markers.get(row.get('_source_post_id'))
        if marker:row['location']['geo']={'latitude':marker.get('lat'),'longitude':marker.get('lng')}
    return records


def tnew_events(body, page):
    """Read only the selected TNEW performance, never its More Dates options."""
    soup = BeautifulSoup(body, 'html.parser')
    detail = soup.select_one('.tn-event-detail__performance-details-container')
    if not detail:
        return []
    title = text(detail.select_one('.tn-event-detail__title'))
    stamp = text(detail.select_one('.tn-event-detail__display-time'))
    # Explicit year and clock are required; a missing year must not become today.
    if not title or not re.fullmatch(FULL_DATE + r'\s+\d{1,2}:\d{2}\s*[AP]M', stamp, re.I):
        return []
    unavailable = text(detail.select_one('.tn-event-detail__unavailable-text'))
    sold_out = bool(re.search(r'\bsold\s*out\b', unavailable, re.I))
    buy = soup.select_one('#tn-add-to-cart-button')
    open_registration = buy is not None and not buy.has_attr('disabled') and not unavailable
    description = text(detail.select_one('.tn-event-detail__description'))
    # Preserve this material audience restriction before the public excerpt limit.
    if 'people with memory loss and their care partners' in description.lower():
        description = 'For people with memory loss and their care partners. ' + description
    row = {'name': title, 'startDate': parse(stamp).replace(tzinfo=TZ).isoformat(),
           'url': page, 'description': description,
           '_evidence_quote': stamp + (' | ' + unavailable if unavailable else ''),
           'offers': {'availability': 'SoldOut' if sold_out else 'InStock' if open_registration else 'unknown'},
           '_registration': {'status': 'sold_out' if sold_out else 'open' if open_registration else 'unknown',
                             'opens_at': None, 'deadline': None, 'url': page,
                             'note': 'Selected performance only. Availability observed on the public ticket page; recheck before booking. Other dates can have different titles and availability.'}}
    if 'Tivoli Cinema' in text(soup.select_one('main')):
        row['_categories'] = ['film_literature']
    if 'Atkins Auditorium' in description:
        row['location'] = {'name': 'Atkins Auditorium'}
    elif 'Meet in Bloch Lobby' in description:
        row['location'] = {'name': 'Bloch Lobby'}
    return [row]


def html_events(body,source,page):
    if source['format']=='tnew':return tnew_events(body,page)
    if source['format']=='library':return library_events(body,page)
    if source['format']=='carbonhouse':return carbonhouse_events(body,page,source)
    if source['format']=='visitkc':return visitkc_events(body,page)
    if source['format']=='squarespace':
        soup=BeautifulSoup(body,'html.parser');rows=[]
        for card in soup.select('article.eventlist-event'):
            day=card.select_one('time.event-date[datetime]');clock=card.select_one('time.event-time-localized-start');end=card.select_one('time.event-time-localized-end');link=card.select_one('.eventlist-title-link')
            if not day or not clock or not link:continue
            start=parse(text(clock),default=parse(day['datetime'])).replace(tzinfo=TZ)
            finish=parse(text(end),default=parse(end['datetime'])).replace(tzinfo=TZ) if end and end.get('datetime') else None
            rows.append({'name':text(link),'startDate':start.isoformat(),'endDate':finish.isoformat() if finish else None,'url':urljoin(page,link['href']),'location':{'name':text(card.select_one('.eventlist-meta-address'))},'description':text(card.select_one('.eventlist-description'))})
        return rows
    if source['format']=='opera':
        if '/event/' not in page:return []
        soup=BeautifulSoup(body,'html.parser')
        title=text(soup.select_one('h1')) or text(soup.title).split(' – ')[0]
        rows=[]
        for node in soup.select('.vem-one-occurrence .vem-single-event-date-start'):
            stamp=text(node)
            if not re.search(FULL_DATE,stamp):continue
            rows.append({'name':title,'startDate':parse(stamp).replace(tzinfo=TZ).isoformat(),'url':page,
                         'description':text(soup.select_one('.vem-single-event-description')),
                         '_evidence_quote':stamp,'_categories':['music_performance']})
        return rows
    return []
