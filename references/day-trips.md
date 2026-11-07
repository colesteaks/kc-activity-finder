# Day-trip planning

Use this mode for “where could we go within X hours?”, “what is worth a day trip?”, destination comparisons and same-day itineraries. It belongs to the agent skill; no website feature, database, new scheduled research or paid routing integration is required. [Entry prompts](../prompts/day-trip.md) are reusable examples, not required wording.

## Start with a worthwhile destination

A destination earns a recommendation through activities that justify the drive. Do not return a radius-sorted city list or assemble a day from convenient filler. Start with one strong anchor, optionally a second nearby anchor, and explain what is distinctive: a landscape, hands-on experience, unusual collection, seasonal opportunity, performance or neighborhood cluster. A single excellent experience can justify the trip; more stops do not automatically make a better day.

Preserve alternatives and raw activity records, including unresolved or unavailable leads. Group actual venues/occurrences by destination after capture and deduplication. A destination is a coherent area with feasible transfers, not a whole region whose attractions are hours apart. Treat multiple daily occurrences of the same offering as one anchor choice. Keep cities, venues, park entrances, exhibit runs and activity instances distinct.

## Establish the request with minimal friction

- **Origin and driving limit:** use a supplied city/neighborhood or an origin explicitly established in the conversation. Do not infer an exact address. Ask for a missing origin or limit together. Convert hours to minutes. An unlabeled “within two hours” defaults to **one way**, stated explicitly. If wording suggests a round-trip/total budget, resolve that instead. Check the return direction as well as the outbound direction. A total-driving limit includes local transfers.
- **Date:** optional for initial destination exploration. Without a date, compare possibilities and label seasonal/event-dependent options, closed weekdays and booking windows. Do not assert a dated event, opening hours or availability for an unspecified visit. Before creating an actionable itinerary, get the exact date, departure and latest return; a date range can produce alternative days, not one ambiguous schedule.
- **People and preferences:** adult-only, kids, mixed group, actual ages when relevant, interests, accessibility, walking tolerance, food/budget needs and constraints such as naps or return time. Ask only what materially affects the next decision. Unknown age guidance is not all-ages eligibility. Children ages 0–5 are an optional party profile, never the discovery boundary.
- **Driving versus day length:** disclose outbound, return and local travel separately. A four-hour destination may technically fit a one-way cap yet leave too little worthwhile time for a day trip. Offer it only with that tradeoff, or as a separately labeled overnight idea if useful; never quietly exceed a hard constraint.

Do not require the user to choose a destination, supply an address, set every preference or commit to a date before showing useful initial options. Once they choose, reuse the inventory and ask only the remaining planning essentials. Do not book, buy or register on their behalf without explicit authorization.

## Apply the eight-stage workflow

Preserve the sequence in `SKILL.md`. The research agent performs live discovery and judgment; the helper below checks submitted travel and schedule facts.

