import frappe
from frappe.utils import nowdate, date_diff

def execute(filters=None):
    columns = [
        {"fieldname": "dak_id", "label": "Diarization No", "fieldtype": "Link", "options": "Inward Dak", "width": 180},
        {"fieldname": "vip_type", "label": "VIP / Priority Class", "fieldtype": "Data", "width": 200},
        {"fieldname": "subject", "label": "Subject", "fieldtype": "Data", "width": 300},
        {"fieldname": "sender", "label": "Sender / Origin", "fieldtype": "Data", "width": 220},
        {"fieldname": "receipt_date", "label": "Receipt Date", "fieldtype": "Date", "width": 120},
        {"fieldname": "sla_due_date", "label": "SLA Due Date", "fieldtype": "Date", "width": 120},
        {"fieldname": "days_remaining", "label": "Days Remaining", "fieldtype": "Int", "width": 130},
        {"fieldname": "urgency", "label": "Urgency Status", "fieldtype": "Data", "width": 140},
        {"fieldname": "recipient_desk", "label": "Current Desk", "fieldtype": "Data", "width": 200},
        {"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 110}
    ]

    today = nowdate()

    query = """
        SELECT 
            name AS dak_id,
            vip_type,
            subject,
            CONCAT(IFNULL(sender_name, ''), ' (', IFNULL(sender_organization, 'External'), ')') AS sender,
            receipt_date,
            sla_due_date,
            DATEDIFF(sla_due_date, %(today)s) AS days_remaining,
            CASE 
                WHEN DATEDIFF(sla_due_date, %(today)s) < 0 THEN 'OVERDUE'
                WHEN DATEDIFF(sla_due_date, %(today)s) <= 2 THEN 'CRITICAL'
                WHEN DATEDIFF(sla_due_date, %(today)s) <= 5 THEN 'APPROACHING'
                ELSE 'NORMAL'
            END AS urgency,
            recipient AS recipient_desk,
            status
        FROM `tabInward Dak`
        WHERE is_vip_reference = 1
        ORDER BY DATEDIFF(sla_due_date, %(today)s) ASC
    """

    data = frappe.db.sql(query, {"today": today}, as_dict=True)
    return columns, data
