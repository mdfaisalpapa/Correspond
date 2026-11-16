# Copyright (c) 2026, Mohammed Faisal and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from correspond.correspond.doctype.outward_dak.outward_dak import (
    submit_dfa_for_approval,
    approve_dfa,
    mark_dfa_for_dispatch
)
from correspond.correspond.dfa_templates import get_dfa_template


class IntegrationTestOutwardDak(IntegrationTestCase):
    """
    Integration tests for OutwardDak & Sprint 2 Features:
    - Government DFA Templates
    - Multi-stage Approval Workflow
    - Central Dispatch Register Number Generation
    """

    def setUp(self):
        frappe.set_user("Administrator")
        self.cleanup_test_records()

        # Create Test Office & Section if needed
        if not frappe.db.exists("Correspond Office", "TEST-OFFICE"):
            frappe.get_doc({
                "doctype": "Correspond Office",
                "office_name": "Test Office",
                "office_abbr": "TO"
            }).insert(ignore_permissions=True)

        if not frappe.db.exists("Correspond Section", "TEST-SEC"):
            frappe.get_doc({
                "doctype": "Correspond Section",
                "section_name": "Test Section",
                "section_abbr": "ADM"
            }).insert(ignore_permissions=True)

        if not frappe.db.exists("Correspond Desk Profile", "TEST-DESK-SO"):
            frappe.get_doc({
                "doctype": "Correspond Desk Profile",
                "desk_name": "TEST-DESK-SO",
                "desk_title": "Section Officer 1",
                "user": "Administrator",
                "office": "TEST-OFFICE",
                "section": "TEST-SEC",
                "designation": "Section Officer"
            }).insert(ignore_permissions=True)

        # Create master test file
        self.test_file = frappe.new_doc("Correspond File")
        self.test_file.subject = "File for DFA Testing"
        self.test_file.description = "DFA testing file"
        self.test_file.file_owner = "TEST-DESK-SO"
        self.test_file.current_custodian = "TEST-DESK-SO"
        self.test_file.desk_section = "ADM"
        self.test_file.insert(ignore_permissions=True)

    def tearDown(self):
        self.cleanup_test_records()

    def cleanup_test_records(self):
        for dak in frappe.get_all("Outward Dak", filters={"subject": ["like", "Test DFA%"]}, pluck="name"):
            frappe.delete_doc("Outward Dak", dak, force=1, ignore_permissions=True)
        for f in frappe.get_all("Correspond File", filters={"subject": "File for DFA Testing"}, pluck="name"):
            frappe.delete_doc("Correspond File", f, force=1, ignore_permissions=True)

    def test_dfa_templates_availability(self):
        """Ensure standard Government DFA templates load with boilerplate."""
        om_template = get_dfa_template("Office Memorandum")
        self.assertIn("OFFICE MEMORANDUM", om_template)
        self.assertIn("GOVERNMENT OF INDIA", om_template)

        do_template = get_dfa_template("Demi-Official (D.O.) Letter")
        self.assertIn("D.O. No.", do_template)

        sanction_template = get_dfa_template("Sanction Order")
        self.assertIn("FINANCIAL SANCTION ORDER", sanction_template)

    def test_dfa_lifecycle_and_dispatch_registration(self):
        """Test full Draft -> Submitted -> Approved -> Dispatched workflow."""
        dak = frappe.new_doc("Outward Dak")
        dak.subject = "Test DFA Sanction of Equipment"
        dak.primary_file = self.test_file.name
        dak.sender = "TEST-DESK-SO"
        dak.dfa_type = "Sanction Order"
        dak.recipient_type = "External User"
        dak.receiver = "Vendor ABC"
        dak.receiver_email = "vendor@example.com"
        dak.letter_body = "<p>Sanction order text</p>"
        dak.status = "Draft"
        dak.insert(ignore_permissions=True)

        dak_name = dak.name
        self.assertEqual(dak.status, "Draft")

        # 1. Submit for approval
        sub_res = submit_dfa_for_approval(dak_name)
        self.assertEqual(sub_res["status"], "success")
        self.assertEqual(frappe.db.get_value("Outward Dak", dak_name, "status"), "Submitted for Approval")

        # 2. Approve DFA
        app_res = approve_dfa(dak_name)
        self.assertEqual(app_res["status"], "success")
        self.assertEqual(frappe.db.get_value("Outward Dak", dak_name, "status"), "Approved")
        self.assertIsNotNone(frappe.db.get_value("Outward Dak", dak_name, "approved_on"))

        # 3. Mark for Dispatch & Register Number Generation
        disp_res = mark_dfa_for_dispatch(dak_name, dispatch_mode="Speed Post", consignment_number="SP123456789IN")
        self.assertEqual(disp_res["status"], "success")
        dispatch_no = disp_res["dispatch_no"]
        self.assertTrue(len(dispatch_no) > 0)
        self.assertIn("ADM/OUT", dispatch_no)

        dak_doc = frappe.get_doc("Outward Dak", dak_name)
        self.assertEqual(dak_doc.status, "Marked for Dispatch")
        self.assertEqual(dak_doc.consignment_number, "SP123456789IN")
        self.assertEqual(dak_doc.dispatch_mode, "Speed Post")
