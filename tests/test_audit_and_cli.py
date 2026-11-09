import csv
import json
import os
import sqlite3
import subprocess
import sys

import pytest

from conftest import ROOT
from e911.audit import describe_inputs, list_runs, record_run
from e911.cli import main
from e911.reconcile import ReconcileResult


def test_audit_history_is_append_only(tmp_path, sample_result, samples):
    db = str(tmp_path / "audit.db")
    first = record_run(db, sample_result, describe_inputs({"locations": samples["locations"]}))
    assert first["run_id"] == 1 and first["previous_run_id"] is None

    # Second run with everything fixed: all findings resolved.
    second = record_run(db, ReconcileResult(stats={"accuracy_pct": 100.0}), {})
    assert second["previous_run_id"] == 1
    assert len(second["resolved_findings"]) == len(sample_result.findings)
    assert second["new_findings"] == []

    runs = list_runs(db)
    assert [r["run_id"] for r in runs] == [2, 1]
    assert runs[0]["accuracy_pct"] == 100.0

    conn = sqlite3.connect(db)
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("DELETE FROM findings")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn.execute("UPDATE runs SET critical = 0")


def test_inputs_are_hashed(samples):
    described = describe_inputs({"locations": samples["locations"],
                                 "neighbors": samples["neighbors"], "missing": None})
    assert len(described["locations"]["sha256"]) == 64
    assert "sw-main-2f-idf3.cdp.txt" in described["neighbors"]["files"]
    assert "missing" not in described


def _reconcile_args(samples, out, db):
    return ["reconcile", "--locations", samples["locations"], "--neighbors", samples["neighbors"],
            "--cer-switchports", samples["cer_switchports"],
            "--cer-unlocated", samples["cer_unlocated"], "--inventory", samples["inventory"],
            "--out", out, "--audit-db", db]


def test_cli_reconcile_writes_reports(tmp_path, samples, capsys):
    out, db = str(tmp_path / "reports"), str(tmp_path / "audit.db")
    code = main(_reconcile_args(samples, out, db))
    assert code == 1  # critical findings present (default --fail-on critical)
    assert sorted(os.listdir(out)) == ["findings.csv", "remediation.csv", "summary.json",
                                       "summary.md"]
    with open(os.path.join(out, "summary.json"), encoding="utf-8") as fh:
        summary = json.load(fh)
    assert summary["stats"]["phones_observed"] == 9
    assert summary["run"]["run_id"] == 1
    with open(os.path.join(out, "remediation.csv"), newline="", encoding="utf-8") as fh:
        assert len(list(csv.DictReader(fh))) == 3
    assert "Dispatchable-location accuracy" in capsys.readouterr().out


def test_cli_fail_on_none(tmp_path, samples):
    args = _reconcile_args(samples, str(tmp_path / "r"), str(tmp_path / "a.db")) + \
        ["--fail-on", "none"]
    assert main(args) == 0


def test_cli_validate(samples, capsys):
    assert main(["validate", "--locations", samples["template"]]) == 0
    assert "0 issue(s)" in capsys.readouterr().out


def test_cli_push_is_dry_run_by_default(tmp_path, samples, capsys):
    out = str(tmp_path / "reports")
    main(_reconcile_args(samples, out, str(tmp_path / "a.db")))
    capsys.readouterr()
    code = main(["push", "--remediation", os.path.join(out, "remediation.csv"),
                 "--cer-host", "cer-pub.example.org"])
    text = capsys.readouterr().out
    assert code == 0
    assert "PLAN   192.0.2.11  ERL ERL_MAIN_2F_ED  ports 1/0/14, 1/0/15" in text
    assert "Dry run only" in text


def test_cli_history(tmp_path, samples, capsys):
    db = str(tmp_path / "a.db")
    main(_reconcile_args(samples, str(tmp_path / "r1"), db))
    main(_reconcile_args(samples, str(tmp_path / "r2"), db))
    capsys.readouterr()
    assert main(["history", "--audit-db", db]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 3 and "44.4%" in lines[1]


def test_module_entry_point(samples):
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "python"))
    done = subprocess.run([sys.executable, "-m", "e911", "validate", "--locations",
                           samples["template"]], capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr


def test_existing_compliance_report_reads_v2_template(tmp_path, samples):
    """Regression: reporting/compliance_report.py keeps working with the v2 template."""
    inventory = tmp_path / "inv.csv"
    inventory.write_text("device_name,description,model,device_pool\n"
                         "SEP001122334455,ED,Cisco 8865,DP\nSEP0000000000FF,Spare,Cisco 8865,DP\n")
    out = tmp_path / "report.csv"
    done = subprocess.run([sys.executable, os.path.join(ROOT, "python", "reporting",
                                                        "compliance_report.py"),
                           "--inventory", str(inventory), "--locations", samples["template"],
                           "--output", str(out)], capture_output=True, text=True)
    assert done.returncode == 1  # one device has no location
    with open(out, newline="", encoding="utf-8") as fh:
        rows = {r["device_name"]: r["compliant"] for r in csv.DictReader(fh)}
    assert rows == {"SEP001122334455": "YES", "SEP0000000000FF": "NO"}
