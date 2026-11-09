"""
Healthcare UC Automation - CUCM Phone Operations
================================================

This module provides utilities for managing Cisco Unified Communications Manager
phone endpoints in healthcare environments. Designed for enterprise-scale 
deployments (40,000+ endpoints) with HIPAA compliance requirements.

Author: Freddy Simon Paul Antony
License: MIT
"""

import logging
import os
import sys
from typing import List, Dict, Optional
from dataclasses import dataclass
import csv
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PhoneEndpoint:
    """Represents a phone endpoint in the UC infrastructure."""
    device_name: str
    mac_address: str
    model: str
    description: str
    device_pool: str
    location: str
    e911_location: Optional[str] = None
    registered: bool = False
    
    
class CUCMPhoneManager:
    """
    Manager class for Cisco UCM phone operations.
    
    Designed for healthcare environments requiring:
    - HIPAA-compliant logging (no PHI in logs)
    - Bulk operations for large-scale deployments
    - E911/RAY BAUM's Act location management
    - Zero-downtime migration support
    
    Example Usage:
        manager = CUCMPhoneManager(
            cucm_host="cucm-pub.healthcare.local",
            username="axl-user",
            password="<secure>"
        )
        
        # Bulk provision from CSV
        manager.bulk_provision_from_csv("new_phones.csv")
        
        # Generate compliance report
        manager.generate_e911_compliance_report("compliance_report.csv")
    """
    
    def __init__(self, cucm_host: str, username: str, password: str, 
                 verify_ssl: bool = True):
        """
        Initialize CUCM connection.
        
        Args:
            cucm_host: CUCM Publisher hostname/IP
            username: AXL API username
            password: AXL API password
            verify_ssl: Whether to verify SSL certificates
        """
        self.cucm_host = cucm_host
        self.username = username
        self._password = password
        self.verify_ssl = verify_ssl
        self._session = None
        
        logger.info(f"Initialized CUCM manager for host: {cucm_host}")
    
    def connect(self) -> bool:
        """
        Establish connection to CUCM AXL API.
        
        Returns:
            bool: True if connection successful
        """
        # In production, this would use zeep/requests to connect to AXL SOAP API
        # Sanitized example - actual implementation uses AXL WSDL
        logger.info("Connecting to CUCM AXL API...")
        
        # Connection logic would go here
        # self._session = create_axl_session(...)
        
        logger.info("CUCM connection established")
        return True
    
    def get_phone_by_name(self, device_name: str) -> Optional[PhoneEndpoint]:
        """
        Retrieve phone details by device name.
        
        Args:
            device_name: The device name (e.g., SEP001122334455)
            
        Returns:
            PhoneEndpoint object if found, None otherwise
        """
        logger.info(f"Querying phone: {device_name}")
        
        # AXL getPhone query would go here
        # response = self._session.service.getPhone(name=device_name)
        
        # Return sanitized example
        return None
    
    def bulk_provision_from_csv(self, csv_path: str, 
                                 dry_run: bool = True) -> Dict[str, int]:
        """
        Bulk provision phones from CSV file.
        
        Healthcare-specific considerations:
        - Validates E911 location data before provisioning
        - Supports phased rollout for zero-downtime migrations
        - Logs all operations for compliance audit trail
        
        Args:
            csv_path: Path to CSV file with phone data
            dry_run: If True, validate only without making changes
            
        Returns:
            Dict with counts: {'success': N, 'failed': N, 'skipped': N}
        """
        results = {'success': 0, 'failed': 0, 'skipped': 0}
        
        logger.info(f"Starting bulk provisioning from: {csv_path}")
        logger.info(f"Dry run mode: {dry_run}")
        
        try:
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    device_name = row.get('device_name', '')
                    
                    # Validate required fields
                    if not self._validate_phone_data(row):
                        logger.warning(f"Validation failed for: {device_name}")
                        results['skipped'] += 1
                        continue
                    
                    # Validate E911 location (RAY BAUM's Act compliance)
                    if not row.get('e911_location'):
                        logger.warning(f"Missing E911 location for: {device_name}")
                        results['skipped'] += 1
                        continue
                    
                    if not dry_run:
                        # Actual provisioning would occur here
                        # self._provision_phone(row)
                        pass
                    
                    results['success'] += 1
                    
        except FileNotFoundError:
            logger.error(f"CSV file not found: {csv_path}")
            raise
        except Exception as e:
            logger.error(f"Bulk provisioning error: {str(e)}")
            raise
        
        logger.info(f"Bulk provisioning complete: {results}")
        return results
    
    def _validate_phone_data(self, phone_data: Dict) -> bool:
        """
        Validate phone data meets healthcare deployment requirements.
        
        Args:
            phone_data: Dictionary of phone attributes
            
        Returns:
            bool: True if validation passes
        """
        required_fields = [
            'device_name', 
            'mac_address', 
            'device_pool', 
            'location'
        ]
        
        for field in required_fields:
            if not phone_data.get(field):
                return False
        
        # Validate MAC address format
        mac = phone_data.get('mac_address', '').replace(':', '').replace('-', '')
        if len(mac) != 12:
            return False
        
        return True
    
    def generate_e911_compliance_report(self, output_path: str) -> int:
        """
        Generate E911/RAY BAUM's Act compliance report.
        
        Healthcare facilities must ensure dispatchable location accuracy
        for all phone endpoints per RAY BAUM's Act requirements.
        
        This report identifies:
        - Endpoints missing E911 location data
        - Endpoints with outdated location information
        - Compliance percentage by facility/building
        
        Args:
            output_path: Path for output CSV report
            
        Returns:
            int: Number of non-compliant endpoints found
        """
        logger.info("Generating E911 compliance report...")
        
        non_compliant_count = 0
        
        # In production, this would query all phones and check E911 locations
        # phones = self._get_all_phones()
        # for phone in phones:
        #     if not phone.e911_location:
        #         non_compliant_count += 1
        
        report_data = {
            'generated_at': datetime.now().isoformat(),
            'total_endpoints': 0,
            'compliant': 0,
            'non_compliant': non_compliant_count,
            'compliance_percentage': 0.0
        }
        
        logger.info(f"E911 compliance report generated: {output_path}")
        logger.info(f"Non-compliant endpoints found: {non_compliant_count}")
        
        return non_compliant_count
    
    def migrate_endpoint_to_webex(self, device_name: str, 
                                   webex_location_id: str,
                                   validate_only: bool = True) -> bool:
        """
        Migrate phone endpoint from on-premises CUCM to Webex Calling.
        
        Zero-Downtime Migration Methodology:
        1. Validate current endpoint configuration
        2. Verify Webex Calling location/number availability
        3. Export user preferences and speed dials
        4. Create Webex Calling device/user
        5. Update E911 location in Webex
        6. Validate registration in Webex
        7. Decommission on-premises device
        
        Args:
            device_name: CUCM device name
            webex_location_id: Target Webex Calling location
            validate_only: If True, perform validation without migration
            
        Returns:
            bool: True if migration/validation successful
        """
        logger.info(f"{'Validating' if validate_only else 'Migrating'} "
                   f"endpoint: {device_name}")
        
        # Step 1: Get current config
        current_phone = self.get_phone_by_name(device_name)
        if not current_phone:
            logger.error(f"Phone not found: {device_name}")
            return False
        
        # Step 2-7: Migration steps would be implemented here
        # This is a methodology framework - actual implementation
        # depends on specific environment configuration
        
        if validate_only:
            logger.info(f"Validation passed for: {device_name}")
        else:
            logger.info(f"Migration completed for: {device_name}")
        
        return True


