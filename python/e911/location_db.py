"""
Location database: loading and data-quality validation.

The location database is the hospital's own record of its cable plant: which
switch port is patched to which jack, and which room that jack is in. Schema v2
adds jack, patch-panel, civic-address and verification columns to the v1
template; v1 files still load, and the checks that need v2 columns are skipped
for them.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field, fields
from datetime import date, datetime
from typing import Dict, List, Optional, Set

from .models import CIVIC_FIELDS, Finding, LocationRecord
from .normalize import is_analog_device_name, make_port_key, normalize_port

V2_COLUMNS = ("jack_id", "patch_panel", "switch_ip", "port_id",
              "street", "city", "state", "zip", "last_verified", "verified_by")

_COLUMN_ALIASES = {
    "port": "switch_port",
    "switch": "switch_name",
    "erl": "erl_name",
    "zip_code": "zip",
    "postal_code": "zip",
    "jack": "jack_id",
}

_RECORD_FIELDS = {f.name for f in fields(LocationRecord)} - {"row_number"}


@dataclass
class LocationDatabase:
    path: str
    records: List[LocationRecord] = field(default_factory=list)
    columns: Set[str] = field(default_factory=set)

    @property
    def schema_version(self) -> int:
        return 2 if "jack_id" in self.columns else 1

    @property
    def has_civic_columns(self) -> bool:
        return all(c in self.columns for c in CIVIC_FIELDS)

    @property
    def has_verification_columns(self) -> bool:
        return "last_verified" in self.columns

    def by_port(self) -> Dict[tuple, List[LocationRecord]]:
        index: Dict[tuple, List[LocationRecord]] = defaultdict(list)
        for rec in self.records:
            if rec.switch_port and (rec.switch_name or rec.switch_ip):
                index[rec.port_key].append(rec)
        return index

    def by_device(self) -> Dict[str, LocationRecord]:
        return {r.device_name.strip().upper(): r for r in self.records if r.device_name.strip()}


def load_location_db(path: str) -> LocationDatabase:
    """Read a v1 or v2 location CSV."""
    db = LocationDatabase(path=path)
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        raw_columns = [c.strip().lower() for c in (reader.fieldnames or [])]
        db.columns = {_COLUMN_ALIASES.get(c, c) for c in raw_columns}
        for line_no, row in enumerate(reader, start=2):
            values = {}
            for key, value in row.items():
                if key is None:
                    continue
                name = _COLUMN_ALIASES.get(key.strip().lower(), key.strip().lower())
                if name in _RECORD_FIELDS:
                    values[name] = (value or "").strip()
            if not any(values.values()):
                continue  # blank line
            db.records.append(LocationRecord(row_number=line_no, **values))
    return db


def _parse_date(text: str) -> Optional[date]:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def validate_location_db(db: LocationDatabase, today: Optional[date] = None,
                         stale_days: int = 365) -> List[Finding]:
    """Data-quality checks that need nothing but the location database."""
    today = today or date.today()
    findings: List[Finding] = []

    for rec in db.records:
        where = f"row {rec.row_number}"
        if not rec.dispatchable:
            findings.append(Finding(
                code="INCOMPLETE_LOCATION", severity="high",
                message=f"{where}: no dispatchable location; missing "
                        f"{', '.join(rec.missing_dispatchable)}.",
                switch_name=rec.switch_name, port=rec.switch_port,
                device_name=rec.device_name, jack_id=rec.jack_id,
                recommendation="Survey the jack and record building, floor and room.",
            ))
        if (not rec.switch_port or not (rec.switch_name or rec.switch_ip)) \
                and not is_analog_device_name(rec.device_name):
            findings.append(Finding(
                code="MISSING_SWITCH_PORT", severity="medium",
                message=f"{where}: location is not tied to a switch port, so it "
                        f"cannot be verified against the network.",
                device_name=rec.device_name, jack_id=rec.jack_id,
                recommendation="Trace the jack to its patch panel and switch port.",
            ))
        if db.has_civic_columns:
            missing = [f for f in CIVIC_FIELDS if not getattr(rec, f)]
            if missing:
                findings.append(Finding(
                    code="MISSING_CIVIC_ADDRESS", severity="medium",
                    message=f"{where}: civic address incomplete; missing {', '.join(missing)}.",
                    switch_name=rec.switch_name, port=rec.switch_port, jack_id=rec.jack_id,
                    recommendation="Fill in the street address the PSAP will dispatch to.",
                ))
        if db.has_verification_columns:
            verified = _parse_date(rec.last_verified) if rec.last_verified else None
            if verified is None or (today - verified).days > stale_days:
                age = "never verified" if not rec.last_verified else (
                    "unreadable verification date" if verified is None
                    else f"last verified {rec.last_verified}")
                findings.append(Finding(
                    code="STALE_VERIFICATION", severity="low",
                    message=f"{where}: {age} (policy: every {stale_days} days).",
                    switch_name=rec.switch_name, port=rec.switch_port, jack_id=rec.jack_id,
                    recommendation="Re-verify the jack on site and update last_verified.",
                ))

    for key, recs in db.by_port().items():
        rooms = {(r.building, r.floor, r.room, r.erl_name) for r in recs}
        if len(recs) > 1 and len(rooms) > 1:
            rows = ", ".join(str(r.row_number) for r in recs)
            findings.append(Finding(
                code="DUPLICATE_PORT_MAPPING", severity="high",
                message=f"{recs[0].switch_name} {normalize_port(recs[0].switch_port)} is mapped to "
                        f"{len(rooms)} different locations (rows {rows}).",
                switch_name=recs[0].switch_name, port=recs[0].switch_port,
                expected="one location per port",
                observed="; ".join(r.location_label for r in recs),
                recommendation="Trace the port and keep the one correct record.",
            ))

    jacks: Dict[str, List[LocationRecord]] = defaultdict(list)
    for rec in db.records:
        if rec.jack_id:
            jacks[f"{rec.building.lower()}|{rec.jack_id.lower()}"].append(rec)
    for recs in jacks.values():
        ports = {make_port_key(r.switch_name or r.switch_ip, r.switch_port) for r in recs}
        if len(recs) > 1 and len(ports) > 1:
            findings.append(Finding(
                code="DUPLICATE_JACK", severity="medium",
                message=f"Jack {recs[0].jack_id} in {recs[0].building} is patched to "
                        f"{len(ports)} different switch ports.",
                jack_id=recs[0].jack_id,
                observed="; ".join(
                    f"{r.switch_name} {normalize_port(r.switch_port)}" for r in recs),
                recommendation="Confirm the patch at the panel and correct the record.",
            ))
    return findings
