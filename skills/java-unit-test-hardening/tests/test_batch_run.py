from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import batch_run  # noqa: E402


class CampaignPathScopeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {
            "workflows": [
                {
                    "workflow_id": "order-purchase-allot",
                    "module_id": "mall4cloud-order",
                    "test_build_files": ["mall4cloud-order/pom.xml"],
                    "docs_path": "docs/tests/order-purchase-allot-tests",
                }
            ]
        }

    def test_triage_is_always_a_campaign_owned_path(self) -> None:
        self.assertTrue(
            batch_run.allowed_campaign_path(self.payload, "docs/tests/TRIAGE.md")
        )

    def test_production_source_is_not_campaign_owned(self) -> None:
        self.assertFalse(
            batch_run.allowed_campaign_path(
                self.payload,
                "mall4cloud-order/src/main/java/example/OrderService.java",
            )
        )


if __name__ == "__main__":
    unittest.main()
