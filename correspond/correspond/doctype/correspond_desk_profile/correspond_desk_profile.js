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

    refresh: function(frm) {
        // 3. Make all fields read-only for non-admins, leaving only the signature block editable
        let is_admin = frappe.user.has_role("System Manager");
        
        if (!is_admin) {
            $.each(frm.fields_dict, function(fieldname, field) {
                if (fieldname !== 'signature_block') {
                    frm.set_df_property(fieldname, 'read_only', 1);
                }
            });
        }
    },

    // =========================================================
    // AUTO-RESIZE SIGNATURE IMAGE BEFORE SAVING
    // =========================================================
    before_save: function(frm) {
        if (frm.doc.signature_block) {
            // Create a temporary invisible container to safely read the HTML
            let temp_div = document.createElement('div');
            temp_div.innerHTML = frm.doc.signature_block;

            // Find all images inside the signature text editor
            let images = temp_div.getElementsByTagName('img');
            let modified = false;

            // Loop through any found images and force them to signature size
            for (let i = 0; i < images.length; i++) {
                images[i].style.maxWidth = '160px';
                images[i].style.maxHeight = '65px';
                images[i].style.width = 'auto';
                images[i].style.height = 'auto';
                images[i].style.objectFit = 'contain';
                modified = true;
            }

            // If we modified an image, quietly update the field before the database saves it
            if (modified) {
                frm.set_value('signature_block', temp_div.innerHTML);
            }
        }
    },
    
    // 4. Auto-fetch the Default Department when an Office is selected
    office: function(frm) {
        if (frm.doc.office) {
            frappe.db.get_value('Correspond Office', frm.doc.office, 'default_department')
            .then(r => {
                if (r && r.message && r.message.default_department) {
                    frm.set_value('department', r.message.default_department);
                }
            });
        }
    },
    
    // 5. Clear dependent fields automatically if the user changes the Department midway
    department: function(frm) {
        frm.set_value('section', '');
        frm.set_value('designation', '');
    }
});