# KC Activity Finder — Transformation Plan & PR Handoff Ledger

- **Worktree:** `/Users/colejurden/Development/kc-activity-finder-review`
- **Branch:** `review/adversarial-audit`
- **Base Commit:** `66530ca` (`main`, snapshot `2026-11-24T15:24:55-06:00`)
- **Local Runtime (`.venv`):** Python `3.9.6` (`jsonschema==4.25.1`, `beautifulsoup4==4.15.0`, `python-dateutil==3.0.0`, `brotli==1.2.1`, `tzdata==2026.6`); CI runs Python `3.12` (`requirements.txt` + `requirements-collector.txt`) + Node `25.x`

> **For any successor agent taking over from this branch/PR:**
> 1. Inspect the milestone checklist below to find the first `[ ]` milestone.
> 2. Activate `.venv` inside the worktree root and run all verification commands listed under **PR Handoff Protocol** before making edits.
> 3. Complete the next milestone, update the checklist + measured metrics + commit SHA table in this file, verify all tests pass, and commit atomically.

---

## Preserved Repository Invariants (Do Not Break)

1. `data/primary-sources.txt` (`KC daily`, SHA-256 `0a268fbfd2c4098c22795598bd4b11fa81809878f0928e9469945e1d479627d3`) and the `provided-seed` node in `data/source-graph.json` remain verbatim and untouched.
2. All 33 `REQUIRED_FILES`, 8 `EXPECTED_STAGES` in `data/workflow.json`, and 5 `REQUIRED_COVERAGE` regions (`Kansas City metro`, `Lawrence`, `Columbia`, `Bentonville`, `surrounding areas`) stay intact (`scripts/validate_repo.py`).
3. `VERSION` (`1.1.0`), `SKILL.md` frontmatter `metadata.version`, and `CHANGELOG.md` remain synchronized (`scripts/build_release.py` + `scripts/verify_release.py`).
4. Python code stays Python 3.9+ compatible (`from __future__ import annotations`, no `match/case` or PEP 604 `|` union runtime syntax) so both macOS Python 3.9.6 `.venv` and CI Python 3.12 pass.
5. Zero fabricated URLs, ages, prices, hours, or event dates; `robots.txt` and 403/429 access blocks are respected strictly.

---

## Baseline Empirical Snapshot (`66530ca`, `2026-11-24`)

| Metric | Baseline (`66530ca`) | Current (`review/adversarial-audit`) | Target |
| --- | --- | --- | --- |
| Total records / distinct `offering_id`s | 3,478 / 1,105 | 3,618 / 1,128 | Higher diversity, lower repeat bloat |
| Top-3 source share (`visitkc` + `kc-library` + `momentary`) | 93.5% (3,254 / 3,478) | 93.1% (3,367 / 3,618) | < 70% |
| Regional distribution (`KC` / `Bentonville` / `Columbia` / `Lawrence` / `Surrounding`) | 3,162 / 285 / 24 / 7 / 0 | 3,291 / 295 / 24 / 8 / 0 | Meaningful multi-region + day/weekend corridors |
| `web/activities.json` payload (and relational `bundle.min.json`) | 11 MB (`activities.json` only) | 10,062,801 bytes minified + 988,605 byte bundle | Minified `activities.json` + < 1 MB `bundle.min.json` |
| Age guidance present (`ages.min`/`all_ages`) vs discovery `hints` | 28 (0.8%) / none | 28 (0.8%) / 3,618 audience hints (100%) | Strict `ages` preserved + >85% `hints.audience` |
| Stale / disappeared records | 454 (13.1%) | 496 (13.7%) | < 5% (with 14-day TTL + yield-drop guard) |
| Active live structured parsers vs total routes | 19 / 56 | 18 structured routes with events / 59 registry routes (32 routes contributed any record) | 7 reusable platform adapters + multi-region live sources |
| `data/places.json` entries (with coordinates) | 12 (9 with coords) | 15 (15 with coords; 3 prior gaps Census-matched, 3 new Census matches) | 30+ places with US Census verified coordinates |
| Python unit tests / Node tests | 100 / 24 | 140 / 28 | All green + full coverage of new features |

