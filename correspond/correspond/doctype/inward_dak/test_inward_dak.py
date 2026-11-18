# Copyright (c) 2026, Mohammed Faisal and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate, add_days
from correspond.correspond.doctype.inward_dak.inward_dak import print_docket_label
from correspond.correspond.doctype.correspond_delegation_rule.correspond_delegation_rule import get_active_delegated_desks


class IntegrationTestInwardDak(IntegrationTestCase):
    """
    Integration tests for InwardDak & Sprint 3 Features:
    - Link Officer Delegation Logic
    - Duplicate Receipt Prevention
    - QR Code Docketing Label Generation
    - VIP / Parliament Reference SLA Tracking
    """

    def setUp(self):
        frappe.set_user("Administrator")
        self.cleanup_test_records()

        dept = frappe.db.get_value("Department", {"department_name": "Accounts"}) or "Accounts - _TC"

        # Create Designations if needed
        for d in ["Director", "Deputy Secretary"]:
            if not frappe.db.exists("Designation", d):
                frappe.get_doc({"doctype": "Designation", "designation_name": d}).insert(ignore_permissions=True)

        # Create Test Office & Section
        if not frappe.db.exists("Correspond Office", "TO"):
            frappe.get_doc({
                "doctype": "Correspond Office",
                "office_name": "Test Office",
                "office_abbr": "TO"
            }).insert(ignore_permissions=True)

        if not frappe.db.exists("Correspond Section", "Accounts-TSEC"):
            frappe.get_doc({
                "doctype": "Correspond Section",
                "section_name": "Test Section",
                "section_abbr": "TSEC",
                "department": dept
            }).insert(ignore_permissions=True)

        # Create test users if needed
        for email, name in [("test_dir@example.com", "Test Director"), ("test_ds@example.com", "Test DS")]:
            if not frappe.db.exists("User", email):
                frappe.get_doc({
                    "doctype": "User",
                    "email": email,
                    "first_name": name,
                    "roles": [{"role": "Correspond User"}]
                }).insert(ignore_permissions=True)

        # Create two Desk Profiles for delegation testing
        self.primary_desk = frappe.db.get_value("Correspond Desk Profile", {"user": "test_dir@example.com"}, "name")
        if not self.primary_desk:
            d1 = frappe.get_doc({
                "doctype": "Correspond Desk Profile",
                "user": "test_dir@example.com",
                "office": "TO",
                "department": dept,
                "section": "Accounts-TSEC",
                "designation": "Director"
            }).insert(ignore_permissions=True)
            self.primary_desk = d1.name

        self.delegate_desk = frappe.db.get_value("Correspond Desk Profile", {"user": "test_ds@example.com"}, "name")
        if not self.delegate_desk:
            d2 = frappe.get_doc({
                "doctype": "Correspond Desk Profile",
                "user": "test_ds@example.com",
                "office": "TO",
                "department": dept,
                "section": "Accounts-TSEC",
                "designation": "Deputy Secretary"
            }).insert(ignore_permissions=True)
            self.delegate_desk = d2.name

    def tearDown(self):
        self.cleanup_test_records()

    def cleanup_test_records(self):
        for dak in frappe.get_all("Inward Dak", filters={"subject": ["like", "Test Sprint 3%"]}, fields=["name", "docstatus"]):
            if dak.docstatus == 1:
                try:
                    frappe.get_doc("Inward Dak", dak.name).cancel()
                except Exception:
                    pass
            frappe.delete_doc("Inward Dak", dak.name, force=1, ignore_permissions=True)
        for rule in frappe.get_all("Correspond Delegation Rule", filters={"desk": getattr(self, "primary_desk", "TEST-DESK-PRIMARY")}, pluck="name"):
            frappe.delete_doc("Correspond Delegation Rule", rule, force=1, ignore_permissions=True)

    def test_link_officer_delegation(self):
        """Test delegation engine allows delegate desk to inherit primary custody."""
        rule = frappe.new_doc("Correspond Delegation Rule")
        rule.desk = self.primary_desk
        rule.delegate_desk = self.delegate_desk
        rule.from_date = nowdate()
        rule.to_date = add_days(nowdate(), 5)
        rule.is_active = 1
        rule.delegation_reason = "Official Deputation to State HQ"
        rule.insert(ignore_permissions=True)

        active_desks = get_active_delegated_desks("test_ds@example.com")
        self.assertIn(self.primary_desk, active_desks)

    def test_duplicate_receipt_detection(self):
        """Test system blocks duplicate inward receipts with same external reference."""
        dak1 = frappe.new_doc("Inward Dak")
        dak1.subject = "Test Sprint 3 Receipt 1"
        dak1.sender_organization = "Ministry of Finance"
        dak1.external_reference_number = "MOF/2026/EXP/999"
        dak1.external_reference_date = nowdate()
        dak1.insert(ignore_permissions=True)

        # Attempting identical second diarization should throw duplicate exception
        dak2 = frappe.new_doc("Inward Dak")
        dak2.subject = "Test Sprint 3 Duplicate Attempt"
        dak2.sender_organization = "Ministry of Finance"
        dak2.external_reference_number = "MOF/2026/EXP/999"
        dak2.external_reference_date = nowdate()
        
        with self.assertRaises(frappe.exceptions.ValidationError):
            dak2.insert(ignore_permissions=True)

    def test_vip_sla_calculation_and_qr_docket(self):
        """Test VIP reference priority SLA calculation and QR code generation."""
        dak = frappe.new_doc("Inward Dak")
        dak.subject = "Test Sprint 3 PMO Directive on Infrastructure"
        dak.sender_organization = "Prime Minister's Office"
        dak.is_vip_reference = 1
        dak.vip_type = "PMO Reference"
        dak.receipt_date = nowdate()
        dak.insert(ignore_permissions=True)

        # PMO Reference default SLA is 3 days
        expected_sla = add_days(nowdate(), 3)
        self.assertEqual(str(dak.sla_due_date), str(expected_sla))

        # Submit and verify QR barcode generation
        dak.submit()
        self.assertIsNotNone(dak.barcode_image)
        self.assertTrue(dak.barcode_image.startswith("data:image/png;base64,"))

        # Verify printable docket HTML
        docket_html = print_docket_label(dak.name)
        self.assertIn("GOVT E-DAK DOCKET", docket_html)
        self.assertIn(dak.name, docket_html)
        self.assertIn("PMO Reference", docket_html)
