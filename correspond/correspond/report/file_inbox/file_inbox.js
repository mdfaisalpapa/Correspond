frappe.query_reports["File Inbox"] = {
    "filters": [],
    
    "onload": function(report) {
        // Add Bulk Forward button to the top right of the report
        report.page.add_inner_button(__('Bulk Forward'), function() {
            
            let selected_files = [];
            if (report.data) {
                selected_files = report.data.filter(d => d.select === 1 || d.select === true).map(d => d.file_number);
            }

            if (selected_files.length === 0) {
                frappe.msgprint({ title: 'Notice', message: 'Please select at least one file using the checkboxes.', indicator: 'orange' });
                return;
            }

            let d = new frappe.ui.Dialog({
                title: 'Bulk Forward Files',
                fields: [
                    {
                        fieldname: 'help_text',
                        fieldtype: 'HTML',
                        options: `<div class="alert alert-info">You are about to securely transfer <b>${selected_files.length}</b> file(s) to a new desk.</div>`
                    },
                    {
                        label: 'Forward To (Select Desk)',
                        fieldname: 'recipient_profile',
                        fieldtype: 'Link',
                        options: 'Correspond Desk Profile',
                        reqd: 1,
                        get_query: () => {
                            return {
                                query: 'correspond.correspond.doctype.correspond_file.correspond_file.get_forward_recipients'
                            };
                        }
                    },
                    {
                        label: 'Remarks',
                        fieldname: 'remarks',
                        fieldtype: 'Small Text',
                        reqd: 1,
                        default: 'Files transferred due to desk reassignment/merger.'
                    }
                ],
                primary_action_label: `Forward ${selected_files.length} File(s)`,
                primary_action(values) {
                    d.get_primary_btn().prop('disabled', true);
                    
                    frappe.call({
                        method: 'correspond.correspond.doctype.correspond_file.correspond_file.bulk_forward_files',
                        args: {
                            file_names: JSON.stringify(selected_files),
                            recipient_profile: values.recipient_profile,
                            remarks: values.remarks
                        },
                        callback: function(res) {
                            d.hide();
                            if (!res.exc) {
                                frappe.show_alert({
                                    message: `Successfully forwarded ${res.message.count} files!`, 
                                    indicator: 'green'
                                });
                                report.refresh();
                            }
                        }
                    });
                }
            });
            d.show();
        });
    },

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if ((column.fieldname === "file_number" || column.fieldname === "subject") && data && data.file_number) {
            let display_text = column.fieldname === "file_number" ? data.file_number : (data.subject || '');
            return `<a href="/app/correspond-file/${encodeURIComponent(data.file_number)}" 
                       onclick="sessionStorage.setItem('correspond_source', 'File Inbox');"
                       style="color: #0052cc; text-decoration: underline; font-weight: 500;">
                       ${display_text}
                    </a>`;
        }

        if (column.fieldname === "attachments" && data) {
            if (data.attachments) {
                let files = data.attachments.split(',');
                let count = files.length;
                let safe_files = encodeURIComponent(JSON.stringify(files));
                
                return `<a href="javascript:void(0);" onclick="window.show_inbox_attachments('${safe_files}')" 
                           style="color: #e67e22; font-weight: 600; font-size: 12px;">
                           <i class="fa fa-paperclip" style="margin-right: 3px;"></i> ${count} Attached
                        </a>`;
            } else {
                return `<span style="color: #a3a3a3; font-size: 12px;">None</span>`;
            }
        }

        return value;
    }
};

// ==========================================================
// POPUP DIALOG LOGIC
// ==========================================================
window.show_inbox_attachments = function(encoded_files) {
    let files = JSON.parse(decodeURIComponent(encoded_files));
    let html = '<div style="margin-bottom: 10px; color: #555;">Sub-files currently attached to this master folder:</div><ul class="list-group">';
    
    files.forEach(f => {
        html += `<li class="list-group-item" style="padding: 10px;">
                    <a href="javascript:void(0);" onclick="window.open_iframe_file('${f}')" style="font-weight: 500;">
                        <i class="fa fa-folder-open text-warning" style="margin-right: 5px;"></i> ${f}
                    </a>
                 </li>`;
    });
    html += '</ul>';

    let d = new frappe.ui.Dialog({
        title: 'Attached Sub-files',
        fields: [{ fieldname: 'file_list', fieldtype: 'HTML', options: html }]
    });
    d.show();
};

window.open_iframe_file = function(docname) {
    let url = `/app/correspond-file/${encodeURIComponent(docname)}?view=iframe`;
    let dialog = new frappe.ui.Dialog({
        title: `<i class="fa fa-folder-open text-warning"></i> Viewing Attached File: <b>${docname}</b>`,
        size: 'extra-large', 
        fields: [
            { fieldname: 'file_frame', fieldtype: 'HTML', options: `<div style="height: 82vh; width: 100%; overflow: hidden; border-radius: 4px;"><iframe src="${url}" style="width: 100%; height: 100%; border: none;"></iframe></div>` }
        ]
    });
    dialog.$wrapper.find('.modal-dialog').css({'max-width': '95vw', 'width': '95vw'});
    dialog.show();
};

frappe.router.on('change', () => {
    let route = frappe.get_route();
    if (route[0] === 'query-report' && route[1] === 'File Inbox') {
        setTimeout(() => { if (frappe.query_report) frappe.query_report.refresh(); }, 100);
    }
});
