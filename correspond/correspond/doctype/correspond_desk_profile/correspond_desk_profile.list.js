frappe.listview_settings['Correspond Desk Profile'] = {
    refresh: function(listview) {
        let is_admin = frappe.user.has_role("System Manager");
        
        // Only intercept for regular users; let System Managers manage the full list
        if (!is_admin) {
            // Hide the list view container immediately to prevent flickering
            $(listview.wrapper).find('.layout-main').hide();

            // Fetch the specific profile name tied to the logged-in user
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Correspond Desk Profile',
                    filters: { user: frappe.session.user },
                    fieldname: 'name'
                },
                callback: function(r) {
                    if (r.message && r.message.name) {
                        // Instantly jump straight to their personal form view
                        frappe.set_route('Form', 'Correspond Desk Profile', r.message.name);
                    } else {
                        // Unhide layout and show a clean message if the profile is missing
                        $(listview.wrapper).find('.layout-main').show();
                        frappe.msgprint({
                            title: __('Profile Not Found'),
                            indicator: 'orange',
                            message: __('No Desk Profile has been assigned to your user account ({0}) yet. Please contact your System Manager to create one.', [frappe.session.user])
                        });
                    }
                }
            });
        }
    }
};