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
| Total records / distinct `offering_id`s | 3,478 / 1,105 | 3,478 / 1,105 | Higher diversity, lower repeat bloat |
| Top-3 source share (`visitkc` + `kc-library` + `momentary`) | 93.5% (3,254 / 3,478) | 93.5% | < 70% |
| Regional distribution (`KC` / `Bentonville` / `Columbia` / `Lawrence` / `Surrounding`) | 3,162 / 285 / 24 / 7 / 0 | 3,162 / 285 / 24 / 7 / 0 | Meaningful multi-region + day/weekend corridors |
| `web/activities.json` payload (and relational `bundle.min.json`) | 11 MB (`activities.json` only) | 11 MB | Minified `activities.json` + < 1 MB `bundle.min.json` |
| Age guidance present (`ages.min`/`all_ages`) vs discovery `hints` | 28 (0.8%) / none | 28 (0.8%) / none | Strict `ages` preserved + >85% `hints.audience` |
| Stale / disappeared records | 454 (13.1%) | 454 (13.1%) | < 5% (with 14-day TTL + yield-drop guard) |
| Active live structured parsers vs total routes | 19 / 56 | 21 / 50 (10 new platform adapter engines built & wired) | 7 reusable platform adapters + multi-region live sources |
| `data/places.json` entries (with coordinates) | 12 (9 with coords) | 12 (9 with coords; `crystal-museum` verified hours ported) | 30+ places with US Census verified coordinates |
| Python unit tests / Node tests | 100 / 24 | 133 / 24 | All green + full coverage of new features |

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
- [ ] **M4: Verified Live Source Expansion, Place Geocoding & Graph Sync**
  - Create `scripts/probe_sources.py`, probe official feeds across Tier 1 backyard/metro/Lawrence/Columbia/NWA + Tier 2 day trips + Tier 3 weekend powerhouses, promote verified parsers + honest discovery/evergreen entries, geocode & expand `data/places.json`, sync `data/source-graph.json`, run collection.
- [ ] **M5: Compact Relational Bundle, Static RSS Feeds & CI/Pages Decoupling**
  - Create `scripts/build_web_bundle.py` (`web/bundle.min.json` + `web/feeds/*.xml`), minify `web/activities.json`, decouple daily data commits from `main` onto a `data` branch and split `build`/`deploy` jobs in `.github/workflows/activities.yml`.
- [ ] **M6: Consumer Web App Transformation (`web/`)**
  - Add `web/data-loader.mjs` (bundle hydration + `sessionStorage`), `web/ics.mjs` (RFC 5545 export), upgrade `web/filters.mjs` (`PRESETS`, `standoutScore`, generalized `isPromotion`, hint filters), and update `index.html`/`app.js`/`activity.html`/`activity.js`/`styles.css` (presets, standouts default, clean cards, LocalStorage Saved List, Depth coverage + RSS links).
- [ ] **M7: Unify the Agent Skill (`scripts/query_inventory.py`, `SKILL.md` & Docs)**
  - Create `scripts/query_inventory.py`, update `SKILL.md` (index-first fast path + 8-stage ledger compatibility), `README.md`, `references/*.md`, `CHANGELOG.md`, and tests.
- [ ] **M8: Full CI Verification Matrix & PR-Ready Final Handoff**
  - Run `validate_repo.py`, `unittest -v`, `node --test`, `validate_public_data.py`, `build_release.py`, `verify_release.py --smoke-test`, `git diff --check`; finalize metrics & PR summary.

---

## Commit Log

| Milestone | Commit SHA | Notes |
| --- | --- | --- |
| M0 | `77d1d1b` | Baseline verified: 100 Python tests, 24 Node tests, 3,478 public records valid |
| M1 | `65d7634` | 118 Python tests, 24 Node tests, `validate_repo` + `validate_public_data` passing |
| M2 | `7c2448a` | 127 Python tests, 24 Node tests; 10 platform adapters + fuzzy dedup |
| M3 | *(in this commit)* | 133 Python tests, 24 Node tests; hints, geo metadata, depth tiers, Census geocoder helper |

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
