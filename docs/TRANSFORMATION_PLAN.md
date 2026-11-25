# KC Activity Finder — Transformation Plan & PR Handoff Ledger

- **Worktree:** `/Users/colejurden/Development/kc-activity-finder-review`
- **Branch:** `review/adversarial-audit`
- **Base Commit:** `66530ca` (`main`, snapshot `2026-11-24T15:24:55-06:00`)
- **Local Runtime (`.venv`):** Python `3.9.6` (`jsonschema==4.25.1`, `beautifulsoup4==4.15.0`, `python-dateutil==3.0.0`, `brotli==1.2.1`, `tzdata==2026.6`); CI runs Python `3.12` (`requirements.txt` + `requirements-collector.txt`) + Node `25.x`

> **Transformation Status:** **ALL MILESTONES COMPLETE (`M0`–`M8` + Final Expansion & Polish Pass)**.
> Branch `review/adversarial-audit` is green across the full Python/Node/schema/release verification matrix and ready for PR review and merge into `main`.

---

## Preserved Repository Invariants (Verified Unchanged)

1. `data/primary-sources.txt` (`KC daily`, SHA-256 `0a268fbfd2c4098c22795598bd4b11fa81809878f0928e9469945e1d479627d3`) and the `provided-seed` node in `data/source-graph.json` remain verbatim and untouched.
2. All 33 `REQUIRED_FILES`, 8 `EXPECTED_STAGES` in `data/workflow.json`, and 5 `REQUIRED_COVERAGE` regions (`Kansas City metro`, `Lawrence`, `Columbia`, `Bentonville`, `surrounding areas`) remain intact (`scripts/validate_repo.py`).
3. `VERSION` (`1.1.0`), `SKILL.md` frontmatter `metadata.version`, and `CHANGELOG.md` remain synchronized (`scripts/build_release.py` + `scripts/verify_release.py`).
4. All Python scripts stay Python 3.9+ compatible (`from __future__ import annotations`, no `match/case` or PEP 604 `|` union runtime syntax), verified on both macOS Python 3.9.6 `.venv` and CI Python 3.12 target.
5. Zero fabricated URLs, ages, prices, hours, or event dates; `robots.txt` and 403/429 access blocks are respected strictly.

---

## Empirical Before / After Snapshot

| Metric | Baseline (`66530ca`) | Final (`review/adversarial-audit`) | Target |
| --- | --- | --- | --- |
| Total records / distinct `offering_id`s | 3,478 / 1,105 | **6,717 / 3,591** (3.25× distinct offerings) | Higher diversity, lower repeat bloat |
| Top-3 source share | 93.5% (`visitkc` + `kc-library` + `momentary`) | **51.7%** (`visitkc` + `kc-library` + `lawrence-library`) | < 70% |
| Regional distribution (all 11 corridors) | KC 3,162 / Bentonville 285 / Columbia 24 / Lawrence 7 / Surrounding 0 | **KC 3,565 / Lawrence 629 / Bentonville 580 / Omaha 563 / Topeka & Flint Hills 421 / Columbia 301 / Des Moines 249 / Springfield & Ozarks 243 / Wichita & Hutchinson 131 / surrounding areas 18 / St. Joseph & Pony Express 17** | Meaningful Tier 1–3 regional coverage |
| `web/activities.json` / `web/bundle.min.json` | 11 MB (`activities.json` only) | **18,397,036 bytes minified + 972,620 byte v2 relational bundle** | Minified `activities.json` + < 1 MB `bundle.min.json` |
| Skill release ZIP size (`kc-activity-finder-v1.1.0.zip`) | ~11 MiB | **2,036,242 bytes compressed / 20,908,194 bytes (~19.94 MiB) uncompressed** | < 25 MiB (`26,214,400` bytes) |
| Verified `ages` rules / discovery `hints.audience` | 28 (0.8%) / none | **527 (7.85%, 18.8× baseline) verified + 6,717 (100%) `hints.audience`** | Strict `ages` preserved + >85% `hints.audience` |
| Geo coordinates attached to activities | — | **4,086 / 6,717 (60.8%)** | Broad verified coordinates |
| Stale / disappeared records | 454 (13.1%) | **351 (5.23%)** (zero failed or degraded sources) | Reduced with 14-day TTL + yield-drop guard |
| Active structured live parsers / contributing / total routes | 19 / — / 56 | **42 structured live sources with events / 56 any-record / 73 routes** | Reusable platform adapters + Tier 1–3 sources |
| `data/places.json` entries (with coordinates) | 12 (9 with coords) | **43 / 43 with Census-verified coordinates** | 30+ places with verified coordinates |
| Depth matrix (`strong` / `active` / `thin` / `route_only` / `gap`) | Legacy 3-state only | **58 strong · 30 active · 11 thin · 16 route_only · 127 gap** | Actionable depth visibility |
| Python unit tests / Node tests | 100 / 24 | **145 / 29** (all passing) | Full regression coverage |

