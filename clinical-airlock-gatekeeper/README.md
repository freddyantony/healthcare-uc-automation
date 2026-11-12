# Clinical Airlock Gatekeeper — v0.1 prototype

An open-source, **synthetic-data demonstration** of the Clinical Airlock
methodology's evidence-based safety checks. It is not a hospital-tested system
and **does not authorize a clinical or technical migration**.

## What problem it illustrates

A phone system can register and make calls while important clinical workflows
(paging, emergency calling, nurse-station escalation) remain unverified or fail.
This tool makes missing critical dependencies, failed test results, missing
rollback plans, and missing evidence trigger a **HOLD / NO-GO** result.

## Run without installing additional packages

Python 3.10 or newer:

```bash
python clinical-airlock-gatekeeper/gatekeeper.py
```

Expected synthetic demo result:

```text
Clinical Airlock Gatekeeper — SYNTHETIC DEMO
Decision: HOLD / NO-GO
 - D002: paging_failover = FAIL
```

Change `paging_failover,FAIL` to `paging_failover,PASS` in `test_results.csv`
then run again. It should print `READY FOR HUMAN REVIEW`.

## Run unit tests

```bash
python -m unittest discover -s clinical-airlock-gatekeeper -p 'test_*.py' -v
```

## Contents
- `dependencies.csv`: critical service, owner, required test, rollback plan
- `test_results.csv`: synthetic results, evidence reference, reviewer
- `gatekeeper.py`: conservative evidence-based gate evaluation
- `test_gatekeeper.py`: 5 unit tests for pass and blocking cases

## Limitations and next steps

This is a **prototype using fictional hospital records**. Neither the code nor
its unit tests validate actual emergency routing, bedside workflows, CUCM,
WAN outages, or carrier/PSAP connectivity. Human clinical and technical approval
is mandatory even when a result is `READY FOR HUMAN REVIEW`.

Next: site-agnostic risk register, HTML reports, approval tracking,
read-only CUCM AXL integration, and controlled prospective validation.
