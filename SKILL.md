---
name: kc-activity-finder
description: Find and rank well-verified activities in and around Kansas City for current/weekend plans or longer-horizon signups. Use when recommendations should begin with the maintained KC source graph, verify details on first-party pages, and use broader web search only to fill gaps.
---

# KC Activity Finder

Recommend activities through the fixed sequence below. Do not skip or reorder stages:

**source graph -> deep first-party sweep -> candidate capture -> broader web search -> merge -> fit-based ranking -> adversarial review -> recommendation**

## Invariants

- Start every run from [`data/source-graph.json`](data/source-graph.json). Broader web search supplements that graph; it never replaces the graph sweep.
- Follow source-graph links through to the organizer, venue, registration, or ticketing page. Treat snippets, aggregators, newsletters, and search results as discovery evidence, not final verification.
- Verify date, time, location, price, availability, deadline, and material restrictions from first-party evidence whenever those fields affect the recommendation. Label anything still uncertain.
- Keep Kansas City metro central. Include Lawrence, Columbia, Bentonville, and surrounding areas when the fit or distinctiveness justifies the trip; do not let distant results crowd out strong KC options.
- Separate source prominence from user fit. Sponsorship, repetition, and search rank do not earn ranking points.
- Preserve provenance through merging. A broader-search discovery remains labeled as such even after first-party verification.
- Do not recommend a candidate that fails a hard gate or the adversarial review.

## Choose a mode

- `weekend-current`: actionable options now, tonight, this week, or this weekend. Emphasize live availability, schedule accuracy, weather sensitivity, and practical logistics.
- `signup-horizon`: races, festivals, classes, timed-entry experiences, and ticketed events worth reserving in advance. Emphasize on-sale status, registration deadlines, lead time, and calendar value.

If the request spans both, run both modes and present separate sections.

## Run the workflow

Read [`references/workflow.md`](references/workflow.md) for the stage-by-stage procedure and candidate evidence rules. Capture candidates in the shape defined by [`schemas/candidate.schema.json`](schemas/candidate.schema.json).

Before scoring, read [`references/ranking.md`](references/ranking.md). Apply hard gates first, then the mode-aware 100-point rubric. Scores organize judgment; they do not replace it.

Before producing the answer, read and apply [`references/adversarial-review.md`](references/adversarial-review.md). Use [`references/output-contract.md`](references/output-contract.md) for the final response.

When maintaining the graph itself, follow [`references/updating-sources.md`](references/updating-sources.md). Never rewrite the supplied seed file to make maintenance more convenient.