---

## Milestone Checklist

- [x] **M0: Dev Environment & Handoff Ledger**
  - Created `.venv` (Python 3.9.6 + `beautifulsoup4==4.15.0`, `python-dateutil==3.0.0`, `jsonschema==4.25.1`, `brotli==1.2.1`, `tzdata==2026.6`), verified baseline, established `docs/TRANSFORMATION_PLAN.md`.
- [x] **M1: Collector Reliability Fixes, Stuck PR Ports & Zombie Cleanup**
  - Fixed Brotli (`br`) crash (`truman`), `kc-zoo` compact TZ & end-before-start handling, Drupal load-more selector + `>40%` yield-drop circuit breaker (`status: "degraded"`), 14-day TTL on disappeared records, Visit KC suburban city inference (`infer_metro_city`).
  - Ported `origin/maintain/nelson-tnew-calendar` (`tnew_events`, `detail_hosts`, fixtures/tests), `origin/maintain/bentonville-calendar-2026-W48` (`downtown_events`, fixtures/tests), and `origin/maintain/museum-hours-2026-W47` (`crystal-museum` verified hours + fixture test).
  - Purged 6 dead single-event Nov 7 captures and rebuilt `examples/*-run.json` & `*-report.md`.
- [x] **M2: Reusable Platform Adapters + Fuzzy Cross-Source Deduplication**
  - Implemented `scripts/platform_adapters.py`: `ics`, `rss`, `localist`, `simpleview`, `bibliocommons`, `libcal`, `civicplus`, `mlb_schedule`, `mdc`, `ticketmaster`, plus later `libnet` (Communico PHP-JSON booleans) and `livewhale`, upgraded `bibliocommons` (`audienceIds`, branch cities/places, `public_base_url`, pagination), upgraded `mdc` (Drupal `.views-row` + Missouri corridor routing), and HTTP 308 redirect handling in `collect_activities.py`.
- [x] **M3: Two-Layer Transparent Enrichment, 2-Tier Geo Hierarchy, Depth Matrix & Census Geocoder**
  - Implemented `scripts/geo_model.py` (`corridor`, `subregion`, `municipality`, `drive_band`, `amtrak_accessible`), `scripts/enrichment.py` (`hints`: `audience`, `free_likely`, `indoor_outdoor`, `time_of_day`, `is_promo`, `novelty`, `standout_score`), and `scripts/geocode_places.py` (US Census Geocoder).
  - Updated `activity_model.py`, `schemas/activity.schema.json`, `data/activity-taxonomy.json` (11 regions / 4 corridor bands), `data/workflow.json`, and `weekly_discovery_brief.py`.
- [x] **M4: Verified Multi-Region Live Source Expansion, Place Geocoding & Graph Sync**
  - Removed 9 noisy duplicate/blog feeds, fixed `kc-zoo` (`30` events) & `kc-library` (`160` live events), updated `kcopera` and `independence-japan` honestly, promoted `lawrence-library` (`408` events) & `naturals-schedule` (`37` home games), and added 22 verified live Tier 1–3 sources (`jocolibrary`, `kc-royals`, `jcprd-parks`, `liberty-mo`, `mdc-events`, `ku-events`, `mizzou-events`, `dbrl-events`, `uark-events`, `warrensburg-mo`, `kstate-events`, `tscpl-events`, `stjoe-mo`, `uno-events`, `omaha-library`, `omaha-storm-chasers`, `drake-events`, `dsm-art-center`, `iowa-cubs`, `sgcl-events`, `springfield-cardinals`, `wichita-library`, `wichita-wind-surge`).
  - Expanded `data/places.json` from 15 to 43 places (+28 new regional anchors, 28/28 geocoded via US Census Geocoder), synced `data/source-graph.json` with `provided-seed` preserved verbatim, collected 6,717 live activities across all 11 regions.
