import frappe
from frappe import _
from frappe.model.document import Document

class CorrespondDeskProfile(Document):
    def before_insert(self):
        # Prevent non-admin users from creating new desk profiles
        if "System Manager" not in frappe.get_roles():
            frappe.throw(_("Only System Managers can create new Desk Profiles."))

    def validate(self):
        # Enforce field-level restriction for non-admin users
        if "System Manager" not in frappe.get_roles():
            doc_before = self.get_doc_before_save()
            if doc_before:
                # Identify all fields except the signature block
                meta_fields = [
                    f.fieldname for f in self.meta.fields 
                    if f.fieldname != 'signature_block' 
                    and f.fieldtype not in ('Section Break', 'Column Break', 'HTML', 'Button', 'Read Only')
                ]
                
                # Check if any restricted field was modified
                for field in meta_fields:
                    if self.get(field) != doc_before.get(field):
                        frappe.throw(_("You are only permitted to edit the Signature Block."))

    def on_trash(self):
        # 1. Check if this desk has ever sent or received a file in the File Movement Log
        has_movements = (
            frappe.db.exists("File Movement Log", {"sender_desk": self.name}) or
            frappe.db.exists("File Movement Log", {"recipient_desk": self.name})
        )
        
        # 2. Check if any file is currently sitting at this desk
        has_active_files = frappe.db.exists("Correspond File", {"current_custodian": self.name})

        if has_movements or has_active_files:
            frappe.throw(
                _("Cannot delete Desk Profile '{0}' because it contains active files or historical File Movement Logs. Please mark it as Disabled instead.").format(self.name)
            )
            
    def autoname(self):
        # 1. Clean the Department (Removes the " - KVC3" suffix automatically)
        clean_dept = self.department.split(" - ")[0].strip() if self.department else None
        
        # 2. Gather the parts
        parts = [
            self.office.strip() if self.office else None,
            clean_dept,
            self.section.strip() if self.section else None
        ]
        
        # 3. Format the designation with the seat number ONLY if a seat number exists
        if self.designation:
            if self.seat_number:
                desig_part = f"{self.designation.strip()}-{self.seat_number.strip()}"
            else:
                desig_part = self.designation.strip()
            parts.append(desig_part)
        
        # 4. Join them together with slashes
        self.name = "/".join(filter(None, parts))

    def before_save(self):
        # 1. Gather human-readable labels from linked masters
        office_name = frappe.db.get_value("Correspond Office", self.office, "office_name") or self.office
        
        # Fetch the human-readable department name from the Department DocType
        dept_name = None
        if self.department:
            dept_name = frappe.db.get_value("Department", self.department, "department_name")
        dept_label = dept_name or self.department or "General"
        
        section_name = frappe.db.get_value("Correspond Section", self.section, "section_name") or self.section
        
        # 2. Fetch the full designation name from the linked Designation DocType
        full_desig = None
        if self.designation:
            full_desig = frappe.db.get_value("Designation", self.designation, "custom_designation_full_name")
        
        desig_label = full_desig or self.designation or "Desk"
        
        if self.seat_number:
            desig_part = f"{desig_label.strip()}-{self.seat_number.strip()}"
        else:
            desig_part = desig_label.strip()
        
        # 3. Format cleanly with the correct Department Name
        self.desk_title = f"{desig_part}, {section_name}, {dept_label}, {office_name}"


def get_permission_query_conditions(user):
    """Restrict users to see only their own desk profile record in list views."""
    if not user:
        user = frappe.session.user
    
    if "System Manager" in frappe.get_roles(user):
        return None
        
    return f"`tabCorrespond Desk Profile`.user = {frappe.db.escape(user)}"


def has_permission(doc, ptype, user):
    """Prevent users from opening other users' profiles via direct URL manipulation."""
    if not user:
        user = frappe.session.user
        
    if "System Manager" in frappe.get_roles(user):
        return True
        
    return doc.user == user