---

## Milestone Checklist

- [x] **M0: Dev Environment & Handoff Ledger**
  - Create `.venv`, install dependencies (`beautifulsoup4==4.15.0`, `python-dateutil==3.0.0`, `jsonschema==4.25.1`, `brotli==1.2.1`), verify baseline (`validate_repo.py`, `100` Python tests, `24` Node tests, `validate_public_data.py`), write `docs/TRANSFORMATION_PLAN.md`.
- [x] **M1: Collector Reliability Fixes, Stuck PR Ports & Zombie Cleanup**
  - Fixed Brotli (`br`) crash (`truman`), `kc-zoo` compact TZ & end-before-start handling, Drupal load-more selector + `>40%` yield-drop circuit breaker (`status: "degraded"`), 14-day TTL on disappeared records, Visit KC suburban city inference (`infer_metro_city`).
  - Ported `origin/maintain/nelson-tnew-calendar` (`tnew_events`, `detail_hosts`, fixtures/tests), `origin/maintain/bentonville-calendar-2026-W48` (`downtown_events`, fixtures/tests), and `origin/maintain/museum-hours-2026-W47` (`crystal-museum` verified hours + fixture test).
  - Purged 6 dead single-event Nov 7 captures (`kc-pet-fest`, `central-avenue-dia`, `troost-united`, `dfscon`, `crossroads-flea`, `ls-mistletoe`), updated `kcopera` → `https://kcopera.org/events/` and `mavericks` → `https://kcmavericks.com/schedule`, rebuilt `examples/*-run.json` & `*-report.md`.
- [x] **M2: 7 Reusable Platform Adapters + Fuzzy Cross-Source Deduplication**
  - Implemented `scripts/platform_adapters.py`: `ics` (RFC 5545 unfolding + `RRULE` + `EXDATE`), `rss` (RSS 2.0/Atom explicit-date only), `localist`, `simpleview`, `bibliocommons`, `libcal`, `civicplus`, `mlb_schedule` (`home_only`), `mdc`, and env-gated `ticketmaster`.
  - Wired all 10 platform formats into `scripts/collect_activities.py` and upgraded `reconcile()` with canonical venue normalization + token-set Jaccard (`>= 0.72`) cross-source corroboration while preserving multi-session showtimes. Added fixtures & 9 tests in `tests/test_platform_adapters.py`.
- [x] **M3: Two-Layer Transparent Enrichment, 2-Tier Geo Hierarchy, Depth Matrix & Census Geocoder**
  - Implemented `scripts/geo_model.py` (`corridor`, `subregion`, `municipality`, `drive_band`, `amtrak_accessible`), `scripts/enrichment.py` (`hints`: `audience`, `free_likely`, `indoor_outdoor`, `time_of_day`, `is_promo`, `novelty`, `standout_score`), and `scripts/geocode_places.py` (US Census Geocoder; tested with a stub fetch, not applied to `data/places.json`).
  - Updated `activity_model.py`, `schemas/activity.schema.json`, `data/activity-taxonomy.json`, `data/workflow.json`, and `weekly_discovery_brief.py` (depth tiers + `kc-daily-source-map` frequency × platform scoring). Published inventory metrics are unchanged until a collection run.
- [x] **M4: Verified Live Source Expansion, Place Geocoding & Graph Sync**
  - Added `scripts/probe_sources.py`. Probed 18 repository-known https feeds: 17 tier 1, 1 unassigned, 0 tier 2, 0 tier 3. Promoted Kansas City Convention Center ICS (9 events) and Nelson-Atkins RSS, plus discovery-only rows for fetched feeds with no explicit dates. Comment feeds and one-off `.ics` exports were withheld. 403/robots/redirect failures were not recorded as empty calendars.
  - Census-geocoded the 3 places that already had addresses and no coordinates, and added Gieringer’s Family Farm, Cider Hill Family Orchard, and Deanna Rose Children’s Farmstead from addresses already written in source proposals. `data/places.json` is 15/15 with coordinates. Official pages did not yield enough schema.org street addresses to reach 30.
  - Appended reviewed-supplement graph nodes without changing the `provided-seed` node. Local collection (not the GitHub workflow) wrote 3,618 activities.
