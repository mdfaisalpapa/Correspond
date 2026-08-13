# Copyright (c) 2026, Mohammed Faisal and contributors
# For license information, please see license.txt

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
        fields=["name", "note_details", "file", "docstatus"],
        order_by="creation asc",
    )

    # 3. Fetch all daks linked via Outward Dak child tables
    dak_meta = frappe.get_meta("Outward Dak")
    dak_child_tables = [
        df.options for df in dak_meta.get_table_fields() if df.fieldtype == "Table"
    ]

    dak_names = set()
    for table in dak_child_tables:
        child_meta = frappe.get_meta(table)
        link_fields = [
            df.fieldname
            for df in child_meta.fields
            if df.fieldtype == "Link" and df.options in ["Correspond File", "File"]
        ]
        if link_fields:
            for lf in link_fields:
                dak_rows = frappe.get_all(
                    table, filters={lf: ["in", all_files]}, fields=["parent"]
                )
                for dr in dak_rows:
                    if dr.get("parent"):
                        dak_names.add(dr.get("parent"))

    daks = []
    if dak_names:
        daks = frappe.get_all(
            "Outward Dak",
            filters={"name": ["in", list(dak_names)]},
            fields=["name", "subject"],
        )

    return {"files": all_files, "notes": notes, "daks": daks}
