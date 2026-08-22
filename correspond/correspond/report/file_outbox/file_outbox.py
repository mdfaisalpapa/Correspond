import frappe

def execute(filters=None):
    user = frappe.session.user
    desk = frappe.db.get_value("Correspond User Profile", {"user": user}, ["office", "designation"], as_dict=True) or {}
    
    columns = [
        {"fieldname": "file_number", "label": "File Number", "fieldtype": "Data", "width": 220},
        {"fieldname": "subject", "label": "Subject", "fieldtype": "Data", "width": 300},
        {"fieldname": "sent_to", "label": "Sent To", "fieldtype": "Link", "options": "User", "width": 150},
        {"fieldname": "sent_on", "label": "Sent On", "fieldtype": "Datetime", "width": 160},
        {"fieldname": "remarks", "label": "Remarks", "fieldtype": "Data", "width": 250},
        {"fieldname": "attachments", "label": "Attachments", "fieldtype": "Data", "width": 120}
    ]
    
    if not desk.get("office") or not desk.get("designation"):
        return columns, []
    
    data = frappe.db.sql("""
        SELECT 
            df.name as file_number, df.subject,
            (SELECT moved_to FROM `tabFile Movement Log` WHERE parent = df.name AND action_office = %(office)s AND action_designation = %(designation)s ORDER BY timestamp DESC LIMIT 1) as sent_to,
            (SELECT timestamp FROM `tabFile Movement Log` WHERE parent = df.name AND action_office = %(office)s AND action_designation = %(designation)s ORDER BY timestamp DESC LIMIT 1) as sent_on,
            (SELECT remarks FROM `tabFile Movement Log` WHERE parent = df.name AND action_office = %(office)s AND action_designation = %(designation)s ORDER BY timestamp DESC LIMIT 1) as remarks,
            (SELECT GROUP_CONCAT(linked_file SEPARATOR ',') FROM `tabAttached Files Log` WHERE parent = df.name AND status = 'Active') as attachments
        FROM `tabCorrespond File` df
        WHERE EXISTS (SELECT 1 FROM `tabFile Movement Log` WHERE parent = df.name AND action_office = %(office)s AND action_designation = %(designation)s)
        AND (df.desk_office != %(office)s OR df.desk_designation != %(designation)s)
        AND ifnull(df.is_attached, 0) = 0
        ORDER BY (SELECT MAX(timestamp) FROM `tabFile Movement Log` WHERE parent = df.name AND action_office = %(office)s AND action_designation = %(designation)s) DESC
    """, {"office": desk.get("office"), "designation": desk.get("designation")}, as_dict=True)
    
    return columns, data
