import frappe

# ==========================================
# INWARD DAK SECURITY
# ==========================================

def get_inward_dak_query(user):
    """Filters the List View. System Managers and Registry Clerks see all Daks."""
    if not user: user = frappe.session.user
    roles = frappe.get_roles(user)
    
    if "System Manager" in roles or "Correspond Registry Clerk" in roles:
        return "" 
    
    # CHANGED: 'assigned_to' updated to 'recipient'
    return f"(`tabInward Dak`.recipient = '{user}')"

def has_inward_dak_permission(doc, user=None, permission_type="read"):
    """Prevents unauthorized URL access."""
    if not user: user = frappe.session.user
    roles = frappe.get_roles(user)
    
    if "System Manager" in roles or "Correspond Registry Clerk" in roles:
        return True
        
    # CHANGED: 'assigned_to' updated to 'recipient'
    return doc.recipient == user


# ==========================================
# CORRESPOND FILE SECURITY
# ==========================================

def get_correspond_file_query(user):
    """Filters the List View so users ONLY see files currently in their active custody."""
    if not user: user = frappe.session.user
    roles = frappe.get_roles(user)
    
    if "System Manager" in roles or "Correspond Registry Clerk" in roles:
        return ""
        
    # Strictly limit the Inbox list view to active custody and attached sub-files
    return f"""(
        `tabCorrespond File`.current_custodian = '{user}' 
        OR 
        (`tabCorrespond File`.is_attached = 1 AND `tabCorrespond File`.attached_to IN (
            SELECT name FROM `tabCorrespond File` WHERE current_custodian = '{user}'
        ))
    )
    """

def has_correspond_file_permission(doc, user=None, permission_type="read"):
    """Prevents access unless user is custodian, master custodian, or has movement history."""
    if not user: user = frappe.session.user
    roles = frappe.get_roles(user)
    
    if "System Manager" in roles or "Correspond Registry Clerk" in roles:
        return True
        
    # 1. User has direct custody of the file
    if doc.current_custodian == user:
        return True
        
    # 2. File is an attached sub-file, and user has custody of the Master File
    if doc.is_attached and doc.attached_to:
        master_custodian = frappe.db.get_value("Correspond File", doc.attached_to, "current_custodian")
        if master_custodian == user:
            return True
            
    # 3. User previously held the file (Supports Outbox routing visibility)
    has_history = frappe.db.exists(
        "File Movement Log", 
        {"parent": doc.name, "moved_from": user, "parenttype": "Correspond File"}
    )
    if has_history:
        return True
            
    return False