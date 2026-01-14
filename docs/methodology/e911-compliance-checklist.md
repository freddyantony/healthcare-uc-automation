# RAY BAUM's Act / Kari's Law Compliance Implementation Checklist

## Healthcare Multi-Line Telephone System (MLTS) E911 Compliance Guide

**Author:** Freddy Simon Paul Antony  
**Version:** 1.0  
**Last Updated:** January 2026  
**Regulatory Reference:** RAY BAUM's Act Section 506, Kari's Law Act of 2017

---

## Overview

This checklist provides a systematic approach to implementing RAY BAUM's Act compliant dispatchable location for 911 calls in healthcare Multi-Line Telephone System (MLTS) environments.

**Healthcare facilities present unique challenges:**
- Large multi-building campuses (often 500,000+ square feet)
- Complex floor plans with clinical areas
- Frequent endpoint moves as departments reorganize
- Integration requirements with clinical systems
- Life-safety implications requiring highest accuracy

---

## Regulatory Requirements Summary

### Kari's Law (Effective February 2020)
- [ ] Direct 911 dialing without prefix (no "9" required)
- [ ] Notification to central location when 911 called

### RAY BAUM's Act Section 506 (Effective January 2020)
- [ ] Dispatchable location conveyed with 911 calls
- [ ] Location must include building, floor, and room/suite

**Penalties for Non-Compliance:** Up to $10,000 + $500/day per violation

---

## Phase 1: Assessment

### 1.1 Inventory Current State

| Item | Status | Notes |
|------|--------|-------|
| Total phone endpoints | _____ | |
| Buildings/locations | _____ | |
| Current 911 routing method | _____ | |
| PSAP serving area | _____ | |
| Carrier for 911 | _____ | |

### 1.2 Gap Analysis

- [ ] Can users dial 911 directly without prefix?
- [ ] Is notification sent when 911 is dialed?
- [ ] Is dispatchable location (building/floor/room) sent?
- [ ] Are soft clients (Jabber, Webex) included?
- [ ] Are remote workers addressed?

### 1.3 Technology Inventory

| Component | Current | Needed |
|-----------|---------|--------|
| PBX/UC Platform | | |
| Emergency Responder | | |
| Location Service (Intrado, etc.) | | |
| Network Discovery | | |

---

## Phase 2: Design

### 2.1 Emergency Response Location (ERL) Design

**Healthcare ERL Granularity Recommendation:**

| Facility Size | Minimum ERL Granularity |
|--------------|------------------------|
| < 10,000 sq ft | Building + Floor |
| 10,000 - 50,000 sq ft | Building + Floor + Wing/Zone |
| > 50,000 sq ft | Building + Floor + Room/Suite |
| Multi-building campus | Building + Floor + Room/Suite |

**Healthcare-Specific ERL Considerations:**
- Emergency Department: Room-level granularity
- Operating Rooms: Room-level granularity
- Patient floors: Room-level granularity
- Administrative areas: Zone-level may be acceptable

### 2.2 Location Determination Method

| Method | Pros | Cons | Healthcare Fit |
|--------|------|------|----------------|
| Switch port mapping | Accurate, reliable | Labor intensive setup | Recommended |
| LLDP/CDP discovery | Automatic | Requires network support | Good supplement |
| IP subnet mapping | Simple | Less granular | Not sufficient alone |
| Wireless AP mapping | Good for mobile | Requires integration | Use with desk phones |
| Manual entry | Flexible | Error-prone | Last resort |

**Recommended Approach:** Switch port mapping primary, supplemented by LLDP/CDP discovery for moves.

