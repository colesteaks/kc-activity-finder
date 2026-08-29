# KC Activity Finder

A source-first skill for finding activities centered on the Kansas City metro, with deliberate coverage of Lawrence, Columbia, Bentonville, and surrounding areas.

It supports two questions:

| Mode | Best for | Decision emphasis |
| --- | --- | --- |
| `weekend-current` | Now, tonight, this week, or this weekend | Live schedule, availability, weather, and logistics |
| `signup-horizon` | Races, festivals, classes, timed entry, and ticketed events | Registration status, deadlines, lead time, and calendar value |

## Core guarantee

Every run follows this sequence:

1. source graph
2. deep first-party sweep
3. candidate capture
4. broader web search
5. merge
6. fit-based ranking
7. adversarial review
8. recommendation

The supplied primary-source artifact is preserved verbatim at [`data/primary-sources.txt`](data/primary-sources.txt). It contains the seed `KC daily`, resolved in the graph to [KC Daily](https://www.kcdaily.com/). The graph is swept before ordinary web search. Search can uncover gaps, but it cannot stand in for the primary graph or for first-party verification.

## Repository map

```text
kc-activity-finder/
|-- SKILL.md                         Skill entry point and operating invariants
|-- agents/openai.yaml               Codex UI metadata
|-- data/
|   |-- primary-sources.txt          Verbatim user-supplied seed artifact
|   |-- source-graph.json            Maintained source graph and expansion rules
|   `-- workflow.json                Machine-readable stages, modes, and geography
|-- schemas/
|   |-- candidate.schema.json        Candidate ledger contract
|   |-- query.schema.json            Request contract
|   |-- recommendation.schema.json   Final structured output contract
|   `-- source-graph.schema.json     Source graph contract
|-- references/
|   |-- workflow.md                  Stage-by-stage research procedure
|   |-- ranking.md                   Hard gates and 100-point fit rubric
|   |-- adversarial-review.md        Pre-recommendation challenge checklist
|   |-- output-contract.md           Human-facing response requirements
|   `-- updating-sources.md          Safe source maintenance procedure
|-- examples/                        Fictional deterministic fixtures for both modes
|-- scripts/validate_repo.py         Structural and semantic validation
|-- tests/test_repository.py         Executable invariant tests
`-- .github/workflows/validate.yml   Continuous validation
```

## Use the skill

Place this repository in a Codex skills directory or reference its `SKILL.md`, then ask for a current or signup-horizon recommendation. For example:

```text
Use $kc-activity-finder to find three memorable things for two adults to do
this weekend, mostly within the KC metro, with one day-trip wildcard.
```

The skill is intentionally procedural rather than tied to a single scraper. It can use the browsing and search tools available in its host environment while retaining the same provenance, ranking, and review contracts.

## Validate changes

Requires Python 3.10 or newer and no third-party packages.

```bash
python3 scripts/validate_repo.py
python3 -m unittest discover -s tests -v
```

See [`references/updating-sources.md`](references/updating-sources.md) before changing source data. In particular, do not add a general event directory as a new seed merely because it ranks well in search.
