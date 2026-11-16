import frappe
from frappe.utils import nowdate

def execute(filters=None):
    columns = [
        {"fieldname": "file_number", "label": "File Number", "fieldtype": "Link", "options": "Correspond File", "width": 220},
        {"fieldname": "subject", "label": "Subject", "fieldtype": "Data", "width": 300},
        {"fieldname": "retention_category", "label": "Retention Category", "fieldtype": "Data", "width": 200},
        {"fieldname": "closed_on", "label": "Closed On", "fieldtype": "Datetime", "width": 160},
        {"fieldname": "retention_due_date", "label": "Weeding / Expiry Due Date", "fieldtype": "Date", "width": 160},
        {"fieldname": "retention_status", "label": "Retention Status", "fieldtype": "Data", "width": 140},
        {"fieldname": "closed_by", "label": "Closed By", "fieldtype": "Link", "options": "User", "width": 180},
        {"fieldname": "status", "label": "File Status", "fieldtype": "Data", "width": 100}
    ]

    today = nowdate()

    query = """
        SELECT 
            name AS file_number,
            subject,
            ifnull(retention_category, 'Routine / Operational (3 Years)') AS retention_category,
            closed_on,
            retention_due_date,
            CASE 
                WHEN retention_due_date IS NULL THEN 'PERMANENT RECORD'
                WHEN retention_due_date < %(today)s THEN 'DUE FOR WEEDING'
                ELSE 'RETAIN IN RECORD ROOM'
            END AS retention_status,
            closed_by,
            status
        FROM `tabCorrespond File`
        WHERE status IN ('Closed', 'Archived')
        ORDER BY closed_on DESC
    """

    data = frappe.db.sql(query, {"today": today}, as_dict=True)
    return columns, data
