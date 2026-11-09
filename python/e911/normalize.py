"""
Name normalization shared by every source.

Switches, CER and CUCM each spell the same thing differently:
``GigabitEthernet1/0/12`` vs ``Gi1/0/12``, ``sw-main-2f.example.org`` vs
``SW-MAIN-2F``, ``0011.2233.4455`` vs ``00:11:22:33:44:55``. Every comparison in
the engine goes through these helpers so a spelling difference is never
reported as location drift.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Optional, Tuple

# Interface-type aliases (lower-case) -> canonical short prefix.
_INTERFACE_ALIASES = {
    "gigabitethernet": "Gi", "gige": "Gi", "gig": "Gi", "gi": "Gi",
    "tengigabitethernet": "Te", "tengige": "Te", "ten": "Te", "te": "Te",
    "twogigabitethernet": "Tw", "two": "Tw", "tw": "Tw",
    "twentyfivegige": "Twe", "twe": "Twe",
    "fivegigabitethernet": "Fi", "fi": "Fi",
    "fastethernet": "Fa", "fa": "Fa",
    "fortygigabitethernet": "Fo", "fo": "Fo",
    "hundredgige": "Hu", "hu": "Hu",
    "appgigabitethernet": "Ap", "ap": "Ap",
    "ethernet": "Eth", "eth": "Eth", "et": "Eth",
    "port-channel": "Po", "portchannel": "Po", "po": "Po",
}

_INTERFACE_RE = re.compile(r"^\s*([A-Za-z][A-Za-z\-]*)\s*([0-9].*)$")

# CUCM device-name prefixes that embed the device MAC address.
_MAC_NAME_RE = re.compile(r"^(SEP|ATA|BAT)([0-9A-F]{12})$", re.IGNORECASE)

# SCCP voice-gateway analog ports: AN + gateway MAC + 3-digit port index.
_ANALOG_NAME_RE = re.compile(r"^AN[0-9A-F]{12}\d{3}$", re.IGNORECASE)


def normalize_port(port: Optional[str]) -> str:
    """Return the canonical short interface name, e.g. ``Gi1/0/12``.

    Unknown prefixes are kept as written so nothing is silently merged.
    """
    if not port:
        return ""
    text = port.strip()
    match = _INTERFACE_RE.match(text)
    if not match:
        return text
    prefix, number = match.group(1), match.group(2).strip()
    canonical = _INTERFACE_ALIASES.get(prefix.lower(), prefix)
    return f"{canonical}{number}"


def port_compare_key(port: Optional[str]) -> str:
    """Case-insensitive comparison key for an interface name."""
    return normalize_port(port).lower()


def is_ip_address(value: Optional[str]) -> bool:
    if not value:
        return False
    try:
        ipaddress.ip_address(value.strip())
        return True
    except ValueError:
        return False


def normalize_switch(name: Optional[str]) -> str:
    """Lower-case a switch hostname and drop its domain suffix.

    IP addresses are returned unchanged.
    """
    if not name:
        return ""
    text = name.strip()
    if is_ip_address(text):
        return text
    return text.split(".", 1)[0].lower()


def normalize_mac(value: Optional[str]) -> Optional[str]:
    """Return a 12-digit lower-case MAC, or None if the value is not a MAC."""
    if not value:
        return None
    digits = re.sub(r"[^0-9A-Fa-f]", "", value)
    if len(digits) != 12:
        return None
    return digits.lower()


def mac_from_device_name(device_name: Optional[str]) -> Optional[str]:
    """Extract the MAC embedded in a CUCM device name (``SEP``/``ATA``/``BAT``)."""
    if not device_name:
        return None
    match = _MAC_NAME_RE.match(device_name.strip())
    return match.group(2).lower() if match else None


def is_analog_device_name(device_name: Optional[str]) -> bool:
    return bool(device_name and _ANALOG_NAME_RE.match(device_name.strip()))


def device_name_from_mac(mac: str, prefix: str = "SEP") -> str:
    return f"{prefix}{mac.upper()}"


PortKey = Tuple[str, str]


def make_port_key(switch: str, port: str) -> PortKey:
    """Key used to join every source on (switch, port)."""
    return normalize_switch(switch), port_compare_key(port)