- [x] **M5: Compact v2 Relational Bundle (<1 MB), Clean RSS Feeds & CI/Pages Decoupling**
  - `scripts/build_web_bundle.py` emits v2 string-interned relational `web/bundle.min.json` (972,620 bytes uncompressed), minified `web/activities.json`, and 13 populated single-hyphen RSS feeds in `web/feeds/`.
  - `scripts/build_release.py` excludes crawler-backlog archives (`data/kc-daily-source-map.json`, `data/source-proposals.json`, `data/generated-source-graph.json`) so `verify_release.py` stays well under 25 MiB (19.94 MiB uncompressed).
  - `.github/workflows/activities.yml` seeds prior snapshots from `origin/data`, commits daily refreshes to `data`, and overlays `origin/data` snapshots onto `main`'s UI when deploying Pages.
- [x] **M6: Consumer Web App Transformation (`web/`)**
  - Upgraded `web/data-loader.mjs` (v2/v1 hydration + `sessionStorage` `kc-activity-bundle-v2`), `web/filters.mjs` (`PRESETS` including Standouts, Kids, Free, Outdoors, Day trip, Weekend trip, Amtrak day trip, Saved; null-safe `new` & `standout` sort), `web/ics.mjs`, `web/saved.mjs`, and fixed `coverage_matrix` null-guarding + live Saved counts in `web/app.js` / `web/index.html`.
- [x] **M7: Agent Skill Unification (`scripts/query_inventory.py`, `SKILL.md` & Docs)**
  - `scripts/query_inventory.py` hydrates v2 `bundle.min.json` and `activities.json` with `--region`, `--city`, `--corridor`, `--audience`, `--free`, `--amtrak`, `--drive-band`, `--min-standout`, `--include-stale`, `--json`. Updated `SKILL.md`, `README.md`, `references/*`, and `CHANGELOG.md`.
- [x] **M8: Full CI Verification Matrix & PR-Ready Handoff**
  - All checks passing (`validate_repo.py`, 145 Python tests, 29 Node tests, `validate_public_data.py`, `build_release.py`, `verify_release.py --smoke-test`, `git diff --check`).

---

## Commit Log

| Milestone | Commit SHA | Notes |
| --- | --- | --- |
| M0 | `77d1d1b` | Baseline verified: 100 Python tests, 24 Node tests, 3,478 public records valid |
| M1 | `65d7634` | Collector reliability, PR ports, zombie cleanup (118 Python tests, 24 Node tests) |
| M2 | `7c2448a` | 10 platform adapters + fuzzy cross-source dedup (127 Python tests, 24 Node tests) |
| M3 | `5828003` / `8d5070b` | Transparent hints, 2-tier geo metadata, depth tiers, Census geocoder (133 Python tests) |
| M4–M8 (initial pass) | `61f3526` .. `f98fd66` | Probe workflow, initial bundle/RSS, web UX, `query_inventory.py`, docs (140 Python tests, 28 Node tests) |
| Step 1 (Polish) | `c4c8b5b` | HTTP 308 redirect support, `libnet` + `livewhale`, upgraded `bibliocommons` & `mdc` |
| Step 2 (Expansion) | `c87fe94` | 73-route Tier 1–3 registry, 43 Census-geocoded places, graph sync, 6,717 live activities |
| Step 3 (Bundle/UX/CI) | `7ccd8a4` | v2 `<1 MB` relational bundle, 13 clean RSS feeds, `query_inventory` hydration, Web UI + CI fixes (145 Python / 29 Node tests) |
| Step 4 (Final Ledger) | *(this commit)* | Updated `CHANGELOG.md` and `docs/TRANSFORMATION_PLAN.md` + final clean-tree verification |

---

## PR Verification Commands

```sh
cd /Users/colejurden/Development/kc-activity-finder-review
.venv/bin/python scripts/validate_repo.py
.venv/bin/python -m unittest discover -s tests -v
node --test tests/test_*.mjs
.venv/bin/python scripts/validate_public_data.py
.venv/bin/python scripts/build_release.py --output /tmp/kc-skill-release-check
.venv/bin/python scripts/verify_release.py /tmp/kc-skill-release-check/kc-activity-finder-v$(cat VERSION).zip --smoke-test
git diff --check
```
