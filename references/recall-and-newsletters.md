# Recall audits and newsletter-derived source discovery

The November 7, 2026 audit found a real recall failure: the selected KC weekend showed only nine records, seven from the zoo and parks. Most of the overall inventory was from Northwest Arkansas. Library collection used the signature-events page rather than all activities, generic JSON-LD could not read several actual calendar formats, a compressed venue response was being decoded as garbage, and the newsletter frontier stopped at four homepage links that could be featured guides.

## Reverse-engineer sources from the seed

`data/primary-sources.txt` remains unchanged and authoritative. `scripts/newsletter_sources.py` enumerates the public KC Daily archive to its terminal page and follows valid linked newsletter posts. It extracts body links, not site navigation. URLs retain issue/title/publication and observation provenance; tracking-only parameters are removed. Social links are retained as unreviewed leads. Missing or malformed references stay distinct from successful archive reads. Never bypass private access, robots exclusions, CAPTCHAs, denied access or rate limits.

The initial observed archive had 934 public posts over 104 pages; every one was read. One additional linked post was read, four linked post references returned errors, and eighteen malformed relative links were excluded from the newsletter queue. The resulting snapshot records 11,733 distinct outbound targets across 2,655 domains. These include media, ads, social pages, maps and ticketing as well as activity providers. They are **not 2,655 verified activity sources**.

Install `requirements.txt` and `requirements-collector.txt` before archive/collection commands.

```sh
python3 scripts/newsletter_sources.py
```

This is an explicit historical backfill, not a daily requirement. It uses bounded standard requests, cache/conditional HTTP and no LLM calls. A failed enumeration preserves the previous map. Incomplete audits/checkpoints go to `.partial.json`, never replace a completed authoritative snapshot. The output distinguishes completeness of the enumerated public archive from missing linked posts; it cannot account for deleted, private or unpublished editions.

Daily `refresh_sources.py` imports suitable historical leads and reads two recent archive pages plus their newsletter bodies. It does not select the first four homepage cards. Recent newsletter links are retained even when they point to social or niche providers. Proposals remain unreviewed until geography, ownership, current activity value and extraction are checked. Historical links are durable source leads, not current event facts. Never bulk-import an old newsletter's dates as upcoming activities.

Read the compact weekly brief, not the full history JSON, during normal agent work. Review high-value provider/calendar routes and preserve referring issues when promoting them into `data/collection-sources.json`. The generated graph links to the history snapshot and records reviewed supplements separately from the original seed.

## Test recall against actual roundups

For each relevant weekend, capture a small benchmark from the current KC Daily edition and at least one independent listicle. Inspect the real article's date/year and content; recycled newsletter URLs and search-engine caches can show a different edition. Exclude Friday-only events when evaluating a Saturday–Sunday window. Confirm leads on organizer, venue or organizer-linked ticketing pages. Record conflicts, sold-out ticket tiers, walk-up access, session hours and gaps.

```sh
python3 scripts/check_recall.py data/recall-benchmarks/kc-weekend-2026-11-07.json
```

`--strict` returns exit code 2 for missing anchors when the benchmark still applies to the inventory horizon. This is useful for a targeted repair, not as a permanent assertion that an expired November weekend must stay in the public file. The weekly brief flags an expired benchmark for renewal. A passing benchmark measures those named anchors only; do not describe it as exhaustive city coverage or an independent quality score.

Use an organizer's calendar or approved alternative when a primary site is blocked. The convention center's own Meeple-A-Thon event, for example, provided a public venue confirmation while the organizer homepage presented a challenge. Do not use a changed identity or evade that challenge. A venue's run window is not proof of each individual session time.

## Keep collection repairable

- Visit KC: use its own advertised `/wp-json/vkc/v1/events` API with exact dates, true pagination and post-ID-linked location markers. Do not assume changing a GET `pg` parameter on the HTML page changes its results. Detect repeated-page responses as collection gaps.
- KC Library: use `/calendar`, explicit dated activity cards and the Drupal Load More control. Signature events are a separate subset. Skip unrelated navigation links when the index already yielded the actual rows.
- Carbonhouse venue calendars: capture explicit year/date/show-time cards. Do not assume every venue exposes JSON-LD.
- Opera/Squarespace: retain explicit dated occurrences, including real individual sessions. Do not turn missing years into the current year.
- Guarded reviewed captures: for a useful nonstandard first-party page, store exact quoted date/status guards and reviewed raw event facts in the registry. The collector rereads the actual source and refuses to renew the observation if required text changes. Captures expire through the ordinary horizon rules. They are narrow adapters, not a claim that the provider's whole calendar was parsed.
- Compression/access: decode supported HTTP compression with a size limit, and report challenges as gaps rather than empty calendars.

For a targeted repair without wiping unrelated data or resetting its check times:

```sh
python3 scripts/collect_activities.py --only kc-library --only visitkc
```

Tests cover real public markup structures, missing years, repeated pagination, guarded-date changes, source preservation, map coordinate IDs, newsletter body/social capture, and wrong-year/canceled benchmark matches.

## Present the inventory honestly

The site groups repeated dates by offering and shows their details together. Menu/offer advertising is retained but optional in the default browser. Area-calendar records disclose their source and need for time/availability confirmation. Counts use distinct offerings rather than daily occurrences. Partial coverage is visible next to the results; discovery-only, failed and parser-limited routes are never described as checked event coverage.

The website remains a browsable inventory. Personalized skill recommendations still require the full first-party sweep, party-fit ranking and adversarial review; a big flat file cannot replace those steps.
