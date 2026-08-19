import frappe
from frappe.model.document import Document
from frappe import _
import math
import json
import re

class CorrespondFile(Document):
    pass

@frappe.whitelist()
def get_file_and_references(file_name, note_page=1, active_tab='#tab-toc'):
    user = frappe.session.user
    all_files = [file_name]
    note_page = int(note_page)

    # 1. ACCESS CONTROL & TEMPORAL VERSIONING 
    file_doc = frappe.get_doc("Correspond File", file_name)
    is_custodian = (file_doc.current_custodian == user)
    has_full_access = is_custodian or ("System Manager" in frappe.get_roles(user))

    is_historical = False
    cutoff_date = None

    if not has_full_access:
        last_movement = frappe.db.sql("""
            SELECT MAX(timestamp) FROM `tabFile Movement Log` 
            WHERE parent = %s AND moved_from = %s
        """, (file_name, user))

        if last_movement and last_movement[0][0]:
            is_historical = True
            cutoff_date = last_movement[0][0]
        else:
            frappe.throw(_("Access Denied: You are neither the current custodian nor in the routing history of this file."), frappe.PermissionError)

    # 2. FETCH DATA (Standard SQL/ORM logic)
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
    html = f"""
    <div class="eoffice-scroll-container" style="padding: 15px; background-color: #f4fdf8; border-radius: 8px; border: 1px solid #c3e6cb; height: 75vh; overflow-y: auto; position: relative;">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #155724; padding-bottom: 10px; margin-bottom: 15px;">
            <h4 style="color: #155724; margin: 0;">Green Sheet</h4>
            <div style="background: #e9ecef; padding: 4px 8px; border-radius: 4px; font-size: 12px; display: flex; align-items: center;">
                <button class="btn btn-xs btn-default prev-notes-btn" style="padding: 2px 6px;"><b>&lt;</b></button>
                <span style="margin: 0 10px; font-weight: bold; color: #495057;">{start_idx + 1 if total_notes > 0 else 0} - {end_idx} of {total_notes} Note(s)</span>
                <button class="btn btn-xs btn-default next-notes-btn" style="padding: 2px 6px;"><b>&gt;</b></button>
            </div>
        </div>
    """
    if has_draft and not is_snapshot:
        html += '<div style="background-color: #fff3cd; color: #856404; padding: 8px; border-radius: 4px; font-size: 12px; text-align: center; margin-bottom: 15px; border: 1px solid #ffeeba;">⚠️ <b>Locked:</b> Cannot add new notes while an existing note is in Draft state.</div>'

    if paginated_notes:
        for idx, note in enumerate(paginated_notes):
            actual_no = start_idx + idx + 1
            is_draft = (note.docstatus == 0)
            is_green = (note.status == 'Green')
            badge = '<span class="badge badge-success" style="float: right;">Final</span>'
            bg, border = '#fff', '1px solid #e2e3e5'

            if is_draft:
                if is_snapshot:
                    badge, bg, border = '<span class="badge badge-warning" style="float: right;">Draft at time of detachment</span>', '#fffde7', '1px solid #ffe082'
                elif is_green:
                    badge = f'<button class="btn btn-xs btn-warning toggle-state-btn" data-note-name="{note.name}" data-state="Yellow" style="float: right; margin-left: 5px;">Revert to Yellow</button><button class="btn btn-xs btn-default edit-note-btn" data-note-name="{note.name}" style="float: right; margin-left: 10px; background-color: #fff; border: 1px solid #ddd;">Edit Note</button><span class="badge badge-success" style="float: right;">Green (Ready)</span>'
                    bg, border = '#e8f5e9', '1px solid #c8e6c9'
                else:
                    badge = f'<button class="btn btn-xs btn-success toggle-state-btn" data-note-name="{note.name}" data-state="Green" style="float: right; margin-left: 5px;">Mark Green</button><button class="btn btn-xs btn-default edit-note-btn" data-note-name="{note.name}" style="float: right; margin-left: 10px; background-color: #fff; border: 1px solid #ddd;">Edit Note</button><span class="badge badge-warning" style="float: right;">Yellow Draft</span>'
                    bg, border = '#fffde7', '1px solid #ffe082'

            html += f"""
            <div id="note-{note.name}" class="target-reference-item" style="margin-bottom: 20px; border-bottom: 1px solid #c3e6cb; padding-bottom: 15px;">
                <div style="font-size: 12px; color: #155724; margin-bottom: 8px;"><b style="font-size: 14px; text-decoration: underline;">Note #{actual_no}</b> &nbsp;•&nbsp; <b>{note.owner}</b> • {badge}</div>
                <div style="font-size: 14px; color: #333; background: {bg}; padding: 10px; border-radius: 5px; border: {border};">{note.get('note_details', '')}</div>
            </div>"""
    else:
        html += '<p style="text-align: center; color: #777; margin-top: 20px;">No notings found.</p>'

    return html + '</div>'


