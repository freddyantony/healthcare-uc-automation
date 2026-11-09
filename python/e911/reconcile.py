"""
Reconciliation engine.

Joins the four sources on (switch, port) and reports every place they disagree.

Finding codes (severity):

    UNMAPPED_PORT        critical  phone plugged into a port with no jack/room record
    PORT_ERL_MISMATCH    critical  CER sends a different ERL than the location record
                                   (high when no phone is on the port right now)
    PORT_NOT_IN_CER      high      port has a location record but no ERL in CER
    SWITCH_NOT_IN_CER    high      CER is not tracking a switch the location DB uses
    DEVICE_MOVED         high      phone recorded at one jack is now on another port
    CER_UNLOCATED        high      CER cannot place the phone
    ANALOG_UNMAPPED      high      analog station with no recorded location
    CER_TRACKING_STALE   medium    CER shows a different phone on the port than the switch does
    DEVICE_NOT_OBSERVED  medium    wired phone in CUCM not seen on any surveyed switch
    + the location-database checks in location_db.validate_location_db()

Accuracy score = phones whose current port resolves to a complete dispatchable
location (and, when CER data is supplied, to the same ERL in CER), divided by all
phones observed on the network.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from .inventory import is_analog, is_soft_or_wireless
from .location_db import LocationDatabase, validate_location_db
from .models import CerPort, Finding, InventoryDevice, LocationRecord, PortObservation, \
    UnlocatedPhone
from .normalize import device_name_from_mac, is_ip_address, normalize_mac, \
    normalize_port, normalize_switch, port_compare_key


@dataclass
class ReconcileResult:
    findings: List[Finding] = field(default_factory=list)
    stats: Dict[str, object] = field(default_factory=dict)
    remediation: List[Dict[str, str]] = field(default_factory=list)

    def counts_by_severity(self) -> Dict[str, int]:
        counts = Counter(f.severity for f in self.findings)
        return {s: counts.get(s, 0) for s in ("critical", "high", "medium", "low", "info")}

    def counts_by_code(self) -> Dict[str, int]:
        return dict(sorted(Counter(f.code for f in self.findings).items()))


class SwitchResolver:
    """Maps switch IPs and hostnames from every source to one canonical name."""

    def __init__(self):
        self._ip_to_name: Dict[str, str] = {}

    def learn(self, name: str, ip: str) -> None:
        if name and ip and not is_ip_address(name):
            self._ip_to_name.setdefault(ip.strip(), normalize_switch(name))

    def canon(self, name_or_ip: str) -> str:
        value = (name_or_ip or "").strip()
        if is_ip_address(value):
            return self._ip_to_name.get(value, value)
        return normalize_switch(value)

    def key(self, switch: str, port: str):
        return self.canon(switch), port_compare_key(port)


def _same(a: str, b: str) -> bool:
    return (a or "").strip().lower() == (b or "").strip().lower()


def reconcile(db: LocationDatabase,
              observations: Optional[List[PortObservation]] = None,
              cer_ports: Optional[List[CerPort]] = None,
              unlocated: Optional[List[UnlocatedPhone]] = None,
              inventory: Optional[List[InventoryDevice]] = None,
              stale_days: int = 365,
              today: Optional[date] = None) -> ReconcileResult:
    observations = observations or []
    result = ReconcileResult()
    findings = result.findings
    findings.extend(validate_location_db(db, today=today, stale_days=stale_days))

    resolver = SwitchResolver()
    for rec in db.records:
        resolver.learn(rec.switch_name, rec.switch_ip)
    for port in cer_ports or []:
        resolver.learn(port.switch_host, port.switch_ip)

    # --- index every source on the canonical (switch, port) key -------------
    loc_by_port: Dict[tuple, LocationRecord] = {}
    for rec in db.records:
        if rec.switch_port and (rec.switch_name or rec.switch_ip):
            loc_by_port.setdefault(resolver.key(rec.switch_name or rec.switch_ip,
                                                rec.switch_port), rec)
    loc_by_device = db.by_device()

    cer_by_port: Dict[tuple, CerPort] = {}
    cer_switches = set()
    cer_by_mac: Dict[str, CerPort] = {}
    for port in cer_ports or []:
        switch = resolver.canon(port.switch_host or port.switch_ip)
        cer_switches.add(switch)
        cer_by_port.setdefault((switch, port_compare_key(port.interface)), port)
        mac = normalize_mac(port.phone_mac)
        if mac:
            cer_by_mac.setdefault(mac, port)

    inv_by_name = {d.device_name.upper(): d for d in inventory or []}
    inv_by_mac = {d.mac: d for d in inventory or [] if d.mac}

    # --- which observations are phones, and which device each one is --------
    phones: List[tuple] = []  # (observation, device_name, key)
    for obs in observations:
        device = inv_by_name.get(obs.device_id.upper()) if obs.device_id else None
        if device is None and obs.mac:
            device = inv_by_mac.get(obs.mac)
        if not (obs.is_phone or device is not None):
            continue
        if device is not None:
            name = device.device_name
        elif obs.device_id and not obs.device_id.count("."):
            name = obs.device_id
        elif obs.mac:
            name = device_name_from_mac(obs.mac)
        else:
            name = obs.device_id
        phones.append((obs, name, resolver.key(obs.switch_name, obs.port)))

    observed_by_device: Dict[str, tuple] = {}
    observed_macs = set()
    occupied_ports = set()
    for obs, name, key in phones:
        observed_by_device.setdefault(name.upper(), (obs, key))
        occupied_ports.add(key)
        if obs.mac:
            observed_macs.add(obs.mac)

    # --- 1. phones on ports with no location record ---------------------------
    verified = 0
    for obs, name, key in phones:
        rec = loc_by_port.get(key)
        if rec is None:
            findings.append(Finding(
                code="UNMAPPED_PORT", severity="critical",
                message=f"{name} is connected to {obs.switch_name} {obs.port}, which has no "
                        f"jack or room on record. A 911 call from it has no verified "
                        f"dispatchable location.",
                switch_name=obs.switch_name, port=obs.port, device_name=name,
                observed=f"{obs.source.upper()} neighbor {obs.device_id or obs.mac}",
                recommendation="Trace the port to its jack, survey the room and add a "
                               "location record.",
            ))
            continue
        if not rec.dispatchable:
            continue  # already reported as INCOMPLETE_LOCATION
        cer = cer_by_port.get(key)
        if cer_ports is None or (cer is not None and _same(cer.erl_name, rec.erl_name)):
            verified += 1
        if cer is not None and obs.mac:
            cer_mac = normalize_mac(cer.phone_mac)
            if cer_mac and cer_mac != obs.mac:
                findings.append(Finding(
                    code="CER_TRACKING_STALE", severity="medium",
                    message=f"CER still shows {cer.phone_mac} on {obs.switch_name} {obs.port}; "
                            f"the switch reports {name} there now.",
                    switch_name=obs.switch_name, port=obs.port, device_name=name,
                    jack_id=rec.jack_id, expected=name, observed=cer.phone_mac,
                    recommendation="Check that CER's switch discovery schedule covers this "
                                   "switch, or run a discovery for it.",
                ))

    # --- 2. CER's ERL for every recorded port ------------------------------------
    if cer_ports is not None:
        missing_switches = {}
        for key, rec in loc_by_port.items():
            if not rec.erl_name:
                continue
            switch = key[0]
            if switch not in cer_switches:
                missing_switches.setdefault(switch, rec)
                continue
            cer = cer_by_port.get(key)
            live = key in occupied_ports
            if cer is None or not cer.erl_name:
                findings.append(Finding(
                    code="PORT_NOT_IN_CER", severity="high",
                    message=f"{rec.switch_name} {normalize_port(rec.switch_port)} "
                            f"({rec.location_label}) has no ERL in CER"
                            + ("" if cer else "; CER has no record of the port") + ".",
                    switch_name=rec.switch_name, port=rec.switch_port,
                    device_name=rec.device_name, jack_id=rec.jack_id,
                    expected=rec.erl_name, observed="(none)",
                    recommendation="Assign the recorded ERL to the port in CER "
                                   "(see remediation file).",
                ))
                if cer is not None:
                    result.remediation.append(_remediation_row(rec, cer, "PORT_NOT_IN_CER"))
            elif not _same(cer.erl_name, rec.erl_name):
                findings.append(Finding(
                    code="PORT_ERL_MISMATCH", severity="critical" if live else "high",
                    message=f"CER would send ERL {cer.erl_name} for {rec.switch_name} "
                            f"{normalize_port(rec.switch_port)}; the location record says "
                            f"{rec.erl_name} ({rec.location_label})."
                            + (" A phone is on this port now." if live else ""),
                    switch_name=rec.switch_name, port=rec.switch_port,
                    device_name=rec.device_name, jack_id=rec.jack_id,
                    expected=rec.erl_name, observed=cer.erl_name,
                    recommendation="Correct the ERL in CER after confirming the jack "
                                   "(see remediation file).",
                ))
                result.remediation.append(_remediation_row(rec, cer, "PORT_ERL_MISMATCH"))
        for switch, rec in sorted(missing_switches.items()):
            ports = sum(1 for k in loc_by_port if k[0] == switch)
            findings.append(Finding(
                code="SWITCH_NOT_IN_CER", severity="high",
                message=f"CER is not tracking switch {rec.switch_name} "
                        f"({rec.switch_ip or 'IP unknown'}); {ports} recorded port(s) on it "
                        f"cannot be located by CER.",
                switch_name=rec.switch_name,
                recommendation="Add the switch to CER's LAN switch list and run discovery.",
            ))

    # --- 3. phones that moved off their recorded jack ---------------------------
    for device_key, rec in loc_by_device.items():
        seen = observed_by_device.get(device_key)
        if not seen:
            continue
        obs, key = seen
        rec_key = resolver.key(rec.switch_name or rec.switch_ip, rec.switch_port)
        if rec.switch_port and key != rec_key:
            new_rec = loc_by_port.get(key)
            findings.append(Finding(
                code="DEVICE_MOVED", severity="high",
                message=f"{rec.device_name} was recorded at {rec.location_label} but is now on "
                        f"{obs.switch_name} {obs.port} "
                        f"({new_rec.location_label if new_rec else 'unmapped port'}).",
                switch_name=obs.switch_name, port=obs.port, device_name=rec.device_name,
                jack_id=rec.jack_id,
                expected=f"{rec.switch_name} {normalize_port(rec.switch_port)}",
                observed=f"{obs.switch_name} {obs.port}",
                recommendation="Update device_name in the location records; 911 location "
                               "follows the new port.",
            ))

    # --- 4. phones CER cannot place -----------------------------------------------
    for phone in unlocated or []:
        mac = normalize_mac(phone.mac)
        name = inv_by_mac[mac].device_name if mac and mac in inv_by_mac else (
            device_name_from_mac(mac) if mac else phone.mac)
        seen = observed_by_device.get(name.upper())
        rec = loc_by_port.get(seen[1]) if seen else None
        where = (f"switch discovery places it on {seen[0].switch_name} {seen[0].port}"
                 + (f" ({rec.location_label})" if rec else " (unmapped port)")) if seen else \
            "switch discovery did not find it either"
        findings.append(Finding(
            code="CER_UNLOCATED", severity="high",
            message=f"CER cannot locate {name} (ext {phone.extension or '?'}); {where}.",
            switch_name=seen[0].switch_name if seen else "",
            port=seen[0].port if seen else "", device_name=name,
            observed=phone.effective_erl or phone.erl_used_info,
            recommendation="Add the switch to CER, or assign the phone a manual ERL "
                           "from the location record.",
        ))

    # --- 5. CUCM devices the network survey could not account for ---------------
    soft = analog = 0
    for device in inventory or []:
        if is_soft_or_wireless(device):
            soft += 1
            continue
        if is_analog(device):
            analog += 1
            rec = loc_by_device.get(device.device_name.upper())
            if rec is None or not rec.dispatchable:
                label = device.description or "no description"
                findings.append(Finding(
                    code="ANALOG_UNMAPPED", severity="high",
                    message=f"Analog station {device.device_name} ({label}) has no complete "
                            f"location record. CER cannot track analog lines automatically.",
                    device_name=device.device_name,
                    recommendation="Record the station's room and jack in the location "
                                   "database (device_name column).",
                ))
            continue
        name = device.device_name.upper()
        if name in observed_by_device or (device.mac and (
                device.mac in observed_macs or device.mac in cer_by_mac)):
            continue
        if observations:
            findings.append(Finding(
                code="DEVICE_NOT_OBSERVED", severity="medium",
                message=f"{device.device_name} ({device.model}) is configured in CUCM but was "
                        f"not seen on any surveyed switch or in CER.",
                device_name=device.device_name,
                recommendation="Extend the switch survey, or confirm the phone is offline "
                               "or decommissioned.",
            ))

    findings.sort(key=lambda f: (-f.rank, f.code, f.switch_name, f.port, f.device_name))
    phones_total = len(phones)
    result.stats = {
        "location_records": len(db.records),
        "location_schema_version": db.schema_version,
        "switches_surveyed": len({resolver.canon(o.switch_name) for o in observations}),
        "phones_observed": phones_total,
        "phones_on_mapped_ports": sum(1 for _o, _n, k in phones if k in loc_by_port),
        "phones_verified": verified,
        "accuracy_pct": round(100.0 * verified / phones_total, 1) if phones_total else None,
        "cer_ports": len(cer_ports or []),
        "cer_unlocated": len(unlocated or []),
        "inventory_devices": len(inventory or []),
        "inventory_soft_or_wireless": soft,
        "inventory_analog": analog,
        "remediation_rows": len(result.remediation),
    }
    return result


def _remediation_row(rec: LocationRecord, cer: CerPort, reason: str) -> Dict[str, str]:
    return {
        "switch_name": rec.switch_name,
        "switch_ip": rec.switch_ip or cer.switch_ip,
        "switch_port": rec.switch_port,
        "port_id": rec.port_id or cer.port_identifier,
        "erl_name": rec.erl_name,
        "current_erl": cer.erl_name,
        "building": rec.building,
        "floor": rec.floor,
        "room": rec.room,
        "jack_id": rec.jack_id,
        "finding": reason,
    }


def remediation_by_switch(rows: List[Dict[str, str]]) -> Dict[tuple, List[str]]:
    """Group remediation rows into one CER update per (switch IP, ERL)."""
    grouped: Dict[tuple, List[str]] = defaultdict(list)
    for row in rows:
        if row.get("switch_ip") and row.get("port_id") and row.get("erl_name"):
            grouped[(row["switch_ip"], row["erl_name"])].append(row["port_id"])
    return dict(grouped)
