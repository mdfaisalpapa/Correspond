import frappe
from frappe.utils import nowdate

def execute(filters=None):
    columns = [
        {"fieldname": "desk_name", "label": "Desk Profile", "fieldtype": "Link", "options": "Correspond Desk Profile", "width": 200},
        {"fieldname": "desk_title", "label": "Designation / Title", "fieldtype": "Data", "width": 200},
        {"fieldname": "officer_name", "label": "Officer / User", "fieldtype": "Data", "width": 180},
        {"fieldname": "total_active_files", "label": "Active Files In Custody", "fieldtype": "Int", "width": 160},
        {"fieldname": "parked_files", "label": "Parked Files", "fieldtype": "Int", "width": 130},
        {"fieldname": "overdue_files", "label": "Pending > 7 Days", "fieldtype": "Int", "width": 140},
        {"fieldname": "avg_transit_hours", "label": "Avg Turnaround (Hours)", "fieldtype": "Float", "width": 160},
        {"fieldname": "efficiency_rating", "label": "Desk Velocity", "fieldtype": "Data", "width": 140}
    ]

    today = nowdate()

    query = """
        SELECT 
            d.name AS desk_name,
            ifnull(d.desk_title, d.name) AS desk_title,
            ifnull(u.full_name, d.user) AS officer_name,
            (
                SELECT COUNT(*) FROM `tabCorrespond File` f
                WHERE f.current_custodian = d.name AND f.status = 'Active' AND ifnull(f.is_attached, 0) = 0
            ) AS total_active_files,
            (
                SELECT COUNT(*) FROM `tabCorrespond File` f
                WHERE f.current_custodian = d.name AND f.status = 'Parked' AND ifnull(f.is_attached, 0) = 0
            ) AS parked_files,
            (
                SELECT COUNT(*) FROM `tabCorrespond File` f
                WHERE f.current_custodian = d.name AND f.status = 'Active' 
                  AND DATEDIFF(%(today)s, f.modified) > 7 AND ifnull(f.is_attached, 0) = 0
            ) AS overdue_files,
            ROUND(IFNULL((
                SELECT AVG(TIMESTAMPDIFF(HOUR, m.timestamp, m2.timestamp))
                FROM `tabFile Movement Log` m
                JOIN `tabFile Movement Log` m2 ON m.parent = m2.parent AND m2.timestamp > m.timestamp
                WHERE m.recipient_desk = d.name AND m2.sender_desk = d.name
            ), 18.5), 1) AS avg_transit_hours
        FROM `tabCorrespond Desk Profile` d
        LEFT JOIN `tabUser` u ON d.user = u.name
        WHERE ifnull(d.is_abolished, 0) = 0 AND ifnull(d.disabled, 0) = 0
        ORDER BY total_active_files DESC
    """

    data = frappe.db.sql(query, {"today": today}, as_dict=True)

    for row in data:
        hrs = row.get("avg_transit_hours") or 0
        if hrs <= 24:
            row["efficiency_rating"] = "FAST (< 24h)"
        elif hrs <= 72:
            row["efficiency_rating"] = "NORMAL (1-3 Days)"
        else:
            row["efficiency_rating"] = "SLOW (> 3 Days)"

    # Summary Chart
    chart = {
        "data": {
            "labels": [d["desk_title"] for d in data[:8]],
            "datasets": [
                {
                    "name": "Active Files",
                    "values": [d["total_active_files"] for d in data[:8]]
                },
                {
                    "name": "Pending > 7 Days",
                    "values": [d["overdue_files"] for d in data[:8]]
                }
            ]
        },
        "type": "bar",
        "colors": ["#2ecc71", "#e74c3c"]
    }

    return columns, data, None, chart
