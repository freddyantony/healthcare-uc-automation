import os
import sys

from conftest import ROOT, TODAY  # noqa: F401
from e911.cer import load_export_file

sys.path.insert(0, os.path.join(ROOT, "python", "cucm_axl"))
from phone_operations import E911LocationManager  # noqa: E402


class StubClient:
    def __init__(self, samples):
        self.ports = load_export_file(samples["cer_switchports"], "switchport")
        self.unlocated = load_export_file(samples["cer_unlocated"], "unlocated")
        self.updates = []

    def export_switchports(self):
        return self.ports

    def export_unlocated(self):
        return self.unlocated

    def discovery_complete(self):
        return True

    def update_switchport_erl(self, switch_ip, port_ids, erl_name):
        self.updates.append((switch_ip, list(port_ids), erl_name))
        return {"status": "Success"}


def test_update_resolves_hostname_and_interface(samples):
    client = StubClient(samples)
    manager = E911LocationManager("cer-pub.example.org", client=client)
    assert manager.update_switch_port_location("sw-main-2f-idf3", "Gi1/0/14", "ERL_MAIN_2F_ED")
    assert client.updates == [("192.0.2.11", ["1/0/14"], "ERL_MAIN_2F_ED")]


def test_bulk_update_dry_run_then_apply(samples):
    client = StubClient(samples)
    manager = E911LocationManager("cer-pub.example.org", client=client)
    plan = manager.bulk_update_locations_from_csv(samples["locations"])
    # 13 rows: 1 missing room, 1 analog without a switch port -> skipped
    assert plan == {"updated": 0, "failed": 0, "skipped": 2, "planned": 11}
    assert client.updates == []
    applied = manager.bulk_update_locations_from_csv(samples["locations"], apply=True)
    assert applied["updated"] == 11 and len(client.updates) == 11


def test_gap_report_combines_cer_and_location_db(samples):
    manager = E911LocationManager("cer-pub.example.org", client=StubClient(samples))
    gaps = manager.generate_location_gap_report(samples["locations"])
    sources = [g["source"] for g in gaps]
    assert sources.count("CER unlocated phones") == 1
    assert sources.count("location database") >= 3