- [x] **M5: Compact Relational Bundle, Static RSS Feeds & CI/Pages Decoupling**
  - `scripts/build_web_bundle.py` writes minified `web/activities.json`, relational `web/bundle.min.json` (988,605 bytes), and 13 explicit-date feeds in `web/feeds/`.
  - `.github/workflows/activities.yml` tests on the existing path filters, commits scheduled refreshes to the `data` branch, and deploys Pages only for a manual run with deploy enabled. This branch was not dispatched.
- [x] **M6: Consumer Web App Transformation (`web/`)**
  - Added `web/data-loader.mjs`, `web/ics.mjs`, and `web/saved.mjs`. `web/filters.mjs` has presets, standout ordering, generalized promotion detection, and hint filters. The list defaults to standout hints, cards omit long descriptions, and coverage shows depth counts plus RSS links. Saved items stay in `localStorage`.
- [x] **M7: Unify the Agent Skill (`scripts/query_inventory.py`, `SKILL.md` & Docs)**
  - Added `scripts/query_inventory.py` and tests. `SKILL.md` documents the index-first lookup and keeps the eight-stage ledger for recommendations. README, changelog, and the reference docs point at hints, feeds, probes, and the data branch.
- [x] **M8: Full CI Verification Matrix & PR-Ready Final Handoff**
  - Local matrix passed: `validate_repo.py`, 140 Python tests, 28 Node tests, `validate_public_data.py` (3,618 activities), release smoke test, and `git diff --check`.

### Still short of the numeric targets

- Top-3 source share is 93.1%, not under 70%.
- Stale/disappeared records are 496 (13.7%), not under 5%.
- Place coordinates are 15, not 30+. Tier 2 and tier 3 have no reviewed feed URLs in the repo, and the new corridor regions have no collected events.
- Verified age guidance is still 28 records (0.8%). Audience hints are labels on every row and do not change those ages.

---

## Commit Log

| Milestone | Commit SHA | Notes |
| --- | --- | --- |
| M0 | `77d1d1b` | Baseline verified: 100 Python tests, 24 Node tests, 3,478 public records valid |
| M1 | `65d7634` | 118 Python tests, 24 Node tests, `validate_repo` + `validate_public_data` passing |
| M2 | `7c2448a` | 127 Python tests, 24 Node tests; 10 platform adapters + fuzzy dedup |
| M3 | `5828003` | 133 Python tests, 24 Node tests; hints, geo metadata, depth tiers, Census geocoder helper |
| M4 | `61f3526` | Probe report, 9 promoted routes, 15 geocoded places, local collection to 3,618 activities |
| M5 | `6c86299` | 988,605 byte bundle, 13 RSS feeds, collection commits to `data` |
| M6 | `ecff262` | Bundle loader, hint presets, calendar export, saved list |
| M7 | `1057d55` | `query_inventory.py` and skill docs |
| M8 | *(in this commit)* | 140 Python tests, 28 Node tests, validators and release smoke test |

---

## PR Handoff Protocol

To resume or verify work on branch `review/adversarial-audit`:

```sh
cd /Users/colejurden/Development/kc-activity-finder-review
.venv/bin/python scripts/validate_repo.py
.venv/bin/python -m unittest discover -s tests -q
node --test tests/test_*.mjs
.venv/bin/python scripts/validate_public_data.py
.venv/bin/python scripts/build_release.py --output /tmp/kc-skill-release-check
.venv/bin/python scripts/verify_release.py /tmp/kc-skill-release-check/kc-activity-finder-v$(cat VERSION).zip --smoke-test
git diff --check
```
