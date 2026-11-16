import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate

class CorrespondDelegationRule(Document):
    def validate(self):
        if self.desk == self.delegate_desk:
            frappe.throw(_("Primary Desk and Delegate Desk cannot be the same."))

        if self.from_date and self.to_date and getdate(self.from_date) > getdate(self.to_date):
            frappe.throw(_("From Date cannot be later than To Date."))

def get_active_delegated_desks(user):
    """
    Returns list of primary desks currently delegated to any of the user's active desks.
    Used by inbox queries and permission checks.
    """
    user_desks = frappe.get_all("Correspond Desk Profile", filters={"user": user, "is_abolished": 0, "disabled": 0}, pluck="name")
    if not user_desks:
        return []

    today = nowdate()
    delegated_desks = frappe.db.sql("""
        SELECT DISTINCT desk
        FROM `tabCorrespond Delegation Rule`
        WHERE delegate_desk IN %(desks)s
          AND is_active = 1
          AND from_date <= %(today)s
          AND (to_date IS NULL OR to_date >= %(today)s)
    """, {"desks": user_desks, "today": today}, pluck="desk")

    return delegated_desks or []
