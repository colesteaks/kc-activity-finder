# Fit-based ranking

Rank for the request, not for general popularity. Apply hard gates before assigning points.

## Hard gates

Drop a candidate when any of these is true:

- it falls outside the requested window or signup horizon;
- it is cancelled, conclusively sold out, or registration is closed, unless the user asked for resale or waitlist options;
- a stated age, accessibility, budget, travel, or schedule constraint makes it unusable;
- its identity, date, place, or availability cannot be verified well enough to act;
- the only support is a search result, aggregator, or editorial mention with no first-party confirmation;
- a material conflict between sources remains unresolved.

## 100-point rubric

| Dimension | Max | Question |
| --- | ---: | --- |
| Personal fit | 30 | How directly does it match stated interests, group needs, constraints, and desired energy? |
| Timing and actionability | 15 | Can the user act at the right time, and is there useful urgency? |
| Distinctiveness | 15 | Is it unusually memorable, seasonal, limited, local, or hard to replicate? |
| Evidence confidence | 15 | Are material details current and supported by first-party evidence? |
| Logistics | 10 | Are travel, duration, parking/transit, accessibility, and schedule friction manageable? |
| Value | 10 | Is the experience compelling relative to full cost and time? |
| Geographic intent | 5 | Does it preserve KC as the center or earn a requested regional wildcard slot? |

Record integer points for each dimension. `total` is the sum of all seven dimensions plus penalties, floored at zero.

## Mode interpretation

For `weekend-current`, timing and actionability reward confirmed hours, live inventory, sensible sequencing, weather resilience, and low last-minute friction.

For `signup-horizon`, timing and actionability reward an open registration or on-sale window, a verified deadline, appropriate lead time, and an event substantial enough to reserve calendar space.

Distinctiveness should not automatically favor distant options. A Lawrence, Columbia, Bentonville, or surrounding-area candidate earns its place by offering a better fit or more distinctive experience than available KC-metro alternatives.

## Penalties

Use negative integers and explain each applied penalty in working notes.

| Condition | Typical penalty |
| --- | ---: |
| Availability is unknown but the event is otherwise actionable | -10 |
| A material field is supported only by stale evidence | -10 to -20 |
| Price or fees are meaningfully unclear | -5 |
| Weather risk has no reasonable fallback | -5 to -10 |
| Travel friction is easy to underestimate | -5 to -15 |
| Non-fatal preference conflict | -5 to -20 |

Do not use a penalty to rescue a hard-gate failure.

## Bias controls and ties

- Sponsorship, placement in a newsletter, repetition across aggregators, and search rank receive no points.
- Multiple pages copying one announcement do not count as independent confirmation.
- Do not reward a source merely because it was in the seed graph; reward the candidate's fit and evidence.
- Break close ties by evidence confidence, then personal fit, then lower logistics burden. Use geographic variety only when it adds genuine choice.
