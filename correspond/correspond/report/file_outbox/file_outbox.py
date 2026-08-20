import frappe

def execute(filters=None):
    user = frappe.session.user
    
    # 1. Define the columns for the Outbox report grid
    columns = [
        {
            "fieldname": "name", 
            "label": "File ID", 
            "fieldtype": "Link", 
            "options": "Correspond File", 
            "width": 160
        },
        {
            "fieldname": "subject", 
            "label": "Subject", 
            "fieldtype": "Data", 
            "width": 320
        },
        {
            "fieldname": "current_custodian", 
            "label": "Current Custodian", 
            "fieldtype": "Link", 
            "options": "User", 
            "width": 180
        },
        {
            "fieldname": "modified", 
            "label": "Last Updated", 
            "fieldtype": "Datetime", 
            "width": 150
        }
    ]
    
    # 2. Pure SQL logic: Files the user moved away, but doesn't currently hold
    data = frappe.db.sql("""
        SELECT DISTINCT 
            df.name, 
            df.subject, 
            df.current_custodian,
            df.modified
        FROM `tabCorrespond File` df
        JOIN `tabFile Movement Log` fml ON fml.parent = df.name
        WHERE fml.moved_from = %s
          AND df.current_custodian != %s
          AND fml.parenttype = 'Correspond File'
        ORDER BY df.modified DESC
    """, (user, user), as_dict=True)
    
    return columns, data