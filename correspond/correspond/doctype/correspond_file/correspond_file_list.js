frappe.listview_settings['Correspond File'] = {
    onload: function(listview) {
        // Intercept the list view load and redirect directly to the Inbox report
        frappe.set_route('query-report', 'File Inbox');
    }
};