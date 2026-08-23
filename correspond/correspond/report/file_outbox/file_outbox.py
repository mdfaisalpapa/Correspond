import frappe

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {"fieldname": "file_number", "label": "File Number", "fieldtype": "Link", "options": "Correspond File", "width": 220},
        {"fieldname": "subject", "label": "Subject", "fieldtype": "Data", "width": 300},
        {"fieldname": "action", "label": "Action", "fieldtype": "Data", "width": 100},
        {"fieldname": "recipient_desk", "label": "Sent To Desk", "fieldtype": "Link", "options": "Correspond Desk Profile", "width": 220},
        {"fieldname": "timestamp", "label": "Date & Time", "fieldtype": "Datetime", "width": 160},
        {"fieldname": "sender_desk", "label": "Sent From (Your Desk)", "fieldtype": "Link", "options": "Correspond Desk Profile", "width": 180},
        {"fieldname": "remarks", "label": "Remarks", "fieldtype": "Data", "width": 250},
        {"fieldname": "attachments", "label": "Attachments", "fieldtype": "Data", "width": 120}
    ]

def get_data(filters):
    user = frappe.session.user
    
    auth_desks = frappe.get_all("Correspond Desk Profile", filters={"user": user}, pluck="name")
    
    if not auth_desks:
        return []

    query = """
        SELECT 
            log.parent AS file_number,
            file.subject,
            log.action,
            log.recipient_desk,
            log.timestamp,
            log.sender_desk,
            log.remarks,
            (SELECT GROUP_CONCAT(linked_file SEPARATOR ',') FROM `tabAttached Files Log` WHERE parent = file.name AND status = 'Active') as attachments
        FROM `tabFile Movement Log` log
        LEFT JOIN `tabCorrespond File` file ON log.parent = file.name
        WHERE log.sender_desk IN %(auth_desks)s
        ORDER BY log.timestamp DESC
    """
    
    return frappe.db.sql(query, {"auth_desks": auth_desks}, as_dict=True)
