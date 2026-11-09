"""CUCM endpoint inventory (the CSV written by reporting/endpoint_inventory.py)."""

from __future__ import annotations

import csv
from typing import List

from .models import InventoryDevice
from .normalize import is_analog_device_name

_SOFT_PREFIXES = ("CSF", "BOT", "TCT", "TAB")
_WIRELESS_OR_SOFT_MODELS = ("jabber", "client services framework", "dual mode",
                            "wireless", "8821", "webex", "spark", "remote destination")


def load_inventory(path: str) -> List[InventoryDevice]:
    devices = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("device_name") or row.get("devicename") or "").strip()
            if name:
                devices.append(InventoryDevice(
                    device_name=name,
                    description=(row.get("description") or "").strip(),
                    model=(row.get("model") or "").strip(),
                    device_pool=(row.get("device_pool") or row.get("devicepool") or "").strip(),
                ))
    return devices


def is_soft_or_wireless(device: InventoryDevice) -> bool:
    """Located by CER through Wi-Fi access point or subnet, not a switch port."""
    if device.device_name.upper().startswith(_SOFT_PREFIXES):
        return True
    model = device.model.lower()
    return any(token in model for token in _WIRELESS_OR_SOFT_MODELS)


def is_analog(device: InventoryDevice) -> bool:
    """Analog station behind a voice gateway; never visible on an Ethernet port."""
    return is_analog_device_name(device.device_name) or "analog" in device.model.lower()
