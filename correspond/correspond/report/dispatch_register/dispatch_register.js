frappe.query_reports["Dispatch Register"] = {
    "filters": [
        {
            "fieldname": "dfa_type",
            "label": __("DFA Type"),
            "fieldtype": "Select",
            "options": "\nOffice Memorandum\nDemi-Official (D.O.) Letter\nSanction Order\nCircular\nOffice Order\nGeneral Letter"
        },
        {
            "fieldname": "dispatch_mode",
            "label": __("Dispatch Mode"),
            "fieldtype": "Select",
            "options": "\nEmail\nSpeed Post\nRegistered Post\nSpecial Messenger / Peon Book\nBy Hand\nPortal Upload"
        }
    ],

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname === "dispatch_register_no" && data && data.dispatch_register_no) {
            return `<b style="color: #155724; font-family: monospace;">${data.dispatch_register_no}</b>`;
        }

        if (column.fieldname === "status" && data) {
            let cls = data.status === "Dispatched" ? "badge-success" : (data.status === "Approved" ? "badge-info" : "badge-secondary");
            return `<span class="badge ${cls}" style="padding: 4px 6px; font-size: 11px;">${data.status}</span>`;
        }

        return value;
    }
};
