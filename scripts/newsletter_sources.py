#!/usr/bin/env python3
"""Reverse-engineer KC Daily's public archive into a provenance-rich source frontier.

Newsletter links are discovery evidence, never first-party event verification.
No model calls. Respect robots, denied access, rate limits and private posts.
"""
import argparse
import concurrent.futures
import json
import gzip
import hashlib
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

from bs4 import BeautifulSoup
from collect_activities import ROOT, TZ, Fetcher, safe_url

ORIGIN = 'https://www.kcdaily.com'
IGNORED = {'beehiiv.com','tally.so','snailkit.io','dnnr.io'}


def is_post(url):
    p=urlsplit(url)
    return p.hostname=='www.kcdaily.com' and bool(re.fullmatch(r'/p/[A-Za-z0-9_-]+',p.path))


def discovery_kind(host,label):
    if any(host==x or host.endswith('.'+x) for x in ['facebook.com','instagram.com','youtube.com','twitter.com','x.com','linkedin.com']):return 'social-lead'
    if any(x in host for x in ['maps.','goo.gl']):return 'map-or-location-lead'
    if re.search(r'advertis|sponsor|subscribe|reach out',label,re.I):return 'advertising-or-subscription'
    if any(x in host for x in ['ticket','eventbrite','axs.com','rezdy','spektrix']):return 'ticket-or-registration-lead'
    if any(x in host for x in ['bizjournals','fox4kc','kshb','kctv5','kmbc','kansascity.com','espn','kansascitymag','axios']):return 'media-sensor'
    return 'unreviewed-provider-lead'


def target_url(url):
    if re.search(r'\s',url):return None
    if not safe_url(url): return None
    p=urlsplit(url)
    query=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid')]
    return urlunsplit((p.scheme,p.netloc.lower(),p.path.rstrip('/') or '/',urlencode(query),''))


def archive_page(body, page):
    soup=BeautifulSoup(body,'html.parser')
    posts={urljoin(page,a['href']):a.get_text(' ',strip=True)[:240] for a in soup.select('a[href]') if is_post(urljoin(page,a['href']))}
    next_link=next((a for a in soup.select('a[href]') if 'load more' in a.get_text(' ',strip=True).casefold() or a.get('rel')==['next']),None)
    next_url=urljoin(page,next_link['href']) if next_link else None
    if next_url and (urlsplit(next_url).hostname!='www.kcdaily.com' or urlsplit(next_url).path!='/archive'): raise ValueError('Unexpected archive pagination target')
    return posts,next_url


def issue_record(body, url):
    soup=BeautifulSoup(body,'html.parser'); content=soup.select_one('#content-blocks')
    article={}
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            obj=json.loads(script.get_text())
            if isinstance(obj,dict) and obj.get('@type') in ('Article','NewsArticle','BlogPosting'): article=obj;break
        except ValueError: pass
    row={'url':url,'title':article.get('headline') or (soup.h1.get_text(' ',strip=True) if soup.h1 else ''),'published_at':article.get('datePublished'),'status':'checked' if content else 'no-readable-content','links':[],'linked_posts':[]}
    if not content:return row
    for a in content.select('a[href]'):
        href=a['href']
        if re.match(r'^(?:www\.)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/|$)',href):href='https://'+href
        link=target_url(urljoin(url,href));label=a.get_text(' ',strip=True)[:140]
        if not link:continue
        host=urlsplit(link).hostname or ''
        if host in ('www.kcdaily.com','kcdaily.com'):
            if is_post(link):row['linked_posts'].append(link)
            continue
        if any(host==x or host.endswith('.'+x) for x in IGNORED):continue
        if not label:continue
        row['links'].append({'url':link,'label':label})
    row['links']=list({x['url']:x for x in row['links']}.values())
    return row


def summarize(issues, archive, checked_at):
    targets={};domains={}
    for issue in issues:
        for link in issue.get('links',[]):
            row=targets.setdefault(link['url'],{'url':link['url'],'host':urlsplit(link['url']).hostname,'label':link['label'],'mentions':0,'example_issues':[],'latest_published_at':None})
            row['mentions']+=1
            row['discovery_kind']=discovery_kind(row['host'],row['label'])
            if len(row['example_issues'])<5:row['example_issues'].append(issue['url'])
            published=issue.get('published_at')
            if published and (not row['latest_published_at'] or published>row['latest_published_at']):
                row['latest_published_at']=published;row['label']=link['label'];row['latest_issue']=issue['url']
    for row in targets.values():
        domain=domains.setdefault(row['host'],{'host':row['host'],'unique_links':0,'mentions':0,'sample_labels':[],'example_issues':[]})
        domain['unique_links']+=1;domain['mentions']+=row['mentions']
        if len(domain['sample_labels'])<5:domain['sample_labels'].append(row['label'])
        if len(domain['example_issues'])<3:
            for issue in row['example_issues']:
                if issue not in domain['example_issues']:domain['example_issues'].append(issue)
                if len(domain['example_issues'])==3:break
    return {'version':1,'checked_at':checked_at,'archive':archive,
        'scope':'Public archive pagination and reachable linked posts only; excludes private, removed and unpublished newsletters.',
        'policy':'All extracted targets remain unreviewed discovery leads; historical mentions do not establish current event dates or availability.',
        'summary':{'issues_indexed':len(issues),'issues_read':sum(i['status']=='checked' for i in issues),'issues_failed':sum(i['status']!='checked' for i in issues),'unique_target_urls':len(targets),'linked_domains':len(domains)},
        'issues':[{k:v for k,v in issue.items() if k not in ('links','linked_posts')}|{'outbound_links':len(issue.get('links',[]))} for issue in issues],
        'domains':sorted(domains.values(),key=lambda x:(-x['mentions'],x['host'])),
        'targets':sorted(targets.values(),key=lambda x:(-x['mentions'],x['url']))}


