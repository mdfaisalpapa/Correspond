import base64
import io
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, getdate, nowdate
import qrcode

class InwardDak(Document):
    def validate(self):
        self.check_duplicate_receipt()
        self.set_sla_defaults()

    def before_insert(self):
        if not self.status:
            self.status = "Draft"

    def before_submit(self):
        if self.status == "Draft":
            self.status = "Diarized"
        self.generate_qr_docket()

    def on_submit(self):
        pass

    def check_duplicate_receipt(self):
        """
        Duplicate Prevention: Checks if a receipt with identical sender organization,
        external reference number, and external reference date has already been diarized.
        """
        if self.external_reference_number and self.sender_organization:
            filters = {
                "name": ["!=", self.name],
                "external_reference_number": self.external_reference_number,
                "sender_organization": self.sender_organization,
                "docstatus": ["!=", 2]
            }
            if self.external_reference_date:
                filters["external_reference_date"] = self.external_reference_date

            existing = frappe.db.exists("Inward Dak", filters)
            if existing:
                frappe.throw(
                    _("Duplicate Inward Receipt: Communication with reference number '{0}' from '{1}' is already diarized as '{2}'.")
                    .format(self.external_reference_number, self.sender_organization, existing)
                )

    def set_sla_defaults(self):
        """Sets standard government SLA target dates for high-priority / VIP references."""
        if self.is_vip_reference and not self.sla_due_date:
            sla_days = 7
            if self.vip_type == "PMO Reference":
                sla_days = 3
            elif self.vip_type == "Court Notice / Summons":
                sla_days = 5
            elif self.vip_type and "Parliament" in self.vip_type:
                sla_days = 2
            self.sla_due_date = add_days(self.receipt_date or nowdate(), sla_days)

    def generate_qr_docket(self):
        """Generates a QR Code slip containing Diarization ID, Date, Sender, and SLA."""
        qr_payload = f"DIARIZATION: {self.name}\nDATE: {self.receipt_date}\nSENDER: {self.sender_organization or self.sender_name}\nSUB: {self.subject}"
        if self.is_vip_reference:
            qr_payload += f"\nVIP: {self.vip_type} (SLA: {self.sla_due_date})"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2,
        )
        qr.add_data(qr_payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        b64_data = base64.b64encode(buffer.getvalue()).decode()
        self.barcode_image = f"data:image/png;base64,{b64_data}"

@frappe.whitelist()
def print_docket_label(dak_name):
    """Returns HTML for printing a 2x1 inch docket sticker."""
    doc = frappe.get_doc("Inward Dak", dak_name)
    if not doc.barcode_image:
        doc.generate_qr_docket()
        frappe.db.set_value("Inward Dak", doc.name, "barcode_image", doc.barcode_image, update_modified=False)

    vip_badge = f"<div style='font-size: 9px; color: red; font-weight: bold;'>⚠️ {doc.vip_type} | Due: {doc.sla_due_date}</div>" if doc.is_vip_reference else ""

    html = f"""
    <div style="width: 280px; height: 140px; border: 1px dashed #333; padding: 5px; font-family: monospace; display: flex; align-items: center; justify-content: space-between;">
        <div style="flex: 1; padding-right: 5px;">
            <div style="font-size: 11px; font-weight: bold; text-transform: uppercase;">GOVT E-DAK DOCKET</div>
            <div style="font-size: 13px; font-weight: bold; color: #155724;">{doc.name}</div>
            <div style="font-size: 10px;">Date: {doc.receipt_date}</div>
            <div style="font-size: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">From: {doc.sender_organization or doc.sender_name or 'External'}</div>
            {vip_badge}
        </div>
        <div>
            <img src="{doc.barcode_image}" style="width: 75px; height: 75px;" />
        </div>
    </div>
    """
    return html
