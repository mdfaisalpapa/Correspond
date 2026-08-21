import frappe
from frappe.model.document import Document
from frappe import _
import math
import json
import re

class CorrespondFile(Document):
    def validate(self):
        # Allow initial creation
        if self.is_new():
            return
            
        # Get the custodian that is currently saved in the database BEFORE this save attempt
        old_custodian = self.db_get('current_custodian')
        
        # If the file belongs to someone else, reject the save
        if old_custodian and old_custodian != frappe.session.user:
            if "System Manager" not in frappe.get_roles(frappe.session.user):
                frappe.throw("Action Denied: You cannot modify a file that is no longer in your active custody.")

    # =========================================================
    # CORE PERMISSION ENGINE OVERRIDE (eOffice Custody Rules)
    # =========================================================
    def has_permission(self, permtype="read", user=None, **kwargs):
        if not user:
            user = frappe.session.user
            
        if "System Manager" in frappe.get_roles(user):
            return True
            
        # Allow document creation for users with Correspond operational roles
        if permtype == "create":
            user_roles = frappe.get_roles(user)
            return any(r in ["System Manager", "Correspond User", "Correspond Registry Clerk"] for r in user_roles)
            
        if permtype == "write":
            # Allow saving if it's a brand new document being created
            if self.is_new():
                user_roles = frappe.get_roles(user)
                return any(r in ["System Manager", "Correspond User", "Correspond Registry Clerk"] for r in user_roles)
            
            # For existing documents, check database custodian value
            db_custodian = frappe.db.get_value("Correspond File", self.name, "current_custodian")
            return db_custodian == user
            
        if permtype == "read":
            if self.is_new():
                return True
                
            # 1. Direct Custody: User currently holds the file
            if self.current_custodian == user:
                return True
                
            # 2. Routing History: User previously sent or received this file directly
            has_history = frappe.db.sql("""
                SELECT 1 FROM `tabFile Movement Log`
                WHERE parent = %s AND (moved_from = %s OR moved_to = %s)
            """, (self.name, user, user))
            
            if has_history:
                return True
                
            # 3. Master File Inherited Custody (The eOffice Detachment Rule)
            master_check = frappe.db.sql("""
                SELECT 1
                FROM `tabAttached Files Log` a
                WHERE a.linked_file = %s
                AND (
                    EXISTS (
                        SELECT 1 FROM `tabCorrespond File` m 
                        WHERE m.name = a.parent AND m.current_custodian = %s
                    )
                    OR
                    EXISTS (
                        SELECT 1 FROM `tabFile Movement Log` fml 
                        WHERE fml.parent = a.parent AND (fml.moved_from = %s OR fml.moved_to = %s)
                    )
                )
            """, (self.name, user, user, user))
            
            if master_check:
                return True
                
            return False
            
        return None
        