def run(output, cache, max_pages=1000, max_issues=10000, workers=2):
    if max_pages<1 or max_issues<1 or workers not in (1,2,3):raise ValueError('Positive limits and one to three workers are required')
    observed=datetime.now(TZ).isoformat();fetcher=Fetcher(cache/'archive')
    index={};seen=set();page=ORIGIN+'/archive';errors=[];terminal=False
    while page and len(seen)<max_pages:
        if page in seen:errors.append({'url':page,'error':'Pagination loop'});break
        try:
            body=fetcher.fetch(page);posts,next_page=archive_page(body,page)
            if not posts:raise ValueError('Archive page has no recognizable post links')
            index.update(posts);seen.add(page);page=next_page
            print(f'archive pages={len(seen)} unique_posts={len(index)}',flush=True)
        except Exception as e:errors.append({'url':page,'error':str(e)});break
    archive_urls=set(index)
    if not archive_urls:raise RuntimeError('No archive posts enumerated; preserving the previous source map')
    terminal=page is None
    if not terminal and not errors:errors.append({'url':page,'error':'Archive page limit reached'})
    records=[];fetched=set()
    def fetch_issue(url):
        # Cache per URL; no worker shares mutable robot/cache state.
        import hashlib
        f=Fetcher(cache/'issues'/hashlib.sha256(url.encode()).hexdigest()[:16]);f.robots=dict(fetcher.robots)
        try:return issue_record(f.fetch(url),url)
        except Exception as e:return {'url':url,'title':index.get(url,''),'published_at':None,'status':'failed','error':str(e),'links':[],'linked_posts':[]}
    while True:
        pending=[url for url in index if url not in fetched][:max_issues-len(fetched)]
        if not pending:break
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            for row in pool.map(fetch_issue,pending):
                fetched.add(row['url']);records.append(row)
                for link in row['linked_posts']:
                    if link not in index:index[link]='Linked from '+row['url']
                if len(records)%25==0:print(f'issues_read={len(records)} discovered={len(index)}',flush=True)
                # Write resumable results while preserving the final completeness distinction.
                if len(records)%100==0:
                    state={'entrypoint':ORIGIN+'/archive','pages_read':len(seen),'terminal_page_reached':terminal,'complete':False,'errors':errors,'remaining':len(index)-len(fetched)}
                    partial=output.with_suffix('.partial.json');partial.parent.mkdir(parents=True,exist_ok=True);partial.write_text(json.dumps(summarize(records,state,observed),indent=2)+'\n')
        if len(fetched)>=max_issues:break
    remaining=len(index)-len(fetched)
    state={'entrypoint':ORIGIN+'/archive','pages_read':len(seen),'terminal_page_reached':terminal,'complete':terminal and not errors and archive_urls<={i['url'] for i in records if i['status']=='checked'},'errors':errors,'remaining':remaining,'archive_posts_indexed':len(archive_urls),'archive_posts_read':sum(i['url'] in archive_urls and i['status']=='checked' for i in records),'linked_posts_failed':sum(i['url'] not in archive_urls and i['status']!='checked' for i in records)}
    result=summarize(records,state,observed)
    target=output if state['complete'] else output.with_suffix('.partial.json')
    target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_suffix('.tmp');temp.write_text(json.dumps(result,indent=2)+'\n');temp.replace(target)
    print(json.dumps(result['summary']|{'archive_complete':state['complete'],'remaining':remaining}),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'data/kc-daily-source-map.json');p.add_argument('--cache',type=Path,default=ROOT/'.collector-cache/kc-daily-history');p.add_argument('--max-pages',type=int,default=1000);p.add_argument('--max-issues',type=int,default=10000);p.add_argument('--workers',type=int,default=2)
    a=p.parse_args();run(a.output,a.cache,a.max_pages,a.max_issues,a.workers)
