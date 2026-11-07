# Execution guide

For day-trip destination comparisons and itineraries, use [day-trip planning](day-trips.md), `schemas/day-trip.schema.json` and `scripts/day_trip_planner.py`. The event-ledger commands and fixed-time candidate rules below apply to weekend/signup modes; do not invent event dates to put an evergreen day-trip anchor into them.

## Research artifacts

Initialize from a request matching `schemas/query.schema.json`. Copy an example request and replace the dates, as_of time and party. Use an offset-aware as_of timestamp in America/Chicago, e.g. `2026-11-07T09:00:00-06:00`. The date window includes both endpoints.

The run contains the request, complete graph digest, coverage ledger, candidate inventory, search history, merge originals, ranked IDs with exclusion reasons, proposed graph additions, and review. `examples/weekend-run.json` and `signup-run.json` illustrate the complete runtime shape. Do not use `--fixture` for live research.

Every candidate follows `candidate.schema.json`. Runtime ranking also requires `fit` with six score/reason pairs. `audience`, `registration`, `travel_minutes`, conflicts and tradeoffs carry audience and logistics facts separately from judgment. `ranking` is retained for backward compatibility with the original seven-factor examples; the engine uses `fit` and request weights. Never compare the two scales as equivalent.

Unknown starts, age limits, prices and deadlines are null. Unknown start or availability cannot be recommended. Registration states include closed and not-open. Keep those rows for future radar/watch lists. For confirmed all-ages policies, record practical numeric bounds with the supporting quotation and explain any upper-bound representation; never invent a maximum age to bypass an unknown policy.

## Coverage and search

Coverage row: `{node_id, status, observed_at, visited_urls, notes}`. Complete exactly one row for every active graph node. Checked/empty need actual visit URLs and an offset timestamp. Failed/deferred need a reason and appear as partial coverage. Record discovered leaf visits in visited_urls and candidate evidence; propose persistent graph nodes separately.

Search row: `{region, query, observed_at, outcome}`. Record all five geography labels from workflow.json. An inaccessible search or no results must be explained in outcome; the tool does not equate a query with comprehensive coverage. Use date/year, age-neutral category, municipality, seasonal and signup variants. Revisit omitted categories before claiming high recall.

## Evidence

Verification entries include `evidence_type`, `url`, `observed_at`, `supports` and `quote`. Runtime support tokens are identity, date, time, location, availability, ages, registration and deadline as applicable. Quote the passage supporting each claim. Fresh first-party evidence must support all required tokens; an unrelated quotation with fabricated tokens is invalid research even though no local validator can detect that lie. Verify registration-provider links from the official organizer.

Date/time and availability always require current official evidence; age evidence is required when participant ages are specified. Signup requires a confirmed registration action and fresh registration evidence. Known deadlines require explicit deadline evidence. Unknown prices and travel estimates are disclosed; strict budget/travel filters exclude unknowns. Costs are per person in USD; do not use that filter as a claimed total family budget. Capture mandatory fees in the maximum or mark fees unknown.

## Review

After ranking, populate review with `{reviewer, blocking_findings: [], candidates: {candidate_id: [{id, status, notes}]}}`. Eligible candidates require all ten check IDs listed in `activity_pipeline.CHECKS`, each pass with a meaningful note. A second pass by the same researcher is acceptable; independent review is encouraged for difficult conflicts. No second agent is required.

Complete the review stage to bind its digest to the facts, search history, coverage and ranking. Re-open changing availability near publication. Live reports reject an as_of clock older than 24 hours. Freshness can be tightened per request; increasing it requires a justified source-specific choice, not a way to rescue stale pages.

## Reusing an inventory

Copy the run, change the request filters/ages/weights, clear review, and reset completed to the first four stages. Rerun merge, ranking and review. This reuses the full inventory without dropping adult-only or child-ineligible rows. Refresh time-sensitive facts when the research clock changes. If graph identity changes, initialize a new run and migrate observations explicitly.

## Output and storage

Reports show eligible picks up to request.limit (default ten), plus every captured candidate and its exclusion reasons. Unknowns, failed coverage and source conflicts remain visible. Fixture reports carry FICTIONAL DEMO headings. Keep private runs outside Git; save user reports durably in the host environment.
