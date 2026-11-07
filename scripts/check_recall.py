#!/usr/bin/env python3
"""Compare a dated, reviewed roundup benchmark with the captured inventory.

This measures named-anchor recall, not completeness, ranking quality or ticket stock.
"""
import argparse
import json
import re
from pathlib import Path


def compare(inventory, benchmark):
    start,end=benchmark['window']['start'],benchmark['window']['end']
    rows=[a for a in inventory['activities'] if a['region']==benchmark['region']
          and a.get('date') and (a.get('end_date') or a['date'])>=start and a['date']<=end
          and a.get('status') not in ('canceled','postponed')]
    results=[]
    for anchor in benchmark['anchors']:
        matches=[a for a in rows if re.search(anchor['title_pattern'],a['title'],re.I)]
        results.append({'id':anchor['id'],'title':anchor['title'],'status':'captured' if matches else 'gap',
                        'record_ids':[a['id'] for a in matches],
                        'source_urls':sorted({a['url'] for a in matches}),
                        'followup':anchor.get('followup') if not matches else None})
    applicable=inventory.get('horizon_start','0000')<=end
    return {'benchmark':benchmark['id'],'region':benchmark['region'],'window':benchmark['window'],
            'applicable':applicable,'captured_anchors':sum(r['status']=='captured' for r in results),
            'expected_anchors':len(results),'weekend_records':len(rows),
            'distinct_weekend_offerings':len({a.get('offering_id',a['id']) for a in rows}),
            'results':results,'note':'Named roundup-anchor recall only. A captured listing is not proof of live availability or a claim to include every possible activity.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('benchmark',type=Path);p.add_argument('--inventory',type=Path,default=Path(__file__).resolve().parents[1]/'web/activities.json');p.add_argument('--output',type=Path);p.add_argument('--strict',action='store_true')
    args=p.parse_args();result=compare(json.loads(args.inventory.read_text()),json.loads(args.benchmark.read_text()));body=json.dumps(result,indent=2)+'\n'
    if args.output:args.output.write_text(body)
    else:print(body,end='')
    raise SystemExit(2 if args.strict and result['applicable'] and result['captured_anchors']<result['expected_anchors'] else 0)
