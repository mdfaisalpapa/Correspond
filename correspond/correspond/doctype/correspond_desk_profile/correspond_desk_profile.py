import frappe
from frappe.model.document import Document

class CorrespondDeskProfile(Document):
    def autoname(self):
        # 1. Clean the Department (Removes the " - KVC3" suffix automatically)
        clean_dept = self.department.split(" - ")[0].strip() if self.department else None
        
        # 2. Gather the parts
        parts = [
            self.office.strip() if self.office else None,
            clean_dept,
            self.section.strip() if self.section else None
        ]
        
        # 3. Format the designation with the seat number ONLY if a seat number exists
        if self.designation:
            if self.seat_number:
                desig_part = f"{self.designation.strip()}-{self.seat_number.strip()}"
            else:
                desig_part = self.designation.strip()
            parts.append(desig_part)
        
        # 4. Join them together with slashes
        self.name = "/".join(filter(None, parts))
