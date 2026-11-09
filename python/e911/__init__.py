"""
Healthcare UC Automation - E911 Reconciliation Engine
=====================================================

Keeps the hospital's physical location records (switch port -> patch panel ->
jack -> room) in agreement with what the network and Cisco Emergency Responder
(CER) actually report, so every 911 call carries a verified dispatchable
location under RAY BAUM's Act.

The engine compares four independent sources on every run:

1. The location database  - the hospital's record of where each jack is
2. Switch discovery       - CDP / LLDP neighbors and MAC tables (what is plugged in where)
3. CER exports            - the ERL that CER will actually send for each port
4. CUCM inventory         - every phone the call-control system knows about

and reports where they disagree, scores dispatchable-location accuracy, keeps an
append-only audit history, and produces a remediation file that can be applied
to CER through its Configuration API.

Author: Freddy Antony
License: MIT
"""

__version__ = "0.2.0"
