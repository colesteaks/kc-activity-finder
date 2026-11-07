# Research workflow

Use all eight stages in order. A stage can be brief when the request is narrow, but it cannot be silently replaced by a later stage.

## 1. Source graph

Load `data/source-graph.json` and record the run's `as_of` time. Sweep every active provided seed and the relevant active descendants already in the graph.

Build a small coverage matrix before browsing:

- requested dates or signup horizon;
- requested interests and constraints;
- Kansas City metro versus regional wildcard slots;
- missing categories, dates, or geographies.

The matrix identifies gaps for stage 4. It is not permission to skip the graph.

## 2. Deep first-party sweep

For each relevant discovery node:

1. Inspect current issues, weekend roundups, calendars, and future-looking archive posts.
2. Follow promising outbound links to the official organizer, venue, registration, or ticket page.
3. Check the first-party page itself for date, time, location, cost, availability, deadline, restrictions, and cancellation notes.
4. Capture the exact page and observation time supporting each material field.
5. Note inaccessible pages or missing evidence rather than filling details from memory.

An organizer-owned event page, venue-owned calendar, official registration form, or authorized ticket page counts as first party. A search snippet, repost, generic event directory, social summary by an unrelated account, or editorial newsletter does not.

For `weekend-current`, prioritize the newest issue and relevant current calendars. For `signup-horizon`, also inspect future announcements, season schedules, registration pages, and on-sale notices.

## 3. Candidate capture

Write every plausible activity to a candidate ledger before ordinary web search. Follow `schemas/candidate.schema.json` and retain:

- discovery channel and discovery URL;
- source-graph node, when applicable;
- all first-party verification URLs and observation times;
- event time in `America/Chicago`;
- price range and fee uncertainty;
- availability or registration status and deadline;
- restrictions, weather sensitivity, and logistics relevant to fit;
- a stable dedupe key.

Keep excluded candidates in the same complete ledger with a short reason such as `outside-window`, `sold-out`, `preference-conflict`, or `unverified` so later search does not repeatedly rediscover them.

## 4. Broader web search

Only now run targeted searches to fill the matrix gaps. Prefer queries combining an underserved area, activity type, and date or signup window. Examples of valid intentions include:

- a Lawrence option when the graph produced only KC-metro candidates;
- open fall race registration when the user wants signup-worthy fitness events;
- a first-party page for a candidate whose graph source supplied incomplete logistics.

Label new discoveries `broader-web-search`. Open and verify the first-party page before allowing the candidate to advance. A search result alone is never sufficient evidence.

## 5. Merge

Merge records that refer to the same real-world activity. Use normalized title, organizer, venue, and start time; do not rely on title alone.

When merging:

- preserve every discovery and verification URL;
- prefer first-party facts over editorial or aggregator summaries;
- keep the most recently observed availability state;
- retain material conflicts as caveats until resolved;
- never relabel a web discovery as a provided seed.

Recurring series with meaningfully different dates remain separate occurrences unless the answer is recommending the series itself.

## 6. Fit-based ranking

Read `references/ranking.md`. Apply hard gates, score survivors, and document penalties. Use the selected mode when interpreting timing and actionability.

Ranking creates a review order. It does not authorize recommending a poorly verified high scorer.

## 7. Adversarial review

Apply `references/adversarial-review.md` to every likely selection. Attempt to disprove that each candidate is current, available, accurately described, and appropriate for the request. Resolve failures, demote uncertain candidates, and drop failed candidates.

If an attractive result fails, review the next ranked candidate rather than weakening the checklist.

## 8. Recommendation

Use `references/output-contract.md`. Lead with a small useful recommendation layer, followed by the complete inventory and exclusions. Each selection must explain the fit, give actionable logistics and a first-party link, and disclose material uncertainty or urgency.

## Completion condition

Stop when:

- the source graph has been swept and documented;
- at least one gap-oriented broader search pass has been completed when gaps exist;
- the candidate ledger is merged and ranked;
- every selected candidate has first-party evidence and passes adversarial review; and
- another search pass is unlikely to change the selected set materially.

If evidence is insufficient, return fewer recommendations and say what could not be verified.

