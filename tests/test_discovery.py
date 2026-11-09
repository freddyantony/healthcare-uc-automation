import os

from e911.discovery import (load_neighbor_dir, merge_observations, parse_cdp_neighbors_detail,
                            parse_lldp_neighbors_detail, parse_mac_address_table)


def _read(samples, name):
    with open(os.path.join(samples["neighbors"], name), encoding="utf-8") as fh:
        return fh.read()


def test_cdp_finds_phones_and_uplink(samples):
    obs = parse_cdp_neighbors_detail(_read(samples, "sw-main-2f-idf3.cdp.txt"), "sw-main-2f-idf3")
    by_port = {o.port: o for o in obs}
    assert set(by_port) == {"Gi1/0/12", "Gi1/0/20", "Gi1/0/18", "Te1/1/1"}
    phone = by_port["Gi1/0/12"]
    assert phone.is_phone and phone.mac == "001122334455" and phone.ip == "192.0.2.101"
    assert "8865" in phone.platform
    assert not by_port["Te1/1/1"].is_phone


def test_lldp_phone_identity(samples):
    obs = parse_lldp_neighbors_detail(_read(samples, "sw-main-2f-idf3.lldp.txt"), "sw")
    assert len(obs) == 1
    phone = obs[0]
    assert phone.port == "Gi1/0/14" and phone.device_id == "SEP001122334499"
    assert phone.mac == "001122334499" and phone.is_phone


def test_mac_table_skips_uplinks(samples):
    obs = parse_mac_address_table(_read(samples, "sw-main-2f-idf3.mac.txt"), "sw")
    ports = {o.port for o in obs}
    assert "Te1/1/1" not in ports  # five MACs -> uplink
    assert "Gi1/0/16" in ports     # ATA with no CDP/LLDP
    assert {o.mac for o in obs if o.port == "Gi1/0/12"} == {"001122334455", "7c2e0d110001"}


def test_merge_prefers_cdp_and_keeps_one_per_device(samples):
    text_cdp = _read(samples, "sw-main-2f-idf3.cdp.txt")
    text_mac = _read(samples, "sw-main-2f-idf3.mac.txt")
    merged = merge_observations(parse_cdp_neighbors_detail(text_cdp, "sw")
                                + parse_mac_address_table(text_mac, "sw"))
    gi12 = [o for o in merged if o.port == "Gi1/0/12"]
    assert len(gi12) == 2  # phone + PC behind it
    phone = next(o for o in gi12 if o.mac == "001122334455")
    assert phone.source == "cdp"


def test_load_neighbor_dir(samples):
    obs = load_neighbor_dir(samples["neighbors"])
    phones = {o.device_id for o in obs if o.is_phone}
    assert {"SEP001122334455", "SEP001122334499", "SEP001122334477",
            "SEP001122334488", "SEP0011223344AA"} <= phones
    assert {o.switch_name for o in obs} == {"sw-main-2f-idf3", "sw-main-3f-idf1",
                                            "sw-annex-1f-idf1"}
