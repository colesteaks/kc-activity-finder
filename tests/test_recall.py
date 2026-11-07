import copy
import gzip
import json
import sys
import tempfile
import unittest
from datetime import date,datetime
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from calendar_adapters import library_events,carbonhouse_events,visitkc_events,visitkc_api_events,html_events
from collect_activities import response_body,collect_source,normalize,run,reconcile,TZ
from newsletter_sources import archive_page,issue_record,is_post,summarize
from check_recall import compare

SOURCE={'id':'test','name':'Test Library','region':'Kansas City metro','city':'Kansas City','kind':'organizer','format':'library','url':'https://example.test/calendar','pattern':r'/calendar/[^/?]+','max_details':0}
NOW=datetime(2026,11,7,10,tzinfo=TZ)


def card(title='Jigsaw Swap',date='Saturday, November 7, 2026'):
    return f'<div class="views-row"><h3><a href="/calendar/{title.lower().replace(" ","-")}">{title}</a></h3><div class="search-result__details__date"><span>{date}</span><span class="time">1:00pm</span></div><div class="search-result__details__location">Plaza Branch</div></div>'


def api_data(title='Festival',pagination=True):
    return {'success':True,'posts':[{'type':'header','date':'Saturday, November 7, 2026'},{'type':'event','content':f'<div class="js-post type-event" data-map-ids="42"><h3 class="entry-title"><a href="https://example.test/events/{title}">{title}</a></h3><p class="card-text">Park</p></div>'}], 'markers':[{'postId':42,'lat':39,'lng':-94.5}], 'pagination':{'html':'<button data-pg="2">2</button>' if pagination else ''}}


