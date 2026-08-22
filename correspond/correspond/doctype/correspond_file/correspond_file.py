import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe import _
import math
import json
import re

def get_desk(user):
    """Helper to fetch the desk profile for a given user, including department and section[cite: 1]"""
    return frappe.db.get_value(
        "Correspond User Profile", 
        {"user": user}, 
        ["office", "department", "section", "designation"], 
        as_dict=True
    ) or {}

class CorrespondFile(Document):

    def autoname(self):
        if self.is_new():
            user_desk = get_desk(frappe.session.user)
            office = user_desk.get("office")
            dept = user_desk.get("department")
            section = user_desk.get("section")
            
            # 1. Department Abbreviation: First 2 characters uppercased
            if dept:
                dept_name = frappe.db.get_value("Department", dept, "department_name") or dept
                dept_abbr = dept_name[:2].upper()
            else:
                dept_abbr = "DE"
            
            # 2. Office Abbreviation
            if office:
                office_data = frappe.db.get_value("Correspond Office", office, ["office_abbr", "department"], as_dict=True) or {}
                office_abbr = office_data.get("office_abbr") or office
            else:
                office_abbr = "GEN"
            
            # 3. Section Abbreviation (4 chars)
            if section:
                section_abbr = frappe.db.get_value("Correspond Section", section, "section_abbr") or "GENL"
            else:
                section_abbr = "GENL"
            
            # 4. Generate the real sequence and set the document's internal ID
            self.name = make_autoname(f"{dept_abbr}/{office_abbr}/{section_abbr}/.YYYY./.####")
            
            # 5. OVERWRITE the JavaScript preview with the real generated number!
            self.file_number = self.name
            
    def before_insert(self):
        user_desk = get_desk(frappe.session.user)
        self.desk_office = user_desk.get("office")
        self.desk_department = user_desk.get("department")
        self.desk_section = user_desk.get("section")
        self.desk_designation = user_desk.get("designation")
        
        # MUST BE ADDED:
        self.file_owner = frappe.session.user
        self.current_custodian = frappe.session.user
        
        self.file_number = self.name

    def validate(self):
        if self.is_new():
            return
            
        old_custodian = self.db_get('current_custodian')
        if old_custodian and old_custodian != frappe.session.user:
            user_desk = get_desk(frappe.session.user)
            is_new_incumbent = (self.desk_office == user_desk.get("office") and self.desk_designation == user_desk.get("designation"))
            is_admin = ("System Manager" in frappe.get_roles(frappe.session.user))
            
            if not is_new_incumbent and not is_admin:
                frappe.throw("Action Denied: You cannot modify a file that is no longer at your desk.")

    def has_permission(self, permtype="read", user=None, **kwargs):
        if not user:
            user = frappe.session.user
            
        if "System Manager" in frappe.get_roles(user):
            return True

        user_desk = get_desk(user)
        u_office = user_desk.get("office")
        u_desig = user_desk.get("designation")
        
        if self.desk_office and u_office == self.desk_office:
            office_admin = frappe.db.get_value("Correspond Office", self.desk_office, "office_admin")
            if office_admin == user:
                return True
            
        if permtype == "create":
            return any(r in ["System Manager", "Correspond User", "Correspond Registry Clerk"] for r in frappe.get_roles(user))
            
        if permtype == "write":
            if self.is_new():
                return any(r in ["System Manager", "Correspond User", "Correspond Registry Clerk"] for r in frappe.get_roles(user))
            
            db_office = frappe.db.get_value("Correspond File", self.name, "desk_office")
            db_desig = frappe.db.get_value("Correspond File", self.name, "desk_designation")
            return (db_office == u_office and db_desig == u_desig)
            
        if permtype == "read":
            if self.is_new():
                return True
                
            if self.desk_office == u_office and self.desk_designation == u_desig:
                return True
                
            has_history = frappe.db.sql("""
                SELECT 1 FROM `tabFile Movement Log`
                WHERE parent = %s AND action_office = %s AND action_designation = %s
            """, (self.name, u_office, u_desig))
            if has_history: return True
                
            master_check = frappe.db.sql("""
                SELECT 1
                FROM `tabAttached Files Log` a
                WHERE a.linked_file = %s
                AND (
                    EXISTS (SELECT 1 FROM `tabCorrespond File` m WHERE m.name = a.parent AND m.desk_office = %s AND m.desk_designation = %s)
                    OR
                    EXISTS (SELECT 1 FROM `tabFile Movement Log` fml WHERE fml.parent = a.parent AND fml.action_office = %s AND fml.action_designation = %s)
                )
            """, (self.name, u_office, u_desig, u_office, u_desig))
            if master_check: return True
            return False
        return None
        
