import frappe

def execute(filters=None):
    user = frappe.session.user
    auth_desks = frappe.get_all("Correspond Desk Profile", filters={"user": user}, pluck="name")
    
    columns = [
        {"fieldname": "dak_id", "label": "Dak ID", "fieldtype": "Dynamic Link", "options": "doctype", "width": 200},
        {"fieldname": "doctype", "label": "Type", "fieldtype": "Data", "hidden": 1},
        {"fieldname": "subject", "label": "Subject", "fieldtype": "Data", "width": 300},
        {"fieldname": "dak_source", "label": "Source", "fieldtype": "Data", "width": 130},
        {"fieldname": "sender_info", "label": "Sender / Origin", "fieldtype": "Data", "width": 300},
        {"fieldname": "date", "label": "Date Received", "fieldtype": "Date", "width": 120}
    ]

    if not auth_desks:
        auth_desks = ['']

    query = """
        SELECT 
            name AS dak_id,
            'Inward Dak' AS doctype,
            subject,
            'External Receipt' AS dak_source,
            CONCAT(IFNULL(sender_name, 'Unknown'), ' (', IFNULL(sender_organization, 'External'), ')') AS sender_info,
            receipt_date AS date
        FROM `tabInward Dak`
        WHERE (recipient IN %(auth_desks)s OR owner = %(user)s) 
        AND status != 'Draft'
        
        UNION ALL
        
        SELECT 
            o.name AS dak_id,
            'Outward Dak' AS doctype,
            o.subject,
            'Internal Transfer' AS dak_source,
            CONCAT(IFNULL(u.full_name, d.user), ' - ', IFNULL(d.desk_title, d.name)) AS sender_info,
            DATE(o.modified) AS date
        FROM `tabOutward Dak` o
        LEFT JOIN `tabCorrespond Desk Profile` d ON o.sender = d.name
        LEFT JOIN `tabUser` u ON d.user = u.name
        WHERE (o.internal_recipient IN %(auth_desks)s OR o.owner = %(user)s) 
        AND o.status = 'Approved'
        
        ORDER BY date DESC
    """
    
    data = frappe.db.sql(query, {"auth_desks": auth_desks, "user": user}, as_dict=True)
    return columns, data