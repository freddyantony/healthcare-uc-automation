# Healthcare Unified Communications Automation Framework

[![CI](https://github.com/freddyantony/healthcare-uc-automation/actions/workflows/ci.yml/badge.svg)](https://github.com/freddyantony/healthcare-uc-automation/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Ansible 2.9+](https://img.shields.io/badge/ansible-2.9+-red.svg)](https://www.ansible.com/)

## Overview

This repository contains automation scripts and methodology documentation for
**healthcare unified communications infrastructure management**. The tools and
frameworks are intended for open use by the broader healthcare IT community —
particularly resource-constrained rural and Critical Access Hospitals that need
RAY BAUM's Act 911 compliance and safe legacy-to-cloud migration without
proprietary commercial tooling.

**Author:** Freddy Antony
**Focus Areas:**
- 911 / E911 compliance (RAY BAUM's Act / Kari's Law) via deterministic Layer 2 mapping
  and continuous reconciliation against the network and Cisco Emergency Responder
- Staged legacy-to-cloud migration (the Clinical Airlock Framework)
- Cisco UC provisioning, inventory, and compliance reporting (AXL / Ansible)

**What's new in v0.2.0:** the [E911 Reconciliation Engine](docs/methodology/e911-reconciliation-engine.md),
which verifies every night that each phone's 911 location matches the hospital's
physical records. See the [changelog](CHANGELOG.md).

---

## Repository Structure

```
healthcare-uc-automation/
├── README.md · CHANGELOG.md · CITATION.cff · LICENSE
├── pyproject.toml · requirements.txt
├── .github/workflows/ci.yml                   # Lint, tests, playbook syntax checks
├── clinical-airlock-gatekeeper/               # Clinical Airlock v0.1 prototype
│   ├── README.md                              # Overview and usage instructions
│   ├── gatekeeper.py                          # Migration readiness gate evaluation
│   ├── dependencies.csv                       # Synthetic clinical dependencies
│   ├── test_results.csv                       # Synthetic test results
│   └── test_gatekeeper.py                     # Automated unit tests
├── docs/
│   ├── methodology/
│   │   ├── e911-reconciliation-engine.md      # How the engine works and complements CER
│   │   ├── e911-compliance-checklist.md       # RAY BAUM's Act implementation guide
│   │   └── clinical-airlock-framework.md      # Staged cloud-migration methodology
│   └── architecture/
│       └── healthcare-uc-reference-architecture.md
├── ansible/
│   ├── requirements.yml                       # Collections used by the playbooks
│   ├── playbooks/
│   │   ├── e911-reconcile.yml                 # Nightly collection + reconciliation
│   │   └── e911-location-update.yml           # CER Configuration API ERL updates
│   └── inventory/
│       └── inventory.yml.example              # Sanitized example inventory
├── python/
│   ├── e911/                                  # E911 reconciliation engine (v0.2.0)
│   │   ├── location_db.py                     # Location database v2 + data-quality checks
│   │   ├── discovery.py                       # CDP / LLDP / MAC-table discovery
│   │   ├── cer.py                             # CER export + Configuration API client
│   │   ├── inventory.py                       # CUCM inventory loader
│   │   ├── reconcile.py                       # Cross-source drift detection + accuracy score
│   │   ├── audit.py                           # Append-only audit history (SQLite)
│   │   ├── report.py                          # CSV / JSON / Markdown outputs
│   │   └── cli.py                             # `e911` command line
│   ├── cucm_axl/
│   │   └── phone_operations.py                # CUCM AXL phone & E911 operations
│   └── reporting/
│       ├── endpoint_inventory.py              # Live AXL inventory → CSV
│       └── compliance_report.py               # E911 dispatchable-location report
├── samples/e911/                              # Synthetic sample hospital (no real data)
├── templates/
│   └── e911-location-database-template.csv    # Location database template (v2)
└── tests/                                     # pytest suite
```

---

## Key Components

### 1. E911 Reconciliation Engine (v0.2.0)

Cisco Emergency Responder (CER) tracks which switch port a phone is on and sends the
ERL assigned to that port. Whether that ERL is the right room depends on cable-plant
data CER cannot see. The engine compares four independent sources on every run:

| Source | What it says |
| --- | --- |
| Location database v2 | Which jack and room each switch port reaches, and the civic address |
| Switch discovery (CDP, LLDP, MAC tables) | Which phone is plugged into which port right now |
| CER exports | Which ERL CER will send for each port; which phones it cannot place |
| CUCM inventory (AXL) | Every phone the call-control system knows about |

It reports 15 kinds of disagreement (phones on unmapped ports, CER ERL mismatches,
switches CER is not tracking, device moves, stale CER tracking, unmapped analog
stations and more), scores **dispatchable-location accuracy**, keeps an **append-only
audit history**, and writes a `remediation.csv` that can be applied to CER through its
Configuration API. Details: [E911 Reconciliation Engine](docs/methodology/e911-reconciliation-engine.md).

### 2. E911 / RAY BAUM's Act Compliance Tooling

- [E911 Compliance Checklist](docs/methodology/e911-compliance-checklist.md) — implementation guide
- `ansible/playbooks/e911-location-update.yml` — CER Configuration API ERL updates
  (dry run by default, gated on CER discovery, change-logged)
- `python/reporting/compliance_report.py` — per-building dispatchable-location gap report

### 3. Clinical Airlock Framework (methodology)

A vendor-agnostic, three-phase staged methodology for migrating legacy PBX systems
to cloud UC without disrupting life-critical clinical services: **Forensic Discovery
Protocol → Clinical Sandbox Validation → Data-Driven Promotion Analysis.** See
[docs/methodology/clinical-airlock-framework.md](docs/methodology/clinical-airlock-framework.md).

### 4. Clinical Airlock Gatekeeper (v0.1 Prototype)

The [Clinical Airlock Gatekeeper](clinical-airlock-gatekeeper/README.md) is a Python-based reference implementation of the Clinical Airlock Framework's evidence-based migration readiness checks.

It demonstrates how healthcare UC engineers can assess migration readiness before advancing critical communication services from legacy PBX infrastructure to modern platforms.

**Current capabilities:**

- Track critical clinical communication dependencies, including emergency calling, paging, and nurse-station escalation.
- Evaluate required functional test results against documented migration checks.
- Detect failed tests, missing supporting evidence, and incomplete rollback plans.
- Produce a **HOLD / NO-GO** result when required safety checks are not satisfied.
- Return **READY FOR HUMAN REVIEW** when configured requirements are satisfied.
- Validate the Gatekeeper logic using automated Python unit tests.

**Current status:** v0.1 prototype using synthetic hospital data. The tool does not connect to production CUCM systems, execute migrations, or independently certify clinical safety. Final migration authorization remains the responsibility of designated clinical and technical stakeholders.

[View Source Code and Instructions](clinical-airlock-gatekeeper/README.md)

### 5. CUCM Inventory & Reporting (Python / AXL)

- `python/reporting/endpoint_inventory.py` — connects to CUCM over AXL, executes a live
  inventory query, and writes a CSV plus a model/device-pool summary.
- `python/cucm_axl/phone_operations.py` — phone-operation helpers and an
  `E911LocationManager` backed by the reconciliation engine.

---

## Getting Started

### Prerequisites

- Python 3.8+
- Ansible 2.9+ and the collections in `ansible/requirements.yml` (for the playbooks)
- For live runs: a CER 14+ API account, read-only SSH access to access switches, and a
  read-capable CUCM AXL application user
- For AXL scripts: the **AXL WSDL toolkit** for your CUCM version, downloaded from
  *CUCM Admin > Application > Plugins > Cisco CallManager AXL SOAP Toolkit*
  (Cisco licensing; not redistributed here)

### Installation

```bash
git clone https://github.com/freddyantony/healthcare-uc-automation.git
cd healthcare-uc-automation

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -e ".[dev]"         # e911 engine + tests; add [network] for live switch collection
pip install -r requirements.txt # AXL scripts
ansible-galaxy collection install -r ansible/requirements.yml
```

### Try the engine on the sample hospital

```bash
e911 reconcile \
    --locations samples/e911/locations.csv \
    --neighbors samples/e911/neighbors \
    --cer-switchports samples/e911/cer/switchport_export.xml \
    --cer-unlocated samples/e911/cer/unlocated_export.xml \
    --inventory samples/e911/cucm/endpoint_inventory.csv \
    --out reports --audit-db reports/e911_audit.db

e911 push --remediation reports/remediation.csv --cer-host cer-pub.example.org   # dry run
e911 history --audit-db reports/e911_audit.db
```

### Try Clinical Airlock Gatekeeper (Synthetic Demo)

The Clinical Airlock Gatekeeper runs locally using synthetic hospital data and requires Python 3.10 or newer. No CUCM connection or additional Python packages are required.

From the repository root:

```bash
python clinical-airlock-gatekeeper/gatekeeper.py
```

The demonstration includes a failed paging validation and is expected to produce:

```text
Decision: HOLD / NO-GO
```

Run the automated unit tests:

```bash
python -m unittest discover -s clinical-airlock-gatekeeper -p "test_*.py" -v
```

The test suite checks the Gatekeeper's readiness evaluation behavior.

See the [Gatekeeper README](clinical-airlock-gatekeeper/README.md) for additional information.

### Credentials

Credentials always come from the environment (or a local `.env`, which is git-ignored):

```bash
export CUCM_AXL_USER="axl-readonly"       CUCM_AXL_PASSWORD="********"
export CER_API_USER="e911-api"            CER_API_PASSWORD="********"
export SWITCH_USER="netops-ro"            SWITCH_PASSWORD="********"
```

### Example: live endpoint inventory

```bash
python python/reporting/endpoint_inventory.py \
    --host cucm-pub.example.org \
    --wsdl ./schema/12.5/AXLAPI.wsdl \
    --output endpoint_inventory.csv
```

### Tests

```bash
pytest
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [E911 Reconciliation Engine](docs/methodology/e911-reconciliation-engine.md) | Cross-source E911 verification, finding catalog, operating procedure |
| [E911 Compliance Checklist](docs/methodology/e911-compliance-checklist.md) | RAY BAUM's Act implementation guide for healthcare MLTS |
| [Clinical Airlock Framework](docs/methodology/clinical-airlock-framework.md) | Staged zero-downtime migration methodology for healthcare PBX-to-cloud transitions |
| [Clinical Airlock Gatekeeper](clinical-airlock-gatekeeper/README.md) | Python prototype for evidence-based clinical migration readiness checks, safety gates, and synthetic validation tests |
| [Reference Architecture](docs/architecture/healthcare-uc-reference-architecture.md) | High-availability healthcare UC design patterns |
| [Changelog](CHANGELOG.md) | Release history |

---

## Contributing

This repository documents healthcare communication infrastructure methodologies for
open use by the broader healthcare IT community — particularly resource-constrained
rural and Critical Access Hospitals seeking RAY BAUM's Act compliance without
proprietary commercial tooling.

Hospital IT teams, healthcare informatics researchers, and UC engineers are welcome to
open issues with questions, deployment feedback, or suggested improvements via the
GitHub Issues tab.

---

## Citation

If you use this work, please cite it using [CITATION.cff](CITATION.cff) (GitHub shows a
"Cite this repository" button).

---

## Disclaimer

- All code and documentation is sanitized to remove any Protected Health Information
  (PHI) or organization-specific sensitive data. Sample data is synthetic.
- Scripts are provided as reference implementations and should be tested in
  non-production environments before deployment.
- Users are responsible for compliance with their organization's security policies and
  HIPAA requirements.

---

## License

Licensed under the MIT License — see the [LICENSE](LICENSE) file.

---

## Author

**Freddy Antony**
Lead Collaboration Engineer | Healthcare Communication Infrastructure
IEEE Senior Member | CCNA Certified

- [Google Scholar](https://scholar.google.com/citations?user=I3CTJ7IAAAAJ&hl=en)
- [LinkedIn](https://www.linkedin.com/in/freddyantony)