@frappe.whitelist()
def get_file_and_references(file_name, note_page=1, active_tab='#tab-toc'):
    user = frappe.session.user
    all_files = [file_name]
    note_page = int(note_page)

    user_desk = get_desk(user)
    u_office = user_desk.get("office")
    u_desig = user_desk.get("designation")

    file_doc = frappe.get_doc("Correspond File", file_name)
    is_custodian = (file_doc.desk_office == u_office and file_doc.desk_designation == u_desig)
    
    is_master_custodian = False
    if file_doc.is_attached and file_doc.attached_to:
        master_doc = frappe.db.get_value("Correspond File", file_doc.attached_to, ["desk_office", "desk_designation"], as_dict=True)
        if master_doc and master_doc.desk_office == u_office and master_doc.desk_designation == u_desig:
            is_master_custodian = True

    is_admin = ("System Manager" in frappe.get_roles(user))
    if file_doc.desk_office and u_office == file_doc.desk_office:
        if frappe.db.get_value("Correspond Office", file_doc.desk_office, "office_admin") == user:
            is_admin = True

    has_full_access = is_custodian or is_master_custodian or is_admin
    is_historical = False
    cutoff_date = None

    if not has_full_access:
        valid_cutoffs = []
        direct_log = frappe.db.sql("""
            SELECT MAX(timestamp) FROM `tabFile Movement Log` 
            WHERE parent = %s AND action_office = %s AND action_designation = %s
        """, (file_name, u_office, u_desig))
        if direct_log and direct_log[0][0]:
            valid_cutoffs.append(direct_log[0][0])

        master_records = frappe.db.sql("""
            SELECT a.parent AS master_file, a.detached_on, m.desk_office, m.desk_designation,
                (SELECT MAX(timestamp) FROM `tabFile Movement Log` WHERE parent = a.parent AND action_office = %s AND action_designation = %s) AS user_master_timestamp
            FROM `tabAttached Files Log` a
            JOIN `tabCorrespond File` m ON a.parent = m.name
            WHERE a.linked_file = %s
        """, (u_office, u_desig, file_name), as_dict=True)

        for rec in master_records:
            if rec.desk_office == u_office and rec.desk_designation == u_desig:
                if rec.detached_on: valid_cutoffs.append(rec.detached_on)
            elif rec.user_master_timestamp:
                effective_cutoff = min(rec.detached_on, rec.user_master_timestamp) if rec.detached_on else rec.user_master_timestamp
                valid_cutoffs.append(effective_cutoff)

        if valid_cutoffs:
            is_historical = True
            cutoff_date = max(valid_cutoffs)
        else:
            frappe.throw(_("Access Denied: Your desk is not in the routing history of this file."), frappe.PermissionError)

    meta = frappe.get_meta("Correspond File")
    child_tables = [df.options for df in meta.get_table_fields() if df.fieldtype == "Table"]

    for table in child_tables:
        child_meta = frappe.get_meta(table)
        link_fields = [df.fieldname for df in child_meta.fields if df.fieldtype == "Link" and df.options in ["Correspond File", "File"]]
        if link_fields:
            rows = frappe.get_all(table, filters={"parent": file_name}, fields=link_fields)
            for r in rows:
                for lf in link_fields:
                    val = r.get(lf)
                    if val and val not in all_files:
                        all_files.append(val)

    notes = frappe.get_all("Correspond Noting", filters={"file": ["in", all_files]}, fields=["name", "note_details", "file", "docstatus", "owner", "status", "creation"], order_by="creation asc")
    
    draft_daks, final_daks = [], []
    outward_links = frappe.get_all("Outward Dak Linked File", filters={"file": ["in", all_files]}, pluck="parent")
    outward_primaries = frappe.get_all("Outward Dak", filters={"primary_file": ["in", all_files]}, pluck="name")
    outward_names = list(set(outward_links + outward_primaries))
    
    if outward_names:
        outward_data = frappe.get_all("Outward Dak", filters={"name": ["in", outward_names]}, fields=["name", "subject", "modified as sort_date", "primary_file", "docstatus", "status", "creation"])
        for d in outward_data:
            label = "Outward Dak" if d.get("primary_file") == file_name else "Linked Outward"
            has_attach = bool(frappe.db.exists("File", {"attached_to_doctype": "Outward Dak", "attached_to_name": d.name}))
            dak_info = {"name": d.name, "subject": d.subject, "doctype": "Outward Dak", "label": label, "sort_date": d.sort_date, "has_attachments": has_attach, "is_draft": d.docstatus == 0, "status": d.status}
            if dak_info["is_draft"]: draft_daks.append(dak_info)
            else: final_daks.append(dak_info)

    inward_links = frappe.get_all("Inward Dak Linked File", filters={"file": ["in", all_files]}, fields=["parent", "creation as sort_date"])
    if inward_links:
        inward_parents = list(set([d.parent for d in inward_links]))
        inward_data = frappe.get_all("Inward Dak", filters={"name": ["in", inward_parents]}, fields=["name", "subject", "docstatus", "status"])
        inward_dict = {d.name: d for d in inward_data}
        for link in inward_links:
            if link.parent in inward_dict:
                doc_data = inward_dict[link.parent]
                has_attach = bool(frappe.db.exists("File", {"attached_to_doctype": "Inward Dak", "attached_to_name": link.parent}))
                dak_info = {"name": link.parent, "subject": doc_data.subject, "doctype": "Inward Dak", "label": "Inward Dak", "sort_date": link.sort_date, "has_attachments": has_attach, "is_draft": doc_data.docstatus == 0, "status": doc_data.status}
                if dak_info["is_draft"]: draft_daks.append(dak_info)
                else: final_daks.append(dak_info)

    if is_historical and cutoff_date:
        notes = [n for n in notes if n.creation <= cutoff_date]
        draft_daks = [d for d in draft_daks if d.get('sort_date') and d.get('sort_date') <= cutoff_date]
        final_daks = [d for d in final_daks if d.get('sort_date') and d.get('sort_date') <= cutoff_date]

    final_daks = sorted(final_daks, key=lambda k: k.get("sort_date") or "", reverse=False)
    for index, dak in enumerate(final_daks): dak["serial_no"] = index + 1
    draft_daks = sorted(draft_daks, key=lambda k: k.get("sort_date") or "", reverse=False)

    has_draft = any(n.docstatus == 0 for n in notes)
    page_size = 5
    total_notes = len(notes)
    max_pages = math.ceil(total_notes / page_size) if total_notes > 0 else 1
    if note_page > max_pages: note_page = max_pages
    if note_page < 1: note_page = 1
    start_idx = (note_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_notes)
    paginated_notes = notes[start_idx:end_idx]
    submitted_notes = [n for n in notes if n.docstatus == 1]

    green_sheet_html = render_green_sheet(paginated_notes, start_idx, end_idx, total_notes, has_draft, is_historical)
    dak_tabs_html = render_dak_tabs(submitted_notes, final_daks, draft_daks, active_tab, is_historical)

    return {
        "green_sheet_html": green_sheet_html,
        "dak_tabs_html": dak_tabs_html,
        "is_historical": is_historical,
        "cutoff_date": cutoff_date,
        "has_draft": has_draft
    }