@frappe.whitelist()
def get_file_and_references(file_name, note_page=1, active_tab='#tab-toc'):
    user = frappe.session.user
    all_files = [file_name]
    note_page = int(note_page)

    # 1. ACCESS CONTROL & TEMPORAL VERSIONING 
    file_doc = frappe.get_doc("Correspond File", file_name)
    is_custodian = (file_doc.current_custodian == user)
    
    # --- NEW: INHERITED CUSTODY CHECK ---
    is_master_custodian = False
    if file_doc.is_attached and file_doc.attached_to:
        master_custodian = frappe.db.get_value("Correspond File", file_doc.attached_to, "current_custodian")
        if master_custodian == user:
            is_master_custodian = True

    # Added is_master_custodian to the access check
    has_full_access = is_custodian or is_master_custodian or ("System Manager" in frappe.get_roles(user))

    is_historical = False
    cutoff_date = None

    if not has_full_access:
        valid_cutoffs = []

        # 1. Direct History: User directly forwarded or received the sub-file at some point
        direct_log = frappe.db.sql("""
            SELECT MAX(timestamp) FROM `tabFile Movement Log` 
            WHERE parent = %s AND (moved_from = %s OR moved_to = %s)
        """, (file_name, user, user))
        if direct_log and direct_log[0][0]:
            valid_cutoffs.append(direct_log[0][0])

        # 2. Inherited Master File History: The eOffice "Context" Rule
        master_records = frappe.db.sql("""
            SELECT 
                a.parent AS master_file,
                a.detached_on,
                m.current_custodian,
                (SELECT MAX(timestamp) FROM `tabFile Movement Log` WHERE parent = a.parent AND (moved_from = %s OR moved_to = %s)) AS user_master_timestamp
            FROM `tabAttached Files Log` a
            JOIN `tabCorrespond File` m ON a.parent = m.name
            WHERE a.linked_file = %s
        """, (user, user, file_name), as_dict=True)

        for rec in master_records:
            # CASE A: User CURRENTLY holds the Master File
            if rec.current_custodian == user:
                # Grant access exactly up to the date it was detached
                if rec.detached_on:
                    valid_cutoffs.append(rec.detached_on)
            
            # CASE B: User PREVIOUSLY held the Master File
            elif rec.user_master_timestamp:
                if rec.detached_on:
                    # They lose access based on whichever happened FIRST (detachment or forwarding)
                    effective_cutoff = min(rec.detached_on, rec.user_master_timestamp)
                    valid_cutoffs.append(effective_cutoff)
                else:
                    # File was never detached, so they lose access when they forwarded the master file
                    valid_cutoffs.append(rec.user_master_timestamp)

        # Find the absolute latest timestamp the user is legally allowed to see
        if valid_cutoffs:
            is_historical = True
            cutoff_date = max(valid_cutoffs)
        else:
            frappe.throw(_("Access Denied: You are neither the current custodian nor in the routing history of this file."), frappe.PermissionError)

    # 2. FETCH DATA (Standard SQL/ORM logic begins here...)
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

    # 3. TEMPORAL SECURITY STRIP
    if is_historical and cutoff_date:
        notes = [n for n in notes if n.creation <= cutoff_date]
        draft_daks = [d for d in draft_daks if d.get('sort_date') and d.get('sort_date') <= cutoff_date]
        final_daks = [d for d in final_daks if d.get('sort_date') and d.get('sort_date') <= cutoff_date]

    final_daks = sorted(final_daks, key=lambda k: k.get("sort_date") or "", reverse=False)
    for index, dak in enumerate(final_daks): dak["serial_no"] = index + 1
    draft_daks = sorted(draft_daks, key=lambda k: k.get("sort_date") or "", reverse=False)

    # 4. SERVER-SIDE PAGINATION LOGIC
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

    # 5. RENDER SECURE HTML ON SERVER
    green_sheet_html = render_green_sheet(paginated_notes, start_idx, end_idx, total_notes, has_draft, is_historical)
    dak_tabs_html = render_dak_tabs(submitted_notes, final_daks, draft_daks, active_tab, is_historical)

    return {
        "green_sheet_html": green_sheet_html,
        "dak_tabs_html": dak_tabs_html,
        "is_historical": is_historical,
        "cutoff_date": cutoff_date,
        "has_draft": has_draft
    }


# ================================================================
# SERVER-SIDE RENDERERS (Replaces JavaScript Strings)
# ================================================================
def render_green_sheet(paginated_notes, start_idx, end_idx, total_notes, has_draft, is_snapshot):
    # Prepare the data context to pass to the Jinja template
    context = {
        "notes": paginated_notes,
        "start_idx": start_idx,
        "end_idx": end_idx,
        "total_notes": total_notes,
        "has_draft": has_draft,
        "is_snapshot": is_snapshot
    }
    
    # Render and return the template HTML
    return frappe.render_template("correspond/templates/green_sheet.html", context)

