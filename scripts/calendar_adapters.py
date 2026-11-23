"""Explicit visible calendar formats that do not expose Event JSON-LD."""
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from html import escape
from dateutil.parser import parse

TZ=ZoneInfo('America/Chicago')
FULL_DATE=r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d\d'


def text(node):return node.get_text(' ',strip=True) if node else ''


def downtown_events(body, page):
    """Read explicit dated cards; never infer years, age limits or ticket stock."""
    soup=BeautifulSoup(body,'html.parser');rows=[]
    clock=r'\d{1,2}(?::\d{2})?\s*(?:am|pm)'
    for card in soup.select('a.evcard[href]'):
        title=text(card.select_one('.evcard-content-headline'))
        stamp=text(card.select_one('.evcard-content-date'))
        times=text(card.select_one('.evcard-content-time'))
        link=urljoin(page,card['href']);target=urlsplit(link)
        if (not title or not re.fullmatch(r'(?:[A-Za-z]+,\s*)?[A-Za-z]+\s+\d{1,2},\s+20\d\d',stamp)
                or target.scheme!='https' or target.netloc.lower()!=urlsplit(page).netloc.lower()
                or target.username or target.password or not target.path.startswith('/do/')):continue
        try:
            day=parse(stamp,fuzzy=False)
            if stamp.split(',')[0] in ('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday') and not stamp.startswith(day.strftime('%A')+','):continue
            start=day.date().isoformat();finish=None;all_day=True
            match=re.fullmatch(r'('+clock+r')(?:\s*[-–—]\s*('+clock+r'))?',times,re.I)
            if times and not match:continue
            if match:
                start=parse(match[1],default=day).replace(tzinfo=TZ);all_day=False
                if match[2]:
                    finish=parse(match[2],default=day).replace(tzinfo=TZ)
                    if finish<start:finish+=timedelta(days=1)
                start=start.isoformat();finish=finish.isoformat() if finish else None
        except (ValueError,OverflowError):continue
        rows.append({'name':title,'startDate':start,'endDate':finish,'url':link,
            'location':{'name':text(card.select_one('.evcard-content-venue'))},
            '_all_day':all_day,'_evidence_quote':stamp+(' '+times if times else ''),
            '_schedule':{'kind':'one_off','note':'Explicit visible calendar occurrence; additional series dates may exist on the detail page.'},
            'description':'Visible organizer calendar card. Confirm admission, age rules and registration on the linked detail page.'})
    return rows


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


def html_events(body,source,page):
    if source['format']=='downtown':return downtown_events(body,page)
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