def render_green_sheet(paginated_notes, start_idx, end_idx, total_notes, has_draft, is_snapshot):
    context = {"notes": paginated_notes, "start_idx": start_idx, "end_idx": end_idx, "total_notes": total_notes, "has_draft": has_draft, "is_snapshot": is_snapshot}
    return frappe.render_template("correspond/templates/green_sheet.html", context)

def render_dak_tabs(submitted_notes, final_daks, draft_daks, active_tab, is_snapshot):
    context = {"submitted_notes": submitted_notes, "final_daks": final_daks, "draft_daks": draft_daks, "active_tab": active_tab, "is_snapshot": is_snapshot}
    return frappe.render_template("correspond/templates/dak_tabs.html", context)
    
@frappe.whitelist()
def set_note_state(note_name, status):
    doc = frappe.get_doc("Correspond Noting", note_name)
    if doc.docstatus == 0:
        doc.status = status
        doc.save(ignore_permissions=True)
    return {"status": "success"}

@frappe.whitelist()
def forward_file(file_name, recipient, remarks):
    user = frappe.session.user
    doc = frappe.get_doc("Correspond File", file_name)
    
    sender_desk = get_desk(user)
    recipient_desk = get_desk(recipient)
    rec_office = recipient_desk.get("office")
    rec_dept = recipient_desk.get("department")
    rec_section = recipient_desk.get("section")
    
    doc.current_custodian = recipient
    doc.desk_office = rec_office
    doc.desk_department = rec_dept
    doc.desk_section = rec_section
    doc.desk_designation = recipient_desk.get("designation")

    # --- PERMISSION FIX: Auto-submit notes bypassing user role restrictions ---
    green_notes = frappe.get_all("Correspond Noting", filters={"file": file_name, "docstatus": 0, "status": "Green"}, pluck="name")
    for note_name in green_notes:
        note_doc = frappe.get_doc("Correspond Noting", note_name)
        note_doc.flags.ignore_permissions = True
        note_doc.submit()

    row_data = {
        "timestamp": frappe.utils.now_datetime(),
        "moved_from": user, "moved_to": recipient, "action": "Forwarded", "remarks": remarks,
        "action_office": sender_desk.get("office"), "action_designation": sender_desk.get("designation")
    }

    doc.append("movement_log", row_data)
    doc.save(ignore_permissions=True)

    for attached in doc.get("attached_files", []):
        if attached.status == "Active":
            child_file = frappe.get_doc("Correspond File", attached.linked_file)
            child_file.current_custodian = recipient 
            child_file.desk_office = rec_office
            child_file.desk_department = rec_dept
            child_file.desk_section = rec_section
            child_file.desk_designation = recipient_desk.get("designation")
            child_log = row_data.copy()
            child_log["remarks"] = f"[Moved with Master File {file_name}] {remarks}"
            child_file.append("movement_log", child_log)
            child_file.save(ignore_permissions=True)

    return {"status": "success"}

