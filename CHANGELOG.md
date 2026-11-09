# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-11-09

E911 Reconciliation Engine: continuous, independent verification that every phone's
911 location matches the hospital's physical records.

### Added
- `python/e911/` reconciliation engine comparing four sources on every run: the
  location database, switch discovery (CDP, LLDP, MAC tables), Cisco Emergency
  Responder exports and the CUCM inventory.
- Fifteen finding types, from phones on unmapped ports and CER ERL mismatches to stale
  CER tracking and unmapped analog stations, each with a severity and a recommended fix.
- Dispatchable-location accuracy score per run.
- Append-only SQLite audit history with input SHA-256 hashes and new/resolved findings
  between runs.
- CER client for the export API (`switchport/info`, `unlocatedphones/info`,
  `discoverystatus`) and the Configuration API (`PUT /cerappservices/service/switchport/`).
- `e911` command line: `validate`, `collect`, `reconcile`, `history`, `push`.
- `ansible/playbooks/e911-reconcile.yml` for scheduled collection and reconciliation.
- `ansible/requirements.yml` for the Ansible collections the playbooks use.
- Synthetic sample hospital dataset in `samples/e911/`.
- Test suite (60 tests) and GitHub Actions CI (lint, tests on Python 3.10, 3.11 and 3.12, playbook
  syntax checks).
- `pyproject.toml` packaging with an `e911` console script.
- `docs/methodology/e911-reconciliation-engine.md`, `CITATION.cff`, this changelog.

### Changed
- Location database template v2: `jack_id`, `patch_panel`, `switch_ip`, `port_id`,
  civic address and verification columns. v1 files remain supported.
- `e911-location-update.yml` uses the CER 14+ Configuration API with a dedicated CER
  API account, accepts the engine's `remediation.csv`, waits for CER discovery to
  complete, detects partial failures and writes a change log. Uses
  `community.general.read_csv`.
- `E911LocationManager` in `python/cucm_axl/phone_operations.py` runs on the engine's
  CER client and validation.
- Example inventory adds CER API credentials and a `voice_switches` group.
- `.gitignore` keeps secrets, run outputs, real location data and audit databases out
  of version control.

## [1.0.0] - 2026-06-15

### Added
- E911 / RAY BAUM's Act compliance checklist and Clinical Airlock Framework methodology.
- Healthcare UC reference architecture.
- CUCM endpoint inventory over AXL (`reporting/endpoint_inventory.py`).
- E911 dispatchable-location compliance report (`reporting/compliance_report.py`).
- Bulk ERL update playbook and location database template (v1).
- AXL phone-operation helpers.

[0.2.0]: https://github.com/freddyantony/healthcare-uc-automation/compare/v1.0.0...v0.2.0
[1.0.0]: https://github.com/freddyantony/healthcare-uc-automation/releases/tag/v1.0.0
