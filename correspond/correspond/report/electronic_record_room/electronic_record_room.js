frappe.query_reports["Electronic Record Room"] = {
    "filters": [],

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname === "retention_status" && data) {
            if (data.retention_status === "DUE FOR WEEDING") {
                return `<span class="badge badge-danger font-weight-bold" style="padding: 4px 6px;"><i class="fa fa-trash"></i> DUE FOR WEEDING</span>`;
            } else if (data.retention_status === "PERMANENT RECORD") {
                return `<span class="badge badge-success" style="padding: 4px 6px;"><i class="fa fa-archive"></i> PERMANENT</span>`;
            } else {
                return `<span class="badge badge-info" style="padding: 4px 6px;">RETAIN</span>`;
            }
        }

        if (column.fieldname === "status" && data) {
            let cls = data.status === "Archived" ? "badge-secondary" : "badge-warning";
            return `<span class="badge ${cls}" style="padding: 4px 6px;">${data.status}</span>`;
        }

        return value;
    }
};
