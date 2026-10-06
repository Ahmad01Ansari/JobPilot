"""
Unit tests for SetupRequirement and requirement status models.
"""

import unittest
from app.services.setup.setup_requirements import (
    SetupRequirement,
    RequirementCriticality,
    RequirementStatus,
)


class TestSetupRequirements(unittest.TestCase):
    def test_setup_requirement_defaults(self):
        req = SetupRequirement(
            key="test_req",
            title="Test Requirement",
            description="Testing requirement model.",
            criticality=RequirementCriticality.CORE,
        )
        self.assertEqual(req.key, "test_req")
        self.assertEqual(req.status, RequirementStatus.NOT_STARTED)
        self.assertEqual(req.criticality, RequirementCriticality.CORE)
        self.assertFalse(req.blocking)

    def test_serialization_roundtrip(self):
        req = SetupRequirement(
            key="candidate_profile",
            title="Candidate Profile",
            description="Personal info",
            criticality=RequirementCriticality.CORE,
            status=RequirementStatus.READY,
            blocking=True,
            route="profile",
            fix_action="edit_profile",
            details={"name": "Ahmad Raza", "skills": 5},
        )
        as_dict = req.to_dict()
        self.assertEqual(as_dict["key"], "candidate_profile")
        self.assertEqual(as_dict["status"], "READY")
        self.assertEqual(as_dict["criticality"], "CORE")
        self.assertEqual(as_dict["details"]["name"], "Ahmad Raza")

        restored = SetupRequirement.from_dict(as_dict)
        self.assertEqual(restored.key, req.key)
        self.assertEqual(restored.status, RequirementStatus.READY)
        self.assertEqual(restored.criticality, RequirementCriticality.CORE)
        self.assertTrue(restored.blocking)
        self.assertEqual(restored.details["skills"], 5)


if __name__ == "__main__":
    unittest.main()
