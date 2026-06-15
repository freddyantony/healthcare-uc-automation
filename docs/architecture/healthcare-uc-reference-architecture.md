# Healthcare UC Reference Architecture

## Design Patterns for Enterprise Healthcare Unified Communications

**Author:** Freddy Simon Paul Antony
**Version:** 1.0
**Last Updated:** January 2026
**Environment:** Enterprise Healthcare (40,000+ endpoints, multi-state)

---

## Purpose

This document describes the high-availability reference architecture patterns used to
operate large-scale healthcare unified communications environments while meeting the
reliability, security, and life-safety requirements of clinical settings. It is
intended as a vendor-agnostic design reference for healthcare IT teams planning or
hardening their own UC infrastructure.

The patterns described here underpin the two methodology documents in this repository:
the [Clinical Airlock Framework](../methodology/clinical-airlock-framework.md) for
staged cloud migration, and the
[E911 Compliance Checklist](../methodology/e911-compliance-checklist.md) for RAY BAUM's
Act dispatchable-location accuracy.

---

## 1. Design Principles

1. **No single point of failure** in any life-critical voice path.
2. **Geographic redundancy** across data centers for disaster recovery.
3. **Local survivability** so a site keeps dialing during WAN loss.
4. **Isolation of contact-center load** from hospital voice services.
5. **Deterministic emergency location** (Layer 2 port mapping) over probabilistic
   IP-subnet mapping.
6. **Least-privilege, audited automation** for all bulk operations.

---

## 2. Cluster Topology

A large multi-site healthcare deployment separates foundation (hospital voice) from
contact-center workloads so that heavy SIP routing in the contact center cannot degrade
life-critical hospital telephony.

```
                         ┌───────────────────────────┐
                         │   Session Management Edge  │
                         │      (SME routing hub)     │
                         └─────────────┬─────────────┘
              ┌────────────────────────┼────────────────────────┐
              ▼                        ▼                         ▼
   ┌────────────────────┐  ┌────────────────────┐   ┌────────────────────┐
   │ Foundation Cluster │  │ Foundation Cluster │   │   Agent Cluster    │
   │   (Hospitals A-B)  │  │   (Hospitals C-D)  │   │ (Contact Center)   │
   │  CUCM Pub + Subs   │  │  CUCM Pub + Subs   │   │  CUCM + UCCE/CVP   │
   └─────────┬──────────┘  └─────────┬──────────┘   └─────────┬──────────┘
             ▼                       ▼                         ▼
      ┌─────────────┐         ┌─────────────┐           ┌─────────────┐
      │ SRST / local│         │ SRST / local│           │ Finesse     │
      │ survivability│        │ survivability│          │ agent desk  │
      └─────────────┘         └─────────────┘           └─────────────┘
```

**Rationale:** Geographically isolated foundation clusters limit blast radius — a fault
in one cluster does not propagate to others. Dedicated agent clusters shield hospital
voice from contact-center SIP demand. A central SME hub provides a single inter-cluster
routing plane.

---

## 3. High-Availability Building Blocks

| Layer | Pattern | Purpose |
|-------|---------|---------|
| Site survivability | SRST / Enhanced SRST nodes | Keep local dial tone and 911 during WAN loss |
| Data center | Active/standby across two sites over DWDM | DR and maintenance without downtime |
| Call processing | Publisher + redundant subscribers | Node loss tolerance |
| Contact center | Redundant CVP + Finesse, side-A/side-B | No single point of failure for agents |
| Edge / remote | Expressway MRA, dual-NIC proxy pair | Secure remote endpoints without VPN client |
| Emergency | Cisco Emergency Responder + Layer 2 mapping | Dispatchable location accuracy |

---

## 4. Emergency Call Path (Dispatchable Location)

The emergency design uses **deterministic Layer 2 switch-port mapping** rather than
probabilistic Layer 3 IP-subnet mapping. The physical wall port a device is plugged
into is a fixed, known location; an IP address can change as devices move across a
campus-wide network.

```
   IP Phone ──(CDP/LLDP)──▶ Access Switch ──▶ Cisco Emergency Responder
                                                  │  port→ERL mapping
                                                  ▼
                                          911 / PSAP with
                                       Building / Floor / Room
```

See the [E911 Compliance Checklist](../methodology/e911-compliance-checklist.md) for
the implementation procedure and the `ansible/playbooks/e911-location-update.yml`
playbook for bulk ERL updates.

---

## 5. Automation & Observability

- **Provisioning / inventory:** CUCM AXL SOAP API via Python (`python/cucm_axl`,
  `python/reporting`).
- **Bulk configuration:** Ansible playbooks (`ansible/playbooks`).
- **Compliance reporting:** scheduled `compliance_report.py` runs that exit non-zero
  on any dispatchable-location gap, suitable for gating in CI or a cron monitor.
- **Change safety:** all bulk tools default to dry-run / check mode; writes require an
  explicit flag.

---

## 6. Security Posture

- Least-privilege AXL application users (read-only for reporting tools).
- Secrets sourced from environment variables or Ansible Vault — never committed.
- TLS verification on by default; disabling it is a lab-only, explicit opt-out.
- No PHI is read, logged, or stored by any tool in this repository.