@frappe.whitelist()
def attach_sub_file(master_file, child_file):
    user = frappe.session.user
    master = frappe.get_doc("Correspond File", master_file)
    child = frappe.get_doc("Correspond File", child_file)
    user_desk = get_desk(user)

    if master.desk_office != user_desk.get("office") or master.desk_designation != user_desk.get("designation"):
        if "System Manager" not in frappe.get_roles(user):
            frappe.throw("You cannot attach files to a folder that is not at your desk.")
            
    if child.is_attached: frappe.throw(f"File {child_file} is already attached to {child.attached_to}.")
    if master.is_attached: frappe.throw("You cannot attach sub-files into a file that is currently attached elsewhere.")

    child.is_attached = 1
    child.attached_to = master_file
    child.current_custodian = master.current_custodian
    child.desk_office = master.desk_office
    child.desk_department = master.desk_department
    child.desk_section = master.desk_section
    child.desk_designation = master.desk_designation
    child.save(ignore_permissions=True)

    frappe.get_doc({
        "doctype": "File Movement Log", "parent": child_file, "parenttype": "Correspond File",
        "parentfield": "movement_log", "timestamp": frappe.utils.now_datetime(),
        "action": "Attached", "remarks": f"Attached to Master File: {master_file}", "moved_from": user,
        "action_office": user_desk.get("office"), "action_designation": user_desk.get("designation")
    }).insert(ignore_permissions=True)
    
    master.append("movement_log", {
        "timestamp": frappe.utils.now_datetime(), "action": "Attached",
        "remarks": f"Attached Sub-file: {child_file}", "moved_from": user,
        "action_office": user_desk.get("office"), "action_designation": user_desk.get("designation")
    })

    existing_row = next((r for r in master.attached_files if r.linked_file == child_file), None)
    if existing_row:
        existing_row.status = "Active"
        existing_row.attached_on = frappe.utils.now_datetime()
        existing_row.detached_on = None
    else:
        master.append("attached_files", {"linked_file": child_file, "status": "Active", "attached_on": frappe.utils.now_datetime()})

    master.has_active_attachments = 1 
    master.save(ignore_permissions=True)
    return {"status": "success"}

@frappe.whitelist()
def detach_sub_files(master_file, child_files_json):
    user = frappe.session.user
    master = frappe.get_doc("Correspond File", master_file)
    child_files = json.loads(child_files_json)
    user_desk = get_desk(user)

    if master.desk_office != user_desk.get("office") or master.desk_designation != user_desk.get("designation"):
        if "System Manager" not in frappe.get_roles(user):
            frappe.throw("You cannot detach files from a folder that is not at your desk.")

    for row in master.attached_files:
        if row.linked_file in child_files and row.status == "Active":
            row.status = "Detached"
            row.detached_on = frappe.utils.now_datetime()
            
            child = frappe.get_doc("Correspond File", row.linked_file)
            child.is_attached = 0
            child.attached_to = None
            child.save(ignore_permissions=True)

            frappe.get_doc({
                "doctype": "File Movement Log", "parent": row.linked_file, "parenttype": "Correspond File",
                "parentfield": "movement_log", "timestamp": frappe.utils.now_datetime(),
                "action": "Detached", "remarks": f"Detached from Master File: {master_file}", "moved_from": user,
                "action_office": user_desk.get("office"), "action_designation": user_desk.get("designation")
            }).insert(ignore_permissions=True)

            master.append("movement_log", {
                "timestamp": frappe.utils.now_datetime(), "action": "Detached",
                "remarks": f"Detached Sub-file: {row.linked_file}", "moved_from": user,
                "action_office": user_desk.get("office"), "action_designation": user_desk.get("designation")
            })

    master.has_active_attachments = 1 if any(r.status == "Active" for r in master.attached_files) else 0
    master.save(ignore_permissions=True)
    return {"status": "success"}

