frappe.query_reports["File Outbox"] = {
    "filters": [],
    
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        // 1. Formatting for "Initiate Action"
        if (column.fieldname === "action" && data && data.file_number) {
            return `<a href="/app/correspond-file/${encodeURIComponent(data.file_number)}" 
                       style="color: #0052cc; text-decoration: underline; font-weight: 500; font-size: 12px;">
                       Initiate Action
                    </a>`;
        }

        // 2. Formatting for the "Attachments" Popup Link
        if (column.fieldname === "attachments" && data) {
            if (data.attachments) {
                let files = data.attachments.split(',');
                let count = files.length;
                let safe_files = encodeURIComponent(JSON.stringify(files));
                
                return `<a href="javascript:void(0);" onclick="window.show_outbox_attachments('${safe_files}')" 
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
// LIST DIALOG: Shows the list of attached files
// ==========================================================
window.show_outbox_attachments = function(encoded_files) {
    let files = JSON.parse(decodeURIComponent(encoded_files));
    
    let html = '<div style="margin-bottom: 10px; color: #555;">The following sub-files moved inside this master folder:</div><ul class="list-group">';
    files.forEach(f => {
        // Changed href to trigger the iframe popup function
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

// ==========================================================
// IFRAME DIALOG: Opens the actual file in a full-screen popup
// ==========================================================
window.open_iframe_file = function(docname) {
    let url = `/app/correspond-file/${encodeURIComponent(docname)}?view=iframe`;
    
    let dialog = new frappe.ui.Dialog({
        title: `<i class="fa fa-folder-open text-warning"></i> Viewing Attached File: <b>${docname}</b>`,
        size: 'extra-large', 
        fields: [
            {
                fieldname: 'file_frame',
                fieldtype: 'HTML',
                options: `<div style="height: 82vh; width: 100%; overflow: hidden; border-radius: 4px;"><iframe src="${url}" style="width: 100%; height: 100%; border: none;"></iframe></div>`
            }
        ]
    });

    dialog.$wrapper.find('.modal-dialog').css({'max-width': '95vw', 'width': '95vw'});
    dialog.show();
};

// ==========================================================
// AUTO-REFRESH: Triggers when navigating from the sidebar
// ==========================================================
frappe.router.on('change', () => {
    let route = frappe.get_route();
    if (route[0] === 'query-report' && route[1] === 'File Outbox') {
        setTimeout(() => {
            if (frappe.query_report) {
                frappe.query_report.refresh();
            }
        }, 100);
    }
});
