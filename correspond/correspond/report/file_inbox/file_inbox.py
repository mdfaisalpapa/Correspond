import frappe

def execute(filters=None):
    user = frappe.session.user
    
    columns = [
        {
            "fieldname": "file_number", 
            "label": "File Number", 
            "fieldtype": "Data", 
            "width": 220
        },
        {
            "fieldname": "subject", 
            "label": "Subject", 
            "fieldtype": "Data", 
            "width": 300
        },
        {
            "fieldname": "sent_by", 
            "label": "Sent By", 
            "fieldtype": "Link", 
            "options": "User", 
            "width": 150
        },
        {
            "fieldname": "sent_on", 
            "label": "Sent On", 
            "fieldtype": "Datetime", 
            "width": 160
        },
        {
            "fieldname": "remarks", 
            "label": "Remarks", 
            "fieldtype": "Data", 
            "width": 250
        },
        {
            "fieldname": "attachments", 
            "label": "Attachments", 
            "fieldtype": "Data", 
            "width": 120
        }
    ]
    
    data = frappe.db.sql("""
        SELECT 
            df.name as file_number,
            df.subject,
            (SELECT moved_from FROM `tabFile Movement Log` WHERE parent = df.name AND action = 'Forwarded' ORDER BY timestamp DESC LIMIT 1) as sent_by,
            (SELECT timestamp FROM `tabFile Movement Log` WHERE parent = df.name AND action = 'Forwarded' ORDER BY timestamp DESC LIMIT 1) as sent_on,
            (SELECT remarks FROM `tabFile Movement Log` WHERE parent = df.name AND action = 'Forwarded' ORDER BY timestamp DESC LIMIT 1) as remarks,
            (
                SELECT GROUP_CONCAT(linked_file SEPARATOR ',') 
                FROM `tabAttached Files Log` 
                WHERE parent = df.name AND status = 'Active'
            ) as attachments
        FROM `tabCorrespond File` df
        WHERE df.current_custodian = %(user)s
          AND ifnull(df.is_attached, 0) = 0
        ORDER BY COALESCE(
            (SELECT timestamp FROM `tabFile Movement Log` WHERE parent = df.name AND action = 'Forwarded' ORDER BY timestamp DESC LIMIT 1), 
            df.modified
        ) DESC
    """, {"user": user}, as_dict=True)
    
    return columns, data