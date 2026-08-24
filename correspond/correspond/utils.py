import frappe
from frappe import _

def block_rename(doc, method=None):
    frappe.throw(
        _("Renaming {0} codes is strictly restricted to maintain audit history and file movement integrity.").format(doc.doctype)
    )
