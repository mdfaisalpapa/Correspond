import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe import _
import math
import json
import re

def get_primary_desk(user):
    """Returns the user's primary active desk profile (Used for stamping sender actions)"""
    return frappe.db.get_value(
        "Correspond Desk Profile", 
        {"user": user, "is_abolished": 0}, 
        ["name", "office", "department", "section", "designation"], 
        as_dict=True,
        order_by="creation asc"
    ) or {}

def get_authorized_desks(user):
    """Returns ALL desk profiles assigned to this user (Primary + Additional Charge + Abolished Archives)"""
    return frappe.get_all(
        "Correspond Desk Profile", 
        filters={"user": user}, 
        fields=["name", "office", "department", "section", "designation"]
    )

@frappe.whitelist()
def is_user_custodian(file_name):
    """API for the frontend to check if the user holds the active desk for a file."""
    user = frappe.session.user
    if "System Manager" in frappe.get_roles(user):
        return True
    doc = frappe.get_value("Correspond File", file_name, ["desk_office", "desk_designation"], as_dict=True)
    if not doc: return False
    auth_desks = get_authorized_desks(user)
    return any(d.office == doc.desk_office and d.designation == doc.desk_designation for d in auth_desks)

class CorrespondFile(Document):

    def autoname(self):
        if self.is_new():
            user_desk = get_primary_desk(frappe.session.user)
            office = user_desk.get("office")
            dept = user_desk.get("department")
            section = user_desk.get("section")
            
            if dept:
                dept_name = frappe.db.get_value("Department", dept, "department_name") or dept
                dept_abbr = dept_name[:2].upper()
            else:
                dept_abbr = "DE"
            
            if office:
                office_data = frappe.db.get_value("Correspond Office", office, ["office_abbr", "department"], as_dict=True) or {}
                office_abbr = office_data.get("office_abbr") or office
            else:
                office_abbr = "GEN"
            
            if section:
                section_abbr = frappe.db.get_value("Correspond Section", section, "section_abbr") or "GENL"
            else:
                section_abbr = "GENL"
            
            self.name = make_autoname(f"{dept_abbr}/{office_abbr}/{section_abbr}/.YYYY./.####")
            self.file_number = self.name
            
    def before_insert(self):
        user_desk = get_primary_desk(frappe.session.user)
        self.desk_office = user_desk.get("office")
        self.desk_department = user_desk.get("department")
        self.desk_section = user_desk.get("section")
        self.desk_designation = user_desk.get("designation")
        
        self.file_owner = frappe.session.user
        self.current_custodian = frappe.session.user
        self.file_number = self.name

    def validate(self):
        if self.is_new():
            return
            
        old_custodian = self.db_get('current_custodian')
        if old_custodian and old_custodian != frappe.session.user:
            auth_desks = get_authorized_desks(frappe.session.user)
            is_new_incumbent = any(self.desk_office == d.office and self.desk_designation == d.designation for d in auth_desks)
            is_admin = ("System Manager" in frappe.get_roles(frappe.session.user))
            
            if not is_new_incumbent and not is_admin:
                frappe.throw("Action Denied: You cannot modify a file that is no longer at your desk.")

    def has_permission(self, permtype="read", user=None, **kwargs):
        if not user: user = frappe.session.user
            
        if "System Manager" in frappe.get_roles(user): return True

        auth_desks = get_authorized_desks(user)
        auth_desk_names = [d.name for d in auth_desks]
        
        if self.desk_office and any(d.office == self.desk_office for d in auth_desks):
            office_admin = frappe.db.get_value("Correspond Office", self.desk_office, "office_admin")
            if office_admin == user: return True
            
        if permtype == "create":
            return any(r in ["System Manager", "Correspond User", "Correspond Registry Clerk"] for r in frappe.get_roles(user))
            
        if permtype == "write":
            if self.is_new():
                return any(r in ["System Manager", "Correspond User", "Correspond Registry Clerk"] for r in frappe.get_roles(user))
            
            db_office = frappe.db.get_value("Correspond File", self.name, "desk_office")
            db_desig = frappe.db.get_value("Correspond File", self.name, "desk_designation")
            return any(d.office == db_office and d.designation == db_desig for d in auth_desks)
            
        if permtype == "read":
            if self.is_new(): return True
                
            if any(self.desk_office == d.office and self.desk_designation == d.designation for d in auth_desks):
                return True
                
            if auth_desk_names:
                format_strings = ','.join(['%s'] * len(auth_desk_names))
                has_history = frappe.db.sql(f"""
                    SELECT 1 FROM `tabFile Movement Log`
                    WHERE parent = %s AND (sender_desk IN ({format_strings}) OR recipient_desk IN ({format_strings}))
                """, tuple([self.name] + auth_desk_names + auth_desk_names))
                if has_history: return True
                
                master_check = frappe.db.sql(f"""
                    SELECT 1
                    FROM `tabAttached Files Log` a
                    WHERE a.linked_file = %s
                    AND (
                        EXISTS (SELECT 1 FROM `tabCorrespond File` m WHERE m.name = a.parent AND m.desk_office IN ({format_strings}) AND m.desk_designation IN ({format_strings}))
                        OR
                        EXISTS (SELECT 1 FROM `tabFile Movement Log` fml WHERE fml.parent = a.parent AND (fml.sender_desk IN ({format_strings}) OR fml.recipient_desk IN ({format_strings})))
                    )
                """, tuple([self.name] + [d.office for d in auth_desks] + [d.designation for d in auth_desks] + auth_desk_names + auth_desk_names))
                if master_check: return True
                
            return False
        return None

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_forward_recipients(doctype, txt, searchfield, start, page_len, filters):
    return frappe.db.sql("""
        SELECT name, CONCAT(user, ' (', designation, ' - ', section, ')') AS description
        FROM `tabCorrespond Desk Profile`
        WHERE user != %s 
          AND ifnull(is_abolished, 0) = 0
          AND (name LIKE %s OR user LIKE %s OR designation LIKE %s OR section LIKE %s)
        LIMIT %s, %s
    """, (frappe.session.user, f"%{txt}%", f"%{txt}%", f"%{txt}%", f"%{txt}%", start, page_len))
        