def render_dak_tabs(submitted_notes, final_daks, draft_daks, active_tab, is_snapshot):
    drafts_badge = f'<span class="badge badge-danger ml-1">{len(draft_daks)}</span>' if draft_daks else ''
    toc_a, prev_a, draft_a = ('active', 'show active') if active_tab == '#tab-toc' else ('', ''), ('active', 'show active') if active_tab == '#tab-prev-notes' else ('', ''), ('active', 'show active') if active_tab == '#tab-drafts' else ('', '')

    html = f"""
    <div style="background-color: #fff; border-radius: 8px; border: 1px solid #dee2e6; height: 75vh; display: flex; flex-direction: column;">
        <ul class="nav nav-tabs" id="eofficeRightTabs" role="tablist" style="background: #f8f9fa; border-radius: 8px 8px 0 0; padding: 5px 0 0 5px; margin-bottom: 0;">
            <li class="nav-item"><a class="nav-link {toc_a[0]}" data-target="#tab-toc" role="tab" style="font-weight: 600; color: #495057; cursor: pointer;">ToC</a></li>
            <li class="nav-item"><a class="nav-link {prev_a[0]}" data-target="#tab-prev-notes" role="tab" style="font-weight: 600; color: #495057; cursor: pointer;">Previous Notings</a></li>
            <li class="nav-item"><a class="nav-link {draft_a[0]}" data-target="#tab-drafts" role="tab" style="font-weight: 600; color: #495057; cursor: pointer;">Drafts {drafts_badge}</a></li>
        </ul>
        <div class="tab-content" id="eofficeRightTabsContent" style="flex-grow: 1; overflow-y: auto; padding: 15px;">
            <div class="tab-pane fade {toc_a[1]}" id="tab-toc" role="tabpanel">"""
    
    html += generate_dak_html(final_daks, is_snapshot) if final_daks else '<p style="text-align: center; color: #777; margin-top: 20px;">No finalized correspondence found.</p>'
    html += f'</div><div class="tab-pane fade {prev_a[1]}" id="tab-prev-notes" role="tabpanel"><div style="background-color: #f4fdf8; border-radius: 8px; border: 1px solid #c3e6cb; padding: 15px; min-height: 50vh;">'

    if submitted_notes:
        for idx, note in enumerate(submitted_notes):
            html += f'<div style="margin-bottom: 20px; border-bottom: 1px solid #c3e6cb; padding-bottom: 15px;"><div style="font-size: 12px; color: #155724; margin-bottom: 8px;"><b style="font-size: 14px; text-decoration: underline;">Note #{idx+1}</b> &nbsp;•&nbsp; <b>{note.owner}</b><span class="badge badge-success" style="float: right;">Final</span></div><div style="font-size: 14px; color: #333; background: #fff; padding: 10px; border-radius: 5px; border: 1px solid #e2e3e5;">{note.get("note_details","")}</div></div>'
    else: html += '<p style="text-align: center; color: #777; margin-top: 20px;">No previous notings found.</p>'
    
    html += f'</div></div><div class="tab-pane fade {draft_a[1]}" id="tab-drafts" role="tabpanel">'
    html += generate_dak_html(draft_daks, is_snapshot) if draft_daks else '<p style="text-align: center; color: #777; margin-top: 20px;">No pending drafts.</p>'
    return html + '</div></div></div>'

