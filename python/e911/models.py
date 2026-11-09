"""Data records exchanged between the engine's stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .normalize import mac_from_device_name, make_port_key, normalize_mac, normalize_port

# Severity ranks, highest first. "critical" means a 911 call placed right now
# could carry a wrong or missing dispatchable location.
SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}

DISPATCHABLE_FIELDS = ("building", "floor", "room")
CIVIC_FIELDS = ("street", "city", "state", "zip")


@dataclass
class LocationRecord:
    """One row of the location database: a physical jack and where it is."""

    building: str = ""
    floor: str = ""
    room: str = ""
    jack_id: str = ""
    patch_panel: str = ""
    switch_name: str = ""
    switch_ip: str = ""
    switch_port: str = ""
    port_id: str = ""
    erl_name: str = ""
    elin: str = ""
    street: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    device_name: str = ""
    last_verified: str = ""
    verified_by: str = ""
    row_number: int = 0

    @property
    def port_key(self):
        return make_port_key(self.switch_name or self.switch_ip, self.switch_port)

    @property
    def dispatchable(self) -> bool:
        return all((getattr(self, f) or "").strip() for f in DISPATCHABLE_FIELDS)

    @property
    def missing_dispatchable(self):
        return [f for f in DISPATCHABLE_FIELDS if not (getattr(self, f) or "").strip()]

    @property
    def location_label(self) -> str:
        parts = [self.building, f"Floor {self.floor}" if self.floor else "", self.room]
        label = " / ".join(p for p in parts if p)
        if self.jack_id:
            label = f"{label} (jack {self.jack_id})" if label else f"jack {self.jack_id}"
        return label or "(no location)"


@dataclass
class PortObservation:
    """A device the switch reports on one of its ports."""

    switch_name: str
    port: str
    source: str  # "cdp", "lldp" or "mac"
    device_id: str = ""
    mac: Optional[str] = None
    ip: str = ""
    platform: str = ""
    is_phone: bool = False

    def __post_init__(self):
        self.mac = normalize_mac(self.mac) or mac_from_device_name(self.device_id)

    @property
    def port_key(self):
        return make_port_key(self.switch_name, self.port)


@dataclass
class CerPort:
    """One switch port as exported by Cisco Emergency Responder."""

    switch_host: str = ""
    switch_ip: str = ""
    if_name: str = ""
    port_identifier: str = ""
    port_name: str = ""
    port_description: str = ""
    erl_name: str = ""
    location: str = ""
    phone_mac: str = ""
    phone_extension: str = ""
    phone_ip: str = ""
    phone_type: str = ""

    @property
    def interface(self) -> str:
        return self.if_name or self.port_name


@dataclass
class UnlocatedPhone:
    """A phone CER could not place, from its unlocated-phones export."""

    mac: str = ""
    ip: str = ""
    extension: str = ""
    assigned_erl: str = ""
    effective_erl: str = ""
    erl_used_info: str = ""
    server_group: str = ""


@dataclass
class InventoryDevice:
    """A device configured in CUCM (from endpoint_inventory.py)."""

    device_name: str
    description: str = ""
    model: str = ""
    device_pool: str = ""

    @property
    def mac(self) -> Optional[str]:
        return mac_from_device_name(self.device_name)


@dataclass
class Finding:
    """One disagreement or data-quality problem found by a run."""

    code: str
    severity: str
    message: str
    switch_name: str = ""
    port: str = ""
    device_name: str = ""
    jack_id: str = ""
    expected: str = ""
    observed: str = ""
    recommendation: str = ""
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        self.port = normalize_port(self.port)

    @property
    def fingerprint(self) -> str:
        """Stable identity used to compare runs (new vs resolved)."""
        return "|".join([
            self.code,
            (self.switch_name or "").lower(),
            (self.port or "").lower(),
            (self.device_name or "").upper(),
            (self.jack_id or "").lower(),
        ])

    @property
    def rank(self) -> int:
        return SEVERITY_ORDER.get(self.severity, 0)
