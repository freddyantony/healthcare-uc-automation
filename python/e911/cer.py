"""
Cisco Emergency Responder (CER) client.

Two documented CER interfaces are used:

* **Export API** (read-only, XML) - ``GET /cerappservices/export/...``
  ``discoverystatus``, ``switchport/info`` and ``unlocatedphones/info``. CER
  issues a ``JSESSIONID`` cookie on an unauthenticated first request; later
  requests send Basic auth plus that cookie.
* **Configuration API** (CER 14+, Publisher only) -
  ``PUT /cerappservices/service/switchport/`` assigns an ERL to switch ports.

Exports can also be parsed from saved XML files, so a reconciliation run does
not need live CER access.

References:
https://developer.cisco.com/site/cer/documents/api-reference/
https://developer.cisco.com/docs/cer-config-api/latest/erl-management/
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

try:  # Prefer the hardened parser when it is installed.
    from defusedxml import ElementTree as ET  # type: ignore
except ImportError:  # pragma: no cover
    import xml.etree.ElementTree as ET  # nosec - CER exports are trusted input

from .models import CerPort, UnlocatedPhone

EXPORT_BASE = "/cerappservices/export"
SWITCHPORT_CONFIG_PATH = "/cerappservices/service/switchport/"


class CERError(RuntimeError):
    """CER returned an error or an unusable response."""


def _child(element, tag: str) -> str:
    """Text of a direct child, matching the tag name case-insensitively."""
    wanted = tag.lower()
    for child in list(element):
        if child.tag.split("}")[-1].lower() == wanted:
            return (child.text or "").strip()
    return ""


def _children(element, tag: str):
    wanted = tag.lower()
    return [c for c in list(element) if c.tag.split("}")[-1].lower() == wanted]


def parse_status(xml_text: str) -> str:
    root = ET.fromstring(xml_text)
    if root.tag.split("}")[-1].lower() == "status":
        return (root.text or "").strip()
    status = _child(root, "status")
    return status or (root.text or "").strip()


def parse_switchport_export(xml_text: str) -> Tuple[str, List[CerPort]]:
    """Parse ``/switchport/info``: SwitchPort > switchip* > portDetails*."""
    root = ET.fromstring(xml_text)
    status = _child(root, "status")
    ports: List[CerPort] = []
    for switch in _children(root, "switchip"):
        host = _child(switch, "SwitchHostName")
        ip = _child(switch, "SwitchIPAddress")
        for detail in _children(switch, "portDetails"):
            ports.append(CerPort(
                switch_host=host,
                switch_ip=ip,
                if_name=_child(detail, "IfName"),
                port_identifier=_child(detail, "PortIdentifier"),
                port_name=_child(detail, "PortName"),
                port_description=_child(detail, "PortDescription"),
                erl_name=_child(detail, "ERLName"),
                location=_child(detail, "Location"),
                phone_mac=_child(detail, "PhoneMACAddress"),
                phone_extension=_child(detail, "PhoneExtension"),
                phone_ip=_child(detail, "PhoneIPAddress"),
                phone_type=_child(detail, "PhoneType"),
            ))
    return status, ports


def parse_unlocated_export(xml_text: str) -> Tuple[str, List[UnlocatedPhone]]:
    """Parse ``/unlocatedphones/info``: UnlocatedDetails > PhoneDetails*."""
    root = ET.fromstring(xml_text)
    status = _child(root, "status")
    phones = [UnlocatedPhone(
        mac=_child(d, "PhoneMACAddr"),
        ip=_child(d, "PhoneIPAddr"),
        extension=_child(d, "PhoneExt"),
        assigned_erl=_child(d, "AssignedERL"),
        effective_erl=_child(d, "EffectiveERL"),
        erl_used_info=_child(d, "ERLUsedInfo"),
        server_group=_child(d, "CerServerGroup"),
    ) for d in _children(root, "PhoneDetails")]
    return status, phones


def _check_export_status(status: str) -> None:
    if "publisher is active" in status.lower():
        raise CERError(f"CER refused the export: {status} Point the client at the Publisher.")


class CERClient:
    """Minimal CER client for the export and Configuration APIs."""

    def __init__(self, host: str, username: str, password: str, verify_ssl: bool = True,
                 timeout: int = 30, session=None):
        import requests  # local import keeps offline parsing dependency-free

        self.base = host if host.startswith("http") else f"https://{host}"
        self.auth = (username, password)
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.verify = verify_ssl
        self._primed = False

    # -- export API -------------------------------------------------------
    def _prime_session(self) -> None:
        """First request without credentials: CER answers 401 and sets JSESSIONID."""
        if not self._primed:
            self.session.get(f"{self.base}{EXPORT_BASE}/discoverystatus",
                             headers={"Accept": "text/xml"}, timeout=self.timeout)
            self._primed = True

    def _get_export(self, path: str) -> str:
        self._prime_session()
        response = self.session.get(f"{self.base}{EXPORT_BASE}/{path}", auth=self.auth,
                                    headers={"Accept": "text/xml"}, timeout=self.timeout)
        if response.status_code == 401:
            raise CERError("CER rejected the credentials (HTTP 401).")
        if response.status_code >= 400:
            raise CERError(f"CER export {path} failed: HTTP {response.status_code}")
        return response.text

    def discovery_status(self) -> str:
        return parse_status(self._get_export("discoverystatus"))

    def discovery_complete(self) -> bool:
        return "discovery is complete" in self.discovery_status().lower()

    def export_switchports(self) -> List[CerPort]:
        status, ports = parse_switchport_export(self._get_export("switchport/info"))
        _check_export_status(status)
        return ports

    def export_unlocated(self) -> List[UnlocatedPhone]:
        status, phones = parse_unlocated_export(self._get_export("unlocatedphones/info"))
        _check_export_status(status)
        return phones

    # -- configuration API ------------------------------------------------
    def update_switchport_erl(self, switch_ip: str, port_ids: Iterable[str],
                              erl_name: str) -> dict:
        """Assign ``erl_name`` to the given ports (CER PortIdentifier values)."""
        body = {"IPaddress": switch_ip, "Allports": "false", "ERLName": erl_name,
                "Ports": list(port_ids)}
        response = self.session.put(
            f"{self.base}{SWITCHPORT_CONFIG_PATH}", json=body, auth=self.auth,
            headers={"Accept": "application/json"}, timeout=self.timeout)
        try:
            payload = response.json()
        except ValueError:
            payload = {"status": f"HTTP {response.status_code}", "message": response.text[:500]}
        if response.status_code >= 400 or "fail" in str(payload.get("status", "")).lower():
            raise CERError(f"ERL update on {switch_ip} failed: {payload}")
        return payload


def load_export_file(path: str, kind: str):
    """Parse a saved CER export. ``kind`` is ``switchport`` or ``unlocated``."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    parser = parse_switchport_export if kind == "switchport" else parse_unlocated_export
    status, items = parser(text)
    _check_export_status(status)
    return items


def resolve_port_identifier(ports: List[CerPort], switch: str, interface: str) -> Optional[CerPort]:
    """Find the CER port for a switch (hostname or IP) and interface name."""
    from .normalize import make_port_key, normalize_switch

    target = make_port_key(switch, interface)
    for port in ports:
        for name in (port.switch_host, port.switch_ip):
            if name and make_port_key(normalize_switch(name), port.interface) == target:
                return port
    return None
