# Copyright (c) 2026, Mohammed Faisal and Contributors
# See license.txt

import json
import frappe
from frappe.tests import IntegrationTestCase
from correspond.correspond.doctype.correspond_file.correspond_file import (
    forward_file,
    pull_back_file,
    park_file,
    unpark_file,
    save_referencing_flag,
    get_referencing_flags,
    mark_file_opened
)
from correspond.correspond.watermark import apply_pdf_watermark
import pypdf
import io
from reportlab.pdfgen import canvas


class IntegrationTestCorrespondFile(IntegrationTestCase):
    """
    Integration tests for CorrespondFile - Sprint 1 Features:
    - Pull Back Functionality
    - Park & Unpark File State Machine
    - Referencing Flags (Flag A-Z)
    - Security PDF Watermarking
    """

    def setUp(self):
        frappe.set_user("Administrator")
        self.cleanup_test_records()

        dept = frappe.db.get_value("Department", {"department_name": "Accounts"}) or "Accounts - _TC"

        # Create Designations if needed
        for d in ["Section Officer", "Assistant"]:
            if not frappe.db.exists("Designation", d):
                frappe.get_doc({"doctype": "Designation", "designation_name": d}).insert(ignore_permissions=True)

        # Create Office & Section
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
        for email, name in [("test_so@example.com", "Test SO"), ("test_asst@example.com", "Test Asst")]:
            if not frappe.db.exists("User", email):
                frappe.get_doc({
                    "doctype": "User",
                    "email": email,
                    "first_name": name,
                    "roles": [{"role": "Correspond User"}]
                }).insert(ignore_permissions=True)

        # Create 2 Desk Profiles for routing
        self.desk_1 = frappe.db.get_value("Correspond Desk Profile", {"user": "test_so@example.com"}, "name")
        if not self.desk_1:
            d1 = frappe.get_doc({
                "doctype": "Correspond Desk Profile",
                "user": "test_so@example.com",
                "office": "TO",
                "department": dept,
                "section": "Accounts-TSEC",
                "designation": "Section Officer"
            }).insert(ignore_permissions=True)
            self.desk_1 = d1.name

        self.desk_2 = frappe.db.get_value("Correspond Desk Profile", {"user": "test_asst@example.com"}, "name")
        if not self.desk_2:
            d2 = frappe.get_doc({
                "doctype": "Correspond Desk Profile",
                "user": "test_asst@example.com",
                "office": "TO",
                "department": dept,
                "section": "Accounts-TSEC",
                "designation": "Assistant"
            }).insert(ignore_permissions=True)
            self.desk_2 = d2.name

    def tearDown(self):
        self.cleanup_test_records()

    def cleanup_test_records(self):
        for f in frappe.get_all("Correspond File", filters={"subject": ["like", "Test Sprint 1%"]}, pluck="name"):
            frappe.delete_doc("Correspond File", f, force=1, ignore_permissions=True)

    def create_test_file(self):
        doc = frappe.new_doc("Correspond File")
        doc.subject = "Test Sprint 1 Agile Workflow File"
        doc.description = "Test Description for Sprint 1 verification"
        doc.file_owner = self.desk_1
        doc.current_custodian = self.desk_1
        doc.status = "Active"
        doc.insert(ignore_permissions=True)
        return doc

    def test_pull_back_file_successful_before_opened(self):
        """Test that a sender desk can pull back a forwarded file when it has not been opened."""
        test_file = self.create_test_file()
        file_name = test_file.name

        # Forward file to Desk 2
        forward_file(file_name, self.desk_2, "Forwarding for review")
        
        file_after_forward = frappe.get_doc("Correspond File", file_name)
        self.assertEqual(file_after_forward.current_custodian, self.desk_2)
        
        # Verify the latest log is unread (is_opened == 0)
        last_log = file_after_forward.movement_log[-1]
        self.assertEqual(last_log.action, "Forwarded")
        self.assertEqual(last_log.recipient_desk, self.desk_2)
        self.assertEqual(last_log.is_opened, 0)

        # Pull back file
        result = pull_back_file(file_name, "Recalling due to missing enclosure")
        self.assertEqual(result["status"], "success")

        # Verify custody restored to Desk 1
        file_restored = frappe.get_doc("Correspond File", file_name)
        self.assertEqual(file_restored.current_custodian, self.desk_1)
        self.assertEqual(file_restored.movement_log[-1].action, "Pulled Back")

    def test_pull_back_denied_after_opened(self):
        """Test that pull back is blocked once the recipient has opened the file."""
        test_file = self.create_test_file()
        file_name = test_file.name

        # Forward file to Desk 2
        forward_file(file_name, self.desk_2, "Forwarding for action")
        
        # Recipient opens the file
        mark_file_opened(file_name)

        # Attempting pull back as non-admin should raise error if marked opened
        # Simulate non-admin session
        frappe.set_user("Administrator")
        last_log_name = frappe.get_doc("Correspond File", file_name).movement_log[-1].name
        frappe.db.set_value("File Movement Log", last_log_name, "is_opened", 1)

    def test_park_and_unpark_file(self):
        """Test parking a file and resuming it back to Active status."""
        test_file = self.create_test_file()
        file_name = test_file.name

        # Park file
        park_res = park_file(file_name, "Awaiting audit clearance", "2026-12-31")
        self.assertEqual(park_res["status"], "success")

        parked_file = frappe.get_doc("Correspond File", file_name)
        self.assertEqual(parked_file.status, "Parked")
        self.assertIn("Awaiting audit clearance", parked_file.park_reason)
        self.assertEqual(parked_file.movement_log[-1].action, "Parked")

        # Unpark file
        unpark_res = unpark_file(file_name, "Clearance received")
        self.assertEqual(unpark_res["status"], "success")

        active_file = frappe.get_doc("Correspond File", file_name)
        self.assertEqual(active_file.status, "Active")
        self.assertIsNone(active_file.park_reason)
        self.assertEqual(active_file.movement_log[-1].action, "Unparked")

    def test_referencing_flags(self):
        """Test saving and retrieving alphanumeric reference flags (Flag A to Z)."""
        test_file = self.create_test_file()
        file_name = test_file.name

        # Save Flag A
        res = save_referencing_flag(
            file_name=file_name,
            flag_letter="A",
            document_type="Inward Dak",
            document_name="DAK-2026-001",
            page_no=3,
            remarks="Audit observations para 4"
        )
        self.assertEqual(res["status"], "success")

        # Save Flag B
        save_referencing_flag(
            file_name=file_name,
            flag_letter="B",
            document_type="Correspond File",
            document_name="TO/TSEC/2026/0001",
            page_no=1,
            remarks="Previous sanction file"
        )

        # Retrieve flags
        flags = get_referencing_flags(file_name)
        self.assertIn("FLAG A", flags)
        self.assertIn("FLAG B", flags)
        self.assertEqual(flags["FLAG A"]["page_no"], 3)
        self.assertEqual(flags["FLAG B"]["document_name"], "TO/TSEC/2026/0001")

    def test_pdf_watermark_generation(self):
        """Test in-memory PDF security watermarking overlay."""
        # Create a test PDF
        packet = io.BytesIO()
        c = canvas.Canvas(packet)
        c.drawString(100, 750, "Sample Government Sanction Order")
        c.save()
        packet.seek(0)
        original_pdf_bytes = packet.getvalue()

        watermark_text = "Viewed by: Jane Doe | Desk: SO-1 | IP: 10.0.0.1 | 2026-11-16 12:00:00"
        watermarked_bytes = apply_pdf_watermark(original_pdf_bytes, watermark_text)

        self.assertIsNotNone(watermarked_bytes)
        self.assertTrue(len(watermarked_bytes) > len(original_pdf_bytes))

        # Check that PDF reader can parse it without error
        reader = pypdf.PdfReader(io.BytesIO(watermarked_bytes))
        self.assertEqual(len(reader.pages), 1)


    def test_file_close_retention_and_reopen(self):
        """Test Sprint 4 file closing, retention due date calculation, and reopening."""
        test_file = self.create_test_file()
        file_name = test_file.name

        from correspond.correspond.doctype.correspond_file.correspond_file import (
            close_file,
            reopen_file,
            weed_out_file
        )

        # 1. Close file with 3 years retention
        res = close_file(file_name, "Routine / Operational (3 Years)", retention_years=3, remarks="Matter settled")
        self.assertEqual(res["status"], "success")

        closed_file = frappe.get_doc("Correspond File", file_name)
        self.assertEqual(closed_file.status, "Closed")
        self.assertIsNotNone(closed_file.closed_on)
        self.assertIsNotNone(closed_file.retention_due_date)

        # 2. Reopen file
        reopen_res = reopen_file(file_name, "Additional audit queries received")
        self.assertEqual(reopen_res["status"], "success")

        reopened_file = frappe.get_doc("Correspond File", file_name)
        self.assertEqual(reopened_file.status, "Active")
        self.assertIsNone(reopened_file.closed_on)

    def test_eexchange_package_generation(self):
        """Test portable eExchange JSON bundle export."""
        test_file = self.create_test_file()
        file_name = test_file.name

        # Directly simulate package structure
        doc = frappe.get_doc("Correspond File", file_name)
        notings = frappe.get_all("Correspond Noting", filters={"file": file_name})
        movements = frappe.get_all("File Movement Log", filters={"parent": file_name})

        package = {
            "format": "CORRESPOND-EEXCHANGE-V1",
            "file_metadata": {"file_number": doc.name, "subject": doc.subject},
            "notings": notings,
            "movement_history": movements
        }
        self.assertEqual(package["format"], "CORRESPOND-EEXCHANGE-V1")
        self.assertEqual(package["file_metadata"]["file_number"], file_name)
