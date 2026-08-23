frappe.query_reports["File Outbox"] = {
    "filters": [],
    
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if ((column.fieldname === "file_number" || column.fieldname === "subject") && data && data.file_number) {
            let display_text = column.fieldname === "file_number" ? data.file_number : (data.subject || '');
            return `<a href="/app/correspond-file/${encodeURIComponent(data.file_number)}" 
                       onclick="sessionStorage.setItem('correspond_source', 'File Outbox');"
                       style="color: #0052cc; text-decoration: underline; font-weight: 500;">
                       ${display_text}
                    </a>`;
        }

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

window.show_outbox_attachments = function(encoded_files) {
    let files = JSON.parse(decodeURIComponent(encoded_files));
    
    let html = '<div style="margin-bottom: 10px; color: #555;">The following sub-files moved inside this master folder:</div><ul class="list-group">';
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

window.open_correspond_file = function(file_number, source) {
    sessionStorage.setItem('correspond_source', source);
    frappe.set_route('correspond-file', file_number);
};
