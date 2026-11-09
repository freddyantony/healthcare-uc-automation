"""
Command line: ``e911`` (installed) or ``python -m e911`` (with python/ on PYTHONPATH).

    e911 validate  --locations locations.csv
    e911 collect   --hosts switches.txt --out neighbors/          (needs netmiko)
    e911 reconcile --locations locations.csv --neighbors neighbors/ \\
                   --cer-switchports cer_switchport.xml --cer-unlocated cer_unlocated.xml \\
                   --inventory endpoint_inventory.csv --out reports/ --audit-db e911_audit.db
    e911 history   --audit-db e911_audit.db
    e911 push      --remediation reports/remediation.csv --cer-host cer-pub.example.org [--apply]

Credentials always come from the environment: CER_API_USER / CER_API_PASSWORD for
CER and SWITCH_USER / SWITCH_PASSWORD for switch collection.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from typing import List, Optional

from . import __version__
from .audit import describe_inputs, list_runs, record_run
from .cer import CERClient, CERError, load_export_file
from .discovery import collect_live, load_neighbor_dir
from .inventory import load_inventory
from .location_db import load_location_db, validate_location_db
from .models import SEVERITY_ORDER
from .reconcile import reconcile, remediation_by_switch
from .report import render_markdown, write_all

log = logging.getLogger("e911")


def _env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"Set {name} in the environment.")
    return value


def _exit_code(findings, fail_on: str) -> int:
    if fail_on == "none":
        return 0
    threshold = 1 if fail_on == "any" else SEVERITY_ORDER[fail_on]
    return 1 if any(f.rank >= threshold for f in findings) else 0


def cmd_validate(args) -> int:
    db = load_location_db(args.locations)
    findings = validate_location_db(db, stale_days=args.stale_days)
    print(f"{len(db.records)} records, schema v{db.schema_version}, {len(findings)} issue(s)")
    for f in findings:
        print(f"  [{f.severity}] {f.code}: {f.message}")
    return _exit_code(findings, args.fail_on)


def cmd_collect(args) -> int:
    with open(args.hosts, encoding="utf-8") as fh:
        hosts = fh.read().splitlines()
    written = collect_live(hosts, _env("SWITCH_USER"), _env("SWITCH_PASSWORD"), args.out,
                           device_type=args.device_type)
    print(f"Wrote {len(written)} file(s) to {args.out}")
    return 0


def cmd_reconcile(args) -> int:
    db = load_location_db(args.locations)
    observations = load_neighbor_dir(args.neighbors) if args.neighbors else []

    cer_ports = unlocated = None
    if args.cer_host:
        client = CERClient(args.cer_host, _env("CER_API_USER"), _env("CER_API_PASSWORD"),
                           verify_ssl=not args.no_verify)
        if not client.discovery_complete():
            raise SystemExit("CER discovery is not complete; try again later.")
        cer_ports, unlocated = client.export_switchports(), client.export_unlocated()
    else:
        if args.cer_switchports:
            cer_ports = load_export_file(args.cer_switchports, "switchport")
        if args.cer_unlocated:
            unlocated = load_export_file(args.cer_unlocated, "unlocated")
    inventory = load_inventory(args.inventory) if args.inventory else None

    result = reconcile(db, observations, cer_ports, unlocated, inventory,
                       stale_days=args.stale_days)
    run = None
    if args.audit_db:
        run = record_run(args.audit_db, result, describe_inputs({
            "locations": args.locations, "neighbors": args.neighbors,
            "cer_switchports": args.cer_switchports, "cer_unlocated": args.cer_unlocated,
            "inventory": args.inventory, "cer_host": args.cer_host}))
    write_all(args.out, result, run)
    print(render_markdown(result, run))
    print(f"Reports written to {args.out}")
    return _exit_code(result.findings, args.fail_on)


def cmd_history(args) -> int:
    runs = list_runs(args.audit_db, args.limit)
    print("run  started_at                 version  crit high  med  low  accuracy")
    for r in runs:
        acc = "-" if r["accuracy_pct"] is None else f"{r['accuracy_pct']}%"
        print(f"{r['run_id']:>3}  {r['started_at']:<25}  {r['tool_version']:<7}  "
              f"{r['critical']:>4} {r['high']:>4} {r['medium']:>4} {r['low']:>4}  {acc}")
    return 0


def cmd_push(args) -> int:
    with open(args.remediation, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    batches = remediation_by_switch(rows)
    skipped = len(rows) - sum(len(p) for p in batches.values())
    for (switch_ip, erl), ports in sorted(batches.items()):
        mode = "APPLY" if args.apply else "PLAN "
        print(f"{mode}  {switch_ip}  ERL {erl}  ports {', '.join(ports)}")
    if skipped:
        print(f"Skipped {skipped} row(s) without switch_ip, port_id or erl_name.")
    if not args.apply:
        print("Dry run only. Re-run with --apply to write to CER.")
        return 0
    client = CERClient(args.cer_host, _env("CER_API_USER"), _env("CER_API_PASSWORD"),
                       verify_ssl=not args.no_verify)
    if not client.discovery_complete():
        raise SystemExit("CER discovery is not complete; no changes made.")
    failures = 0
    for (switch_ip, erl), ports in sorted(batches.items()):
        try:
            response = client.update_switchport_erl(switch_ip, ports, erl)
            print(f"OK     {switch_ip}  ERL {erl}: {response.get('message', response)}")
        except CERError as exc:
            failures += 1
            print(f"FAILED {switch_ip}  ERL {erl}: {exc}")
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="e911", description="E911 reconciliation engine")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    fail_choices = ["critical", "high", "medium", "low", "any", "none"]

    p = sub.add_parser("validate", help="check the location database on its own")
    p.add_argument("--locations", required=True)
    p.add_argument("--stale-days", type=int, default=365)
    p.add_argument("--fail-on", choices=fail_choices, default="high")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("collect", help="collect CDP/LLDP/MAC tables from switches over SSH")
    p.add_argument("--hosts", required=True, help="file with one switch per line")
    p.add_argument("--out", required=True)
    p.add_argument("--device-type", default="cisco_ios")
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("reconcile", help="compare all sources and report drift")
    p.add_argument("--locations", required=True)
    p.add_argument("--neighbors", help="directory of <switch>.<cdp|lldp|mac>.txt files")
    p.add_argument("--cer-switchports", help="saved CER switchport/info export (XML)")
    p.add_argument("--cer-unlocated", help="saved CER unlocatedphones/info export (XML)")
    p.add_argument("--cer-host", help="read exports live from this CER Publisher")
    p.add_argument("--inventory", help="CUCM endpoint inventory CSV")
    p.add_argument("--out", default="reports")
    p.add_argument("--audit-db", help="SQLite audit history to append this run to")
    p.add_argument("--stale-days", type=int, default=365)
    p.add_argument("--fail-on", choices=fail_choices, default="critical")
    p.add_argument("--no-verify", action="store_true", help="skip TLS verification (labs only)")
    p.set_defaults(func=cmd_reconcile)

    p = sub.add_parser("history", help="show past runs from the audit history")
    p.add_argument("--audit-db", required=True)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("push", help="apply remediation.csv to CER (dry run by default)")
    p.add_argument("--remediation", required=True)
    p.add_argument("--cer-host", required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--no-verify", action="store_true")
    p.set_defaults(func=cmd_push)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"Input not found: {exc}", file=sys.stderr)
        return 2
    except CERError as exc:
        print(f"CER error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