def generate_dak_html(daks, is_snapshot):
    html = ''
    for dak in daks:
        clip = '<i class="fa fa-paperclip text-muted" style="margin-left: 10px; font-size: 1.1em;" title="Contains Attachments"></i>' if dak.get('has_attachments') else ''
        b_cls = "badge-primary" if dak['label'] == 'Inward Dak' else "badge-success" if dak['label'] == 'Outward Dak' else "badge-warning"
        lbl = f'<span class="badge {b_cls}" style="float: right;">{dak["label"]}</span>'
        
        ws_bdg = ''
        if not dak['is_draft'] and dak.get('status'):
            w_cls = "badge-success" if dak['status'] in ['Dispatched', 'Closed'] else "badge-info" if dak['status'] in ['Approved', 'Marked'] else "badge-secondary"
            ws_bdg = f'<span class="badge {w_cls}" style="float: right; margin-right: 8px; font-size: 10px; padding: 4px 6px;">{dak["status"]}</span>'

        serial = '<span class="badge badge-danger" style="margin-right: 5px;">DRAFT</span>' if dak['is_draft'] else f'<b style="font-size: 14px; color: #155724;">#{dak["serial_no"]}</b> &nbsp;•&nbsp;'
        
        if dak['is_draft']:
            if is_snapshot: act_html = f'<span style="font-weight: 600; color: #6c757d;"><b>Subject:</b> {dak.get("subject", "Untitled")} (Draft)</span>'
            elif dak['doctype'] == 'Outward Dak': act_html = f'<a href="javascript:void(0);" class="edit-dak-btn" data-dak-name="{dak["name"]}" title="Edit draft" style="font-weight: 600; color: #1f272e; text-decoration: none;"><b>Subject:</b> {dak.get("subject", "Untitled")} <i class="fa fa-pencil text-primary" style="margin-left: 5px;"></i></a>'
            else: act_html = f'<a href="/app/{dak["doctype"].lower().replace(" ", "-")}/{dak["name"]}" target="_blank" title="Edit draft" style="font-weight: 600; color: #1f272e; text-decoration: none;"><b>Subject:</b> {dak.get("subject", "Untitled")} <i class="fa fa-pencil text-primary" style="margin-left: 5px;"></i></a>'
        else: act_html = f'<a href="/api/method/frappe.utils.print_format.download_pdf?doctype={dak["doctype"]}&name={dak["name"]}&format=Standard&no_letterhead=0" target="_blank" title="Download PDF" style="font-weight: 600; color: #1f272e; text-decoration: none;"><b>Subject:</b> {dak.get("subject", "Untitled")} <i class="fa fa-file-pdf-o text-danger" style="margin-left: 5px;"></i></a>'

        html += f'<div id="dak-{dak["name"]}" class="target-reference-item" style="margin-bottom: 20px; border-bottom: 1px solid #dee2e6; padding-bottom: 15px; background: {"#fff8e1" if dak["is_draft"] else "#fff"}; padding: 10px; border-radius: 5px; border: 1px solid #ced4da;"><div style="font-size: 12px; color: #495057; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;"><div>{serial} <b>ID:</b> {dak["name"]}</div><div>{ws_bdg} {lbl}</div></div><div style="font-size: 14px; color: #333; margin-top: 5px;">{act_html} {clip}</div></div>'
    return html
@frappe.whitelist()
def set_note_state(note_name, status):
    doc = frappe.get_doc("Correspond Noting", note_name)
    if doc.docstatus == 0:
        doc.status = status
        doc.save(ignore_permissions=True)
    return {"status": "success"}


@frappe.whitelist()
def forward_file(file_name, recipient, remarks):
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

    # Dynamically map fields to the File Movement Log child table
    movement_meta = frappe.get_meta("File Movement Log")
    movement_fields = [df.fieldname for df in movement_meta.fields]
    
    row_data = {"remarks": remarks}
    if "to_user" in movement_fields:
        row_data["to_user"] = recipient
    elif "recipient" in movement_fields:
        row_data["recipient"] = recipient
    elif "user" in movement_fields:
        row_data["user"] = recipient
        
    if "date" in movement_fields:
        row_data["date"] = frappe.utils.nowdate()
    elif "timestamp" in movement_fields:
        row_data["timestamp"] = frappe.utils.now()

    doc.append("movement_log", row_data)
    doc.save(ignore_permissions=True)

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

    # 4. UPSERT LOGIC: Update existing row if it exists, otherwise create new
    existing_row = next((r for r in master.attached_files if r.linked_file == child_file), None)
    
    if existing_row:
        existing_row.status = "Active"
        existing_row.attached_on = frappe.utils.now_datetime()
        existing_row.detached_on = None # Clear the old detached date
    else:
        master.append("attached_files", {
            "linked_file": child_file,
            "status": "Active",
            "attached_on": frappe.utils.now_datetime()
        })

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
            
            # 1. Update Grid Row (Do not delete it)
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
    
    frappe.get_doc({
        "doctype": "Outward Dak",
        "primary_file": file_name,
        "receiver": data.get("receiver"),
        "receiver_email": data.get("receiver_email"),
        "subject": data.get("subject"),
        "reference": data.get("reference"),
        "letter_body": data.get("letter_body"),
        "signature": data.get("signature"),
        "attachments": data.get("attachments")
    }).insert(ignore_permissions=True)
    return {"status": "success"}

@frappe.whitelist()
def update_draft_dak(file_name, dak_name, dak_data):
    verify_active_custody(file_name)
    data = json.loads(dak_data)
    
    dak = frappe.get_doc("Outward Dak", dak_name)
    dak.update(data)
    dak.save(ignore_permissions=True)
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
