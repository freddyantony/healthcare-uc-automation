"""
Append-only audit history (SQLite).

Every reconciliation run is recorded with a timestamp, the tool version, the
SHA-256 of each input file and every finding. Database triggers reject UPDATE
and DELETE, so the history can be produced as evidence of continuous RAY BAUM's
Act monitoring: what was wrong, when it was found, and when it was fixed.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from . import __version__
from .reconcile import ReconcileResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at     TEXT NOT NULL,
    tool_version   TEXT NOT NULL,
    inputs_json    TEXT NOT NULL,
    stats_json     TEXT NOT NULL,
    critical       INTEGER NOT NULL,
    high           INTEGER NOT NULL,
    medium         INTEGER NOT NULL,
    low            INTEGER NOT NULL,
    accuracy_pct   REAL
);
CREATE TABLE IF NOT EXISTS findings (
    run_id         INTEGER NOT NULL REFERENCES runs(run_id),
    fingerprint    TEXT NOT NULL,
    code           TEXT NOT NULL,
    severity       TEXT NOT NULL,
    switch_name    TEXT,
    port           TEXT,
    device_name    TEXT,
    jack_id        TEXT,
    expected       TEXT,
    observed       TEXT,
    message        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS findings_run ON findings(run_id);
CREATE TRIGGER IF NOT EXISTS runs_append_only_u BEFORE UPDATE ON runs
    BEGIN SELECT RAISE(ABORT, 'audit history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS runs_append_only_d BEFORE DELETE ON runs
    BEGIN SELECT RAISE(ABORT, 'audit history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS findings_append_only_u BEFORE UPDATE ON findings
    BEGIN SELECT RAISE(ABORT, 'audit history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS findings_append_only_d BEFORE DELETE ON findings
    BEGIN SELECT RAISE(ABORT, 'audit history is append-only'); END;
"""


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def describe_inputs(paths: Dict[str, Optional[str]]) -> Dict[str, dict]:
    """Name -> {path, sha256} for each input file (directories hash each file)."""
    described = {}
    for name, path in paths.items():
        if not path:
            continue
        if os.path.isdir(path):
            described[name] = {"path": path, "files": {
                f: file_sha256(os.path.join(path, f)) for f in sorted(os.listdir(path))
                if os.path.isfile(os.path.join(path, f))}}
        elif os.path.isfile(path):
            described[name] = {"path": path, "sha256": file_sha256(path)}
        else:
            described[name] = {"path": path}
    return described


def connect(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    return conn


def record_run(db_path: str, result: ReconcileResult, inputs: Dict[str, dict],
               started_at: Optional[str] = None) -> Dict[str, object]:
    """Store a run; return its id plus findings new and resolved since the last run."""
    started_at = started_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    severity = result.counts_by_severity()
    with connect(db_path) as conn:
        previous = conn.execute("SELECT MAX(run_id) FROM runs").fetchone()[0]
        prior: Set[str] = set()
        if previous is not None:
            prior = {row[0] for row in conn.execute(
                "SELECT fingerprint FROM findings WHERE run_id = ?", (previous,))}
        cursor = conn.execute(
            "INSERT INTO runs (started_at, tool_version, inputs_json, stats_json, critical, "
            "high, medium, low, accuracy_pct) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (started_at, __version__, json.dumps(inputs, sort_keys=True),
             json.dumps(result.stats, sort_keys=True), severity["critical"], severity["high"],
             severity["medium"], severity["low"], result.stats.get("accuracy_pct")))
        run_id = cursor.lastrowid
        conn.executemany(
            "INSERT INTO findings (run_id, fingerprint, code, severity, switch_name, port, "
            "device_name, jack_id, expected, observed, message) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(run_id, f.fingerprint, f.code, f.severity, f.switch_name, f.port, f.device_name,
              f.jack_id, f.expected, f.observed, f.message) for f in result.findings])
    current = {f.fingerprint for f in result.findings}
    return {
        "run_id": run_id,
        "started_at": started_at,
        "previous_run_id": previous,
        "new_findings": sorted(current - prior) if previous is not None else [],
        "resolved_findings": sorted(prior - current),
    }


def list_runs(db_path: str, limit: int = 20) -> List[Dict[str, object]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT run_id, started_at, tool_version, critical, high, medium, low, accuracy_pct "
            "FROM runs ORDER BY run_id DESC LIMIT ?", (limit,)).fetchall()
    keys = ("run_id", "started_at", "tool_version", "critical", "high", "medium", "low",
            "accuracy_pct")
    return [dict(zip(keys, row)) for row in rows]
