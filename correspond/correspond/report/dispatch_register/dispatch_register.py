import frappe

def execute(filters=None):
    columns = [
        {"fieldname": "dispatch_register_no", "label": "Dispatch No", "fieldtype": "Data", "width": 220},
        {"fieldname": "dak_id", "label": "Dak ID", "fieldtype": "Link", "options": "Outward Dak", "width": 180},
        {"fieldname": "dfa_type", "label": "Type", "fieldtype": "Data", "width": 160},
        {"fieldname": "subject", "label": "Subject", "fieldtype": "Data", "width": 300},
        {"fieldname": "primary_file", "label": "File Number", "fieldtype": "Link", "options": "Correspond File", "width": 220},
        {"fieldname": "recipient", "label": "Dispatched To", "fieldtype": "Data", "width": 250},
        {"fieldname": "dispatch_mode", "label": "Dispatch Mode", "fieldtype": "Data", "width": 140},
        {"fieldname": "consignment_number", "label": "Tracking / Consignment No", "fieldtype": "Data", "width": 180},
        {"fieldname": "dispatched_on", "label": "Date of Dispatch", "fieldtype": "Datetime", "width": 160},
        {"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 120}
    ]

    conditions = []
    values = {}

    if filters and filters.get("dfa_type"):
        conditions.append("o.dfa_type = %(dfa_type)s")
        values["dfa_type"] = filters.get("dfa_type")

    if filters and filters.get("dispatch_mode"):
        conditions.append("o.dispatch_mode = %(dispatch_mode)s")
        values["dispatch_mode"] = filters.get("dispatch_mode")

    where_clause = " AND " + " AND ".join(conditions) if conditions else ""

    query = f"""
        SELECT 
            o.dispatch_register_no,
            o.name AS dak_id,
            ifnull(o.dfa_type, 'General Letter') AS dfa_type,
            o.subject,
            o.primary_file,
            CASE 
                WHEN o.recipient_type = 'Internal User' THEN CONCAT(IFNULL(u.full_name, d.user), ' - ', IFNULL(d.desk_title, d.name))
                ELSE CONCAT(IFNULL(o.receiver, 'Unknown'), ' (', IFNULL(o.receiver_email, 'External'), ')')
            END AS recipient,
            ifnull(o.dispatch_mode, 'Email') AS dispatch_mode,
            ifnull(o.consignment_number, '-') AS consignment_number,
            o.modified AS dispatched_on,
            o.status
        FROM `tabOutward Dak` o
        LEFT JOIN `tabCorrespond Desk Profile` d ON o.internal_recipient = d.name
        LEFT JOIN `tabUser` u ON d.user = u.name
        WHERE (o.status IN ('Dispatched', 'Approved') OR o.dispatch_register_no IS NOT NULL)
        {where_clause}
        ORDER BY o.modified DESC
    """

    data = frappe.db.sql(query, values, as_dict=True)
    return columns, data
