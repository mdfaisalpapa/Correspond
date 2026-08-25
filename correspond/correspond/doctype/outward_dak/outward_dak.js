frappe.ui.form.on('Outward Dak', {
    setup: function(frm) {
        frm.set_query("internal_recipient", function() {
            return { query: "correspond.correspond.doctype.correspond_file.correspond_file.get_forward_recipients" };
        });

        frm.set_query("internal_user", "cc_list", function() {
            return { query: "correspond.correspond.doctype.correspond_file.correspond_file.get_forward_recipients" };
        });
    },

    refresh: function(frm) {
        frm.trigger('recipient_type');

        try {
            frm.page.wrapper.find('.form-footer, .timeline').hide();
        } catch (e) {}

        try {
            let target_report = null;
            let history = frappe.route_history || [];
            
            // 1. Scan active history first
            for (let i = history.length - 1; i >= 0; i--) {
                let route = history[i];
                if (!route || !Array.isArray(route)) continue;

                if (route[0] === "query-report" && route[1] === "Dak Inbox") {
                    target_report = "Dak Inbox"; break;
                } else if (route[0] === "query-report" && route[1] === "Dak Outbox") {
                    target_report = "Dak Outbox"; break;
                } else if (route[0] === "correspond-file" || (route[0] === "Form" && route[1] === "Correspond File")) {
                    target_report = "File"; break;
                }
            }

            // 2. Document-Specific Memory Check
            let session_key = 'outward_dak_source_' + frm.doc.name;
            
            if (target_report) {
                // Save the verified history to the document's unique slot
                sessionStorage.setItem(session_key, target_report);
            } else {
                // If history is wiped (e.g., F5 refresh), read from the slot
                target_report = sessionStorage.getItem(session_key) || "Dak Outbox";
            }

            // 3. Rewrite Form Breadcrumbs
            setTimeout(() => {
                $('.form-page-controls .prev-doc, .form-page-controls .next-doc, .prev-doc, .next-doc').hide();
                let route_str = frappe.get_route_str();
                
                if (typeof frappe.breadcrumbs !== 'undefined') {
                    frappe.breadcrumbs.all = frappe.breadcrumbs.all || {}; 
                    if (target_report === 'File' && frm.doc.primary_file) {
                        frappe.breadcrumbs.all[route_str] = { type: 'Custom', route: '/app/correspond-file/' + encodeURIComponent(frm.doc.primary_file), label: 'File: ' + frm.doc.primary_file };
                    } else {
                        frappe.breadcrumbs.all[route_str] = { type: 'Custom', route: '/app/query-report/' + encodeURIComponent(target_report), label: target_report };
                    }
                    if (typeof frappe.breadcrumbs.update === 'function') frappe.breadcrumbs.update();
                }

                setTimeout(() => {
                    let link_href = (target_report === 'File' && frm.doc.primary_file) ? '/app/correspond-file/' + encodeURIComponent(frm.doc.primary_file) : '/app/query-report/' + encodeURIComponent(target_report);
                    let link_label = (target_report === 'File' && frm.doc.primary_file) ? 'File: ' + frm.doc.primary_file : target_report;

                    $('.page-breadcrumbs a').each(function() {
                        let text = $(this).text().trim();
                        if (text !== 'Home' && text !== '') {
                            $(this).attr('href', link_href).text(link_label);
                        }
                    });
                }, 50);
            }, 300);
        } catch (err) {
            console.error("Custom Breadcrumb Error:", err);
        }
    },

    recipient_type: function(frm) {
        let is_internal = frm.doc.recipient_type === 'Internal User';
        frm.toggle_display('internal_recipient', is_internal);
        frm.toggle_display('receiver', !is_internal);
        frm.toggle_display('receiver_email', !is_internal);
    }
});

frappe.ui.form.on('Outward Dak CC', {
    recipient_type: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        let is_internal = row.recipient_type === 'Internal User';
    }
});
