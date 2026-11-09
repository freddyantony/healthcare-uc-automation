import os
import sys
from datetime import date

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "samples", "e911")
sys.path.insert(0, os.path.join(ROOT, "python"))

# Fixed "today" so verification-age checks are deterministic.
TODAY = date(2026, 11, 9)


@pytest.fixture
def samples():
    return {
        "locations": os.path.join(SAMPLES, "locations.csv"),
        "neighbors": os.path.join(SAMPLES, "neighbors"),
        "cer_switchports": os.path.join(SAMPLES, "cer", "switchport_export.xml"),
        "cer_unlocated": os.path.join(SAMPLES, "cer", "unlocated_export.xml"),
        "inventory": os.path.join(SAMPLES, "cucm", "endpoint_inventory.csv"),
        "template": os.path.join(ROOT, "templates", "e911-location-database-template.csv"),
    }


@pytest.fixture
def sample_result(samples):
    from e911.cer import load_export_file
    from e911.discovery import load_neighbor_dir
    from e911.inventory import load_inventory
    from e911.location_db import load_location_db
    from e911.reconcile import reconcile

    return reconcile(
        load_location_db(samples["locations"]),
        load_neighbor_dir(samples["neighbors"]),
        load_export_file(samples["cer_switchports"], "switchport"),
        load_export_file(samples["cer_unlocated"], "unlocated"),
        load_inventory(samples["inventory"]),
        today=TODAY,
    )
