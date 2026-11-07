# KC Activity Finder

An executable, evidence-first activity research skill for Kansas City metro, Lawrence, Columbia, Bentonville and surrounding areas, including Northwest Arkansas.

**Hosted activity browser:** `web/` is a static GitHub Pages site with age, location, type and date filters. Daily GitHub Actions collect seven months ahead into `web/activities.json`, without any LLM calls. See [hosting and collection](references/hosting-and-collection.md) for scheduling, source expansion, costs and maintenance.

**Ongoing places and map:** parks and permanent attractions have separate hours, seasonal rules and amenities. The optional Leaflet map shares the list filters, groups co-located activities, supports searching the visible area, and links to activity details. [Place and map maintenance](references/places-and-map.md) explains provenance, missing coordinates and tile hosting.

Activities now have a [show page](web/activity.html) reached from each card, and a [schedule-aware model](references/activity-model-and-coverage.md) for outdoor offerings, seasons, exhibits, courses, camps and recurring programs. The graph audits 22 subjects across five regions and distinguishes reviewed routes from actual collected category/format coverage.

**Discover broadly. Filter later.** Collect adult-only events, kids’ activities, family outings, active experiences, arts, performances, classes, races, seasonal events and niche discoveries. Preserve closed, full, canceled and unresolved records. Build separate recommendations for different outings from that inventory.

The [weekly Codex source-improvement loop](references/weekly-source-improvement.md) complements daily collection with bounded link exploration, gap searches, source probes and parser repair. Run `python3 scripts/weekly_discovery_brief.py` for a compact prioritized queue; decisions persist in `data/source-review-ledger.json`.

Supports `weekend-current` and `signup-horizon` (events worth reserving ahead). The required order is source graph → deep first-party sweep → candidate capture → broader web search → merge → fit ranking → adversarial review → recommendations.

**Day trips (skill only):** ask “What destinations have something worth a day trip within two hours of [origin]?” The skill compares compelling anchors, then helps plan a selected day with hours, transfers, meals, booking and return-time checks. It searches beyond the default regions when the drive limit allows. See the [workflow](references/day-trips.md), [reusable prompts](prompts/day-trip.md) and [fictional research example](examples/day-trip-research.json). The deterministic helper checks driving limits and itinerary feasibility without model/API calls:

```sh
python3 scripts/day_trip_planner.py examples/day-trip-research.json --output /tmp/day-trip-checks.json
```

Day-trip inputs use their own schema; the existing event-ledger modes are unchanged. The helper checks submitted facts; a browsing agent still researches, ranks destinations and reviews eligibility, costs, sources and availability.

## What executes

Python manages the research ledger, validates JSON Schema and timestamps, conservatively merges occurrences, preserves evidence and conflicts, computes configurable scores, applies filters, requires adversarial checks, and renders reports with the full inventory and coverage gaps. A human or browsing agent performs live research and interprets pages. There is no unattended scraper or autonomous web-search service hidden behind the CLI.

```bash
python3 -m pip install -r requirements.txt
python3 scripts/validate_repo.py
python3 -m unittest discover -s tests -v
python3 examples/build_demo.py
python3 scripts/activity_pipeline.py report examples/weekend-run.json /tmp/weekend-demo.md
```

The examples are fictional and labeled in the reports. They are never live event recommendations.

## Run live research

Read [SKILL.md](SKILL.md) and [the execution guide](references/execution.md).

```bash
python3 scripts/activity_pipeline.py init my-request.json my-run.json
python3 scripts/activity_pipeline.py stage my-run.json source-graph
# Browse, then edit the coverage ledger and capture raw candidate records.
python3 scripts/activity_pipeline.py stage my-run.json deep-first-party-sweep
python3 scripts/activity_pipeline.py stage my-run.json candidate-capture
# Search each region; append verified or unresolved discoveries and search records.
python3 scripts/activity_pipeline.py stage my-run.json broader-web-search
python3 scripts/activity_pipeline.py stage my-run.json merge
python3 scripts/activity_pipeline.py stage my-run.json fit-based-ranking
# Re-open official pages, populate review checks, resolve blockers.
python3 scripts/activity_pipeline.py stage my-run.json adversarial-review
python3 scripts/activity_pipeline.py report my-run.json my-report.md
```

Stage commands attest to human/agent research; they do not perform it. The engine checks the submitted artifacts, not whether a person actually visited a page or correctly classified its ownership. Review quotations and provenance critically.

## Source authority and current limits

The existing repository preserves the supplied source artifact at [data/primary-sources.txt](data/primary-sources.txt). Its exact bytes are `KC daily`; the graph resolves this to KC Daily. The SHA-256 is checked on every run. It is a discovery sensor, not first-party confirmation. We preserve the seed rather than inventing a larger original file.

**The maintained graph currently contains one seed.** Regional coverage depends on descending to official producer pages and explicitly recorded broader searches. This is not yet a mature, comprehensive source registry. Report that limitation. Add observed official routes with relationship evidence through [the maintenance process](references/updating-sources.md); never relabel supplements as supplied seeds or fabricate historical verification dates.

## Filtering and ranking

[Query schema](schemas/query.schema.json) supports participant ages, region/category filters, maximum per-person price, maximum travel time, minimum movement and custom ranking weights. Empty participant ages mean broad, audience-neutral selection; actual ages enforce eligibility for every participant. Adults-only outings can use adults’ ages; a family outing includes both children and caregivers. Age filters never alter discovery.

The executable rubric is in [ranking.md](references/ranking.md). Unknown eligibility blocks a constrained selection; unknown budget/travel blocks those strict filters. Unavailable, stale, conflicting and secondary-only records remain in inventory. Evidence is fresh within 48 hours by default and checked against an explicit research clock. Live reports reject a research clock older than 24 hours.

## Repository guide

- `scripts/activity_pipeline.py`: execution, filtering, scoring, merging and reports.
- `scripts/validate_repo.py`: preserved seed, workflow and example invariants.
- `schemas/`: request, candidate, source graph and legacy structured recommendation contracts.
- `examples/*-run.json` and `*-report.md`: reproducible engine outputs for both modes.
- `examples/*-recommendation.json`: original illustrative structured output; generated Markdown reports use the richer runtime contract.
- `tests/`: positive and adversarial regression cases.
- `references/`: research, execution, scoring, output and maintenance instructions.

Python 3.11+ recommended; CI uses Python 3.12. No API keys are required by the engine. Browsing tools are provided by the host. Keep family details, addresses, private tickets and credentials out of commits.
