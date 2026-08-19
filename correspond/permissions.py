import frappe

# --- INWARD DAK SECURITY ---
def get_inward_dak_query(user):
    """Filters the List View. System Managers and Registry Clerks see all Daks."""
    if not user: user = frappe.session.user
    roles = frappe.get_roles(user)
    
    if "System Manager" in roles or "Correspond Registry Clerk" in roles:
        return "" 
    
    return f"(`tabInward Dak`.assigned_to = '{user}')"

def has_inward_dak_permission(doc, user=None, permission_type="read"):
    """Prevents unauthorized URL access."""
    if not user: user = frappe.session.user
    roles = frappe.get_roles(user)
    
    if "System Manager" in roles or "Correspond Registry Clerk" in roles:
        return True
        
    return doc.assigned_to == user


# --- CORRESPOND FILE SECURITY ---
def get_correspond_file_query(user):
    """Filters the List View so users see files in their custody AND files attached to those files."""
    if not user: user = frappe.session.user
    roles = frappe.get_roles(user)
    
    if "System Manager" in roles or "Correspond Registry Clerk" in roles:
        return ""
        
    return f"""(
        `tabCorrespond File`.current_custodian = '{user}' 
        OR 
        (`tabCorrespond File`.is_attached = 1 AND `tabCorrespond File`.attached_to IN (
            SELECT name FROM `tabCorrespond File` WHERE current_custodian = '{user}'
        ))
    )"""

def has_correspond_file_permission(doc, user=None, permission_type="read"):
    """Prevents access unless user is custodian of the file, OR custodian of the master file it is attached to."""
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
            
    return False