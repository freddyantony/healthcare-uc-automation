"""
Healthcare UC Automation - CUCM Endpoint Inventory
==================================================

Fully functional reporting tool that connects to a Cisco Unified Communications
Manager (CUCM) cluster over the AXL SOAP API, extracts a complete phone-endpoint
inventory via an executeSQLQuery call, and writes a CSV report plus a summary
breakdown by device model and device pool.

Unlike a reference skeleton, this script performs the real end-to-end operation:
it builds an authenticated zeep SOAP client against the AXL WSDL, executes a live
SQL query against the CUCM database, parses the result set, and produces output.
It requires a reachable CUCM cluster, a read-capable AXL application user, and the
AXL WSDL toolkit (downloaded from your CUCM, per Cisco licensing) to run.

Author: Freddy Simon Paul Antony
License: MIT

------------------------------------------------------------------------------
USAGE
------------------------------------------------------------------------------

    # Credentials via environment (recommended) or a .env file:
    #   export CUCM_AXL_USER="axl-readonly"
    #   export CUCM_AXL_PASSWORD="********"

    python endpoint_inventory.py \
        --host cucm-pub.example.org \
        --wsdl ./schema/12.5/AXLAPI.wsdl \
        --output endpoint_inventory.csv

    # Filter to a model substring and cap rows (lab / spot checks):
    python endpoint_inventory.py --host cucm-pub.example.org \
        --wsdl ./schema/12.5/AXLAPI.wsdl --model-filter "8845" --limit 500

------------------------------------------------------------------------------
NOTES
------------------------------------------------------------------------------
- The AXL WSDL is not redistributed here. Download the AXL Toolkit for your CUCM
  version from: CUCM Admin > Application > Plugins > "Cisco CallManager AXL
  SOAP Toolkit", and point --wsdl at the AXLAPI.wsdl inside it.
- Use a least-privilege AXL application user with read-only access.
- This script reads configuration data only (no PHI). Live registration status
  is a runtime value served by RisPort70, not the AXL database, and is therefore
  out of scope for this configuration-inventory report.
"""

import argparse
import csv
import logging
import os
import sys
import urllib3
from datetime import datetime
from collections import Counter
from typing import Dict, List

from requests import Session
from requests.auth import HTTPBasicAuth
from zeep import Client, Settings
from zeep.cache import SqliteCache
from zeep.transports import Transport
from zeep.exceptions import Fault

try:
    # Optional: load credentials from a local .env if python-dotenv is installed
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("endpoint_inventory")

# AXL binding namespace is stable across CUCM versions; the service URL path is
# always /axl/ on TCP 8443.
AXL_BINDING = "{http://www.cisco.com/AXLAPIService/}AXLAPIBinding"
AXL_PORT = 8443

# Configuration-only inventory query. Joins device -> typemodel (human-readable
# model name) and device -> devicepool. Restricted to Cisco phone models.
INVENTORY_SQL = """
SELECT d.name        AS devicename,
       d.description  AS description,
       tm.name        AS model,
       dp.name        AS devicepool
FROM   device d
       INNER JOIN typemodel tm ON d.tkmodel = tm.enum
       LEFT  JOIN devicepool dp ON d.fkdevicepool = dp.pkid
WHERE  d.tkclass = 1
"""


def build_axl_client(host: str, user: str, password: str, wsdl: str,
                     verify_ssl: bool) -> "Client":
    """
    Build an authenticated zeep client bound to the CUCM AXL service.

    Returns a zeep service proxy on which AXL operations (e.g. executeSQLQuery)
    can be called directly.
    """
    if not os.path.isfile(wsdl):
        raise FileNotFoundError(
            f"AXL WSDL not found at '{wsdl}'. Download the AXL Toolkit from your "
            f"CUCM (Application > Plugins) and point --wsdl at AXLAPI.wsdl."
        )

    session = Session()
    session.auth = HTTPBasicAuth(user, password)
    session.verify = verify_ssl
    if not verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        logger.warning("TLS certificate verification is DISABLED (--no-verify).")

    settings = Settings(strict=False, xml_huge_tree=True)
    transport = Transport(session=session, cache=SqliteCache(timeout=86400))

    logger.info("Loading AXL WSDL and binding to https://%s:%d/axl/", host, AXL_PORT)
    client = Client(wsdl=wsdl, settings=settings, transport=transport)
    service = client.create_service(
        AXL_BINDING, f"https://{host}:{AXL_PORT}/axl/"
    )
    return service


