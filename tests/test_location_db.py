from collections import Counter

from conftest import TODAY
from e911.location_db import load_location_db, validate_location_db


def test_loads_v2_sample(samples):
    db = load_location_db(samples["locations"])
    assert db.schema_version == 2
    assert db.has_civic_columns and db.has_verification_columns
    assert len(db.records) == 13
    first = db.records[0]
    assert first.jack_id == "2F-A01" and first.port_id == "1/0/12"
    assert first.dispatchable


def test_v2_template_is_clean(samples):
    db = load_location_db(samples["template"])
    assert db.schema_version == 2
    assert validate_location_db(db, today=TODAY) == []


def test_v1_file_still_loads_and_skips_v2_checks(tmp_path):
    v1 = tmp_path / "v1.csv"
    v1.write_text(
        "device_name,building,floor,room,switch_name,switch_port,erl_name,elin\n"
        "SEP001122334455,Main Hospital,2,ED-Bay-1,sw1,GigabitEthernet1/0/12,ERL_ED,7045550101\n")
    db = load_location_db(str(v1))
    assert db.schema_version == 1
    assert not db.has_civic_columns
    assert validate_location_db(db, today=TODAY) == []


def test_sample_data_quality_findings(samples):
    findings = validate_location_db(load_location_db(samples["locations"]), today=TODAY)
    codes = Counter(f.code for f in findings)
    assert codes == {
        "INCOMPLETE_LOCATION": 1,      # row 6: room missing
        "DUPLICATE_PORT_MAPPING": 1,   # Gi1/0/26 mapped to OR-5 and OR-6
        "MISSING_CIVIC_ADDRESS": 1,    # Annex row has no street
        "STALE_VERIFICATION": 1,       # ED-Triage last verified 2024
    }


def test_analog_record_needs_no_switch_port(samples):
    findings = validate_location_db(load_location_db(samples["locations"]), today=TODAY)
    assert not any(f.code == "MISSING_SWITCH_PORT" for f in findings)


def test_missing_switch_port_flagged(tmp_path):
    path = tmp_path / "loc.csv"
    path.write_text("building,floor,room,switch_name,switch_port,erl_name\n"
                    "Main,1,101,,,ERL_1\n")
    findings = validate_location_db(load_location_db(str(path)), today=TODAY)
    assert [f.code for f in findings] == ["MISSING_SWITCH_PORT"]


def test_duplicate_jack(tmp_path):
    path = tmp_path / "loc.csv"
    path.write_text("building,floor,room,jack_id,switch_name,switch_port,erl_name\n"
                    "Main,1,101,J1,sw1,Gi1/0/1,ERL_1\n"
                    "Main,1,101,J1,sw1,Gi1/0/2,ERL_1\n")
    findings = validate_location_db(load_location_db(str(path)), today=TODAY)
    assert [f.code for f in findings] == ["DUPLICATE_JACK"]
