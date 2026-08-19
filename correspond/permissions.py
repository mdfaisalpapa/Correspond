import frappe

# --- INWARD DAK SECURITY ---
def get_inward_dak_query(user):
    """Filters the List View and Reports so users only see their own Daks."""
    if not user: user = frappe.session.user
    if "System Manager" in frappe.get_roles(user):
        return "" # System Managers see everything
    
    return f"(`tabInward Dak`.assigned_to = '{user}')"

def has_inward_dak_permission(doc, user=None, permission_type="read"):
    """Prevents users from accessing a Dak via direct URL if it isn't theirs."""
    if not user: user = frappe.session.user
    if "System Manager" in frappe.get_roles(user):
        return True
        
    return doc.assigned_to == user


# --- CORRESPOND FILE SECURITY ---
def get_correspond_file_query(user):
    """Filters the List View and Reports so users only see Files in their custody."""
    if not user: user = frappe.session.user
    if "System Manager" in frappe.get_roles(user):
        return ""
        
    return f"(`tabCorrespond File`.current_custodian = '{user}')"

def has_correspond_file_permission(doc, user=None, permission_type="read"):
    """Prevents users from accessing a File via direct URL if it isn't theirs."""
    if not user: user = frappe.session.user
    if "System Manager" in frappe.get_roles(user):
        return True
        
    return doc.current_custodian == user