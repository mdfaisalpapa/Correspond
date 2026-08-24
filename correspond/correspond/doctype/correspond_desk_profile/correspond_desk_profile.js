frappe.ui.form.on('Correspond Desk Profile', {
    setup: function(frm) {
        
        // 1. Filter the SECTION dropdown to include specific department sections AND global sections
        frm.set_query("section", function() {
            let selected_dept = frm.doc.department;
            
            if (!selected_dept) {
                return { filters: {} };
            }

            return {
                filters: [
                    ["Correspond Section", "department", "in", [selected_dept, "All Departments", "", null]]
                ]
            };
        });

        // 2. Filter the DESIGNATION dropdown
        frm.set_query("designation", function() {
            let selected_dept = frm.doc.department;
            
            if (!selected_dept) {
                return { filters: {} };
            }

            return {
                filters: [
                    ["Designation", "custom_department", "=", selected_dept]
                ]
            };
        });
    },
    
    // 3. Auto-fetch the Default Department when an Office is selected
    office: function(frm) {
        if (frm.doc.office) {
            // Call the database to get the default_department from the selected Correspond Office
            frappe.db.get_value('Correspond Office', frm.doc.office, 'default_department')
            .then(r => {
                if (r && r.message && r.message.default_department) {
                    // Set the department field, which will automatically trigger the filter updates
                    frm.set_value('department', r.message.default_department);
                }
            });
        }
    },
    
    // 4. Clear dependent fields automatically if the user changes the Department midway
    department: function(frm) {
        frm.set_value('section', '');
        frm.set_value('designation', '');
    }
});
