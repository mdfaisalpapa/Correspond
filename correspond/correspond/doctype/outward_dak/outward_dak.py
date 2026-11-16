import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import now_datetime

class OutwardDak(Document):
    def before_insert(self):
        if not self.status:
            self.status = "Draft"

    def on_submit(self):
        if not self.dispatch_register_no:
            self.generate_dispatch_number()
        self.status = "Dispatched"
        self.dispatch_dak()

    def generate_dispatch_number(self):
        """Generates a formal Central Secretariat Dispatch Register Number."""
        prefix = "DISP"
        if self.primary_file and frappe.db.exists("Correspond File", self.primary_file):
            file_doc = frappe.get_doc("Correspond File", self.primary_file)
            section = file_doc.desk_section or "GENL"
            prefix = f"{section}/OUT"
        self.dispatch_register_no = make_autoname(f"{prefix}/.YYYY./.#####")

    def dispatch_dak(self):
        # 1. Process Primary Recipient (To)
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
        <p><b>DFA Type:</b> {self.dfa_type or 'Official Correspondence'}</p>
        <p><b>Dispatch Number:</b> {self.dispatch_register_no or self.name}</p>
        {f"<p><b>Special Remarks/Instructions:</b> {remarks}</p>" if remarks else ""}
        <br>
        <div>{self.letter_body or ''}</div>
        <br>
        <p>Regards,<br>{self.sender or frappe.session.user}</p>
        """

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

# =========================================================================
# SPRINT 2: DFA APPROVAL WORKFLOW APIS
# =========================================================================

@frappe.whitelist()
def submit_dfa_for_approval(dak_name):
    """Submits a draft outward dak for supervisory approval."""
    doc = frappe.get_doc("Outward Dak", dak_name)
    if doc.status not in ["Draft", "Drafting"]:
        frappe.throw(_("Only Draft correspondence can be submitted for approval."))
    
    doc.status = "Submitted for Approval"
    doc.save(ignore_permissions=True)
    return {"status": "success", "message": _("DFA submitted for approval.")}

@frappe.whitelist()
def approve_dfa(dak_name):
    """Approves a fair draft DFA, locking edits and transitioning to Approved."""
    user = frappe.session.user
    doc = frappe.get_doc("Outward Dak", dak_name)
    
    # Identify approver desk
    active_desks = frappe.get_all("Correspond Desk Profile", filters={"user": user, "is_abolished": 0, "disabled": 0}, pluck="name")
    approver_desk = active_desks[0] if active_desks else None
    
    doc.status = "Approved"
    doc.approved_by_desk = approver_desk
    doc.approved_on = now_datetime()
    doc.save(ignore_permissions=True)
    return {"status": "success", "message": _("DFA approved successfully.")}

@frappe.whitelist()
def mark_dfa_for_dispatch(dak_name, dispatch_mode="Email", consignment_number=""):
    """Transitions approved DFA to Marked for Dispatch and reserves a Dispatch Register Number."""
    doc = frappe.get_doc("Outward Dak", dak_name)
    if doc.status not in ["Approved", "Submitted for Approval", "Draft"]:
        frappe.throw(_("Invalid status transition to Dispatch."))

    doc.dispatch_mode = dispatch_mode
    doc.consignment_number = consignment_number
    if not doc.dispatch_register_no:
        doc.generate_dispatch_number()
    doc.status = "Marked for Dispatch"
    doc.save(ignore_permissions=True)
    return {"status": "success", "dispatch_no": doc.dispatch_register_no}

# =========================================================================
# BACKEND SECURITY FAIL-SAFE
# =========================================================================
def get_permission_query_conditions(user):
    if not user: 
        user = frappe.session.user
        
    if "System Manager" in frappe.get_roles(user):
        return ""

    desks = frappe.get_all(
        "Correspond Desk Profile", 
        filters={"user": user}, 
        pluck="name"
    )
    
    if not desks:
        return "1=0"
        
    escaped_desks = ", ".join([frappe.db.escape(d) for d in desks])
    return f"`tabOutward Dak`.sender IN ({escaped_desks})"
