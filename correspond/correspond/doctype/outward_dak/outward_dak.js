frappe.ui.form.on('Outward Dak', {
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
        // Frappe child table grid custom column toggles can be handled via DOM or grid reload if needed
    }
});