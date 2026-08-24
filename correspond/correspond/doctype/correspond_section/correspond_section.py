import frappe
from frappe.model.document import Document

class CorrespondSection(Document):
    def autoname(self):
        # Extract the department abbreviation or code
        dept = self.department.split(" - ")[0].strip() if self.department else "GEN"
        abbr = self.section_abbr.strip() if self.section_abbr else "GENL"
        
        # Generates a clean composite ID like "AC-ADMN2"
        self.name = f"{dept}-{abbr}"