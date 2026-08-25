frappe.listview_settings['Outward Dak'] = {
    onload: function(listview) {
        // Show a quick warning message
        frappe.show_alert({
            message: __('Direct access to the Outward Dak list is disabled. Redirecting to Outbox...'),
            indicator: 'orange'
        });
        
        // Instantly bounce them back to the Dak Outbox
        frappe.set_route('query-report', 'Dak Outbox');
    }
};
