# Recommendation output

Give the user a decision-ready answer, not the research ledger.

## Human-facing format

For each selection include:

1. activity name and a first-party action link;
2. specific date and time in local terms;
3. venue, city, and regional context;
4. why it fits this request;
5. price or a clear statement that price or fees remain unknown;
6. availability, registration deadline, or on-sale urgency when material;
7. one concise caveat or preparation note, if needed;
8. evidence confidence when it is not plainly high.

For `weekend-current`, order the answer so the user can make a plan. Mention weather or same-day rechecks only when relevant.

For `signup-horizon`, group by urgency when helpful: `register soon`, `on sale now`, and `watchlist`. Do not present a watchlist item as currently bookable.

When both modes were requested, keep separate `Do now` and `Book ahead` sections.

## Provenance summary

End with one short methods note stating:

- that the maintained source graph was swept first;
- how many selected candidates were first-party verified;
- whether broader web search supplied any selected candidates; and
- the `as_of` timestamp for availability-sensitive checks.

Do not overwhelm the answer with raw scores or every rejected candidate. Share scoring details only when the user asks or when they explain a close tradeoff.

## Structured output

When the caller requests JSON, follow `schemas/recommendation.schema.json`. Each selected `candidate_id` must point to a candidate that passed adversarial review, and `source_graph_swept` must be true.
