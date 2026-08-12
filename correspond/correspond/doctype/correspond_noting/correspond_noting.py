# Copyright (c) 2026, Mohammed Faisal and contributors
# For license information, please see license.txt

import re
import frappe
from frappe.model.document import Document


class CorrespondNoting(Document):

  def validate(self):
    self.validate_internal_references()

  def validate_internal_references(self):
    if not self.note_details:
      return

    # Regular expression to catch any internal app links embedded in the text editor HTML
    pattern = r'href=["\'](/app/(correspond-noting|correspond-dak)/([^"\']+))["\']'
    matches = re.findall(pattern, self.note_details)

    for full_path, doctype_slug, target_name in matches:
      target_doctype = (
          'Correspond Noting'
          if 'noting' in doctype_slug
          else 'Correspond Dak'
      )

      # 1. Verify the document actually exists
      if not frappe.db.exists(target_doctype, target_name):
        frappe.throw(
            f'Invalid Reference: The referenced document "{target_name}" does'
            ' not exist in the system.'
        )

      # 2. Verify the document belongs to the exact same file
      target_file = frappe.db.get_value(target_doctype, target_name, 'file')
      if target_file != self.file:
        frappe.throw(
            f'Validation Error: Document "{target_name}" belongs to a'
            ' different file and cannot be referenced here.'
        )
