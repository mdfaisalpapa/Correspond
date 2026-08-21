import frappe

def execute(filters=None):
    user = frappe.session.user
    
    columns = [
        {
            "fieldname": "file_number", 
            "label": "File Number", 
            "fieldtype": "Link", 
            "options": "Correspond File", 
            "width": 220
        },
        {
            "fieldname": "subject", 
            "label": "Subject", 
            "fieldtype": "Data", 
            "width": 300
        },
        {
            "fieldname": "sent_to", 
            "label": "Sent To", 
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
            "fieldname": "currently_with", 
            "label": "Currently With", 
            "fieldtype": "Link", 
            "options": "User", 
            "width": 150
        },
        {
            "fieldname": "attachments", 
            "label": "Attachments", 
            "fieldtype": "Data", 
            "width": 120
        },
        {
            "fieldname": "action", 
            "label": "Action", 
            "fieldtype": "Data", 
            "width": 120
        }
    ]
    
    data = frappe.db.sql("""
        SELECT 
            fml.parent as file_number,
            df.subject,
            fml.moved_to as sent_to,
            fml.timestamp as sent_on,
            df.current_custodian as currently_with,
            (
                SELECT GROUP_CONCAT(linked_file SEPARATOR ',') 
                FROM `tabAttached Files Log` 
                WHERE parent = df.name AND status = 'Active'
            ) as attachments,
            df.name as action
        FROM `tabFile Movement Log` fml
        JOIN `tabCorrespond File` df ON fml.parent = df.name
        WHERE fml.moved_from = %(user)s
          AND fml.parenttype = 'Correspond File'
          AND fml.action = 'Forwarded'
          AND (fml.remarks IS NULL OR fml.remarks NOT LIKE '[Moved with Master File%%')
        ORDER BY fml.timestamp DESC
    """, {"user": user}, as_dict=True)
    
    return columns, data
