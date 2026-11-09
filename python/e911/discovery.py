"""
Switch discovery: what is actually plugged in where.

Parses the output of ``show cdp neighbors detail``, ``show lldp neighbors
detail`` and ``show mac address-table`` from Cisco IOS / IOS-XE access switches.
Output can be collected live (netmiko, optional) or by the Ansible playbook
``e911-reconcile.yml``, which saves one file per switch and command:

    <switch>.cdp.txt   <switch>.lldp.txt   <switch>.mac.txt

The MAC table covers devices that do not speak CDP or LLDP (for example some
analog telephone adapters and third-party phones); they are matched to CUCM
devices by the MAC address embedded in the device name.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from .models import PortObservation
from .normalize import mac_from_device_name, normalize_mac, normalize_port

COMMANDS = {
    "cdp": "show cdp neighbors detail",
    "lldp": "show lldp neighbors detail",
    "mac": "show mac address-table dynamic",
}

_SOURCE_PRIORITY = {"cdp": 3, "lldp": 2, "mac": 1}
_BLOCK_SPLIT = re.compile(r"^-{5,}\s*$", re.MULTILINE)
_NON_ACCESS_PORT = re.compile(r"^(Po|Vl|Vlan|CPU|Router|Switch|Drop|Lo|Tu)", re.IGNORECASE)


def _looks_like_phone(*texts: str) -> bool:
    joined = " ".join(t for t in texts if t).lower()
    return "phone" in joined or "telepresence" in joined or "webex desk" in joined


def parse_cdp_neighbors_detail(text: str, switch_name: str) -> List[PortObservation]:
    observations = []
    for block in _BLOCK_SPLIT.split(text or ""):
        device = re.search(r"Device ID:\s*(\S+)", block)
        interface = re.search(r"Interface:\s*([^,\n]+)", block)
        if not device or not interface:
            continue
        platform = re.search(r"Platform:\s*([^,\n]+)", block)
        capabilities = re.search(r"Capabilities:\s*([^\n]+)", block)
        ip = re.search(r"IP(?:v4)? [Aa]ddress:\s*([\d.]+)", block)
        device_id = device.group(1).strip()
        platform_text = platform.group(1).strip() if platform else ""
        observations.append(PortObservation(
            switch_name=switch_name,
            port=normalize_port(interface.group(1)),
            source="cdp",
            device_id=device_id,
            ip=ip.group(1) if ip else "",
            platform=platform_text,
            is_phone=bool(mac_from_device_name(device_id)) or _looks_like_phone(
                platform_text, capabilities.group(1) if capabilities else ""),
        ))
    return observations


def parse_lldp_neighbors_detail(text: str, switch_name: str) -> List[PortObservation]:
    observations = []
    for block in _BLOCK_SPLIT.split(text or ""):
        local = re.search(r"Local Intf:\s*(\S+)", block)
        if not local:
            continue
        name = re.search(r"System Name:\s*(\S+)", block)
        port_id = re.search(r"Port id:\s*(\S+)", block)
        chassis = re.search(r"Chassis id:\s*(\S+)", block)
        desc = re.search(r"System Description:\s*\n\s*([^\n]+)", block)
        caps = re.search(r"System Capabilities:\s*([^\n]+)", block)
        ip = re.search(r"IP(?:v4)?:\s*([\d.]+)", block)
        device_id = name.group(1).strip() if name else ""
        mac = mac_from_device_name(device_id)
        if not mac and port_id:
            mac = normalize_mac(port_id.group(1)[:12]) or normalize_mac(port_id.group(1))
        if not mac and chassis:
            mac = normalize_mac(chassis.group(1))
        description = desc.group(1).strip() if desc else ""
        observations.append(PortObservation(
            switch_name=switch_name,
            port=normalize_port(local.group(1)),
            source="lldp",
            device_id=device_id,
            mac=mac,
            ip=ip.group(1) if ip else "",
            platform=description,
            is_phone=bool(mac_from_device_name(device_id)) or _looks_like_phone(description)
            or bool(caps and re.search(r"\bT\b", caps.group(1))),
        ))
    return observations


_MAC_ROW = re.compile(
    r"^\s*(\d+|All)\s+([0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4})\s+(\S+)\s+(\S+)",
    re.MULTILINE)


def parse_mac_address_table(text: str, switch_name: str,
                            max_macs_per_port: int = 3) -> List[PortObservation]:
    """Access-port MAC entries. Ports learning more than ``max_macs_per_port``
    addresses are treated as uplinks and skipped."""
    per_port: Dict[str, List[str]] = defaultdict(list)
    for _vlan, mac, entry_type, port in _MAC_ROW.findall(text or ""):
        if entry_type.upper() not in ("DYNAMIC", "STATIC") or _NON_ACCESS_PORT.match(port):
            continue
        normalized = normalize_mac(mac)
        if normalized and normalized not in per_port[port]:
            per_port[port].append(normalized)
    observations = []
    for port, macs in per_port.items():
        if len(macs) > max_macs_per_port:
            continue
        for mac in macs:
            observations.append(PortObservation(
                switch_name=switch_name, port=normalize_port(port), source="mac", mac=mac))
    return observations


_PARSERS = {
    "cdp": parse_cdp_neighbors_detail,
    "lldp": parse_lldp_neighbors_detail,
    "mac": parse_mac_address_table,
}


def merge_observations(observations: Iterable[PortObservation]) -> List[PortObservation]:
    """One observation per (switch, port, device). CDP beats LLDP beats MAC,
    and gaps in the winner are filled from the others."""
    merged: Dict[tuple, PortObservation] = {}
    for obs in observations:
        identity = obs.mac or obs.device_id.upper() or "?"
        key = (obs.port_key, identity)
        current = merged.get(key)
        if current is None:
            merged[key] = obs
            continue
        winner, other = (obs, current) if (
            _SOURCE_PRIORITY[obs.source] > _SOURCE_PRIORITY[current.source]) else (current, obs)
        for attr in ("device_id", "ip", "platform"):
            if not getattr(winner, attr) and getattr(other, attr):
                setattr(winner, attr, getattr(other, attr))
        winner.mac = winner.mac or other.mac
        winner.is_phone = winner.is_phone or other.is_phone
        merged[key] = winner
    return list(merged.values())


def load_neighbor_dir(path: str, max_macs_per_port: int = 3) -> List[PortObservation]:
    """Parse every ``<switch>.<cdp|lldp|mac>.txt`` file in a directory."""
    observations: List[PortObservation] = []
    for filename in sorted(os.listdir(path)):
        match = re.match(r"^(.+)\.(cdp|lldp|mac)\.txt$", filename)
        if not match:
            continue
        switch_name, source = match.group(1), match.group(2)
        with open(os.path.join(path, filename), encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        if source == "mac":
            observations.extend(parse_mac_address_table(text, switch_name, max_macs_per_port))
        else:
            observations.extend(_PARSERS[source](text, switch_name))
    return merge_observations(observations)


def collect_live(hosts: Iterable[str], username: str, password: str, out_dir: str,
                 device_type: str = "cisco_ios", secret: Optional[str] = None) -> List[str]:
    """Run the discovery commands on each switch over SSH and save the output.

    Requires the optional ``netmiko`` package. Read-only: only ``show`` commands
    are sent.
    """
    try:
        from netmiko import ConnectHandler  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on optional package
        raise RuntimeError("Live collection needs netmiko: pip install netmiko") from exc

    os.makedirs(out_dir, exist_ok=True)
    written = []
    for host in hosts:
        host = host.strip()
        if not host or host.startswith("#"):
            continue
        params = {"device_type": device_type, "host": host,
                  "username": username, "password": password}
        if secret:
            params["secret"] = secret
        with ConnectHandler(**params) as conn:
            hostname = conn.find_prompt().strip("#> ") or host
            for source, command in COMMANDS.items():
                output = conn.send_command(command, read_timeout=120)
                target = os.path.join(out_dir, f"{hostname}.{source}.txt")
                with open(target, "w", encoding="utf-8") as fh:
                    fh.write(output)
                written.append(target)
    return written
