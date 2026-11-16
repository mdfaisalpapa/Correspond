frappe.query_reports["Desk TAT Analytics"] = {
    "filters": [],

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname === "efficiency_rating" && data) {
            let cls = data.efficiency_rating.includes("FAST") ? "badge-success" : (data.efficiency_rating.includes("NORMAL") ? "badge-info" : "badge-danger");
            return `<span class="badge ${cls}" style="padding: 4px 6px;">${data.efficiency_rating}</span>`;
        }

        if (column.fieldname === "overdue_files" && data && data.overdue_files > 0) {
            return `<b style="color: #dc3545;">${data.overdue_files} File(s)</b>`;
        }

        return value;
    }
};
