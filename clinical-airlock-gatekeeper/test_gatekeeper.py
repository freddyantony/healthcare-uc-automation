"""Run using: python -m unittest discover -s clinical-airlock-gatekeeper -p 'test_*.py' -v"""
import unittest
from gatekeeper import evaluate


def dep(test="paging_failover", rollback="Fallback route"):
    return {"dependency_id": "D1", "service": "Paging", "critical": "yes",
            "owner": "UC Engineer", "required_test": test, "rollback_plan": rollback}


def result(status="PASS", evidence="SYN-001"):
    return {"test_id": "paging_failover", "status": status,
            "evidence_id": evidence, "verified_by": "Test Engineer"}


class GatekeeperTests(unittest.TestCase):
    def test_all_critical_checks_pass(self):
        self.assertEqual(evaluate([dep()], [result()])[0], "READY FOR HUMAN REVIEW")

    def test_failed_paging_check_blocks(self):
        self.assertEqual(evaluate([dep()], [result("FAIL")])[0], "HOLD / NO-GO")

    def test_missing_test_blocks(self):
        self.assertEqual(evaluate([dep()], [])[0], "HOLD / NO-GO")

    def test_missing_rollback_blocks(self):
        self.assertEqual(evaluate([dep(rollback="")], [result()])[0], "HOLD / NO-GO")

    def test_pass_without_evidence_blocks(self):
        self.assertEqual(evaluate([dep()], [result(evidence="")])[0], "HOLD / NO-GO")


if __name__ == "__main__":
    unittest.main()