@frappe.whitelist()
def get_file_and_references(file_name, note_page=1, active_tab='#tab-toc'):
    user = frappe.session.user
    all_files = [file_name]
    note_page = int(note_page)

    auth_desks = get_authorized_desks(user)
    auth_desk_names = [d.name for d in auth_desks]

    file_doc = frappe.get_doc("Correspond File", file_name)
    is_custodian = any(file_doc.desk_office == d.office and file_doc.desk_designation == d.designation for d in auth_desks)
    
    is_master_custodian = False
    if file_doc.is_attached and file_doc.attached_to:
        master_doc = frappe.db.get_value("Correspond File", file_doc.attached_to, ["desk_office", "desk_designation"], as_dict=True)
        if master_doc and any(master_doc.desk_office == d.office and master_doc.desk_designation == d.designation for d in auth_desks):
            is_master_custodian = True

    is_admin = ("System Manager" in frappe.get_roles(user))
    if file_doc.desk_office and any(d.office == file_doc.desk_office for d in auth_desks):
        if frappe.db.get_value("Correspond Office", file_doc.desk_office, "office_admin") == user:
            is_admin = True

    has_full_access = is_custodian or is_master_custodian or is_admin
    is_historical = False
    cutoff_date = None

    if not has_full_access:
        valid_cutoffs = []
        if auth_desk_names:
            format_strings = ','.join(['%s'] * len(auth_desk_names))
            direct_log = frappe.db.sql(f"""
                SELECT MAX(timestamp) FROM `tabFile Movement Log` 
                WHERE parent = %s AND (sender_desk IN ({format_strings}) OR recipient_desk IN ({format_strings}))
            """, tuple([file_name] + auth_desk_names + auth_desk_names))
            
            if direct_log and direct_log[0][0]:
                valid_cutoffs.append(direct_log[0][0])

            master_records = frappe.db.sql(f"""
                SELECT a.parent AS master_file, a.detached_on, m.desk_office, m.desk_designation,
                    (SELECT MAX(timestamp) FROM `tabFile Movement Log` WHERE parent = a.parent AND (sender_desk IN ({format_strings}) OR recipient_desk IN ({format_strings}))) AS user_master_timestamp
                FROM `tabAttached Files Log` a
                JOIN `tabCorrespond File` m ON a.parent = m.name
                WHERE a.linked_file = %s
            """, tuple(auth_desk_names + auth_desk_names + [file_name]), as_dict=True)

            for rec in master_records:
                if any(rec.desk_office == d.office and rec.desk_designation == d.designation for d in auth_desks):
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
def forward_file(file_name, recipient_profile, remarks):
    user = frappe.session.user
    doc = frappe.get_doc("Correspond File", file_name)
    
    sender_desk = get_primary_desk(user)
    target_desk = frappe.get_doc("Correspond Desk Profile", recipient_profile)
    
    recipient_user = target_desk.user
    rec_office = target_desk.office
    rec_dept = target_desk.department
    rec_section = target_desk.section
    rec_desig = target_desk.designation
    
    doc.current_custodian = recipient_user
    doc.desk_office = rec_office
    doc.desk_department = rec_dept
    doc.desk_section = rec_section
    doc.desk_designation = rec_desig

    green_notes = frappe.get_all("Correspond Noting", filters={"file": file_name, "docstatus": 0, "status": "Green"}, pluck="name")
    for note_name in green_notes:
        note_doc = frappe.get_doc("Correspond Noting", note_name)
        note_doc.flags.ignore_permissions = True
        note_doc.submit()

    row_data = {
        "timestamp": frappe.utils.now_datetime(),
        "moved_from": user, 
        "moved_to": recipient_user, 
        "action": "Forwarded", 
        "remarks": remarks,
        "sender_desk": sender_desk.get("name"),
        "recipient_desk": recipient_profile
    }

    doc.append("movement_log", row_data)
    doc.save(ignore_permissions=True)

    for attached in doc.get("attached_files", []):
        if attached.status == "Active":
            child_file = frappe.get_doc("Correspond File", attached.linked_file)
            child_file.current_custodian = recipient_user 
            child_file.desk_office = rec_office
            child_file.desk_department = rec_dept
            child_file.desk_section = rec_section
            child_file.desk_designation = rec_desig
            child_log = row_data.copy()
            child_log["remarks"] = f"[Moved with Master File {file_name}] {remarks}"
            child_file.append("movement_log", child_log)
            child_file.save(ignore_permissions=True)

    return {"status": "success"}

