frappe.query_reports["VIP Reference Tracker"] = {
    "filters": [],

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname === "urgency" && data) {
            if (data.urgency === "OVERDUE") {
                return `<span class="badge badge-danger font-weight-bold" style="padding: 4px 6px;"><i class="fa fa-exclamation-triangle"></i> OVERDUE</span>`;
            } else if (data.urgency === "CRITICAL") {
                return `<span class="badge badge-warning font-weight-bold" style="padding: 4px 6px;"><i class="fa fa-clock-o"></i> CRITICAL (<=2 Days)</span>`;
            } else if (data.urgency === "APPROACHING") {
                return `<span class="badge badge-info" style="padding: 4px 6px;">APPROACHING</span>`;
            } else {
                return `<span class="badge badge-success" style="padding: 4px 6px;">NORMAL</span>`;
            }
        }

        if (column.fieldname === "days_remaining" && data) {
            let color = data.days_remaining < 0 ? "#dc3545" : (data.days_remaining <= 2 ? "#fd7e14" : "#28a745");
            return `<b style="color: ${color};">${data.days_remaining} Day(s)</b>`;
        }

        return value;
    }
};
