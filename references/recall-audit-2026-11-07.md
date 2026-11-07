# KC weekend recall audit — November 7, 2026

Scope: Kansas City metro, Saturday November 7 through Sunday November 8, America/Chicago. The user's complaint was tested against the selected website URL, the actual current KC Daily weekend edition and an independent local roundup.

## Measured result

| Measure | Before | After |
| --- | ---: | ---: |
| Default-filter activity cards | 9 | 98 |
| Matching records, before grouping repeated dates | 9 | 119 |
| Sources contributing to those results | 4 | 19 |
| Captured named anchors from the 17-item roundup benchmark | 0 | 17 |

The after figures exclude menu/offer promotions by default and include the ongoing-place option, matching the browser's defaults. Distinct cards are grouped by offering identity; near-duplicate titles across publishers may still need manual resolution. These figures are not a citywide completeness measure or a claim that all listings have current ticket availability.

## Causes found

- The 300-record inventory was dominated by Northwest Arkansas (209 records); KC had 65 across its whole horizon and only nine for this weekend.
- Newsletter discovery inspected only four homepage post links, allowing featured guides to crowd out the actual weekend roundup. No full archive/source backfill existed.
- The library entrypoint was its signature-events subset. The all-activities cards and Load More pages were unsupported.
- Important publishers used HTML calendar cards, explicit occurrence lists or a public calendar API rather than Event JSON-LD.
- Gzip-compressed responses could be decoded as UTF-8 garbage and silently yield no events.
- Raw record counts and repeated daily occurrences obscured actual discovery breadth. Menu advertising appeared alongside activities, while coverage gaps were primarily in the footer.

## Research and source graph

All 934 publicly enumerated KC Daily archive posts were read across 104 pages. One additional valid linked post was read; four other linked post references failed, and eighteen malformed relative links were excluded from the newsletter queue. The snapshot has 11,733 distinct outbound targets across 2,655 domains, including media, advertising, maps and social pages. They remain discovery evidence, not a bulk-approved provider registry.

The preserved original seed bytes/hash are unchanged. Eighteen actually reviewed first-party supplement nodes were promoted into the maintained graph, for nineteen nodes total. The collection registry now has 47 approved routes. Current newsletter bodies and the historical frontier feed unreviewed proposals; reviewed provider calendars remain separate from those leads.

The current-roundup sample includes Garth Brooks, KC Pet Fest, Winter Magic, Free Fallin', Merry & Bright, the KC Current playoff match, Veterans Day Parade, Troost United Fest, Kauffman yoga, The Marriage of Figaro, Central Avenue Día de Muertos, Crossroads Flea, Mavericks hockey, Meeple-A-Thon, Uptown Matsuri, DFSCON and Mistletoe Madness. Friday-only items were excluded from the Saturday–Sunday benchmark.

## Verification decisions

- Meeple-A-Thon's organizer homepage presented a challenge. Its official venue event supplied a permitted confirmation; the challenge was not bypassed. A venue's run window does not establish every session's opening time.
- Troost's advance free registration was sold out, while the organizer explicitly welcomed walk-up registration without a guaranteed lunch/tote bag. That distinction is preserved.
- DFSCON's free afternoon book market is separate from paid early/VIP access. Saturday VIP was sold out; the free afternoon capture does not promise VIP/panel admission.
- Mistletoe Madness's official local-calendar page disagreed with itself about Friday hours. Only the unambiguous Saturday session was captured.
- Crossroads Flea's November 8 occurrence comes from the organizer's explicit seasonal second-Sunday rule, corroborated by the current newsletter. No 2027 season was assumed.
- The library, venue and calendar adapters require explicit years. Date-only area-calendar entries ask visitors to confirm times/availability; unknown ages, fees and capacity remain unknown.

## Durable changes

New adapters cover Visit KC's public dated/paginated API and post-linked markers, KC Library cards/pagination, venue cards, opera occurrences and Squarespace events. Guarded captures handle reviewed nonstandard sources and stop renewing facts when source text changes. Selective refreshes preserve untouched sources' facts and observation times. Exact date-only area-calendar corroboration can merge into one unambiguous organizer occurrence; different performances remain separate.

The website groups repeated dates, makes menu promotions optional, labels area-calendar records and puts partial-coverage information next to the results. Scripts expose a dated recall check, and the weekly brief flags gaps or an expired benchmark for renewal. Daily collection remains deterministic with no model calls.

```sh
python3 scripts/check_recall.py data/recall-benchmarks/kc-weekend-2026-11-07.json --strict
python3 scripts/collect_activities.py --only kc-library --only visitkc
python3 scripts/weekly_discovery_brief.py
```

The strict benchmark is relevant only while its dates remain in the inventory horizon. Create a new sample from the next actual weekend editions; do not preserve expired events just to keep a test green. Existing blocks, unimplemented widgets and unreviewed sources remain visible work. The website is a broad inventory; personally ranked recommendations require the skill's source sweep, fit ranking and adversarial review.
