from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_repo import EXPECTED_STAGES, FIRST_PARTY_TYPES, validate_repository  # noqa: E402


class RepositoryInvariantTests(unittest.TestCase):
    def test_full_repository_validation(self) -> None:
        self.assertEqual(validate_repository(ROOT), [])

    def test_pipeline_order_is_exact(self) -> None:
        workflow = json.loads((ROOT / "data/workflow.json").read_text(encoding="utf-8"))
        self.assertEqual(workflow["ordered_stage_ids"], EXPECTED_STAGES)

    def test_uploaded_seed_is_preserved_verbatim(self) -> None:
        self.assertEqual((ROOT / "data/primary-sources.txt").read_bytes(), b"KC daily\n")

    def test_selected_web_supplements_have_first_party_evidence(self) -> None:
        for prefix in ("weekend", "signup"):
            ledger = json.loads(
                (ROOT / f"examples/{prefix}-candidates.json").read_text(encoding="utf-8")
            )
            recommendation = json.loads(
                (ROOT / f"examples/{prefix}-recommendation.json").read_text(encoding="utf-8")
            )
            by_id = {item["candidate_id"]: item for item in ledger["candidates"]}
            for selected in recommendation["selected"]:
                candidate = by_id[selected["candidate_id"]]
                if candidate["discovery"]["channel"] != "broader-web-search":
                    continue
                evidence_types = {item["evidence_type"] for item in candidate["verification"]}
                self.assertTrue(evidence_types & FIRST_PARTY_TYPES)
                self.assertEqual(candidate["adversarial_review"]["overall"], "pass")


if __name__ == "__main__":
    unittest.main()