def render_dak_tabs(submitted_notes, final_daks, draft_daks, active_tab, is_snapshot):
    # Pass all variables to the Jinja template context
    context = {
        "submitted_notes": submitted_notes,
        "final_daks": final_daks,
        "draft_daks": draft_daks,
        "active_tab": active_tab,
        "is_snapshot": is_snapshot
    }
    
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
    doc.current_custodian = recipient

    # Automatically submit any draft notes marked as 'Green' before forwarding
    green_notes = frappe.get_all(
        "Correspond Noting",
        filters={"file": file_name, "docstatus": 0, "status": "Green"},
        pluck="name"
    )
    for note_name in green_notes:
        note_doc = frappe.get_doc("Correspond Noting", note_name)
        note_doc.submit()

    # 1. Clean, hardcoded movement log dictionary
    row_data = {
        "timestamp": frappe.utils.now_datetime(),
        "moved_from": user,
        "moved_to": recipient,
        "action": "Forwarded",
        "remarks": remarks
    }

    # 2. Update Master File
    doc.append("movement_log", row_data)
    doc.save(ignore_permissions=True)

    # 3. Synchronize Sub-files
    for attached in doc.get("attached_files", []):
        if attached.status == "Active":
            child_file = frappe.get_doc("Correspond File", attached.linked_file)
            child_file.current_custodian = recipient 
            
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

    # 1. Security Checks
    if master.current_custodian != user and "System Manager" not in frappe.get_roles(user):
        frappe.throw("You cannot attach files to a folder that is not in your custody.")
    if child.is_attached:
        frappe.throw(f"File {child_file} is already attached to {child.attached_to}.")
    if master.is_attached:
        frappe.throw("You cannot attach sub-files into a file that is currently attached elsewhere.")

    # 2. Update the Child File
    child.is_attached = 1
    child.attached_to = master_file
    child.current_custodian = master.current_custodian  # <--- NEW: Instantly sync custodian upon attachment
    child.save(ignore_permissions=True)

    # 3. Create Movement Logs
    frappe.get_doc({
        "doctype": "File Movement Log", "parent": child_file, "parenttype": "Correspond File",
        "parentfield": "movement_log", "timestamp": frappe.utils.now_datetime(),
        "action": "Attached", "remarks": f"Attached to Master File: {master_file}", "moved_from": user
    }).insert(ignore_permissions=True)
    
    master.append("movement_log", {
        "timestamp": frappe.utils.now_datetime(), "action": "Attached",
        "remarks": f"Attached Sub-file: {child_file}", "moved_from": user
    })

    # 4. UPSERT LOGIC
    existing_row = next((r for r in master.attached_files if r.linked_file == child_file), None)
    
    if existing_row:
        existing_row.status = "Active"
        existing_row.attached_on = frappe.utils.now_datetime()
        existing_row.detached_on = None
    else:
        master.append("attached_files", {
            "linked_file": child_file,
            "status": "Active",
            "attached_on": frappe.utils.now_datetime()
        })

    # <--- NEW: Toggle the list view indicator ON
    master.has_active_attachments = 1 
    master.save(ignore_permissions=True)
    return {"status": "success"}


@frappe.whitelist()
def detach_sub_files(master_file, child_files_json):
    user = frappe.session.user
    master = frappe.get_doc("Correspond File", master_file)
    child_files = json.loads(child_files_json)

    if master.current_custodian != user and "System Manager" not in frappe.get_roles(user):
        frappe.throw("You cannot detach files from a folder that is not in your custody.")

    for row in master.attached_files:
        if row.linked_file in child_files and row.status == "Active":
            
            # 1. Update Grid Row
            row.status = "Detached"
            row.detached_on = frappe.utils.now_datetime()
            
            # 2. Unlink the Child File
            child = frappe.get_doc("Correspond File", row.linked_file)
            child.is_attached = 0
            child.attached_to = None
            child.save(ignore_permissions=True)

            # 3. Create Movement Logs
            frappe.get_doc({
                "doctype": "File Movement Log", "parent": row.linked_file, "parenttype": "Correspond File",
                "parentfield": "movement_log", "timestamp": frappe.utils.now_datetime(),
                "action": "Detached", "remarks": f"Detached from Master File: {master_file}", "moved_from": user
            }).insert(ignore_permissions=True)

            master.append("movement_log", {
                "timestamp": frappe.utils.now_datetime(), "action": "Detached",
                "remarks": f"Detached Sub-file: {row.linked_file}", "moved_from": user
            })

    # <--- NEW: Check if any active attachments remain. If not, turn the indicator OFF
    active_remaining = any(r.status == "Active" for r in master.attached_files)
    master.has_active_attachments = 1 if active_remaining else 0

    master.save(ignore_permissions=True)
    return {"status": "success"}

