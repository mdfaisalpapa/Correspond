frappe.pages["correspond_console"].on_page_load = function (wrapper) {
    let page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Correspond Desk Console"),
        single_column: true
    });

    wrapper.console_view = new CorrespondDeskConsole(wrapper, page);
};

frappe.pages["correspond_console"].refresh = function (wrapper) {
    if (wrapper.console_view) {
        wrapper.console_view.refresh();
    }
};

class CorrespondDeskConsole {
    constructor(wrapper, page) {
        this.wrapper = wrapper;
        this.page = page;
        this.current_tab = "file_inbox";
        this.setup_actions();
        this.render_layout();
        this.refresh();
    }

    setup_actions() {
        this.page.set_primary_action(__("New File"), () => {
            frappe.new_doc("Correspond File");
        }, "add");

        this.page.add_button(__("Diarize Dak"), () => {
            frappe.new_doc("Inward Dak");
        });

        this.page.add_inner_button(__("Refresh"), () => {
            this.refresh();
        });

        this.page.add_inner_button(__("Bulk Forward"), () => {
            this.handle_bulk_forward();
        }, __("Actions"));
    }

    render_layout() {
        let html = `
            <div class="correspond-console-container" style="padding: 10px 0;">
                <ul class="nav nav-tabs correspond-nav-tabs" style="margin-bottom: 20px; border-bottom: 2px solid var(--border-color);">
                    <li class="nav-item">
                        <a class="nav-link active" data-tab="file_inbox" href="javascript:void(0);" style="font-weight: 600; font-size: 14px;">
                            <i class="fa fa-folder-open text-primary" style="margin-right: 6px;"></i> File Inbox
                            <span class="badge badge-pill badge-primary count-badge-file_inbox" style="margin-left: 6px; font-size: 11px;">0</span>
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" data-tab="file_outbox" href="javascript:void(0);" style="font-weight: 600; font-size: 14px;">
                            <i class="fa fa-paper-plane text-info" style="margin-right: 6px;"></i> File Outbox
                            <span class="badge badge-pill badge-secondary count-badge-file_outbox" style="margin-left: 6px; font-size: 11px;">0</span>
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" data-tab="dak_inbox" href="javascript:void(0);" style="font-weight: 600; font-size: 14px;">
                            <i class="fa fa-envelope text-warning" style="margin-right: 6px;"></i> Dak Inbox
                            <span class="badge badge-pill badge-warning count-badge-dak_inbox" style="margin-left: 6px; font-size: 11px;">0</span>
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" data-tab="dak_outbox" href="javascript:void(0);" style="font-weight: 600; font-size: 14px;">
                            <i class="fa fa-share text-success" style="margin-right: 6px;"></i> Dak Outbox
                            <span class="badge badge-pill badge-success count-badge-dak_outbox" style="margin-left: 6px; font-size: 11px;">0</span>
                        </a>
                    </li>
                </ul>

                <div class="console-tab-content">
                    <div class="console-table-container">
                        <div class="text-center text-muted p-5">
                            <i class="fa fa-spinner fa-spin fa-2x"></i>
                            <div class="mt-2">Loading desk records...</div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        $(this.wrapper).find(".layout-main-section").html(html);

        let self = this;
        $(this.wrapper).find(".correspond-nav-tabs a").on("click", function () {
            self.switch_tab($(this).data("tab"));
        });
    }

    switch_tab(tab_name) {
        this.current_tab = tab_name;
        $(this.wrapper).find(".correspond-nav-tabs a").removeClass("active");
        $(this.wrapper).find(`.correspond-nav-tabs a[data-tab="${tab_name}"]`).addClass("active");
        this.load_table_data();
    }

    refresh() {
        this.load_table_data();
    }

    load_table_data() {
        let self = this;
        let $container = $(this.wrapper).find(".console-table-container");

        frappe.call({
            method: "correspond.correspond.page.correspond_console.correspond_console.get_console_data",
            args: { tab: self.current_tab },
            callback: function (r) {
                if (!r || !r.message) return;
                let counts = r.message.counts || {};
                let items = r.message.data || [];

                // Update badge numbers
                Object.keys(counts).forEach(k => {
                    $(self.wrapper).find(`.count-badge-${k}`).text(counts[k]);
                });

                self.render_items(items);
            }
        });
    }

    render_items(items) {
        let $container = $(this.wrapper).find(".console-table-container");
        if (!items || items.length === 0) {
            $container.html(`
                <div class="text-center text-muted p-5 border rounded" style="background: var(--bg-light-gray);">
                    <i class="fa fa-check-circle fa-2x text-success mb-2"></i>
                    <div style="font-size: 15px; font-weight: 500;">No pending records in this queue.</div>
                    <div class="small text-muted mt-1">Your desk is completely up to date!</div>
                </div>
            `);
            return;
        }

        let html = "";
        if (this.current_tab === "file_inbox") {
            html = this.render_file_inbox_table(items);
        } else if (this.current_tab === "file_outbox") {
            html = this.render_file_outbox_table(items);
        } else if (this.current_tab === "dak_inbox") {
            html = this.render_dak_inbox_table(items);
        } else if (this.current_tab === "dak_outbox") {
            html = this.render_dak_outbox_table(items);
        }

        $container.html(html);
        this.bind_table_events();
    }

    render_file_inbox_table(items) {
        let rows = items.map(d => {
            let status_badge = d.status === "Parked"
                ? `<span class="badge badge-warning">Parked</span>`
                : `<span class="badge badge-success">Active</span>`;

            return `
                <tr>
                    <td style="width: 40px; text-align: center;">
                        <input type="checkbox" class="file-select-checkbox" data-name="${frappe.utils.escape_html(d.name)}">
                    </td>
                    <td style="width: 240px;">
                        <a href="/app/correspond-file/${encodeURIComponent(d.name)}" style="font-weight: 600; color: #0052cc;">
                            <i class="fa fa-folder text-warning mr-1"></i> ${frappe.utils.escape_html(d.name)}
                        </a>
                    </td>
                    <td>
                        <div style="font-weight: 500;">${frappe.utils.escape_html(d.subject || '-')}</div>
                        ${d.remarks ? `<div class="small text-muted mt-1"><i class="fa fa-comment-o mr-1"></i> ${frappe.utils.escape_html(d.remarks)}</div>` : ''}
                    </td>
                    <td style="width: 220px;">
                        <div class="small" style="font-weight: 500;">${frappe.utils.escape_html(d.sent_by || 'Origin Desk')}</div>
                        <div class="small text-muted">${d.sent_on ? frappe.datetime.prettyDate(d.sent_on) : '-'}</div>
                    </td>
                    <td style="width: 100px; text-align: center;">
                        ${status_badge}
                    </td>
                    <td style="width: 110px; text-align: right;">
                        <a href="/app/correspond-file/${encodeURIComponent(d.name)}" class="btn btn-xs btn-primary">
                            Open <i class="fa fa-chevron-right ml-1"></i>
                        </a>
                    </td>
                </tr>
            `;
        }).join("");

        return `
            <div class="table-responsive">
                <table class="table table-hover border" style="background: var(--card-bg);">
                    <thead style="background: var(--bg-light-gray);">
                        <tr>
                            <th style="width: 40px; text-align: center;">
                                <input type="checkbox" class="select-all-checkbox">
                            </th>
                            <th>File Number</th>
                            <th>Subject & Remarks</th>
                            <th>Sent By</th>
                            <th style="text-align: center;">Status</th>
                            <th style="text-align: right;">Action</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;
    }

