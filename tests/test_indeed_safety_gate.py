'''
Unit Tests for Indeed Safety Gate
'''

import unittest
from platforms.indeed.safety_gate import IndeedSafetyGate, SafetyGateResult


class TestIndeedSafetyGate(unittest.TestCase):
    def test_evaluate_auto_approved(self):
        gate = IndeedSafetyGate(pause_mode=False)
        result: SafetyGateResult = gate.evaluate(
            job_title="RPA Developer",
            company="Test Corp",
            answers=[{"question": "Years of Python", "answer": "3"}],
        )
        self.assertTrue(result.approved)
        self.assertFalse(result.requires_human_approval)
        self.assertEqual(result.details["job_title"], "RPA Developer")

    def test_evaluate_pause_before_submit(self):
        gate = IndeedSafetyGate(pause_mode=True)
        result: SafetyGateResult = gate.evaluate(
            job_title="Senior Automation Engineer",
            company="Tech Giants",
            answers=[{"question": "Expected CTC", "answer": "550000"}],
        )
        self.assertFalse(result.approved)
        self.assertTrue(result.requires_human_approval)
        self.assertIn("pause_before_submit", result.reason)


if __name__ == "__main__":
    unittest.main()