# ------------------------------------------------------------------
# CENTRALIZED CUSTODY CHECK
# ------------------------------------------------------------------
def verify_active_custody(file_name):
    """Halts execution instantly if the user is not the active custodian."""
    user = frappe.session.user
    doc = frappe.get_doc("Correspond File", file_name)
    if doc.current_custodian != user and "System Manager" not in frappe.get_roles(user):
        frappe.throw("Action Denied: This file has been moved and is no longer in your active custody.")

# ------------------------------------------------------------------
# STRICT ACTION WRAPPERS (Notes & Daks)
# ------------------------------------------------------------------
@frappe.whitelist()
def add_draft_note(file_name, note_details):
    verify_active_custody(file_name)
    
    frappe.get_doc({
        "doctype": "Correspond Noting",
        "file": file_name,
        "note_details": note_details,
        "status": "Yellow"
    }).insert(ignore_permissions=True)
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
    
    # Dynamically map ALL fields passed from the frontend dialog
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

    # Automatically submit the document if the Approve button was clicked
    if str(submit_doc).lower() == 'true':
        dak.submit()

    return {"status": "success"}


import re

@frappe.whitelist()
def get_reference_lookup_data(file_name):
    """Extremely lightweight endpoint exclusively for populating the Reference Dropdown Dialog"""
    verify_active_custody(file_name) # Ensure they have rights to the file
    
    all_files_list = [file_name]
    current_subj = frappe.db.get_value("Correspond File", file_name, "subject") or "Untitled"
    
    # 1. Pre-format the Reference File dropdown options with Subjects
    file_opts = [{
        "value": file_name,
        "label": f"{file_name}: {current_subj} (Current File)"
    }]
    
    # Grab attached files and their subjects
    child_tables = [df.options for df in frappe.get_meta("Correspond File").get_table_fields() if df.fieldtype == "Table"]
    for table in child_tables:
        child_meta = frappe.get_meta(table)
        
        # Find exactly which fields in the child table link to another file
        link_fields = [f.fieldname for f in child_meta.fields if f.fieldtype == "Link" and f.options in ["Correspond File", "File"]]
        
        if link_fields:
            # FIX: We must explicitly pass 'fields=link_fields' so Frappe actually fetches the data!
            rows = frappe.get_all(table, filters={"parent": file_name}, fields=link_fields)
            for r in rows:
                for lf in link_fields:
                    val = r.get(lf)
                    if val and val not in all_files_list:
                        all_files_list.append(val)
                        
                        # Dynamically fetch the subject of the attached file
                        target_doctype = next((f.options for f in child_meta.fields if f.fieldname == lf), "Correspond File")
                        att_subj = frappe.db.get_value(target_doctype, val, "subject") or "Untitled"
                        
                        file_opts.append({
                            "value": val,
                            "label": f"{val}: {att_subj} (Attached File)"
                        })

    # 2. Fetch and pre-format Notes for the dropdown
    notes = frappe.get_all("Correspond Noting", filters={"file": ["in", all_files_list]}, fields=["name", "note_details", "file"], order_by="creation asc")
    note_opts = []
    
    for i, n in enumerate(notes):
        clean_text = re.sub('<[^<]+?>', '', n.note_details or '')
        snippet = (clean_text[:35] + '...') if len(clean_text) > 35 else clean_text
        note_opts.append({
            "file": n.file,
            "label": f"Note #{i+1}: {snippet} ({n.name})",
            "value": n.name
        })

    # 3. Fetch and pre-format Daks for the dropdown
    dak_opts = []
    outwards = frappe.get_all("Outward Dak", filters={"primary_file": ["in", all_files_list]}, fields=["name", "subject", "primary_file"])
    for d in outwards:
        dak_opts.append({"file": d.primary_file, "label": f"Outward Dak: {d.name} - {d.subject}", "value": d.name})
        
    inwards = frappe.get_all("Inward Dak Linked File", filters={"file": ["in", all_files_list]}, fields=["parent", "file"])
    for d in inwards:
        subj = frappe.db.get_value("Inward Dak", d.parent, "subject") or "Untitled"
        dak_opts.append({"file": d.file, "label": f"Inward Dak: {d.parent} - {subj}", "value": d.parent})

    return {
        "file_opts": file_opts,
        "notes": note_opts,
        "daks": dak_opts
    }
