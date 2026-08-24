import frappe

def execute(filters=None):
    user = frappe.session.user
    
    # Fetch all active desks linked to the user
    auth_desks = frappe.get_all("Correspond Desk Profile", filters={"user": user, "is_abolished": 0, "disabled": 0}, pluck="name")
    
    columns = [
        {"fieldname": "dak_id", "label": "Dak ID", "fieldtype": "Link", "options": "Outward Dak", "width": 200},
        {"fieldname": "subject", "label": "Subject", "fieldtype": "Data", "width": 300},
        {"fieldname": "destination", "label": "Sent To", "fieldtype": "Data", "width": 300},
        {"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 120},
        {"fieldname": "date", "label": "Date Sent", "fieldtype": "Date", "width": 120}
    ]

    if not auth_desks:
        auth_desks = ['']

    query = """
        SELECT 
            o.name AS dak_id,
            o.subject,
            CASE 
                WHEN o.recipient_type = 'Internal User' THEN CONCAT(IFNULL(u.full_name, d.user), ' - ', IFNULL(d.desk_title, d.name))
                ELSE CONCAT(IFNULL(o.receiver, 'Unknown'), ' (External)')
            END AS destination,
            o.status,
            DATE(o.modified) AS date
        FROM `tabOutward Dak` o
        LEFT JOIN `tabCorrespond Desk Profile` d ON o.internal_recipient = d.name
        LEFT JOIN `tabUser` u ON d.user = u.name
        WHERE o.sender IN %(auth_desks)s
        ORDER BY o.modified DESC
    """
    
    data = frappe.db.sql(query, {"auth_desks": auth_desks}, as_dict=True)
    return columns, data