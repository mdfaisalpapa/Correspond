import frappe
from frappe.model.document import Document

class OutwardDak(Document):
    def on_submit(self):
        self.dispatch_dak()

    def dispatch_dak(self):
        # 1. Process Primary Recipient (To)
        # Internal User processing is skipped here because it is automatically handled by the unified Dak Inbox Report
        if self.recipient_type == "External User" and self.receiver_email:
            frappe.enqueue(
                self.send_external_email,
                queue='short',
                email=self.receiver_email,
                name=self.receiver,
                remarks="Primary Dispatch"
            )

        # 2. Process CC List (Copy To)
        for cc in (self.cc_list or []):
            if cc.recipient_type == "External User" and cc.external_email:
                # ENQUEUE THE CC EMAIL
                frappe.enqueue(
                    self.send_external_email,
                    queue='short',
                    email=cc.external_email,
                    name=cc.external_name,
                    remarks=cc.remarks
                )

    def send_external_email(self, email, name, remarks):
        """Sends an email notification with attachments to external users"""
        salutation = f"Dear {name}," if name else "Dear Sir/Madam,"
        
        message = f"""
        <p>{salutation}</p>
        <p>Please find attached correspondence regarding: <b>{self.subject}</b></p>
        {f"<p><b>Special Remarks/Instructions:</b> {remarks}</p>" if remarks else ""}
        <br>
        <div>{self.letter_body or ''}</div>
        <br>
        <p>Regards,<br>{self.signature or frappe.session.user}</p>
        """

        # Gather file attachments linked to this Outward Dak
        attachments = []
        files = frappe.get_all("File", filters={"attached_to_doctype": "Outward Dak", "attached_to_name": self.name}, fields=["file_url"])
        for f in files:
            attachments.append({"file_url": f.file_url})

        frappe.sendmail(
            recipients=[email],
            subject=self.subject,
            message=message,
            delayed=False,
            attachments=attachments
        )