    render_file_outbox_table(items) {
        let rows = items.map(d => {
            let pull_back_btn = d.can_pull_back === 1
                ? `<button class="btn btn-xs btn-danger btn-pull-back" data-name="${frappe.utils.escape_html(d.name)}">
                       <i class="fa fa-undo mr-1"></i> Pull Back
                   </button>`
                : `<span class="badge badge-secondary">${d.is_opened ? 'Opened' : 'Transferred'}</span>`;

            return `
                <tr>
                    <td style="width: 240px;">
                        <a href="/app/correspond-file/${encodeURIComponent(d.name)}" style="font-weight: 600; color: #0052cc;">
                            <i class="fa fa-file-text-o text-muted mr-1"></i> ${frappe.utils.escape_html(d.name)}
                        </a>
                    </td>
                    <td>
                        <div style="font-weight: 500;">${frappe.utils.escape_html(d.subject || '-')}</div>
                        ${d.remarks ? `<div class="small text-muted mt-1">${frappe.utils.escape_html(d.remarks)}</div>` : ''}
                    </td>
                    <td style="width: 220px;">
                        <div class="small" style="font-weight: 500;">${frappe.utils.escape_html(d.recipient_desk || '-')}</div>
                        <div class="small text-muted">Sent: ${d.sent_on ? frappe.datetime.prettyDate(d.sent_on) : '-'}</div>
                    </td>
                    <td style="width: 220px;">
                        <div class="small text-muted">${frappe.utils.escape_html(d.currently_with || '-')}</div>
                    </td>
                    <td style="width: 120px; text-align: center;">
                        ${pull_back_btn}
                    </td>
                </tr>
            `;
        }).join("");

        return `
            <div class="table-responsive">
                <table class="table table-hover border" style="background: var(--card-bg);">
                    <thead style="background: var(--bg-light-gray);">
                        <tr>
                            <th>File Number</th>
                            <th>Subject</th>
                            <th>Sent To</th>
                            <th>Currently With</th>
                            <th style="text-align: center;">Recall / Status</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;
    }

    render_dak_inbox_table(items) {
        let rows = items.map(d => {
            let vip_pill = d.is_vip_reference
                ? `<span class="badge badge-danger mr-1"><i class="fa fa-bolt mr-1"></i>${frappe.utils.escape_html(d.vip_category || 'VIP')}</span>`
                : '';

            return `
                <tr>
                    <td style="width: 220px;">
                        <a href="/app/inward-dak/${encodeURIComponent(d.name)}" style="font-weight: 600; color: #0052cc;">
                            <i class="fa fa-envelope-o text-warning mr-1"></i> ${frappe.utils.escape_html(d.name)}
                        </a>
                    </td>
                    <td>
                        <div style="font-weight: 500;">${vip_pill}${frappe.utils.escape_html(d.subject || '-')}</div>
                        <div class="small text-muted mt-1">From: ${frappe.utils.escape_html(d.sender_organization || 'Direct')} (${d.receipt_mode || 'Physical'})</div>
                    </td>
                    <td style="width: 140px;">
                        <span class="small text-muted">${frappe.datetime.prettyDate(d.creation)}</span>
                    </td>
                    <td style="width: 110px; text-align: center;">
                        <span class="badge badge-info">${frappe.utils.escape_html(d.status || 'Received')}</span>
                    </td>
                    <td style="width: 100px; text-align: right;">
                        <a href="/app/inward-dak/${encodeURIComponent(d.name)}" class="btn btn-xs btn-default">
                            View <i class="fa fa-chevron-right ml-1"></i>
                        </a>
                    </td>
                </tr>
            `;
        }).join("");

        return `
            <div class="table-responsive">
                <table class="table table-hover border" style="background: var(--card-bg);">
                    <thead style="background: var(--bg-light-gray);">
                        <tr>
                            <th>Inward Dak No</th>
                            <th>Subject & Sender</th>
                            <th>Received On</th>
                            <th style="text-align: center;">Status</th>
                            <th style="text-align: right;">Action</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;
    }

