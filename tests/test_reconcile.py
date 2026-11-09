from collections import Counter

from conftest import TODAY
from e911.location_db import load_location_db
from e911.models import PortObservation
from e911.reconcile import reconcile, remediation_by_switch


def _codes(result):
    return Counter(f.code for f in result.findings)


def test_every_finding_type_on_sample(sample_result):
    assert _codes(sample_result) == {
        "PORT_ERL_MISMATCH": 2,
        "UNMAPPED_PORT": 2,
        "ANALOG_UNMAPPED": 1,
        "CER_UNLOCATED": 1,
        "DEVICE_MOVED": 1,
        "DUPLICATE_PORT_MAPPING": 1,
        "INCOMPLETE_LOCATION": 1,
        "PORT_NOT_IN_CER": 1,
        "SWITCH_NOT_IN_CER": 1,
        "CER_TRACKING_STALE": 1,
        "DEVICE_NOT_OBSERVED": 1,
        "MISSING_CIVIC_ADDRESS": 1,
        "STALE_VERIFICATION": 1,
    }


def test_accuracy_score(sample_result):
    stats = sample_result.stats
    assert stats["phones_observed"] == 9
    assert stats["phones_verified"] == 4
    assert stats["accuracy_pct"] == 44.4
    assert stats["switches_surveyed"] == 3
    assert stats["inventory_soft_or_wireless"] == 2
    assert stats["inventory_analog"] == 2


def test_findings_sorted_by_severity(sample_result):
    ranks = [f.rank for f in sample_result.findings]
    assert ranks == sorted(ranks, reverse=True)
    assert sample_result.findings[0].severity == "critical"


def test_live_mismatch_is_critical_latent_is_high(sample_result):
    mismatches = {f.port: f.severity for f in sample_result.findings
                  if f.code == "PORT_ERL_MISMATCH"}
    assert mismatches == {"Gi1/0/14": "critical", "Gi1/0/25": "high"}


def test_device_moved_to_unmapped_port(sample_result):
    moved = next(f for f in sample_result.findings if f.code == "DEVICE_MOVED")
    assert moved.device_name == "SEP001122334466"
    assert moved.expected == "sw-main-2f-idf3 Gi1/0/13"
    assert moved.observed == "sw-main-2f-idf3 Gi1/0/20"


def test_cer_blind_spot_switch(sample_result):
    blind = next(f for f in sample_result.findings if f.code == "SWITCH_NOT_IN_CER")
    assert blind.switch_name == "sw-annex-1f-idf1"


def test_remediation_rows(sample_result):
    rows = {(r["switch_ip"], r["port_id"]): r for r in sample_result.remediation}
    assert set(rows) == {("192.0.2.11", "1/0/14"), ("192.0.2.11", "1/0/15"),
                         ("192.0.2.12", "1/0/25")}
    assert rows[("192.0.2.11", "1/0/14")]["current_erl"] == "ERL_MAIN_3F_OR"
    grouped = remediation_by_switch(sample_result.remediation)
    assert grouped[("192.0.2.11", "ERL_MAIN_2F_ED")] == ["1/0/14", "1/0/15"]
    assert grouped[("192.0.2.12", "ERL_MAIN_3F_OR")] == ["1/0/25"]


def test_location_db_only_run(samples):
    result = reconcile(load_location_db(samples["locations"]), today=TODAY)
    assert result.stats["phones_observed"] == 0
    assert result.stats["accuracy_pct"] is None
    assert "UNMAPPED_PORT" not in _codes(result)


def test_clean_network_scores_100(tmp_path):
    path = tmp_path / "loc.csv"
    path.write_text("building,floor,room,switch_name,switch_port,erl_name\n"
                    "Main,1,101,sw1,Gi1/0/1,ERL_1\n")
    obs = [PortObservation(switch_name="SW1.example.org", port="GigabitEthernet1/0/1",
                           source="cdp", device_id="SEP001122334455", is_phone=True)]
    result = reconcile(load_location_db(str(path)), obs, today=TODAY)
    assert result.findings == []
    assert result.stats["accuracy_pct"] == 100.0


def test_ip_only_cer_switch_resolves_to_hostname(tmp_path):
    from e911.models import CerPort

    path = tmp_path / "loc.csv"
    path.write_text("building,floor,room,switch_name,switch_ip,switch_port,erl_name\n"
                    "Main,1,101,sw1,192.0.2.50,Gi1/0/1,ERL_1\n")
    cer = [CerPort(switch_ip="192.0.2.50", if_name="Gi1/0/1", erl_name="ERL_1",
                   port_identifier="1/0/1")]
    result = reconcile(load_location_db(str(path)), [], cer, today=TODAY)
    assert result.findings == []