1. **Source graph:** verify the unchanged `data/primary-sources.txt` seed via `data/source-graph.json`. Load reviewed collection routes, generated graph/place leaves and existing activity data as starting leads. Identify destinations in multiple directions within the requested driving envelope. Record relevant graph routes and explain deferred/out-of-scope routes. The default five regional bands are a starting graph, not a boundary: a qualifying destination outside them needs temporary official routes and a disclosed coverage gap. Do not include Bentonville merely because it is in the graph if it is beyond this user's limit.
2. **Deep first-party sweep:** explore relevant official tourism directories and then actual producers, venues, parks, trail/entrance maps, museum/exhibit pages, guided experiences, performance schedules, recreation programs and organizer-linked booking providers. Include permanent attractions, seasonal offerings and date-specific events. A tourism roundup is a sensor for a specific activity, not confirmation of its operation. Read facility hours rather than office/gate hours; separate park access from reservation-only activities.
3. **Candidate capture:** retain each activity's official URL, observation time, specific location/entrance, actual run/session dates or evergreen status, opening/closure rules, duration evidence or labeled planning allowance, eligibility/accessibility, costs/fees, booking requirements and uncertainty. Record the discovery channel and any conflicts. Capture weather sensitivity and likely transfer/parking friction. Do not filter by audience or discard inconvenient/unavailable leads during research.
4. **Broader search:** search missing destination corridors and activity categories beyond familiar sources. Log queries, visited sources, actual outcomes and gaps. For a dated request, check destination-specific events and exhibit runs on that day. Find producers behind aggregators and assess an indoor or sheltered alternative when useful. A bounded search cannot establish every possible option; report its limits.
5. **Deduplicate and merge:** merge exact duplicates while preserving provenance and material conflicts. Group activities into destination options. Do not combine separate dates, parks with similar names, different trail entrances or distant branches of a regional organization. Preserve rejected, out-of-range and unresolved options with reasons.
6. **Family/party-fit ranking:** rank destinations around their best anchors and the actual party. Use the dimensions below, then apply hard drive, timing, eligibility, budget and accessibility constraints. Compare 3–6 distinct destination choices when evidence supports them; return fewer rather than padding. Offer a useful nearby option, a more distinctive option and a defensible wildcard only when they add real choice. Avoid treating the shortest drive or most activities as the best trip.
7. **Adversarial review:** reopen official shortlisted activity/hours/booking pages and route estimates. Try to disprove the itinerary: wrong year/date, weekly closed day, seasonal facility closure, mismatched entrance, expired exhibit, sold-out slot, full-series commitment unsuitable for a visit, age/access mismatch, mandatory fees, travel before a timed booking, last admission before closing, unsupported transfer, rush-hour return or weather failure. Check meal/rest/parking time and the same-day return. Record reviewer, evidence and unresolved blockers. Use `day_trip_planner.py` for mechanical checks; passing it is not proof these research checks happened.
8. **Final recommendations:** deliver the destination comparison first. After selection, deliver one coherent itinerary, essential booking actions and a suitable backup, with exact dates/local times, costs/unknowns, driving estimates, key sources/check times and what could change the plan. Include the full destination/activity inventory, exclusions and compact source/search coverage as an appendix or durable linked artifact. Preserve proposed source additions separately; do not promote unreviewed routes just because a trip used them.

### Destination ranking

Use a transparent editorial assessment with a specific reason for each dimension. This is destination-level judgment, not the event engine's individual-candidate score:

| Dimension | What earns a stronger recommendation |
| --- | --- |
| Anchor quality and party fit | Activities the actual travelers have a compelling reason to experience; supported eligibility and practical access |
| Distinctiveness | Something meaningfully different from what they could do at home; no popularity, sponsorship or affiliate bonus |
| Day cohesion | Nearby complementary stops, realistic transfers, meals/rest and enough time at the main attraction |
| Time value | Worthwhile time at the destination relative to all driving; disclose the travel burden instead of optimizing only proximity |
| Confidence and resilience | Current first-party facts, actionable booking, feasible timing and an honest weather/closure backup |

Do not manufacture numeric precision or an inferred enthusiasm score. Explain the top choice, its tradeoff and whom another option suits better. Unknown preference fit stays neutral. A hard constraint cannot be rescued by a great anchor. Keep date-conditional ideas in the comparison, distinct from confirmed date-specific recommendations.

## Output at each step

**Destination exploration:** state origin, driving-limit interpretation, date/party assumptions and coverage limits. Compare destination, conservative outbound/return drive estimate with routing source, strongest anchor(s), why worth the drive, useful nearby additions, total-day implications, approximate known costs, booking/season/weather tradeoffs, activity evidence and confidence. Mark driving “unverified” when only rough estimates are available; it cannot be claimed to meet a strict radius. Show uncertain activity availability separately from route eligibility.

**Selected day:** show the exact date and a relaxed timeline with departure, primary anchor, optional complementary stop, meal/rest, explicit transfers, parking/check-in slack and return. Separate reserved/timed commitments from optional stops. Show what to reserve, what to recheck and an alternative that fits the actual party and date. Restaurant hours/reservations also need checking if a specific restaurant is promised. Flexible meals and unscheduled free time are allowances, not invented confirmed activities. Avoid packing the day to make the destination look better.

For distant trips or small children, fewer anchors and larger buffers are usually more credible than a long checklist. Follow the stated party and preferences rather than applying that profile universally.

