import frappe

# ==========================================
# INWARD DAK SECURITY
# ==========================================
def get_inward_dak_query(user):
    """
    Filters the List View. 
    - System Managers see all.
    - Registry Clerks see all External Daks OR Daks explicitly assigned to them.
    - Normal users see only Daks assigned to them.
    """
    if not user: user = frappe.session.user
    roles = frappe.get_roles(user)
    
    if "System Manager" in roles:
        return "" 
        
    if "Correspond Registry Clerk" in roles:
        # Exclude internal transfers unless the clerk is the explicit recipient
        return f"(`tabInward Dak`.receipt_mode != 'Internal Transfer' OR `tabInward Dak`.recipient = '{user}')"
        
    return f"(`tabInward Dak`.recipient = '{user}')"

def has_inward_dak_permission(doc, user=None, permission_type="read"):
    """Prevents unauthorized URL access for Inward Dak."""
    if not user: user = frappe.session.user
    roles = frappe.get_roles(user)
    
    if "System Manager" in roles:
        return True
        
    if "Correspond Registry Clerk" in roles:
        if doc.receipt_mode != 'Internal Transfer':
            return True
        return doc.recipient == user
        
    return doc.recipient == user


# ==========================================
# CORRESPOND FILE SECURITY
# ==========================================
def get_correspond_file_query(user):
    """
    STRICT INBOX LOCK: 
    Forces the List View to act as a secure Inbox for ALL users (including Registry Clerks).
    """
    if not user: user = frappe.session.user
    roles = frappe.get_roles(user)
    
    if "System Manager" in roles:
        return ""
        
    # Standard rule: Must be active custodian and file must not be attached
    return f"(`tabCorrespond File`.current_custodian = '{user}' AND ifnull(`tabCorrespond File`.is_attached, 0) = 0)"

def has_correspond_file_permission(doc, user=None, permission_type="read"):
    """
    DOCUMENT ACCESS LOGIC:
    Controls who can actually open and view the file form.
    """
    if not user: user = frappe.session.user
    roles = frappe.get_roles(user)
    
    if "System Manager" in roles:
        return True
        
    # 1. Allow if they are the active custodian
    if doc.current_custodian == user:
        return True
        
    # 2. Allow if the file is an attached sub-file, and they hold the Master File
    if doc.is_attached and doc.attached_to:
        master_custodian = frappe.db.get_value("Correspond File", doc.attached_to, "current_custodian")
        if master_custodian == user:
            return True
            
    # 3. Allow read-only access if they previously held the file (Needed for Outbox viewing)
    has_history = frappe.db.exists(
        "File Movement Log", 
        {"parent": doc.name, "moved_from": user, "parenttype": "Correspond File"}
    )
    if has_history:
        return True
            
    return False
