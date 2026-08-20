import frappe
from frappe.model.document import Document

class OutwardDak(Document):
    def on_submit(self):
        self.dispatch_dak()

    def dispatch_dak(self):
        # 1. Process Primary Recipient (To)
        if self.recipient_type == "Internal User" and self.internal_recipient:
            self.create_inward_dak(
                recipient=self.internal_recipient,
                remarks=f"Primary Outward Reference: {self.name}"
            )
        elif self.recipient_type == "External User" and self.receiver_email:
            # ENQUEUE THE EMAIL INSTEAD OF CALLING DIRECTLY
            frappe.enqueue(
                self.send_external_email,
                queue='short',
                email=self.receiver_email,
                name=self.receiver,
                remarks="Primary Dispatch"
            )

        # 2. Process CC List (Copy To)
        for cc in (self.cc_list or []):
            if cc.recipient_type == "Internal User" and cc.internal_user:
                self.create_inward_dak(
                    recipient=cc.internal_user,
                    remarks=f"[CC Remarks]: {cc.remarks or 'None'}"
                )
            elif cc.recipient_type == "External User" and cc.external_email:
                # ENQUEUE THE CC EMAIL
                frappe.enqueue(
                    self.send_external_email,
                    queue='short',
                    email=cc.external_email,
                    name=cc.external_name,
                    remarks=cc.remarks
                )

    def create_inward_dak(self, recipient, remarks):
        """Creates an Inward Dak entry for an internal system user"""
        inward = frappe.get_doc({
            "doctype": "Inward Dak",
            "subject": self.subject,
            "sender_name": f"Internal Dispatch ({frappe.session.user})", # Mapped to your Sender Name field
            "receipt_mode": "Internal Transfer", # Automatically sets the mode
            "recipient": recipient,            # <--- MAPPED TO YOUR EXISTING FIELD
            "remarks": remarks,
            "description": self.letter_body,     # Mapped to your Description field
            "status": "Draft"
        })
        inward.insert(ignore_permissions=True)
        self.copy_attachments_to_doc(inward)

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
            file_path = frappe.get_site_path() + f.file_url.lstrip(".")
            attachments.append({"file_url": f.file_url})

        frappe.sendmail(
            recipients=[email],
            subject=self.subject,
            message=message,
            delayed=False
        )

    def copy_attachments_to_doc(self, target_doc):
        """Copies file attachments from Outward Dak to the newly created Inward Dak"""
        files = frappe.get_all("File", filters={"attached_to_doctype": "Outward Dak", "attached_to_name": self.name})
        for f in files:
            file_doc = frappe.get_doc("File", f.name)
            frappe.get_doc({
                "doctype": "File",
                "file_url": file_doc.file_url,
                "file_name": file_doc.file_name,
                "attached_to_doctype": target_doc.doctype,
                "attached_to_name": target_doc.name,
                "is_private": file_doc.is_private
            }).insert(ignore_permissions=True)