@frappe.whitelist()
def bulk_forward_files(file_names, recipient_profile, remarks):
    """Bulk forwards multiple files to a new desk profile."""
    files = json.loads(file_names)
    success_count = 0
    
    for f_name in files:
        verify_active_custody(f_name)
        forward_file(f_name, recipient_profile, remarks)
        success_count += 1
        
    return {"status": "success", "count": success_count}

@frappe.whitelist()
def attach_sub_file(master_file, child_file):
    user = frappe.session.user
    master = frappe.get_doc("Correspond File", master_file)
    child = frappe.get_doc("Correspond File", child_file)
    user_desks = get_authorized_desks(user)

    if not any(master.desk_office == d.office and master.desk_designation == d.designation for d in user_desks):
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

    primary_desk = get_primary_desk(user)
    frappe.get_doc({
        "doctype": "File Movement Log", "parent": child_file, "parenttype": "Correspond File",
        "parentfield": "movement_log", "timestamp": frappe.utils.now_datetime(),
        "action": "Attached", "remarks": f"Attached to Master File: {master_file}", "moved_from": user,
        "sender_desk": primary_desk.get("name"), "recipient_desk": primary_desk.get("name")
    }).insert(ignore_permissions=True)
    
    master.append("movement_log", {
        "timestamp": frappe.utils.now_datetime(), "action": "Attached",
        "remarks": f"Attached Sub-file: {child_file}", "moved_from": user,
        "sender_desk": primary_desk.get("name"), "recipient_desk": primary_desk.get("name")
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
    user_desks = get_authorized_desks(user)

    if not any(master.desk_office == d.office and master.desk_designation == d.designation for d in user_desks):
        if "System Manager" not in frappe.get_roles(user):
            frappe.throw("You cannot detach files from a folder that is not at your desk.")

    primary_desk = get_primary_desk(user)
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
                "sender_desk": primary_desk.get("name"), "recipient_desk": primary_desk.get("name")
            }).insert(ignore_permissions=True)

            master.append("movement_log", {
                "timestamp": frappe.utils.now_datetime(), "action": "Detached",
                "remarks": f"Detached Sub-file: {row.linked_file}", "moved_from": user,
                "sender_desk": primary_desk.get("name"), "recipient_desk": primary_desk.get("name")
            })

    master.has_active_attachments = 1 if any(r.status == "Active" for r in master.attached_files) else 0
    master.save(ignore_permissions=True)
    return {"status": "success"}

def verify_active_custody(file_name):
    user = frappe.session.user
    doc = frappe.get_doc("Correspond File", file_name)
    auth_desks = get_authorized_desks(user)
    
    if not any(doc.desk_office == d.office and doc.desk_designation == d.designation for d in auth_desks):
        if "System Manager" not in frappe.get_roles(user):
            frappe.throw("Action Denied: This file is no longer at any of your authorized desks.")

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
