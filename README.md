# Healthcare Unified Communications Automation Framework

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
- Staged legacy-to-cloud migration (the Clinical Airlock Framework)
- 911 / E911 compliance (RAY BAUM's Act / Kari's Law) via deterministic Layer 2 mapping
- Cisco UC provisioning, inventory, and compliance reporting (AXL / Ansible)

---

## Repository Structure

```
healthcare-uc-automation/
├── README.md
├── LICENSE
├── requirements.txt
├── docs/
│   ├── methodology/
│   │   ├── clinical-airlock-framework.md      # Staged cloud-migration methodology
│   │   └── e911-compliance-checklist.md       # RAY BAUM's Act implementation guide
│   └── architecture/
│       └── healthcare-uc-reference-architecture.md
├── ansible/
│   ├── playbooks/
│   │   └── e911-location-update.yml           # Bulk ERL location updates
│   └── inventory/
│       └── inventory.yml.example              # Sanitized example inventory
├── python/
│   ├── cucm_axl/
│   │   ├── __init__.py
│   │   └── phone_operations.py                # CUCM AXL phone & E911 operations
│   └── reporting/
│       ├── __init__.py
│       ├── endpoint_inventory.py              # Live AXL inventory → CSV (functional)
│       └── compliance_report.py              # E911 dispatchable-location report (functional)
└── templates/
    └── e911-location-database-template.csv    # ERL location-mapping template
```

---

## Key Components

### 1. Clinical Airlock Framework (methodology)

A vendor-agnostic, three-phase staged methodology for migrating legacy PBX systems
to cloud UC without disrupting life-critical clinical services: **Forensic Discovery
Protocol → Clinical Sandbox Validation → Data-Driven Promotion Analysis.** See
[docs/methodology/clinical-airlock-framework.md](docs/methodology/clinical-airlock-framework.md).

### 2. E911 / RAY BAUM's Act Compliance

Implementation guidance plus working tooling for dispatchable-location accuracy using
deterministic Layer 2 switch-port mapping (room/bed-level), rather than probabilistic
IP-subnet mapping:

- [E911 Compliance Checklist](docs/methodology/e911-compliance-checklist.md) — implementation guide
- `ansible/playbooks/e911-location-update.yml` — bulk ERL update playbook (dry-run by default)
- `python/reporting/compliance_report.py` — generates a per-building dispatchable-location gap report

### 3. CUCM Inventory & Reporting (Python / AXL)

Functional Python utilities using the Cisco AXL SOAP API:

- `python/reporting/endpoint_inventory.py` — connects to CUCM over AXL, executes a live
  inventory query, and writes a CSV plus a model/device-pool summary.
- `python/cucm_axl/phone_operations.py` — phone-operation and E911 location helpers
  (reference implementation; sanitized of environment-specific detail).

---

## Getting Started

### Prerequisites

- Python 3.8+
- Ansible 2.9+ (for the playbooks)
- Access to a Cisco CUCM AXL API (read-capable application user)
- The **AXL WSDL toolkit** for your CUCM version, downloaded from
  *CUCM Admin > Application > Plugins > Cisco CallManager AXL SOAP Toolkit*
  (Cisco licensing; not redistributed here)

### Installation

```bash
git clone https://github.com/freddyantony/healthcare-uc-automation.git
cd healthcare-uc-automation

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Credentials

Set AXL credentials in the environment (or a local `.env`, which is git-ignored):

```bash
export CUCM_AXL_USER="axl-readonly"
export CUCM_AXL_PASSWORD="********"
```

### Example: live endpoint inventory

```bash
python python/reporting/endpoint_inventory.py \
    --host cucm-pub.example.org \
    --wsdl ./schema/12.5/AXLAPI.wsdl \
    --output endpoint_inventory.csv
```

### Example: E911 compliance report

```bash
python python/reporting/compliance_report.py \
    --inventory endpoint_inventory.csv \
    --locations templates/e911-location-database-template.csv \
    --output e911_compliance_report.csv
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Clinical Airlock Framework](docs/methodology/clinical-airlock-framework.md) | Staged zero-downtime migration methodology for healthcare PBX-to-cloud transitions |
| [E911 Compliance Checklist](docs/methodology/e911-compliance-checklist.md) | RAY BAUM's Act implementation guide for healthcare MLTS |
| [Reference Architecture](docs/architecture/healthcare-uc-reference-architecture.md) | High-availability healthcare UC design patterns |

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

## Disclaimer

- All code and documentation is sanitized to remove any Protected Health Information
  (PHI) or organization-specific sensitive data.
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