class RecallTests(unittest.TestCase):
    def test_date_only_calendar_row_corroborates_one_exact_organizer_session(self):
        raw={'name':'Festival','startDate':'2026-11-07T11:00:00-06:00','location':{'name':'Park'}}
        first=normalize(raw,SOURCE,NOW.isoformat(),'https://example.test/official')
        area=normalize(dict(raw,startDate='2026-11-07'),dict(SOURCE,id='area',kind='official-calendar',format='visitkc'),NOW.isoformat(),'https://example.test/area')
        rows=reconcile([], [first,area],[],NOW)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['start'],first['start']);self.assertEqual(len(rows[0]['sources']),2)

    def test_date_only_row_does_not_collapse_two_distinct_performances(self):
        raw={'name':'Concert','startDate':'2026-11-07T11:00:00-06:00','location':{'name':'Hall'}}
        first=normalize(raw,SOURCE,NOW.isoformat(),'https://example.test/official')
        second=normalize(dict(raw,startDate='2026-11-07T15:00:00-06:00'),SOURCE,NOW.isoformat(),'https://example.test/official')
        area=normalize(dict(raw,startDate='2026-11-07'),dict(SOURCE,id='area',kind='official-calendar',format='visitkc'),NOW.isoformat(),'https://example.test/area')
        self.assertEqual(len(reconcile([],[first,second,area],[],NOW)),3)

    def test_http_gzip_is_decoded_and_old_cached_payloads_remain_readable(self):
        body=b'<h1>Official event</h1>'
        self.assertEqual(response_body(gzip.compress(body),'gzip'),body)
        self.assertEqual(response_body(gzip.compress(body)),body)
        with self.assertRaises(ValueError):response_body(body,'br')

    def test_library_reads_visible_all_events_dates_without_inventing_a_year(self):
        rows=library_events(card(),'https://example.test/calendar')
        self.assertEqual(rows[0]['startDate'],'2026-11-07T13:00:00-06:00')
        self.assertEqual(rows[0]['location']['name'],'Plaza Branch')
        self.assertEqual(library_events(card(date='Saturday, November 7'),'https://example.test'),[])
        game=library_events(card(title='Chess game'),'https://example.test')[0]
        normalized=normalize(game,SOURCE,NOW.isoformat(),'https://example.test/calendar')
        self.assertIn('libraries_learning',normalized['categories']);self.assertIn('games_hobbies',normalized['categories'])

    def test_carbonhouse_uses_show_time_and_explicit_year(self):
        body='<div class="entry"><h3><a href="/event/one">Everclear</a></h3><div class="date-time-container"><span class="date">Sun, Nov 8, 2026</span><span class="time">Show 7:30 PM</span></div></div>'
        rows=carbonhouse_events(body,'https://example.test/events',SOURCE)
        self.assertEqual(rows[0]['startDate'],'2026-11-08T19:30:00-06:00')
        self.assertEqual(carbonhouse_events(body.replace(', 2026',''),'https://example.test',SOURCE),[])

    def test_visitkc_ignores_featured_cards_without_a_full_date(self):
        event=api_data()['posts'][1]['content']
        self.assertEqual(visitkc_events(event,'https://example.test'),[])
        rows=visitkc_events('<h2>Saturday, November 7, 2026</h2>'+event,'https://example.test')
        self.assertEqual(rows[0]['startDate'],'2026-11-07')
        self.assertTrue(rows[0]['_all_day'])

    def test_visitkc_map_point_is_tied_to_the_actual_post_id(self):
        rows=visitkc_api_events(api_data(),'https://example.test')
        self.assertEqual(rows[0]['location']['geo']['latitude'],39)
        data=api_data();data['markers'][0]['postId']=999
        self.assertNotIn('geo',visitkc_api_events(data,'https://example.test')[0]['location'])

    def test_library_load_more_pages_are_captured_and_do_not_create_false_truncation(self):
        first=card()+'<a data-drupal-views-infinite-scroll-pager href="?page=1">Load More Results</a>'
        def fetch(_self,url):return card('Game Day') if '?page=1' in url else first
        with tempfile.TemporaryDirectory() as tmp,patch('collect_activities.Fetcher.fetch',fetch):
            rows,health=collect_source(SOURCE,date(2026,11,7),date(2026,11,8),NOW.isoformat(),Path(tmp))
        self.assertEqual(len(rows),2);self.assertEqual(health['visited_count'],2)
        self.assertEqual(health['status'],'checked');self.assertFalse(health['truncated'])

    def test_ignored_pagination_is_a_gap_instead_of_silent_success(self):
        source=dict(SOURCE,format='visitkc',api_url='https://example.test/api',max_pages=3)
        with tempfile.TemporaryDirectory() as tmp,patch('collect_activities.Fetcher.fetch',return_value=json.dumps(api_data())):
            rows,health=collect_source(source,date(2026,11,7),date(2026,11,8),NOW.isoformat(),Path(tmp))
        self.assertEqual(len(rows),1);self.assertEqual(health['status'],'partial')
        self.assertTrue(any('ignored pagination' in e for e in health['errors']))

    def test_capture_guard_stops_refreshing_changed_or_old_dates(self):
        source=dict(SOURCE,format='reviewed-capture',required_text=['November 7, 2026'],captures=[{'name':'Festival','startDate':'2026-11-07'}])
        with tempfile.TemporaryDirectory() as tmp,patch('collect_activities.Fetcher.fetch',return_value='<h1>November 7, 2025</h1>'):
            rows,health=collect_source(source,date(2026,11,7),date(2026,11,8),NOW.isoformat(),Path(tmp))
        self.assertEqual(rows,[]);self.assertEqual(health['status'],'partial')
        self.assertIn('source text changed',health['errors'][0])

    def test_selective_repair_preserves_untouched_rows_and_source_observation_times(self):
        a=normalize({'name':'New event','startDate':'2026-11-08'},SOURCE,NOW.isoformat(),'https://example.test/a')
        other=dict(SOURCE,id='other',name='Other');b=normalize({'name':'Other event','startDate':'2026-11-08'},other,'2026-11-06T10:00:00-06:00','https://example.test/b')
        old_health={'id':'other','name':'Other','region':'Kansas City metro','events':1,'status':'checked','visited_count':1,'checked_at':b['checked_at']}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);reg=root/'sources.json';out=root/'activities.json'
            reg.write_text(json.dumps({'sources':[SOURCE,other]}));out.write_text(json.dumps({'activities':[b],'sources':[old_health]}))
            health=dict(old_health,id='test',name='Test')
            with patch('collect_activities.collect_source',return_value=([a],health)) as fetch:
                result=run(reg,out,root/'cache',NOW,only=['test'])
            self.assertEqual(fetch.call_count,1)
            kept=next(r for r in result['activities'] if r['source_id']=='other')
            self.assertFalse(kept['stale']);self.assertEqual(kept['checked_at'],b['checked_at'])
            self.assertEqual(next(h for h in result['sources'] if h['id']=='other'),old_health)

    def test_archive_pagination_is_not_limited_to_homepage_featured_links(self):
        body='<a href="/p/current">Current newsletter</a><a href="/archive?page=2">Load more</a>'
        posts,next_url=archive_page(body,'https://www.kcdaily.com/archive')
        self.assertIn('https://www.kcdaily.com/p/current',posts)
        self.assertEqual(next_url,'https://www.kcdaily.com/archive?page=2')

    def test_newsletter_keeps_activity_social_links_but_excludes_site_navigation(self):
        body='<header><a href="https://irrelevant.test">Navigation</a></header><div id="content-blocks"><a href="https://provider.test/festival?utm_source=daily">Festival</a><a href="https://www.instagram.com/p/abc/">Community market</a><a href="word salad">Broken link</a></div>'
        row=issue_record(body,'https://www.kcdaily.com/p/current')
        self.assertEqual(len(row['links']),2)
        self.assertTrue(any('instagram.com' in l['url'] for l in row['links']))
        self.assertEqual(row['links'][0]['url'],'https://provider.test/festival')
        self.assertEqual(row['linked_posts'],[])
        self.assertFalse(is_post('https://www.kcdaily.com/p/instagram.com/post'))

    def test_recall_check_does_not_count_wrong_year_or_canceled_records(self):
        benchmark={'id':'test','region':'Kansas City metro','window':{'start':'2026-11-07','end':'2026-11-08'},'anchors':[{'id':'one','title':'Festival','title_pattern':'Festival'}]}
        rows=[{'id':'old','title':'Festival','region':'Kansas City metro','date':'2025-11-07','end_date':'2025-11-07','status':'scheduled'}, {'id':'canceled','title':'Festival','region':'Kansas City metro','date':'2026-11-07','end_date':'2026-11-07','status':'canceled'}]
        self.assertEqual(compare({'activities':rows},benchmark)['captured_anchors'],0)
        rows.append(dict(rows[-1],id='good',status='scheduled',url='https://example.test/festival'))
        self.assertEqual(compare({'activities':rows},benchmark)['captured_anchors'],1)


if __name__=='__main__':unittest.main()
