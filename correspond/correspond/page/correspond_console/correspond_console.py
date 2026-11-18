import frappe
from frappe import _

@frappe.whitelist()
def get_console_data(tab="file_inbox"):
    """
    Returns data and badge counts for the Correspond Desk Console.
    Tabs: 'file_inbox', 'file_outbox', 'dak_inbox', 'dak_outbox'
    """
    user = frappe.session.user
    auth_desks = frappe.get_all(
        "Correspond Desk Profile",
        filters={"user": user, "is_abolished": 0, "disabled": 0},
        pluck="name",
    )

    counts = {
        "file_inbox": 0,
        "file_outbox": 0,
        "dak_inbox": 0,
        "dak_outbox": 0,
    }

    if not auth_desks:
        return {"counts": counts, "data": []}

    # Count File Inbox
    counts["file_inbox"] = frappe.db.count(
        "Correspond File",
        filters={
            "current_custodian": ["in", auth_desks],
            "is_attached": 0,
            "status": ["in", ["Active", "Parked"]],
        },
    )

    # Count File Outbox (files sent by user's desks)
    outbox_files = frappe.db.sql(
        """
        SELECT COUNT(DISTINCT log.parent) as c
        FROM `tabFile Movement Log` log
        JOIN `tabCorrespond File` cf ON log.parent = cf.name
        WHERE log.sender_desk IN %(auth_desks)s
          AND log.action = 'Forwarded'
          AND cf.current_custodian NOT IN %(auth_desks)s
        """,
        {"auth_desks": auth_desks},
        as_dict=True,
    )
    counts["file_outbox"] = outbox_files[0].c if outbox_files else 0

    # Count Dak Inbox (Inward Dak assigned to user or not yet linked to an active file)
    counts["dak_inbox"] = frappe.db.count(
        "Inward Dak",
        filters={
            "docstatus": ["<", 2],
            "status": ["!=", "Closed"],
        },
    )

    # Count Dak Outbox (Outward Dak drafted or dispatched from user's desk)
    counts["dak_outbox"] = frappe.db.count(
        "Outward Dak",
        filters={
            "docstatus": ["<", 2],
        },
    )

    items = []
    if tab == "file_inbox":
        items = frappe.db.sql(
            """
            SELECT 
                df.name as name, 
                df.subject,
                ifnull(df.status, 'Active') as status,
                df.modified,
                (
                    SELECT CONCAT(IFNULL(u.full_name, d.user), ' (', IFNULL(d.desk_title, d.name), ')')
                    FROM `tabFile Movement Log` fml
                    JOIN `tabCorrespond Desk Profile` d ON fml.sender_desk = d.name
                    LEFT JOIN `tabUser` u ON d.user = u.name
                    WHERE fml.parent = df.name AND fml.action = 'Forwarded'
                    ORDER BY fml.timestamp DESC LIMIT 1
                ) as sent_by,
                (
                    SELECT timestamp 
                    FROM `tabFile Movement Log` 
                    WHERE parent = df.name AND action = 'Forwarded' 
                    ORDER BY timestamp DESC LIMIT 1
                ) as sent_on,
                (
                    SELECT remarks 
                    FROM `tabFile Movement Log` 
                    WHERE parent = df.name AND action = 'Forwarded' 
                    ORDER BY timestamp DESC LIMIT 1
                ) as remarks
            FROM `tabCorrespond File` df
            WHERE df.current_custodian IN %(auth_desks)s
              AND ifnull(df.is_attached, 0) = 0
              AND ifnull(df.status, 'Active') IN ('Active', 'Parked')
            ORDER BY COALESCE(
                (SELECT timestamp FROM `tabFile Movement Log` WHERE parent = df.name AND action = 'Forwarded' ORDER BY timestamp DESC LIMIT 1),
                df.modified
            ) DESC
            LIMIT 100
            """,
            {"auth_desks": auth_desks},
            as_dict=True,
        )

    elif tab == "file_outbox":
        items = frappe.db.sql(
            """
            SELECT 
                log.parent AS name,
                file.subject,
                CONCAT(IFNULL(ru.full_name, rdesk.user), ' (', IFNULL(rdesk.desk_title, rdesk.name), ')') AS recipient_desk,
                log.timestamp as sent_on,
                CONCAT(IFNULL(cu.full_name, cdesk.user), ' (', IFNULL(cdesk.desk_title, cdesk.name), ')') AS currently_with,
                ifnull(log.is_opened, 0) AS is_opened,
                CASE 
                    WHEN log.action = 'Forwarded' 
                         AND ifnull(log.is_opened, 0) = 0 
                         AND file.current_custodian = log.recipient_desk 
                    THEN 1 
                    ELSE 0 
                END AS can_pull_back,
                log.remarks
            FROM `tabFile Movement Log` log
            JOIN `tabCorrespond File` file ON log.parent = file.name
            LEFT JOIN `tabCorrespond Desk Profile` rdesk ON log.recipient_desk = rdesk.name
            LEFT JOIN `tabUser` ru ON rdesk.user = ru.name
            LEFT JOIN `tabCorrespond Desk Profile` cdesk ON file.current_custodian = cdesk.name
            LEFT JOIN `tabUser` cu ON cdesk.user = cu.name
            WHERE log.sender_desk IN %(auth_desks)s
              AND log.action = 'Forwarded'
            ORDER BY log.timestamp DESC
            LIMIT 100
            """,
            {"auth_desks": auth_desks},
            as_dict=True,
        )

    elif tab == "dak_inbox":
        items = frappe.get_all(
            "Inward Dak",
            fields=[
                "name",
                "subject",
                "sender_organization",
                "receipt_mode",
                "is_vip_reference",
                "vip_category",
                "creation",
                "status",
            ],
            order_by="creation desc",
            limit=100,
        )

    elif tab == "dak_outbox":
        items = frappe.get_all(
            "Outward Dak",
            fields=[
                "name",
                "subject",
                "dfa_type",
                "recipient_name",
                "dispatch_mode",
                "dispatch_number",
                "creation",
                "status",
            ],
            order_by="creation desc",
            limit=100,
        )

    return {"counts": counts, "data": items}
