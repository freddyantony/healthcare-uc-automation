"""
Healthcare UC Automation - E911 Compliance Report
=================================================

Generates a RAY BAUM's Act / Kari's Law dispatchable-location compliance report
for a CUCM environment. Cross-references the configured phone-endpoint inventory
(from AXL) against an Emergency Response Location (ERL) mapping export, and flags
endpoints that lack a dispatchable location (building / floor / room).

This is functional reference code: given a CUCM endpoint-inventory CSV (produced
by endpoint_inventory.py) and an ERL location-mapping CSV (export from Cisco
Emergency Responder, or the template in templates/), it computes per-building and
overall compliance and writes a gap report.

Author: Freddy Simon Paul Antony
License: MIT

------------------------------------------------------------------------------
USAGE
------------------------------------------------------------------------------

    python compliance_report.py \
        --inventory endpoint_inventory.csv \
        --locations e911_locations.csv \
        --output e911_compliance_report.csv

The --locations file maps each device to its ERL; see
templates/e911-location-database-template.csv for the expected columns.
"""

import argparse
import csv
import logging
import sys
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("compliance_report")

# A dispatchable location under RAY BAUM's Act must resolve to building + floor +
# room/zone. An ERL row is considered complete only when all three are present.
REQUIRED_LOCATION_FIELDS = ("building", "floor", "room")


def load_inventory(path: str) -> List[Dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    logger.info("Loaded %d endpoints from %s", len(rows), path)
    return rows


def load_locations(path: str) -> Dict[str, Dict]:
    """Index the ERL location mapping by device_name for O(1) lookup."""
    mapping = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            key = (row.get("device_name") or "").strip()
            if key:
                mapping[key] = row
    logger.info("Loaded %d location mappings from %s", len(mapping), path)
    return mapping


def is_dispatchable(location: Dict) -> bool:
    """True if the ERL row carries a complete dispatchable location."""
    if not location:
        return False
    return all((location.get(f) or "").strip() for f in REQUIRED_LOCATION_FIELDS)


def evaluate(inventory: List[Dict], locations: Dict[str, Dict]) -> List[Dict]:
    """Join inventory to locations and classify each endpoint's compliance."""
    results = []
    for ep in inventory:
        name = (ep.get("device_name") or "").strip()
        loc = locations.get(name)
        compliant = is_dispatchable(loc)
        results.append({
            "device_name": name,
            "description": ep.get("description", ""),
            "model": ep.get("model", ""),
            "device_pool": ep.get("device_pool", ""),
            "building": (loc or {}).get("building", ""),
            "floor": (loc or {}).get("floor", ""),
            "room": (loc or {}).get("room", ""),
            "erl_name": (loc or {}).get("erl_name", ""),
            "compliant": "YES" if compliant else "NO",
            "gap_reason": "" if compliant else _gap_reason(loc),
        })
    return results


def _gap_reason(loc: Dict) -> str:
    if not loc:
        return "No ERL mapping found for device"
    missing = [f for f in REQUIRED_LOCATION_FIELDS if not (loc.get(f) or "").strip()]
    return "Missing: " + ", ".join(missing) if missing else "Incomplete location"


def summarize(results: List[Dict]) -> None:
    total = len(results)
    compliant = sum(1 for r in results if r["compliant"] == "YES")
    pct = (compliant / total * 100) if total else 0.0

    by_building = defaultdict(lambda: [0, 0])  # building -> [compliant, total]
    for r in results:
        b = r["building"] or "(unmapped)"
        by_building[b][1] += 1
        if r["compliant"] == "YES":
            by_building[b][0] += 1

    print("\n" + "=" * 56)
    print(f"E911 / RAY BAUM'S ACT COMPLIANCE  ({datetime.now():%Y-%m-%d %H:%M})")
    print("=" * 56)
    print(f"Total endpoints:     {total}")
    print(f"Dispatchable (OK):   {compliant}")
    print(f"Non-compliant:       {total - compliant}")
    print(f"Compliance:          {pct:.1f}%\n")
    print("By building:")
    for b, (c, t) in sorted(by_building.items()):
        bpct = (c / t * 100) if t else 0.0
        print(f"  {bpct:5.1f}%  ({c}/{t})  {b}")
    print("=" * 56 + "\n")


def write_report(results: List[Dict], output_path: str) -> None:
    fieldnames = ["device_name", "description", "model", "device_pool",
                  "building", "floor", "room", "erl_name",
                  "compliant", "gap_reason"]
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    logger.info("Wrote compliance report (%d rows) to %s",
                len(results), output_path)


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate an E911 dispatchable-location compliance report."
    )
    p.add_argument("--inventory", required=True,
                   help="Endpoint inventory CSV (from endpoint_inventory.py).")
    p.add_argument("--locations", required=True,
                   help="ERL location-mapping CSV (see templates/).")
    p.add_argument("--output", default="e911_compliance_report.csv",
                   help="Output report CSV path.")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        inventory = load_inventory(args.inventory)
        locations = load_locations(args.locations)
    except FileNotFoundError as e:
        logger.error("Input file not found: %s", e)
        return 2

    results = evaluate(inventory, locations)
    write_report(results, args.output)
    summarize(results)

    non_compliant = sum(1 for r in results if r["compliant"] == "NO")
    # Non-zero exit when gaps exist, so this can gate a CI / scheduled check.
    return 1 if non_compliant else 0


if __name__ == "__main__":
    sys.exit(main())