## Keep research focused

Reuse fresh inventory and reviewed place/source leaves as leads, then verify the few anchors that could justify each destination. Initially compare up to six strong destination options; disclose unsearched directions/categories. Avoid building detailed itineraries, checking specific restaurants or repeating full route research for every option before the user chooses. After selection, spend the deeper verification effort on that day and backup. This controls browsing/model use while retaining rejected leads and reporting coverage honestly. Never relax a hard constraint or pretend to have checked an omitted source to save work.

## Deterministic feasibility helper

Day-trip research uses **`schemas/day-trip.schema.json`**, separate from the fixed-time event engine's `query.schema.json`/`run.schema.json`. Do not send this research object to `activity_pipeline.py init` or invent an event timestamp for a permanent attraction. The eight stages above are the agent's research protocol; this helper does not attest to their completion or render a researched recommendation by itself.

```sh
python3 -m pip install -r requirements.txt
python3 scripts/day_trip_planner.py examples/day-trip-research.json \
  --output /tmp/day-trip-checks.json
python3 -m unittest discover -s tests -p 'test_day_trip_planner.py' -v
```

The bundled example is explicitly **fictional**, with `fixture: true` and `example.test` URLs. It demonstrates the real checker, not real destination recommendations. Keep real research outside Git and set `fixture: false`. Supply an offset-aware current `request.as_of`; live clocks older than 24 hours are rejected.

Input contains a request, destination inventory and optional chosen itinerary. For destination discovery, `date`, `depart_at`, `return_by` and `itinerary` can be null. Every destination has its own route and anchors. Unknown routing facts remain null or `method: rough_estimate`; every anchor retains its official URL, why it is compelling, checked time and known operating windows. Dated windows are specific official sessions or a dated application of verified opening rules/closures—not fabricated daily event occurrences. A `duration_minutes` is an evidenced duration or explicitly labeled planning allowance, not a fabricated published rule.

Routing is supplied by a permitted browser/map/routing tool. Use the actual origin and activity/entrance endpoints, conservative upper estimates, both directions and a check time. Do not derive travel minutes from straight-line distance, a city-center pin or a fixed speed. A route source can be a mapping service; activity and opening facts still need first-party confirmation. If a routing tool is unavailable, return provisional destinations and the exact missing check rather than inventing compliance. The helper accepts routing evidence up to seven days old relative to the research clock; this is a maximum, not justification to skip a changing route/traffic check.

The checker:

- validates the schema, unique IDs, offset-aware times, HTTP(S) evidence URLs, source-seed identity and current live research clock;
- classifies each route as `within_limit`, `over_limit` or `unverified`, preserving every destination;
- applies one-way caps to both directions, or a round-trip cap to their sum during exploration; a planned round-trip cap includes all driving, including local transfers. An optional total-driving budget also bounds local driving;
- checks complete outbound/return legs, leg estimates/allotted time, same-local-day bounds, departure/return limits, overlaps and explicit driving or walking transfers between activities;
- checks each visit's duration, verified operating window, current activity evidence (48 hours maximum), availability and booking readiness;
- reports `mechanically_feasible`, `blocked` or `not_requested`, with reasons. Exit code 2 means a proposed itinerary is blocked; the JSON still contains all results. Invalid research input fails validation rather than becoming an empty result.

It does not call a routing API, infer ages/accessibility, total unknown costs, verify quotations or page ownership, rank destination enjoyment, inspect weather/road closures, make reservations or prove research/review happened. A `within_limit` route is not an activity recommendation; `mechanically_feasible` is not a guaranteed or booked trip. The researcher must verify actual endpoints, all party constraints, sourced facts and the final plan before presenting it as actionable. Unknown or blocked options stay in the discovery inventory.

## Future website integration

Keep this agent-first. Reuse existing activity/place IDs when known and propose new first-party place leaves through maintenance. Do not expand daily crawling to every possible destination or introduce a paid routing dependency just to support an occasional trip request. If this becomes a site feature later, add user-controlled origin/radius and a selected-day itinerary on top of the shared place/activity model; do not create a second unsourced activity database.
