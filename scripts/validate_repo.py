#!/usr/bin/env python3
"""Validate repository structure and source-first recommendation invariants."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


EXPECTED_STAGES = [
    "source-graph",
    "deep-first-party-sweep",
    "candidate-capture",
    "broader-web-search",
    "merge",
    "fit-based-ranking",
    "adversarial-review",
    "recommendation",
]

REQUIRED_COVERAGE = {
    "Kansas City metro",
    "Lawrence",
    "Columbia",
    "Bentonville",
    "surrounding areas",
}

FIRST_PARTY_TYPES = {
    "first-party-event",
    "first-party-organizer",
    "first-party-venue",
    "first-party-registration",
}

REQUIRED_FILES = [
    "README.md",
    "SKILL.md",
    "VERSION",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "CHANGELOG.md",
    "references/installation.md",
    "scripts/build_release.py",
    "scripts/verify_release.py",
    "agents/openai.yaml",
    "data/primary-sources.txt",
    "data/source-graph.json",
    "data/workflow.json",
    "schemas/query.schema.json",
    "schemas/day-trip.schema.json",
    "schemas/candidate.schema.json",
    "schemas/recommendation.schema.json",
    "schemas/source-graph.schema.json",
    "references/workflow.md",
    "references/day-trips.md",
    "prompts/day-trip.md",
    "scripts/day_trip_planner.py",
    "examples/day-trip-research.json",
    "references/ranking.md",
    "references/adversarial-review.md",
    "references/output-contract.md",
    "references/updating-sources.md",
    "examples/weekend-request.json",
    "examples/weekend-candidates.json",
    "examples/weekend-recommendation.json",
    "examples/signup-request.json",
    "examples/signup-candidates.json",
    "examples/signup-recommendation.json",
]


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def ranking_total(candidate: dict[str, Any]) -> int:
    ranking = candidate["ranking"]
    positive_keys = [
        "personal_fit",
        "timing_actionability",
        "distinctiveness",
        "evidence_confidence",
        "logistics",
        "value",
        "geographic_intent",
    ]
    return max(0, sum(ranking[key] for key in positive_keys) + ranking["penalties"])


def has_first_party_evidence(candidate: dict[str, Any]) -> bool:
    return any(
        item.get("evidence_type") in FIRST_PARTY_TYPES
        for item in candidate.get("verification", [])
    )


def validate_repository(root: Path | None = None) -> list[str]:
    root = root or Path(__file__).resolve().parents[1]
    errors: list[str] = []

    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            errors.append(f"missing required file: {relative}")

    for path in sorted(root.rglob("*.json")):
        try:
            load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid JSON in {path.relative_to(root)}: {exc}")

    if errors:
        return errors

    workflow = load_json(root / "data/workflow.json")
    if workflow.get("ordered_stage_ids") != EXPECTED_STAGES:
        errors.append("workflow stages are missing, reordered, or renamed")

    coverage = set(workflow.get("geography", {}).get("coverage_areas", []))
    if not REQUIRED_COVERAGE.issubset(coverage):
        missing = sorted(REQUIRED_COVERAGE - coverage)
        errors.append(f"workflow geography is missing: {', '.join(missing)}")

    graph = load_json(root / "data/source-graph.json")
    seed_path = root / graph["seed_material"]["path"]
    seed_bytes = seed_path.read_bytes()
    actual_hash = hashlib.sha256(seed_bytes).hexdigest()
    if actual_hash != graph["seed_material"].get("sha256"):
        errors.append("primary source seed hash does not match source-graph.json")

    seed_lines = [line for line in seed_path.read_text(encoding="utf-8").splitlines() if line]
    provided_nodes = sorted(
        (
            node
            for node in graph.get("nodes", [])
            if node.get("provenance", {}).get("kind") == "provided-seed"
        ),
        key=lambda node: node["provenance"].get("seed_line", 0),
    )
    provided_raw_values = [node["provenance"].get("raw_value") for node in provided_nodes]
    if provided_raw_values != seed_lines:
        errors.append("provided-seed nodes do not preserve the seed file line for line")

    node_ids = [node.get("id") for node in graph.get("nodes", [])]
    if len(node_ids) != len(set(node_ids)):
        errors.append("source graph contains duplicate node ids")

    node_id_set = set(node_ids)
    for edge in graph.get("edges", []):
        if edge.get("from") not in node_id_set or edge.get("to") not in node_id_set:
            errors.append(f"source graph edge has an unknown endpoint: {edge}")

    supplement_policy = graph.get("supplement_policy", {})
    if supplement_policy.get("allowed_after_stage") != "broader-web-search":
        errors.append("web supplements are allowed before the broader-web-search stage")
    if supplement_policy.get("must_resolve_to_first_party_before_recommendation") is not True:
        errors.append("web supplements are not required to resolve to first-party evidence")
    if supplement_policy.get("never_promote_to_provided_seed") is not True:
        errors.append("web supplements can be incorrectly promoted to provided seeds")

    for prefix, expected_mode in (
        ("weekend", "weekend-current"),
        ("signup", "signup-horizon"),
    ):
        request = load_json(root / f"examples/{prefix}-request.json")
        ledger = load_json(root / f"examples/{prefix}-candidates.json")
        recommendation = load_json(root / f"examples/{prefix}-recommendation.json")

        if request.get("mode") != expected_mode:
            errors.append(f"{prefix} request has the wrong mode")
        if ledger.get("mode") != expected_mode or ledger.get("fixture") is not True:
            errors.append(f"{prefix} candidate ledger is not a labeled {expected_mode} fixture")
        if recommendation.get("mode") != expected_mode:
            errors.append(f"{prefix} recommendation has the wrong mode")
        if recommendation.get("window") != request.get("window"):
            errors.append(f"{prefix} recommendation window differs from its request")
        if recommendation.get("as_of") != request.get("as_of"):
            errors.append(f"{prefix} recommendation as_of differs from its request")

        candidates = ledger.get("candidates", [])
        by_id = {candidate.get("candidate_id"): candidate for candidate in candidates}
        if len(by_id) != len(candidates):
            errors.append(f"{prefix} candidate ids are not unique")

        for candidate in candidates:
            candidate_id = candidate.get("candidate_id", "<missing>")
            if candidate.get("mode") != expected_mode:
                errors.append(f"{candidate_id} has the wrong mode")
            if not candidate.get("title", "").startswith("Fixture:"):
                errors.append(f"{candidate_id} is not visibly labeled as fictional")
            if ranking_total(candidate) != candidate.get("ranking", {}).get("total"):
                errors.append(f"{candidate_id} has an incorrect ranking total")
            if candidate.get("discovery", {}).get("channel") == "broader-web-search":
                if not has_first_party_evidence(candidate):
                    errors.append(f"web supplement {candidate_id} lacks first-party evidence")

        selected = recommendation.get("selected", [])
        selected_candidates: list[dict[str, Any]] = []
        for item in selected:
            candidate_id = item.get("candidate_id")
            candidate = by_id.get(candidate_id)
            if candidate is None:
                errors.append(f"{prefix} selects unknown candidate {candidate_id}")
                continue
            selected_candidates.append(candidate)
            if candidate.get("adversarial_review", {}).get("overall") != "pass":
                errors.append(f"{prefix} selects candidate {candidate_id} without review pass")
            if candidate.get("availability", {}).get("status") in {"sold-out", "cancelled"}:
                errors.append(f"{prefix} selects unavailable candidate {candidate_id}")
            if not has_first_party_evidence(candidate):
                errors.append(f"{prefix} selects unverified candidate {candidate_id}")
            if item.get("action_url") != candidate.get("action_url"):
                errors.append(f"{prefix} action URL differs for {candidate_id}")

        summary = recommendation.get("provenance_summary", {})
        if summary.get("source_graph_swept") is not True:
            errors.append(f"{prefix} recommendation does not attest to a graph sweep")
        first_party_count = sum(has_first_party_evidence(item) for item in selected_candidates)
        if summary.get("first_party_verified") != first_party_count:
            errors.append(f"{prefix} first-party verification count is incorrect")
        web_count = sum(
            item.get("discovery", {}).get("channel") == "broader-web-search"
            for item in selected_candidates
        )
        if summary.get("web_supplements_used") != web_count:
            errors.append(f"{prefix} web supplement count is incorrect")

        window_start = datetime.fromisoformat(request["window"]["start"]).date()
        window_end = datetime.fromisoformat(request["window"]["end"]).date()
        for candidate in selected_candidates:
            start_date = parse_datetime(candidate["timing"]["start"]).date()
            if not window_start <= start_date <= window_end:
                errors.append(f"{candidate['candidate_id']} falls outside the requested window")

    return errors


def main() -> int:
    errors = validate_repository()
    if errors:
        print("Repository validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Repository validation passed.")
    print(f"- {len(REQUIRED_FILES)} required artifacts present")
    print(f"- {len(EXPECTED_STAGES)} workflow stages preserved in order")
    print("- seed provenance, regional coverage, ranking math, and examples verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