    render_dak_outbox_table(items) {
        let rows = items.map(d => {
            return `
                <tr>
                    <td style="width: 220px;">
                        <a href="/app/outward-dak/${encodeURIComponent(d.name)}" style="font-weight: 600; color: #0052cc;">
                            <i class="fa fa-share text-success mr-1"></i> ${frappe.utils.escape_html(d.name)}
                        </a>
                    </td>
                    <td>
                        <div style="font-weight: 500;">${frappe.utils.escape_html(d.subject || '-')}</div>
                        <div class="small text-muted mt-1">To: ${frappe.utils.escape_html(d.recipient_name || '-')} • Type: ${d.dfa_type || 'OM'}</div>
                    </td>
                    <td style="width: 180px;">
                        <div class="small" style="font-weight: 500;">${frappe.utils.escape_html(d.dispatch_number || 'Pending Dispatch')}</div>
                        <div class="small text-muted">${d.dispatch_mode || '-'}</div>
                    </td>
                    <td style="width: 120px; text-align: center;">
                        <span class="badge badge-success">${frappe.utils.escape_html(d.status || 'Draft')}</span>
                    </td>
                    <td style="width: 100px; text-align: right;">
                        <a href="/app/outward-dak/${encodeURIComponent(d.name)}" class="btn btn-xs btn-default">
                            View <i class="fa fa-chevron-right ml-1"></i>
                        </a>
                    </td>
                </tr>
            `;
        }).join("");

        return `
            <div class="table-responsive">
                <table class="table table-hover border" style="background: var(--card-bg);">
                    <thead style="background: var(--bg-light-gray);">
                        <tr>
                            <th>Outward Dak No</th>
                            <th>Subject & Recipient</th>
                            <th>Dispatch Info</th>
                            <th style="text-align: center;">Status</th>
                            <th style="text-align: right;">Action</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;
    }

    bind_table_events() {
        let self = this;
        let $w = $(this.wrapper);

        // Select all
        $w.find(".select-all-checkbox").on("change", function () {
            let checked = $(this).prop("checked");
            $w.find(".file-select-checkbox").prop("checked", checked);
        });

        // Pull Back confirmation
        $w.find(".btn-pull-back").on("click", function () {
            let file_name = $(this).data("name");
            frappe.confirm(
                `Are you sure you want to <b>Pull Back</b> file <code>${file_name}</code> to your desk?<br><br>The recipient has not yet opened this file.`,
                () => {
                    frappe.prompt(
                        {
                            label: "Reason for Recall",
                            fieldname: "reason",
                            fieldtype: "Small Text",
                            reqd: 1,
                            default: "Recalled to update attachments/notings."
                        },
                        (val) => {
                            frappe.call({
                                method: "correspond.correspond.doctype.correspond_file.correspond_file.pull_back_file",
                                args: {
                                    file_name: file_name,
                                    reason: val.reason
                                },
                                callback: function (res) {
                                    frappe.show_alert({
                                        message: `File ${file_name} recalled to your desk.`,
                                        indicator: "green"
                                    });
                                    self.refresh();
                                }
                            });
                        },
                        "Confirm Pull Back",
                        "Recall File"
                    );
                }
            );
        });
    }

    handle_bulk_forward() {
        let self = this;
        let selected = [];
        $(this.wrapper).find(".file-select-checkbox:checked").each(function () {
            selected.push($(this).data("name"));
        });

        if (selected.length === 0) {
            frappe.msgprint({
                title: __("No Files Selected"),
                message: __("Please select at least one file from the Inbox using the checkboxes."),
                indicator: "orange"
            });
            return;
        }

        let d = new frappe.ui.Dialog({
            title: `Bulk Forward (${selected.length} Files)`,
            fields: [
                {
                    fieldname: "info",
                    fieldtype: "HTML",
                    options: `<div class="alert alert-info">Transferring <b>${selected.length}</b> file(s) to a recipient desk.</div>`
                },
                {
                    label: "Recipient Desk",
                    fieldname: "recipient_profile",
                    fieldtype: "Link",
                    options: "Correspond Desk Profile",
                    reqd: 1,
                    get_query: () => {
                        return {
                            query: "correspond.correspond.doctype.correspond_file.correspond_file.get_forward_recipients"
                        };
                    }
                },
                {
                    label: "Forwarding Remarks",
                    fieldname: "remarks",
                    fieldtype: "Small Text",
                    reqd: 1,
                    default: "Bulk forwarded for review / action."
                }
            ],
            primary_action_label: `Forward ${selected.length} File(s)`,
            primary_action(vals) {
                d.get_primary_btn().prop("disabled", true);
                frappe.call({
                    method: "correspond.correspond.doctype.correspond_file.correspond_file.bulk_forward_files",
                    args: {
                        file_names: JSON.stringify(selected),
                        recipient_profile: vals.recipient_profile,
                        remarks: vals.remarks
                    },
                    callback: function (res) {
                        d.hide();
                        if (!res.exc) {
                            frappe.show_alert({
                                message: `Successfully forwarded ${res.message.count} files!`,
                                indicator: "green"
                            });
                            self.refresh();
                        }
                    }
                });
            }
        });
        d.show();
    }
}
