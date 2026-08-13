import frappe
from frappe.model.document import Document

class CorrespondFile(Document):
    pass

@frappe.whitelist()
def get_file_and_references(file_name):
    all_files = [file_name]

    # 1. Get attached files from Correspond File child tables
    meta = frappe.get_meta("Correspond File")
    child_tables = [df.options for df in meta.get_table_fields() if df.fieldtype == "Table"]

    for table in child_tables:
        child_meta = frappe.get_meta(table)
        link_fields = [
            df.fieldname
            for df in child_meta.fields
            if df.fieldtype == "Link" and df.options in ["Correspond File", "File"]
        ]
        if link_fields:
            rows = frappe.get_all(table, filters={"parent": file_name}, fields=link_fields)
            for r in rows:
                for lf in link_fields:
                    val = r.get(lf)
                    if val and val not in all_files:
                        all_files.append(val)

    # 2. Fetch all notes belonging to these files
    notes = frappe.get_all(
        "Correspond Noting",
        filters={"file": ["in", all_files]},
        fields=["name", "note_details", "file", "docstatus", "owner", "status"],
        order_by="creation asc",
    )

    draft_daks = []
    final_daks = []

    # 3. Fetch OUTWARD Daks
    outward_links = frappe.get_all("Outward Dak Linked File", filters={"file": ["in", all_files]}, pluck="parent")
    outward_primaries = frappe.get_all("Outward Dak", filters={"primary_file": ["in", all_files]}, pluck="name")
    
    outward_names = list(set(outward_links + outward_primaries))
    
    if outward_names:
        outward_data = frappe.get_all(
            "Outward Dak",
            filters={"name": ["in", outward_names]},
            fields=["name", "subject", "modified as sort_date", "primary_file", "docstatus", "status"] 
        )
        for d in outward_data:
            label = "Outward Dak" if d.get("primary_file") == file_name else "Linked Outward"
            has_attach = bool(frappe.db.exists("File", {"attached_to_doctype": "Outward Dak", "attached_to_name": d.name}))
            
            dak_info = {
                "name": d.name,
                "subject": d.subject,
                "doctype": "Outward Dak",
                "label": label,
                "sort_date": d.sort_date,
                "has_attachments": has_attach,
                "is_draft": d.docstatus == 0,
                "status": d.status
            }
            if dak_info["is_draft"]:
                draft_daks.append(dak_info)
            else:
                final_daks.append(dak_info)

    # 4. Fetch INWARD Daks
    inward_links = frappe.get_all(
        "Inward Dak Linked File",
        filters={"file": ["in", all_files]},
        fields=["parent", "creation as sort_date"] 
    )
    if inward_links:
        inward_parents = list(set([d.parent for d in inward_links]))
        inward_data = frappe.get_all(
            "Inward Dak",
            filters={"name": ["in", inward_parents]},
            fields=["name", "subject", "docstatus", "status"]
        )
        inward_dict = {d.name: d for d in inward_data}
        
        for link in inward_links:
            if link.parent in inward_dict:
                doc_data = inward_dict[link.parent]
                has_attach = bool(frappe.db.exists("File", {"attached_to_doctype": "Inward Dak", "attached_to_name": link.parent}))
                
                dak_info = {
                    "name": link.parent,
                    "subject": doc_data.subject,
                    "doctype": "Inward Dak",
                    "label": "Inward Dak",
                    "sort_date": link.sort_date,
                    "has_attachments": has_attach,
                    "is_draft": doc_data.docstatus == 0,
                    "status": doc_data.status
                }
                if dak_info["is_draft"]:
                    draft_daks.append(dak_info)
                else:
                    final_daks.append(dak_info)

    # 5. Sort final daks chronologically and assign Serial Numbers
    final_daks = sorted(final_daks, key=lambda k: k.get("sort_date") or "", reverse=False)
    for index, dak in enumerate(final_daks):
        dak["serial_no"] = index + 1

    # 6. Sort draft daks chronologically
    draft_daks = sorted(draft_daks, key=lambda k: k.get("sort_date") or "", reverse=False)

    all_daks = draft_daks + final_daks

    return {"files": all_files, "notes": notes, "daks": all_daks}


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