class E911LocationManager:
    """
    Manager for E911/RAY BAUM's Act dispatchable location compliance.

    Healthcare facilities face unique challenges:
    - Large multi-building campuses (500,000+ sq ft)
    - Frequent endpoint moves due to clinical reorganization
    - Integration with multiple carriers and PSAPs
    - Life-safety implications requiring high accuracy

    Since v0.2.0 this class is a thin facade over the ``e911`` reconciliation
    engine (python/e911), so scripts built on it get the same CER client,
    location-database validation and drift detection as the ``e911`` CLI:

    - update_switch_port_location: CER Configuration API ERL assignment
    - bulk_update_locations_from_csv: applies a location DB or remediation CSV
    - generate_location_gap_report: CER unlocated phones + location-DB gaps

    Credentials default to the CER_API_USER / CER_API_PASSWORD environment
    variables.
    """

    def __init__(self, emergency_responder_host: str, username: Optional[str] = None,
                 password: Optional[str] = None, verify_ssl: bool = True, client=None):
        """
        Initialize E911 Location Manager.

        Args:
            emergency_responder_host: Cisco Emergency Responder Publisher hostname
            username / password: CER API account (default: environment)
            verify_ssl: verify CER's TLS certificate
            client: pre-built e911.cer.CERClient (tests, custom sessions)
        """
        _ensure_e911_importable()
        from e911.cer import CERClient

        self.cer_host = emergency_responder_host
        self.client = client or CERClient(
            emergency_responder_host,
            username or os.environ.get("CER_API_USER", ""),
            password or os.environ.get("CER_API_PASSWORD", ""),
            verify_ssl=verify_ssl,
        )
        self._cer_ports = None
        logger.info(f"Initialized E911 manager for: {emergency_responder_host}")

    def _ports(self):
        if self._cer_ports is None:
            self._cer_ports = self.client.export_switchports()
        return self._cer_ports

    def update_switch_port_location(self, switch_name: str,
                                    port: str,
                                    erl_name: str) -> bool:
        """
        Update Emergency Response Location for a switch port.

        Args:
            switch_name: Network switch hostname or IP address, as known to CER
            port: Interface name (Gi1/0/12) or CER PortIdentifier
            erl_name: Emergency Response Location name

        Returns:
            bool: True if CER accepted the update
        """
        from e911.cer import CERError, resolve_port_identifier

        logger.info(f"Updating ERL for {switch_name}:{port} -> {erl_name}")
        cer_port = resolve_port_identifier(self._ports(), switch_name, port)
        switch_ip = cer_port.switch_ip if cer_port else switch_name
        port_id = cer_port.port_identifier if cer_port else port
        try:
            self.client.update_switchport_erl(switch_ip, [port_id], erl_name)
            return True
        except CERError as exc:
            logger.error(f"ERL update failed for {switch_name}:{port}: {exc}")
            return False

    def bulk_update_locations_from_csv(self, csv_path: str,
                                       apply: bool = False) -> Dict[str, int]:
        """
        Bulk update E911 locations from a CSV file (dry run unless apply=True).

        Accepts a location database (templates/e911-location-database-template.csv)
        or the remediation.csv written by ``e911 reconcile``. Rows without a
        complete dispatchable location (building, floor, room) are skipped.

        Returns:
            Dict with updated / failed / skipped / planned counts
        """
        from e911.location_db import load_location_db

        results = {'updated': 0, 'failed': 0, 'skipped': 0, 'planned': 0}
        logger.info(f"Bulk updating E911 locations from: {csv_path}")
        db = load_location_db(csv_path)
        if apply and not self.client.discovery_complete():
            raise RuntimeError("CER discovery is not complete; no changes made.")
        for rec in db.records:
            if not rec.dispatchable or not rec.erl_name or not rec.switch_port:
                results['skipped'] += 1
                continue
            if not apply:
                results['planned'] += 1
                continue
            ok = self.update_switch_port_location(
                rec.switch_ip or rec.switch_name, rec.port_id or rec.switch_port, rec.erl_name)
            results['updated' if ok else 'failed'] += 1
        logger.info(f"Bulk update results: {results}")
        return results

    def generate_location_gap_report(self, location_csv: Optional[str] = None) -> List[Dict]:
        """
        Identify endpoints without a valid E911 location.

        Critical for RAY BAUM's Act compliance - all MLTS endpoints
        must have dispatchable location (building, floor, room/zone).

        Combines CER's unlocated-phones export with, when ``location_csv`` is
        given, the location database's own data-quality findings.

        Returns:
            List of dicts describing each gap
        """
        logger.info("Scanning for endpoints missing E911 location...")
        gaps = [{
            'source': 'CER unlocated phones',
            'mac': phone.mac,
            'extension': phone.extension,
            'effective_erl': phone.effective_erl,
            'detail': phone.erl_used_info,
        } for phone in self.client.export_unlocated()]
        if location_csv:
            from e911.location_db import load_location_db, validate_location_db

            for finding in validate_location_db(load_location_db(location_csv)):
                gaps.append({
                    'source': 'location database',
                    'code': finding.code,
                    'severity': finding.severity,
                    'detail': finding.message,
                })
        logger.info(f"Found {len(gaps)} endpoints without E911 location")
        return gaps


def _ensure_e911_importable() -> None:
    """Make python/e911 importable when this module is run from a checkout."""
    try:
        import e911  # noqa: F401
    except ImportError:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Example usage and testing
if __name__ == "__main__":
    print("Healthcare UC Automation Framework")
    print("=" * 40)
    print("\nThis module provides automation utilities for:")
    print("- Cisco UCM phone management")
    print("- E911/RAY BAUM's Act compliance")
    print("- Legacy-to-cloud migration")
    print("\nDesigned for enterprise healthcare environments")
    print("with 40,000+ endpoints and HIPAA compliance requirements.")
    print("\nSee README.md for full documentation.")
