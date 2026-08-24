import frappe

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {"fieldname": "file_number", "label": "File No", "fieldtype": "Data", "width": 220},
        {"fieldname": "subject", "label": "Subject", "fieldtype": "Data", "width": 300},
        {"fieldname": "recipient_desk", "label": "Sent To", "fieldtype": "Data", "width": 300},
        {"fieldname": "timestamp", "label": "Sent On", "fieldtype": "Datetime", "width": 160},
        {"fieldname": "currently_with", "label": "Currently With", "fieldtype": "Data", "width": 300},
        {"fieldname": "remarks", "label": "Remarks", "fieldtype": "Data", "width": 250}
    ]

def get_data(filters):
    user = frappe.session.user
    
    auth_desks = frappe.get_all("Correspond Desk Profile", filters={"user": user}, pluck="name")
    
    if not auth_desks:
        return []

    # Joins the current custodian user details to generate the "Currently With" column
    query = """
        SELECT 
            log.parent AS file_number,
            file.subject,
            CONCAT(IFNULL(ru.full_name, rdesk.user), ' - ', IFNULL(rdesk.desk_title, rdesk.name)) AS recipient_desk,
            log.timestamp,
            CONCAT(IFNULL(cu.full_name, cdesk.user), ' - ', IFNULL(cdesk.desk_title, cdesk.name)) AS currently_with,
            log.remarks
        FROM `tabFile Movement Log` log
        LEFT JOIN `tabCorrespond File` file ON log.parent = file.name
        LEFT JOIN `tabCorrespond Desk Profile` rdesk ON log.recipient_desk = rdesk.name
        LEFT JOIN `tabUser` ru ON rdesk.user = ru.name
        LEFT JOIN `tabCorrespond Desk Profile` cdesk ON file.current_custodian = cdesk.name
        LEFT JOIN `tabUser` cu ON cdesk.user = cu.name
        WHERE log.sender_desk IN %(auth_desks)s
        ORDER BY log.timestamp DESC
    """
    
    return frappe.db.sql(query, {"auth_desks": auth_desks}, as_dict=True)