### 2.3 Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    IP Phone                              │
│                       │                                  │
│                       ▼                                  │
│               ┌───────────────┐                          │
│               │ Network Switch│ ◄─── Port-to-Location   │
│               │ (CDP/LLDP)    │      Mapping            │
│               └───────┬───────┘                          │
│                       │                                  │
│                       ▼                                  │
│        ┌──────────────────────────────┐                  │
│        │ Cisco Emergency Responder    │                  │
│        │ - ERL Database               │                  │
│        │ - Route Pattern Mgmt         │                  │
│        │ - ELIN Management            │                  │
│        └──────────────┬───────────────┘                  │
│                       │                                  │
│                       ▼                                  │
│        ┌──────────────────────────────┐                  │
│        │ Location Service (Intrado)    │                  │
│        │ - ALI Database               │                  │
│        │ - PSAP Routing               │                  │
│        └──────────────┬───────────────┘                  │
│                       │                                  │
│                       ▼                                  │
│               ┌───────────────┐                          │
│               │     PSAP      │                          │
│               │ (911 Center)  │                          │
│               └───────────────┘                          │
└─────────────────────────────────────────────────────────┘
```

---

## Phase 3: Implementation

### 3.1 Cisco Emergency Responder Configuration

- [ ] Install/upgrade CER to supported version
- [ ] Configure CUCM integration
- [ ] Define ERL naming convention
- [ ] Create ERLs for all locations
- [ ] Configure ELIN ranges (coordinate with carrier)
- [ ] Set up switch port discovery

### 3.2 Network Configuration

- [ ] Enable CDP/LLDP on all voice VLANs
- [ ] Configure switch port descriptions consistently
- [ ] Document switch-to-building/floor mapping
- [ ] Ensure SNMP access from CER to switches

### 3.3 Carrier Configuration

- [ ] Coordinate ELIN provisioning with carrier
- [ ] Configure ALI records with carrier/Intrado
- [ ] Establish testing procedures with carrier
- [ ] Document carrier escalation contacts

### 3.4 Location Database Build

**Required Data per ERL:**

| Field | Example | Required |
|-------|---------|----------|
| ERL Name | MAIN-HOSP-FL3-WEST | Yes |
| Building Name | Main Hospital | Yes |
| Street Address | 123 Medical Center Dr | Yes |
| City, State, ZIP | Charlotte, NC 28203 | Yes |
| Floor | 3 | Yes |
| Location Detail | West Wing, Rooms 300-350 | Recommended |
| ELIN | 704-555-0100 | Yes |

---

## Phase 4: Testing

### 4.1 Pre-Deployment Testing

| Test | Procedure | Pass Criteria |
|------|-----------|---------------|
| Phone registration | Register test phone | Phone shows in CER |
| Location discovery | Move phone to new port | CER updates location within 5 min |
| ELIN mapping | Verify phone has ELIN | Correct ELIN assigned |
| 911 routing | Trace call route | Routes to correct gateway |

### 4.2 Live 911 Testing

**CRITICAL: Coordinate with PSAP before testing**

- [ ] Contact local PSAP to schedule test
- [ ] Provide test phone numbers
- [ ] Perform test call during scheduled window
- [ ] Verify location displayed at PSAP
- [ ] Document test results

**Healthcare Testing Scope:**
- Test from each building
- Test from multiple floors per building
- Test from clinical areas (ED, OR, ICU)
- Test soft clients if deployed
- Test remote worker scenarios

### 4.3 Test Documentation Template

| Date | Time | Phone | Expected Location | PSAP Confirmed | Pass/Fail |
|------|------|-------|-------------------|----------------|-----------|
| | | | | | |

---

## Phase 5: Ongoing Compliance

### 5.1 Change Management

**Triggers requiring location update:**
- New phone deployment
- Phone move (even within same floor)
- Network switch replacement
- Network port reassignment
- Building renovation/reconfiguration

### 5.2 Regular Audits

| Frequency | Audit Activity |
|-----------|---------------|
| Weekly | Review unlocated phones report |
| Monthly | Spot-check 10% of ERLs |
| Quarterly | Full compliance report |
| Annually | End-to-end test with PSAP |

### 5.3 Reporting Metrics

| Metric | Target | Current |
|--------|--------|---------|
| % phones with valid ERL | 100% | |
| Unlocated phone count | 0 | |
| Average location update time | < 24 hrs | |
| Last PSAP test date | | |
| Last PSAP test result | Pass | |

---

## Phase 6: Documentation Requirements

### 6.1 Required Documentation

- [ ] ERL database (all locations)
- [ ] Switch-to-ERL mapping
- [ ] ELIN inventory
- [ ] Carrier contact information
- [ ] PSAP contact information
- [ ] Test records (maintain 3 years)
- [ ] Change log

### 6.2 Compliance Evidence Package

For regulatory inquiries or audits:
1. Policy document showing compliance commitment
2. ERL database export
3. Test records with PSAP verification
4. Change management procedures
5. Audit reports

---

## Healthcare-Specific Addendum

### Critical Areas Requiring Room-Level Accuracy

| Area | Rationale |
|------|-----------|
| Emergency Department | Active medical emergencies |
| Intensive Care Units | High-acuity patients |
| Operating Rooms | Sedated patients cannot self-locate |
| Labor & Delivery | Time-critical situations |
| Behavioral Health | Security considerations |
| Pediatric Units | Non-verbal patients |

### Soft Client Considerations

Healthcare workers increasingly use:
- Cisco Jabber on workstations
- Webex mobile app
- Teams/other collaboration tools

**Each requires location management:**
- [ ] Workstation-based clients: Use IP subnet or AD site mapping
- [ ] Mobile clients: GPS/cellular location where permitted
- [ ] Remote/work-from-home: Home address registration

### Nurse Call Integration

If nurse call system integrates with phone system:
- [ ] Ensure nurse call events don't block 911
- [ ] Verify nurse call room mapping aligns with E911 ERL
- [ ] Test 911 during nurse call activity

---

## Resources

### Vendor Documentation
- Cisco Emergency Responder Admin Guide
- Intrado Enterprise Services Portal
- NENA Standards (nena.org)

### Regulatory References
- [RAY BAUM's Act Text](https://www.congress.gov/bill/115th-congress/house-bill/4986)
- [Kari's Law Text](https://www.congress.gov/bill/115th-congress/house-bill/582)
- [FCC 911 Requirements](https://www.fcc.gov/general/9-1-1-and-e9-1-1-services)

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 2026 | F. Antony | Initial release |

---

*This checklist is part of an ongoing effort to document healthcare-specific E911 compliance methodologies for dissemination to the broader U.S. healthcare sector.*
