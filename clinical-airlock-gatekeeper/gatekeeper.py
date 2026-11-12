"""Clinical Airlock Gatekeeper v0.1 — synthetic-data readiness demonstration.

Never authorizes production migration; a passing result means only that
specified evidence is complete and ready for independent human review.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read_csv(path: Path, required_columns: set[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        fields = set(reader.fieldnames or [])
        missing = required_columns - fields
        if missing:
            raise ValueError(f"{path.name}: missing columns: {', '.join(sorted(missing))}")
        return [{key: (value or "").strip() for key, value in row.items()}
                for row in reader]


def evaluate(dependencies: list[dict[str, str]],
             test_results: list[dict[str, str]]) -> tuple[str, list[str]]:
    blockers: list[str] = []
    tests: dict[str, dict[str, str]] = {}
    for row in test_results:
        test_id = row["test_id"]
        if not test_id or test_id in tests:
            blockers.append(f"Missing or duplicate test ID: {test_id or '(blank)'}")
        else:
            tests[test_id] = row

    seen: set[str] = set()
    critical_count = 0
    for dep in dependencies:
        dep_id = dep["dependency_id"]
        if not dep_id or dep_id in seen:
            blockers.append(f"Missing or duplicate dependency ID: {dep_id or '(blank)'}")
        else:
            seen.add(dep_id)
        if dep["critical"].lower() not in {"yes", "no"}:
            blockers.append(f"{dep_id}: critical must be yes or no")
            continue
        if dep["critical"].lower() != "yes":
            continue
        critical_count += 1
        for field in ("service", "owner", "required_test", "rollback_plan"):
            if not dep[field]:
                blockers.append(f"{dep_id}: missing {field}")
        test_id = dep["required_test"]
        if not test_id:
            continue
        result = tests.get(test_id)
        if result is None:
            blockers.append(f"{dep_id}: required test '{test_id}' has no result")
        elif result["status"].upper() != "PASS":
            blockers.append(f"{dep_id}: {test_id} = {result['status'] or 'MISSING'}")
        elif not result["evidence_id"] or not result["verified_by"]:
            blockers.append(f"{dep_id}: PASS for {test_id} lacks evidence or reviewer")

    if critical_count == 0:
        blockers.append("No critical dependencies were registered")
    return ("HOLD / NO-GO" if blockers else "READY FOR HUMAN REVIEW", blockers)


def main() -> None:
    parser = argparse.ArgumentParser(description="Clinical Airlock synthetic gate evaluation")
    parser.add_argument("--dependencies", type=Path, default=HERE / "dependencies.csv")
    parser.add_argument("--tests", type=Path, default=HERE / "test_results.csv")
    args = parser.parse_args()
    dependencies = read_csv(args.dependencies, {
        "dependency_id", "service", "critical", "owner", "required_test", "rollback_plan"})
    test_results = read_csv(args.tests, {"test_id", "status", "evidence_id", "verified_by"})
    decision, blockers = evaluate(dependencies, test_results)
    print("Clinical Airlock Gatekeeper — SYNTHETIC DEMO")
    print(f"Decision: {decision}")
    for blocker in blockers:
        print(f" - {blocker}")
    if not blockers:
        print("All listed critical checks passed; authorized clinical and engineering review is still required.")


if __name__ == "__main__":
    main()
