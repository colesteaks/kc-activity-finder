---
name: kc-activity-finder
description: Build broad, first-party-verified activity inventories for Kansas City and surrounding regions; compare worthwhile day trips within a user-specified driving limit, plan realistic itineraries, and filter separately for adults, kids or families, weekends and advance registration.
license: MIT
compatibility: Requires Python 3.11+ and jsonschema for executable helpers. Live research needs host-provided browsing; verified drive limits need routing evidence. Collector dependencies are optional. No API keys are required by the core skill.
metadata:
  author: colesteaks
  version: "1.0.1"
  repository: https://github.com/colesteaks/kc-activity-finder
---

# KC Activity Finder

See [installation and versioning](references/installation.md) for a pinned public release. Resolve all bundled paths from this skill directory, regardless of the caller's working directory. Bundled activity data is a timestamped snapshot; recheck current official facts before recommendations.

## Choose the outing

- For a day trip, “within X hours of driving,” destination comparisons or a same-day itinerary, read [day-trip planning](references/day-trips.md) and use its destination-first workflow. Start with origin and drive limit, compare compelling anchors, then plan the selected destination/date. Include qualifying places beyond the default regional graph. Use the [entry prompts](prompts/day-trip.md) and [deterministic feasibility checker](scripts/day_trip_planner.py); no website or paid routing integration is needed.
- For weekend activity recommendations or advance-registration radar, use the event-ledger workflow below and its existing query schema. Dates/party preferences govern selection, never the breadth of discovery.

Read [activity modeling and coverage](references/activity-model-and-coverage.md) for broad category discovery and the separate schedule, registration and commitment contracts. Explore every taxonomy category in every regional band; record gaps instead of claiming an exhaustive sweep. Inspect outdoor-place directories, sports-season registration and schedule portals, exhibit runs, term catalogs, recurring series and evergreen offerings in addition to event calendars. Preserve unknown dates and hours; never turn a signup window into an activity run or a run into invented daily sessions.

For permanent attractions, use the [place/hours/map contract](references/places-and-map.md). Separate grounds, gates and facility hours; capture each amenity's seasonal, admission and reservation rules. Use verified coordinates with precision/source evidence, keep unmapped places visible, and never equate an evergreen listing with guaranteed daily or 24/7 access.

The static site and daily deterministic collection workflow are documented in [hosting and collection](references/hosting-and-collection.md). Use them for broad discovery; use the workflow below for personalized, adversarially reviewed recommendations. The unattended collection does not claim to perform semantic web search or human review.

Read [execution](references/execution.md), [research workflow](references/workflow.md), [ranking](references/ranking.md), and [adversarial review](references/adversarial-review.md). Run from the repository root with Python 3.11+ and `pip install -r requirements.txt`.

## Non-negotiable sequence

The command-backed sequence below applies to weekend and signup event ledgers. Day trips preserve these eight stages through the destination-based protocol in [day-trip planning](references/day-trips.md), with a separate research schema and feasibility helper.

1. **Source graph:** load `data/source-graph.json`; verify the preserved original seed hash. Record graph identity and every active source in the run ledger. Treat KC Daily as a sensor, not an official producer.
2. **Deep first-party source sweep:** visit anchors and descend through calendars, pagination, program PDFs, session schedules, news, official social and organizer-linked registration portals. Capture raw observations during research. Record checked, empty, failed or deferred routes; failed is never empty.
3. **Candidate capture:** preserve all plausible activities before filtering, including adult-only, kids, family, passive, active, expensive, sold out, closed, canceled and unresolved. Use null for unknown facts. Keep parent programs and child sessions distinct. Save exact evidence quotes, ownership classification and observation times.
4. **Broader web search:** search Kansas City metro, Lawrence, Columbia, Bentonville and surrounding areas. Explicitly include Kansas suburbs, Douglas County, Boone County and Rogers/Springdale/Fayetteville/Northwest Arkansas. Cover categories missing from the graph and date window. Use aggregators as sensors, then confirm on official pages. Log queries and outcomes; propose graph additions separately.
5. **Deduplication and merging:** execute `merge`. Review near-duplicates manually. Exact occurrence merges preserve originals and discovery channels. Conflicting material values block selection until resolved; preserve the original evidence and document resolution.
6. **Fit ranking:** execute `fit-based-ranking`. Apply the outing’s age, interest, region, movement, budget and travel choices to the complete inventory. Never narrow research to ages 0–5. Offer separate adults-only, children and family views when useful. No popularity or sponsorship bonus.
7. **Adversarial review:** reopen official shortlisted pages and attempt to disprove each recommendation. Check identity, schedule/year, location, availability, audience, cost, registration, conflicts, logistics and provenance. Record a named reviewer and notes for each check. Resolve blocking findings. Execute `adversarial-review`; subsequent content changes invalidate the review.
8. **Final recommendations:** execute `report`. Lead with coverage limits, then picks, exact status and deadlines, fit, friction, source links/timestamps, full inventory, exclusions, source-health ledger, broader-search outcomes and proposed graph additions. Do not claim completeness from a one-seed graph or from a missing ledger.

## Scope and decisions

Default timezone is America/Chicago. Resolve relative dates to exact local dates before research. Weekend defaults to the relevant Saturday–Sunday; on Sunday “this weekend” includes that Sunday. Signup horizon defaults to 21–365 days ahead, but include nearer live deadlines when useful. The event CLI takes explicit dates so these choices remain reviewable. Day-trip destination exploration may be undated; obtain an exact day and departure/return bounds before turning it into an actionable itinerary. State whether the drive limit is one way or total; never silently exceed it.

Default to broad discovery. Ask or infer from explicit context whether the outing is adults-only, kids, or mixed family; never infer a home address, exact ages, disabilities, budget or travel radius. Keep narrow constraints out of discovery. Rank only after inventory capture and merging. Physical engagement is an optional preference, not a universal definition of quality.

Discovery-first requests should lead with distinctive and newly found options and show practical backups separately. Fit-first requests should optimize the stated outing. Do not let convenience eliminate interesting candidates during collection. Return fewer verified picks when evidence is insufficient rather than padding the shortlist.

## Execution boundary

The engine is executable and testable, but browsing and judgment remain host responsibilities. A stage attestation cannot prove that live research happened. Never present synthetic fixtures or unvisited URLs as researched events. The current source graph is sparse; expand it through observed relationships and disclose gaps.
