"""Run outputs: findings CSV, CER remediation CSV, JSON and Markdown summaries."""

from __future__ import annotations

import csv
import json
import os
from typing import Dict, List, Optional

from . import __version__
from .reconcile import ReconcileResult

FINDING_COLUMNS = ["severity", "code", "switch_name", "port", "device_name", "jack_id",
                   "expected", "observed", "message", "recommendation"]
REMEDIATION_COLUMNS = ["switch_name", "switch_ip", "switch_port", "port_id", "erl_name",
                       "current_erl", "building", "floor", "room", "jack_id", "finding"]


def write_findings_csv(path: str, result: ReconcileResult) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FINDING_COLUMNS)
        writer.writeheader()
        for f in result.findings:
            writer.writerow({c: getattr(f, c) for c in FINDING_COLUMNS})


def write_remediation_csv(path: str, result: ReconcileResult) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=REMEDIATION_COLUMNS)
        writer.writeheader()
        writer.writerows(result.remediation)


def summary_dict(result: ReconcileResult, run: Optional[Dict[str, object]] = None) -> dict:
    return {
        "tool_version": __version__,
        "run": run or {},
        "stats": result.stats,
        "by_severity": result.counts_by_severity(),
        "by_code": result.counts_by_code(),
    }


def write_summary_json(path: str, result: ReconcileResult,
                       run: Optional[Dict[str, object]] = None) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(summary_dict(result, run), fh, indent=2, sort_keys=True)


def render_markdown(result: ReconcileResult, run: Optional[Dict[str, object]] = None) -> str:
    stats = result.stats
    sev = result.counts_by_severity()
    accuracy = stats.get("accuracy_pct")
    lines = ["# E911 Reconciliation Report", ""]
    if run and run.get("started_at"):
        lines.append(f"Run {run.get('run_id')} at {run['started_at']} · engine v{__version__}")
        lines.append("")
    lines.append(
        f"**Dispatchable-location accuracy: "
        f"{'n/a' if accuracy is None else f'{accuracy}%'}** "
        f"({stats.get('phones_verified', 0)} of {stats.get('phones_observed', 0)} phones on the "
        f"network resolve to a verified location).")
    lines += ["", "| Severity | Findings |", "| --- | --- |"]
    lines += [f"| {s} | {n} |" for s, n in sev.items() if s != "info"]
    lines += ["", "## Sources compared", "",
              f"- Location records: {stats.get('location_records')} "
              f"(schema v{stats.get('location_schema_version')})",
              f"- Switches surveyed: {stats.get('switches_surveyed')}",
              f"- CER ports exported: {stats.get('cer_ports')}; CER unlocated phones: "
              f"{stats.get('cer_unlocated')}",
              f"- CUCM devices: {stats.get('inventory_devices')} "
              f"({stats.get('inventory_soft_or_wireless')} soft/wireless, "
              f"{stats.get('inventory_analog')} analog)"]
    if run and run.get("previous_run_id") is not None:
        lines += ["", "## Since the previous run", "",
                  f"- New findings: {len(run.get('new_findings', []))}",
                  f"- Resolved findings: {len(run.get('resolved_findings', []))}"]
    if result.counts_by_code():
        lines += ["", "## Findings by type", "", "| Code | Count |", "| --- | --- |"]
        lines += [f"| {c} | {n} |" for c, n in result.counts_by_code().items()]
    urgent = [f for f in result.findings if f.severity == "critical"]
    if urgent:
        lines += ["", "## Critical findings", ""]
        lines += [f"- **{f.code}** — {f.message}" for f in urgent[:25]]
        if len(urgent) > 25:
            lines.append(f"- … and {len(urgent) - 25} more (see findings.csv)")
    if result.remediation:
        lines += ["", f"{len(result.remediation)} CER port update(s) are ready in "
                      f"`remediation.csv`; apply them with `e911 push` or the "
                      f"`e911-location-update.yml` playbook (dry run by default)."]
    return "\n".join(lines) + "\n"


def write_all(out_dir: str, result: ReconcileResult,
              run: Optional[Dict[str, object]] = None) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    paths = {
        "findings": os.path.join(out_dir, "findings.csv"),
        "remediation": os.path.join(out_dir, "remediation.csv"),
        "summary_json": os.path.join(out_dir, "summary.json"),
        "summary_md": os.path.join(out_dir, "summary.md"),
    }
    write_findings_csv(paths["findings"], result)
    write_remediation_csv(paths["remediation"], result)
    write_summary_json(paths["summary_json"], result, run)
    with open(paths["summary_md"], "w", encoding="utf-8") as fh:
        fh.write(render_markdown(result, run))
    return list(paths.values())
