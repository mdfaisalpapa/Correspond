import frappe

def execute(filters=None):
    user = frappe.session.user
    
    auth_desks = frappe.get_all("Correspond Desk Profile", filters={"user": user}, fields=["name", "office", "designation"])
    
    columns = [
        {"fieldname": "select", "label": "Select", "fieldtype": "Check", "width": 60},
        {"fieldname": "file_number", "label": "File Number", "fieldtype": "Data", "width": 220},
        {"fieldname": "subject", "label": "Subject", "fieldtype": "Data", "width": 300},
        {"fieldname": "sent_by", "label": "Sent By (Desk)", "fieldtype": "Link", "options": "Correspond Desk Profile", "width": 180},
        {"fieldname": "sent_on", "label": "Sent On", "fieldtype": "Datetime", "width": 160},
        {"fieldname": "remarks", "label": "Remarks", "fieldtype": "Data", "width": 250},
        {"fieldname": "attachments", "label": "Attachments", "fieldtype": "Data", "width": 120}
    ]
    
    if not auth_desks:
        return columns, []
    
    conditions = []
    values = {}
    for i, d in enumerate(auth_desks):
        conditions.append(f"(df.desk_office = %(office_{i})s AND df.desk_designation = %(desig_{i})s)")
        values[f"office_{i}"] = d.office
        values[f"desig_{i}"] = d.designation
    
    where_clause = " OR ".join(conditions)

    # --- PERMISSION FIX: Wrapped `select` in backticks below ---
    data = frappe.db.sql(f"""
        SELECT 
            0 as `select`, 
            df.name as file_number, df.subject,
            (SELECT sender_desk FROM `tabFile Movement Log` WHERE parent = df.name AND action = 'Forwarded' ORDER BY timestamp DESC LIMIT 1) as sent_by,
            (SELECT timestamp FROM `tabFile Movement Log` WHERE parent = df.name AND action = 'Forwarded' ORDER BY timestamp DESC LIMIT 1) as sent_on,
            (SELECT remarks FROM `tabFile Movement Log` WHERE parent = df.name AND action = 'Forwarded' ORDER BY timestamp DESC LIMIT 1) as remarks,
            (SELECT GROUP_CONCAT(linked_file SEPARATOR ',') FROM `tabAttached Files Log` WHERE parent = df.name AND status = 'Active') as attachments
        FROM `tabCorrespond File` df
        WHERE ({where_clause})
          AND ifnull(df.is_attached, 0) = 0
        ORDER BY COALESCE((SELECT timestamp FROM `tabFile Movement Log` WHERE parent = df.name AND action = 'Forwarded' ORDER BY timestamp DESC LIMIT 1), df.modified) DESC
    """, values, as_dict=True)
    
    return columns, data
