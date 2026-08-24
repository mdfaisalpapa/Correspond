import frappe

def execute(filters=None):
    user = frappe.session.user
    
    auth_desks = frappe.get_all("Correspond Desk Profile", 
                                filters={"user": user, "is_abolished": 0, "disabled": 0}, 
                                pluck="name")
    
    # Kept the 'select' column so your Bulk Forward JS button still works!
    columns = [
        {"fieldname": "select", "label": "Select", "fieldtype": "Check", "width": 60},
        {"fieldname": "file_number", "label": "File No", "fieldtype": "Data", "width": 220},
        {"fieldname": "subject", "label": "Subject", "fieldtype": "Data", "width": 300},
        {"fieldname": "sent_by", "label": "Sent By", "fieldtype": "Data", "width": 300},
        {"fieldname": "sent_on", "label": "Sent On", "fieldtype": "Datetime", "width": 160},
        {"fieldname": "remarks", "label": "Remarks", "fieldtype": "Data", "width": 250}
    ]
    
    if not auth_desks:
        return columns, []
    
    data = frappe.db.sql("""
        SELECT 
            0 as `select`, 
            df.name as file_number, 
            df.subject,
            (
                SELECT CONCAT(IFNULL(u.full_name, d.user), ' - ', IFNULL(d.desk_title, d.name))
                FROM `tabFile Movement Log` fml
                JOIN `tabCorrespond Desk Profile` d ON fml.sender_desk = d.name
                LEFT JOIN `tabUser` u ON d.user = u.name
                WHERE fml.parent = df.name AND fml.action = 'Forwarded'
                ORDER BY fml.timestamp DESC LIMIT 1
            ) as sent_by,
            (SELECT timestamp FROM `tabFile Movement Log` WHERE parent = df.name AND action = 'Forwarded' ORDER BY timestamp DESC LIMIT 1) as sent_on,
            (SELECT remarks FROM `tabFile Movement Log` WHERE parent = df.name AND action = 'Forwarded' ORDER BY timestamp DESC LIMIT 1) as remarks
        FROM `tabCorrespond File` df
        WHERE df.current_custodian IN %(auth_desks)s
          AND ifnull(df.is_attached, 0) = 0
        ORDER BY COALESCE((SELECT timestamp FROM `tabFile Movement Log` WHERE parent = df.name AND action = 'Forwarded' ORDER BY timestamp DESC LIMIT 1), df.modified) DESC
    """, {"auth_desks": auth_desks}, as_dict=True)
    
    return columns, data