def verify_active_custody(file_name):
    user = frappe.session.user
    doc = frappe.get_doc("Correspond File", file_name)
    user_desk = get_desk(user)
    
    if doc.desk_office != user_desk.get("office") or doc.desk_designation != user_desk.get("designation"):
        if "System Manager" not in frappe.get_roles(user):
            frappe.throw("Action Denied: This file has been moved and is no longer at your desk.")

@frappe.whitelist()
def add_draft_note(file_name, note_details):
    verify_active_custody(file_name)
    frappe.get_doc({"doctype": "Correspond Noting", "file": file_name, "note_details": note_details, "status": "Yellow"}).insert(ignore_permissions=True)
    return {"status": "success"}

@frappe.whitelist()
def update_draft_note(file_name, note_name, note_details):
    verify_active_custody(file_name)
    frappe.db.set_value('Correspond Noting', note_name, 'note_details', note_details)
    return {"status": "success"}

@frappe.whitelist()
def add_draft_dak(file_name, dak_data):
    verify_active_custody(file_name)
    data = json.loads(dak_data)
    doc = frappe.new_doc("Outward Dak")
    doc.primary_file = file_name
    doc.update(data)
    doc.insert(ignore_permissions=True)
    return {"status": "success"}

@frappe.whitelist()
def update_draft_dak(file_name, dak_name, dak_data, submit_doc=False):
    verify_active_custody(file_name)
    data = json.loads(dak_data)
    dak = frappe.get_doc("Outward Dak", dak_name)
    dak.update(data)
    dak.save(ignore_permissions=True)
    if str(submit_doc).lower() == 'true': dak.submit()
    return {"status": "success"}

@frappe.whitelist()
def get_reference_lookup_data(file_name):
    verify_active_custody(file_name) 
    all_files_list = [file_name]
    current_subj = frappe.db.get_value("Correspond File", file_name, "subject") or "Untitled"
    file_opts = [{"value": file_name, "label": f"{file_name}: {current_subj} (Current File)"}]
    
    for table in [df.options for df in frappe.get_meta("Correspond File").get_table_fields() if df.fieldtype == "Table"]:
        child_meta = frappe.get_meta(table)
        link_fields = [f.fieldname for f in child_meta.fields if f.fieldtype == "Link" and f.options in ["Correspond File", "File"]]
        if link_fields:
            for r in frappe.get_all(table, filters={"parent": file_name}, fields=link_fields):
                for lf in link_fields:
                    val = r.get(lf)
                    if val and val not in all_files_list:
                        all_files_list.append(val)
                        target_doctype = next((f.options for f in child_meta.fields if f.fieldname == lf), "Correspond File")
                        att_subj = frappe.db.get_value(target_doctype, val, "subject") or "Untitled"
                        file_opts.append({"value": val, "label": f"{val}: {att_subj} (Attached File)"})

    notes = frappe.get_all("Correspond Noting", filters={"file": ["in", all_files_list]}, fields=["name", "note_details", "file"], order_by="creation asc")
    note_opts = [{"file": n.file, "label": f"Note #{i+1}: {(re.sub('<[^<]+?>', '', n.note_details or '')[:35] + '...') if len(re.sub('<[^<]+?>', '', n.note_details or '')) > 35 else re.sub('<[^<]+?>', '', n.note_details or '')} ({n.name})", "value": n.name} for i, n in enumerate(notes)]

    dak_opts = [{"file": d.primary_file, "label": f"Outward Dak: {d.name} - {d.subject}", "value": d.name} for d in frappe.get_all("Outward Dak", filters={"primary_file": ["in", all_files_list]}, fields=["name", "subject", "primary_file"])]
    dak_opts += [{"file": d.file, "label": f"Inward Dak: {d.parent} - {frappe.db.get_value('Inward Dak', d.parent, 'subject') or 'Untitled'}", "value": d.parent} for d in frappe.get_all("Inward Dak Linked File", filters={"file": ["in", all_files_list]}, fields=["parent", "file"])]

    return {"file_opts": file_opts, "notes": note_opts, "daks": dak_opts}