def fetch_inventory(service, model_filter: str = "", limit: int = 0) -> List[Dict]:
    """
    Execute the inventory SQL query against CUCM and return a list of row dicts.

    Args:
        service: zeep AXL service proxy.
        model_filter: optional case-insensitive substring to match on model name.
        limit: optional cap on rows returned (0 = no cap).
    """
    sql = INVENTORY_SQL
    if model_filter:
        # Parameterization is not available for executeSQLQuery; the filter is
        # constrained to an alphanumeric/space/dash whitelist to avoid injection.
        safe = "".join(c for c in model_filter if c.isalnum() or c in " -_")
        sql += f" AND tm.name LIKE '%{safe}%'"
    sql += " ORDER BY dp.name, d.name"

    logger.info("Executing AXL SQL inventory query...")
    try:
        resp = service.executeSQLQuery(sql=sql)
    except Fault as fault:
        logger.error("AXL Fault: %s", fault.message)
        raise

    rows = []
    # zeep exposes the AXL response body under the 'return' attribute. Because
    # 'return' is a reserved word, it must be accessed via getattr. Empty result
    # sets come back as None.
    result = getattr(resp, "return", None)
    if result is None:
        logger.info("Query returned no rows.")
        return rows

    # The result set is a sequence of <row> elements, each containing one child
    # element per selected column.
    raw_rows = getattr(result, "row", None)
    if raw_rows is None:
        return rows

    for r in raw_rows:
        # Each row's columns are exposed as child elements; coerce to plain str.
        record = {
            "device_name": _col(r, "devicename"),
            "description": _col(r, "description"),
            "model": _col(r, "model"),
            "device_pool": _col(r, "devicepool"),
        }
        rows.append(record)
        if limit and len(rows) >= limit:
            logger.info("Row limit (%d) reached.", limit)
            break

    logger.info("Retrieved %d endpoint records.", len(rows))
    return rows


def _col(row, name: str) -> str:
    """Extract a column value from a zeep SQL row element, as a clean string."""
    for child in row:
        if child.tag == name:
            return (child.text or "").strip()
    return ""


def write_csv(rows: List[Dict], output_path: str) -> None:
    """Write inventory rows to a CSV file."""
    fieldnames = ["device_name", "description", "model", "device_pool"]
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Wrote %d rows to %s", len(rows), output_path)


def print_summary(rows: List[Dict]) -> None:
    """Print a breakdown of the inventory by model and by device pool."""
    if not rows:
        return
    by_model = Counter(r["model"] for r in rows)
    by_pool = Counter(r["device_pool"] or "(none)" for r in rows)

    print("\n" + "=" * 52)
    print(f"ENDPOINT INVENTORY SUMMARY  ({datetime.now():%Y-%m-%d %H:%M})")
    print("=" * 52)
    print(f"Total endpoints: {len(rows)}\n")

    print("By model:")
    for model, count in by_model.most_common():
        print(f"  {count:>6}  {model}")

    print("\nBy device pool (top 15):")
    for pool, count in by_pool.most_common(15):
        print(f"  {count:>6}  {pool}")
    print("=" * 52 + "\n")


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Extract a CUCM phone-endpoint inventory via AXL and write CSV."
    )
    p.add_argument("--host", required=True,
                   help="CUCM Publisher hostname or IP.")
    p.add_argument("--wsdl", required=True,
                   help="Path to AXLAPI.wsdl from the AXL Toolkit for your version.")
    p.add_argument("--output", default="endpoint_inventory.csv",
                   help="Output CSV path (default: endpoint_inventory.csv).")
    p.add_argument("--model-filter", default="",
                   help="Optional case-insensitive model substring (e.g. '8845').")
    p.add_argument("--limit", type=int, default=0,
                   help="Optional cap on number of rows (0 = no cap).")
    p.add_argument("--no-verify", action="store_true",
                   help="Disable TLS certificate verification (lab use only).")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    user = os.environ.get("CUCM_AXL_USER")
    password = os.environ.get("CUCM_AXL_PASSWORD")
    if not user or not password:
        logger.error(
            "Missing credentials. Set CUCM_AXL_USER and CUCM_AXL_PASSWORD in the "
            "environment or a local .env file."
        )
        return 2

    try:
        service = build_axl_client(
            host=args.host, user=user, password=password,
            wsdl=args.wsdl, verify_ssl=not args.no_verify,
        )
        rows = fetch_inventory(
            service, model_filter=args.model_filter, limit=args.limit
        )
        write_csv(rows, args.output)
        print_summary(rows)
    except FileNotFoundError as e:
        logger.error(str(e))
        return 2
    except Fault:
        return 1
    except Exception as e:  # noqa: BLE001 - top-level guard for a CLI tool
        logger.error("Unexpected error: %s", e)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
