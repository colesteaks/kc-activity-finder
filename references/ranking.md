# Ranking methodology

This rubric scores individual event candidates. For day trips, use the [destination-level assessment](day-trips.md#destination-ranking): compelling anchors, party fit, day cohesion, time value and confidence, followed by driving and itinerary feasibility gates.

Collect before selecting. Hard filters do not delete inventory rows. The executable scoring model supersedes the older seven-factor `ranking` example fields, which remain only for schema compatibility.

## Eligibility gates

Exclude from recommendations, retain in inventory: outside the exact Chicago-local date window; unknown time; unavailable/closed/full/canceled/not-open/waitlist; unresolved material conflicts; unsupported or stale official identity/date/time/place/availability; missing or failed required registration action; passed deadline; or violated explicit age, region, category, budget, movement or travel filters. All supplied participant ages must be eligible, including caregivers. “Family friendly” is not evidence of toddler participation. Unknown eligibility stays unresolved when ages constrain selection.

## Transparent score

Assign 0–5 and a request-specific reason to each dimension. Score = sum(weight × dimension / 5), on a 100-point scale. Default weights:

| Dimension | Weight | Interpretation |
| --- | ---: | --- |
| Age fit | 20 | Suitability for actual party; neutral when ages are unspecified |
| Interest fit | 30 | Match to stated interests; neutral when unknown |
| Movement | 0 | Physical engagement, activated only when desired |
| Distinctiveness | 20 | Seasonal, unusual, local, participatory or rare qualities |
| Logistics | 20 | Travel, timing, duration, access and commitment |
| Value | 10 | Experience relative to full cost and time |

Use 0 for a poor match, 3 for a reasonable/neutral match, 5 for excellent supported fit. Unknown preference fit is neutral, not evidence of excellence. Explain uncertainty. Ties sort by stable candidate ID for reproducibility; use editorial judgment to diversify a final shortlist without altering facts or claiming the score scientifically measures enjoyment.

Custom weights must contain all six dimensions and sum to 100. Suggested active-family profile: age_fit 25, interest_fit 20, movement 25, distinctiveness 10, logistics 15, value 5. Adult arts profile can keep movement at zero. A hard minimum movement filter is separate from weighting. No positive score rescues a failed gate.

Discovery-first output should highlight deep discoveries and signature experiences before practical backups. Fit-first output should prioritize the party’s needs. Rankings are decision support, not probabilities of satisfaction. Never award points for sponsorship, source placement, copying, search rank or popularity. Geographic variety should add meaningful choice, not token distant entries.
