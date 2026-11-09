import pytest

from e911.normalize import (is_analog_device_name, mac_from_device_name, make_port_key,
                            normalize_mac, normalize_port, normalize_switch)


@pytest.mark.parametrize("raw, expected", [
    ("GigabitEthernet1/0/12", "Gi1/0/12"),
    ("Gi1/0/12", "Gi1/0/12"),
    ("gi 1/0/12", "Gi1/0/12"),
    ("TenGigabitEthernet1/1/1", "Te1/1/1"),
    ("TwoGigabitEthernet2/0/7", "Tw2/0/7"),
    ("FastEthernet0/3", "Fa0/3"),
    ("Port-channel10", "Po10"),
    ("Weird9/9", "Weird9/9"),
    ("", ""),
])
def test_normalize_port(raw, expected):
    assert normalize_port(raw) == expected


def test_switch_names_drop_domain_and_case():
    assert normalize_switch("SW-MAIN-2F-IDF3.example.org") == "sw-main-2f-idf3"
    assert normalize_switch("192.0.2.11") == "192.0.2.11"


@pytest.mark.parametrize("raw", ["0011.2233.4455", "00:11:22:33:44:55", "001122334455",
                                 "00-11-22-33-44-55"])
def test_mac_formats_agree(raw):
    assert normalize_mac(raw) == "001122334455"


def test_mac_rejects_non_mac():
    assert normalize_mac("192.0.2.104") is None
    assert normalize_mac("") is None


def test_mac_from_device_name():
    assert mac_from_device_name("SEP0011223344AA") == "0011223344aa"
    assert mac_from_device_name("ATA00AABBCCDD01") == "00aabbccdd01"
    assert mac_from_device_name("CSFJSMITH") is None


def test_analog_names():
    assert is_analog_device_name("AN0A1B2C3D4E5F000")
    assert not is_analog_device_name("SEP0011223344AA")


def test_port_key_joins_spellings():
    assert make_port_key("SW-MAIN-2F-IDF3.example.org", "GigabitEthernet1/0/12") == \
        make_port_key("sw-main-2f-idf3", "Gi1/0/12")
