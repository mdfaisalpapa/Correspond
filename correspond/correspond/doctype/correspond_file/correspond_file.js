frappe.ui.form.on('Correspond File', {
    refresh: function(frm) {
        
        // =========================================================
        // CREATION MODE: CLEAN CREATION FORM
        // =========================================================
        if (frm.is_new()) {
            // 1. Hide system status flags
            frm.toggle_display('is_attached', false);
            frm.toggle_display('has_active_attachments', false);
            
            // Explicitly hide ownership and routing fields during creation
            frm.toggle_display('file_owner', false);
            frm.toggle_display('current_custodian', false);
            frm.toggle_display('attached_to', false);
            
            // 2. Hide the Office View section & its display components
            frm.toggle_display('office_view', false);
            frm.toggle_display('notings_display', false);
            frm.toggle_display('dak_display', false);
            
            // 3. Hide tabs via Frappe API
            frm.toggle_display('attached_files_tab', false);
            frm.toggle_display('movements_tab', false);
            
            // 4. Explicitly hide the tab headers in the UI DOM during creation
            setTimeout(() => {
                $('.form-tabs .nav-item').each(function() {
                    let text = $(this).text().trim();
                    if (text === 'Attached Files' || text === 'Movements') {
                        $(this).hide();
                    }
                });
            }, 100);
            
            // 5. Generate a live file number preview based on the user's active desk profile
            frappe.db.get_value('Correspond User Profile', frappe.session.user, ['department', 'office', 'section'], function(user_profile) {
                if (user_profile && user_profile.office) {
                    frappe.db.get_value('Correspond Office', user_profile.office, 'office_abbr', function(office_res) {
                        let office_abbr = office_res ? office_res.office_abbr : user_profile.office;
                        let dept_abbr = user_profile.department ? user_profile.department.substring(0, 2).toUpperCase() : 'DE';
                        
                        frappe.db.get_value('Correspond Section', user_profile.section, 'section_abbr', function(sec_res) {
                            let sec_abbr = sec_res ? sec_res.section_abbr : 'GENL';
                            let year = new Date().getFullYear();
                            
                            let preview = `${dept_abbr}/${office_abbr}/${sec_abbr}/${year}/[Auto]`;
                            frm.set_value('file_number', preview);
                            frm.set_df_property('file_number', 'read_only', 1);
                        });
                    });
                }
            });
            
        } else {
            // Restore visibility when viewing or editing an existing saved file
            frm.toggle_display('is_attached', true);
            frm.toggle_display('has_active_attachments', true);
            
            // Restore ownership and routing fields for saved files
            frm.toggle_display('file_owner', true);
            frm.toggle_display('current_custodian', true);
            frm.toggle_display('attached_to', true);

            frm.toggle_display('office_view', true);
            frm.toggle_display('notings_display', true);
            frm.toggle_display('dak_display', true);
            frm.toggle_display('attached_files_tab', true);
            frm.toggle_display('movements_tab', true);
            
            // Show tab headers again
            $('.form-tabs .nav-item').show();
            
            frm.set_df_property('file_number', 'read_only', 1);

            // =========================================================
            // UI SYNC FIX: Force visual field to match the actual ID
            // =========================================================
            if (frm.doc.file_number !== frm.doc.name) {
                frm.set_value('file_number', frm.doc.name);
            }

            // =========================================================
            // DEFERRED BREADCRUMB OVERRIDE (Only runs for saved files)
            // =========================================================
            setTimeout(() => {
                let target_report = sessionStorage.getItem('correspond_source') || 'File Inbox';
                if (typeof frappe.breadcrumbs !== 'undefined') {
                    frappe.breadcrumbs.all[frappe.get_route_str()] = {
                        workspace: "Correspond",
                        doctype: target_report,
                        type: 'Report'
                    };
                    if (typeof frappe.breadcrumbs.update === 'function') {
                        frappe.breadcrumbs.update();
                    }
                }
            }, 300);
        }
        
        // --- FRONTEND READ-ONLY LOCK FOR NON-CUSTODIANS ---
        // Added fallback: If custodian is blank due to an old glitch, trust the document owner
        let is_custodian = (frm.doc.current_custodian === frappe.session.user || (!frm.doc.current_custodian && frm.doc.owner === frappe.session.user));
        let is_admin = frappe.user.has_role("System Manager");

        if (!frm.is_new() && !is_custodian && !is_admin) {
            $.each(frm.fields_dict, function(fieldname, field) {
                if (field.df.fieldtype !== 'Table') {
                    frm.set_df_property(fieldname, 'read_only', 1);
                }
            });
        }

        // --- EXPLICITLY SHOW OWNERSHIP FIELDS FOR SAVED FILES ---
        if (!frm.is_new()) {
            frm.toggle_display('file_owner', true);
            frm.toggle_display('current_custodian', true);
            frm.toggle_display('attached_to', true);
        }

        // --- 1. CHILD TABLE IMMUTABILITY ---
        frm.set_df_property('daks_table', 'cannot_add_rows', true);
        frm.set_df_property('daks_table', 'cannot_delete_rows', true);
        
        frm.set_df_property('attached_files', 'cannot_add_rows', true);
        frm.set_df_property('attached_files', 'cannot_delete_rows', true);

        // --- MOVEMENT LOG SECURITY ---
        frm.set_df_property('movement_log', 'cannot_add_rows', true);
        frm.set_df_property('movement_log', 'cannot_delete_rows', true);

        // --- 3. SERVER-SIDE BUTTON WRAPPERS ---
        let attached_grid = frm.fields_dict['attached_files'].grid;
        
        if (attached_grid.wrapper) {
            attached_grid.wrapper.find('.grid-custom-buttons').empty();
        }

        let is_iframe = (window.self !== window.top) || window.location.href.includes('view=iframe');
        let is_subfile = (frm.doc.is_attached == 1 || frm.doc.attached_to);

        if ((frm.is_new() || is_custodian || is_admin) && !is_subfile && !is_iframe) {
            
            attached_grid.add_custom_button(__('Attach File'), () => {
                frappe.prompt([{ label: 'Select File', fieldname: 'file_id', fieldtype: 'Link', options: 'Correspond File', reqd: 1, get_query: () => { return { filters: { name: ['!=', frm.doc.name], is_attached: 0 } }; } }], function(values) {
                    frappe.call({ method: 'correspond.correspond.doctype.correspond_file.correspond_file.attach_sub_file', args: { master_file: frm.doc.name, child_file: values.file_id }, freeze: true, callback: function(r) { if (!r.exc) { frm.reload_doc(); } } });
                }, __('Attach File'), __('Attach'));
            });

            attached_grid.add_custom_button(__('Detach Selected'), () => {
                let selected_rows = attached_grid.get_selected_children();
                if (selected_rows.length === 0 || selected_rows.find(r => r.status !== 'Active')) { frappe.msgprint({ title: 'Invalid', message: 'Select at least one active file.', indicator: 'red' }); return; }
                frappe.confirm(`Detach ${selected_rows.length} file(s)?`, () => {
                    frappe.call({ method: 'correspond.correspond.doctype.correspond_file.correspond_file.detach_sub_files', args: { master_file: frm.doc.name, child_files_json: JSON.stringify(selected_rows.map(r => r.linked_file)) }, freeze: true, callback: function(r) { if (!r.exc) { frm.reload_doc(); } } });
                });
            });
        }

        // --- 4. BIND ASYNC/DELEGATED EVENTS ONCE ---
        if (!frm._ssr_events_bound) {
            frm._ssr_events_bound = true;
            
            $(frm.wrapper).on('click', '.prev-notes-btn', function(e) { e.preventDefault(); if (frm.eoffice_note_page > 1) { frm.eoffice_note_page--; load_eoffice_data(frm); } });
            $(frm.wrapper).on('click', '.next-notes-btn', function(e) { e.preventDefault(); frm.eoffice_note_page++; load_eoffice_data(frm); });
            $(frm.wrapper).on('click', '#eofficeRightTabs .nav-link', function(e) { e.preventDefault(); frm.eoffice_active_tab = $(this).attr('data-target'); load_eoffice_data(frm); });
            
            $(frm.wrapper).on('click', '.edit-dak-btn', function(e) { e.preventDefault(); edit_outward_dak_inline(frm, $(this).attr('data-dak-name')); });
            $(frm.wrapper).on('click', '.edit-note-btn', function(e) { e.preventDefault(); edit_note_inline(frm, $(this).attr('data-note-name')); });
            $(frm.wrapper).on('click', '.toggle-state-btn', function(e) { e.preventDefault(); frappe.call({ method: 'correspond.correspond.doctype.correspond_file.correspond_file.set_note_state', args: { note_name: $(this).attr('data-note-name'), status: $(this).attr('data-state') }, callback: function(res) { if (!res.exc) load_eoffice_data(frm); } }); });

            $(frm.wrapper).on('click', 'a', function(e) { let href = $(this).attr('href'); if (href && (href.includes('#note-') || href.includes('#dak-'))) { let targetId = href.substring(href.indexOf('#') + 1); let targetFileMatch = href.match(/\/correspond-file\/([^\#\?]+)/); let targetFile = targetFileMatch ? targetFileMatch[1] : null; if (!targetFile || targetFile === frm.doc.name) { e.preventDefault(); scroll_to_target(targetId); } else { sessionStorage.setItem('eoffice_scroll_target', targetId); } } });

            // --- MOUSEDOWN INTERCEPTOR ---
            $(frm.wrapper).on('mousedown', '.custom-open-btn', function(e) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();

                let docname = $(this).attr('data-row-name');
                if (!docname) return;
                
                if (window._opening_subfile === docname) return;
                window._opening_subfile = docname;
                setTimeout(() => { window._opening_subfile = false; }, 1000);

                let row_doc = frappe.get_doc('Attached Files Log', docname);
                if (!row_doc || !row_doc.linked_file) return;

                let url = `/app/correspond-file/${encodeURIComponent(row_doc.linked_file)}?view=iframe`;
                let dialog = new frappe.ui.Dialog({
                    title: `<i class="fa fa-folder-open text-warning"></i> Viewing Attached File: <b>${row_doc.linked_file}</b>`,
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

                return false;
            });
            
            $(frm.wrapper).on('click', '.custom-open-btn', function(e) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                return false;
            });
        }
        
        frm.eoffice_note_page = frm.eoffice_note_page || 1;
        frm.eoffice_active_tab = frm.eoffice_active_tab || '#tab-toc';
        make_eoffice_full_width(frm);
        if (!frm.is_new()) { load_eoffice_data(frm); }
    }
});

// ================================================================
// CENTRAL SSR DATA LOADER
// ================================================================
function load_eoffice_data(frm) {
    frm.clear_custom_buttons();
    frappe.call({
        method: 'correspond.correspond.doctype.correspond_file.correspond_file.get_file_and_references',
        args: { file_name: frm.doc.name, note_page: frm.eoffice_note_page, active_tab: frm.eoffice_active_tab },
        callback: function(r) {
            if (!r.message) return;
            
            frm.dashboard.clear_headline();
            
            frm.get_field('notings_display').$wrapper.html(r.message.green_sheet_html);
            frm.get_field('dak_display').$wrapper.html(r.message.dak_tabs_html);

            setTimeout(() => { let targetId = sessionStorage.getItem('eoffice_scroll_target') || (window.location.hash ? window.location.hash.substring(1) : null); if (targetId) { sessionStorage.removeItem('eoffice_scroll_target'); scroll_to_target(targetId); } }, 400);

            if (r.message.is_historical) {
                frm.set_intro(""); 
                let msg = `<i class="fa fa-history" style="margin-right: 5px;"></i> <b>HISTORICAL SNAPSHOT (READ ONLY):</b> You are viewing this file exactly as it existed when it left your custody on <b>${r.message.cutoff_date}</b>. Newer correspondence is securely hidden by the server.`;
                frm.set_intro(msg, "orange");
                frm.disable_save();
                return; 
            } else {
                frm.set_intro("");
            } 

            if (!r.message.has_draft) { frm.add_custom_button('Add Note', () => { add_note_inline(frm); }, 'Actions'); }
            frm.add_custom_button('Add Inward Dak', () => { frappe.prompt([{ label: 'Select Inward Dak', fieldname: 'dak_id', fieldtype: 'Link', options: 'Inward Dak', reqd: 1 }], function(values) { let row = frm.add_child("daks_table"); row.inward_dak = values.dak_id; frm.refresh_field("daks_table"); frm.save(); }, __('Attach Dak to File'), __('Attach')); }, 'Actions');
            frm.add_custom_button('Create Outgoing Dak', () => { create_outward_dak_inline(frm); }, 'Actions');
            frm.add_custom_button('Forward File', () => { let d = new frappe.ui.Dialog({ title: 'Forward File', fields: [{label: 'Forward To', fieldname: 'recipient', fieldtype: 'Link', options: 'User', reqd: 1}, {label: 'Remarks', fieldname: 'remarks', fieldtype: 'Small Text', reqd: 1}], primary_action_label: 'Confirm & Forward', primary_action(values) { frappe.call({ method: 'correspond.correspond.doctype.correspond_file.correspond_file.forward_file', args: { file_name: frm.doc.name, recipient: values.recipient, remarks: values.remarks }, callback: function(res) { if (!res.exc) { d.hide(); load_eoffice_data(frm); } } }); } }); d.show(); }, 'Actions');
        }
    });
}

// ================================================================
// SECURE PYTHON ACTION WRAPPERS
// ================================================================
function add_note_inline(frm) {
    let d = new frappe.ui.Dialog({
        title: 'Add New Note',
        fields: [{ label: '🔗 Quick Reference Tool', fieldname: 'ref_helper_html', fieldtype: 'HTML', options: `<div style="margin-bottom: 10px;"><button type="button" class="btn btn-xs btn-default" id="dialog-insert-ref-btn"><i class="fa fa-link"></i> Insert Reference Link</button></div>` }, { label: 'Note Details', fieldname: 'note_details', fieldtype: 'Text Editor', reqd: 1 }],
        size: 'large', primary_action_label: 'Save as Draft',
        primary_action(values) { frappe.call({ method: 'correspond.correspond.doctype.correspond_file.correspond_file.add_draft_note', args: { file_name: frm.doc.name, note_details: values.note_details }, freeze: true, callback: function(r) { if (!r.exc) { d.hide(); load_eoffice_data(frm); } } }); }
    });
    d.show();
    setTimeout(() => { d.$wrapper.find('#dialog-insert-ref-btn').on('click', (e) => { e.preventDefault(); show_popup_reference_dialog(frm.doc.name, d); }); }, 200);
}

function edit_note_inline(frm, note_name) {
    frappe.db.get_value('Correspond Noting', note_name, 'note_details').then(r => {
        let d = new frappe.ui.Dialog({
            title: 'Edit Draft Note',
            fields: [{ label: '🔗 Quick Reference Tool', fieldname: 'ref_helper_html', fieldtype: 'HTML', options: `<div style="margin-bottom: 10px;"><button type="button" class="btn btn-xs btn-default" id="dialog-insert-ref-btn"><i class="fa fa-link"></i> Insert Reference Link</button></div>` }, { label: 'Note Details', fieldname: 'note_details', fieldtype: 'Text Editor', reqd: 1, default: r.message ? r.message.note_details : '' }],
            size: 'large', primary_action_label: 'Save Changes',
            primary_action(values) { frappe.call({ method: 'correspond.correspond.doctype.correspond_file.correspond_file.update_draft_note', args: { file_name: frm.doc.name, note_name: note_name, note_details: values.note_details }, freeze: true, callback: function() { d.hide(); load_eoffice_data(frm); } }); }
        });
        d.show();
        setTimeout(() => { d.$wrapper.find('#dialog-insert-ref-btn').on('click', (e) => { e.preventDefault(); show_popup_reference_dialog(frm.doc.name, d); }); }, 200);
    });
}

function create_outward_dak_inline(frm) {
    let d = new frappe.ui.Dialog({
        title: 'Create Outgoing Dak (Draft)',
        fields: [
            { fieldtype: 'Section Break', label: 'Recipient Details' },
            { fieldname: 'recipient_type', label: 'Recipient Type', fieldtype: 'Select', options: 'Internal User\nExternal User', reqd: 1, default: 'Internal User' },
            { fieldname: 'internal_recipient', label: 'Internal Recipient', fieldtype: 'Link', options: 'User', depends_on: 'eval:doc.recipient_type=="Internal User"' },
            { fieldname: 'receiver', label: 'Receiver Details', fieldtype: 'Small Text', depends_on: 'eval:doc.recipient_type=="External User"' },
            { fieldname: 'receiver_email', label: 'Receiver Email', fieldtype: 'Data', options: 'Email', depends_on: 'eval:doc.recipient_type=="External User"' },
            
            { fieldtype: 'Section Break', label: 'Content' },
            { fieldname: 'sender', label: 'Sender', fieldtype: 'Link', options: 'User', default: frappe.session.user },
            { fieldname: 'subject', label: 'Subject', fieldtype: 'Data', reqd: 1 },
            { fieldname: 'reference', label: 'Reference', fieldtype: 'Data' },
            { fieldname: 'letter_body', label: 'Letter Body', fieldtype: 'Text Editor', reqd: 1 },
            { fieldname: 'signature', label: 'Signature', fieldtype: 'Data', reqd: 1 },
            
            { fieldtype: 'Section Break', label: 'Processing' },
            { fieldname: 'status', label: 'Status', fieldtype: 'Select', options: 'Draft\nApproved', default: 'Draft' },
            { fieldname: 'attachments', label: 'Attachments', fieldtype: 'Attach' }
        ],
        size: 'large', 
        primary_action_label: 'Create Draft',
        primary_action(values) { 
            frappe.call({ 
                method: 'correspond.correspond.doctype.correspond_file.correspond_file.add_draft_dak', 
                args: { file_name: frm.doc.name, dak_data: JSON.stringify(values) }, 
                freeze: true, 
                callback: function(r) { 
                    if (!r.exc) { d.hide(); frm.eoffice_active_tab = '#tab-drafts'; load_eoffice_data(frm); } 
                } 
            }); 
        }
    });
    d.show();
}

function edit_outward_dak_inline(frm, dak_name) {
    frappe.call({ method: 'frappe.client.get', args: { doctype: 'Outward Dak', name: dak_name }, callback: function(r) {
        if (r.message) {
            let doc = r.message;
            let d = new frappe.ui.Dialog({
                title: 'Edit Outgoing Dak',
                fields: [
                    { fieldtype: 'Section Break', label: 'Recipient Details' },
                    { fieldname: 'recipient_type', label: 'Recipient Type', fieldtype: 'Select', options: 'Internal User\nExternal User', reqd: 1, default: doc.recipient_type || 'Internal User' },
                    { fieldname: 'internal_recipient', label: 'Internal Recipient', fieldtype: 'Link', options: 'User', depends_on: 'eval:doc.recipient_type=="Internal User"', default: doc.internal_recipient },
                    { fieldname: 'receiver', label: 'Receiver Details', fieldtype: 'Small Text', depends_on: 'eval:doc.recipient_type=="External User"', default: doc.receiver },
                    { fieldname: 'receiver_email', label: 'Receiver Email', fieldtype: 'Data', options: 'Email', depends_on: 'eval:doc.recipient_type=="External User"', default: doc.receiver_email },
                    
                    { fieldtype: 'Section Break', label: 'Content' },
                    { fieldname: 'sender', label: 'Sender', fieldtype: 'Link', options: 'User', default: doc.sender || frappe.session.user },
                    { fieldname: 'subject', label: 'Subject', fieldtype: 'Data', reqd: 1, default: doc.subject },
                    { fieldname: 'reference', label: 'Reference', fieldtype: 'Data', default: doc.reference },
                    { fieldname: 'letter_body', label: 'Letter Body', fieldtype: 'Text Editor', reqd: 1, default: doc.letter_body },
                    { fieldname: 'signature', label: 'Signature', fieldtype: 'Data', reqd: 1, default: doc.signature },
                    
                    { fieldtype: 'Section Break', label: 'Processing' },
                    { fieldname: 'status', label: 'Status', fieldtype: 'Select', options: 'Draft\nApproved', default: doc.status || 'Draft' },
                    { fieldname: 'attachments', label: 'Attachments', fieldtype: 'Attach', default: doc.attachments }
                ],
                size: 'large', 
                
                primary_action_label: 'Approve & Finalize',
                primary_action(values) { 
                    values.status = 'Approved'; 
                    frappe.confirm('Are you sure you want to Approve and Finalize this Dak? It cannot be edited afterward.', () => {
                        frappe.call({
                            method: 'correspond.correspond.doctype.correspond_file.correspond_file.update_draft_dak',
                            args: { file_name: frm.doc.name, dak_name: dak_name, dak_data: JSON.stringify(values), submit_doc: true },
                            freeze: true,
                            callback: function(res) {
                                if (!res.exc) { 
                                    d.hide(); 
                                    frm.eoffice_active_tab = '#tab-toc';
                                    load_eoffice_data(frm); 
                                }
                            }
                        });
                    });
                },

                secondary_action_label: 'Save Changes (Keep Draft)',
                secondary_action() {
                    let values = d.get_values();
                    if (!values) return; 
                    
                    frappe.call({ 
                        method: 'correspond.correspond.doctype.correspond_file.correspond_file.update_draft_dak', 
                        args: { file_name: frm.doc.name, dak_name: dak_name, dak_data: JSON.stringify(values), submit_doc: false }, 
                        freeze: true, 
                        callback: function(res) { 
                            if (!res.exc) { 
                                d.hide(); 
                                frm.eoffice_active_tab = '#tab-drafts'; 
                                load_eoffice_data(frm); 
                            } 
                        } 
                    }); 
                }
            });

            d.show();
            d.$wrapper.find('.modal-footer .btn-primary').removeClass('btn-primary').addClass('btn-success');
        }
    }});
}

function scroll_to_target(targetId) {
    let $target = $('#' + targetId);
    if ($target.length) {
        let $container = $target.closest('.eoffice-scroll-container');
        if ($container.length) {
            let containerTop = $container.scrollTop(), elementTop = $target.position().top;
            $container.animate({ scrollTop: containerTop + elementTop - ($container.height() / 2) + ($target.height() / 2) }, 500);
        } else { $target[0].scrollIntoView({ behavior: 'smooth', block: 'center' }); }
        $target.css('background-color', '#fff3cd');
        setTimeout(() => { $target.css('background-color', 'transparent'); }, 2000);
    }
}

// ================================================================
// INSERT FILE REFERENCE DIALOG
// ================================================================
function show_popup_reference_dialog(file_name, parent_dialog) {
    frappe.call({
        method: 'correspond.correspond.doctype.correspond_file.correspond_file.get_reference_lookup_data',
        args: { file_name: file_name },
        callback: function(r) {
            if (!r.message) return;
            let data = r.message;
            let file_options = data.file_opts.map(f => f.label);

            let ref_d = new frappe.ui.Dialog({
                title: 'Insert File Reference',
                fields: [
                    { label: 'Category', fieldname: 'ref_category', fieldtype: 'Select', options: 'Note\nDak', default: 'Note', change: update_dropdowns },
                    { label: 'Reference File', fieldname: 'target_file', fieldtype: 'Select', options: file_options, default: file_options[0], change: update_dropdowns },
                    { label: 'Select Document', fieldname: 'selected_doc', fieldtype: 'Select', options: [], reqd: 1 },
                    { label: 'Custom Link Text (Optional)', fieldname: 'link_text', fieldtype: 'Data' }
                ],
                primary_action_label: 'Insert Into Note',
                primary_action(values) {
                    let selected_file_obj = data.file_opts.find(f => f.label === values.target_file);
                    let actual_file = selected_file_obj ? selected_file_obj.value : file_name;

                    let prefix = values.ref_category === 'Note' ? 'note' : 'dak';
                    let url = `/app/correspond-file/${actual_file}#${prefix}-${values.selected_doc}`;
                    
                    let display_text = values.link_text || `${values.ref_category} (${values.selected_doc})`;

                    let field = parent_dialog.fields_dict['note_details'];
                    if (field && field.quill) {
                        let range = field.quill.getSelection();
                        let cursor_pos = range ? range.index : field.quill.getLength();
                        field.quill.insertText(cursor_pos, ` [${display_text}] `, 'link', url);
                    }
                    ref_d.hide();
                }
            });

            function update_dropdowns() {
                let cat = ref_d.get_value('ref_category');
                let target_label = ref_d.get_value('target_file') || file_options[0];
                let selected_file_obj = data.file_opts.find(f => f.label === target_label);
                let target_id = selected_file_obj ? selected_file_obj.value : file_name;
                
                let filtered = cat === 'Note' 
                    ? data.notes.filter(n => n.file === target_id) 
                    : data.daks.filter(d => d.file === target_id);

                let opts = filtered.length > 0 ? filtered : [{label: 'No records found', value: ''}];
                ref_d.set_df_property('selected_doc', 'options', opts);
            }

            ref_d.show();
            update_dropdowns();
        }
    });
}

// ================================================================
// OFFICE VIEW - FULL WIDTH CSS INJECTION
// ================================================================
function make_eoffice_full_width(frm) {
    if (!$('#eoffice-full-width-css').length) {
        let css = `
            .form-layout, .form-layout .form-section, [data-fieldname="office_view"], [data-fieldname="office_view"] .section-body, [data-fieldname="office_view"] .row { width: 100% !important; max-width: none !important; margin-left: 0 !important; margin-right: 0 !important; box-sizing: border-box !important; } 
            [data-fieldname="office_view"] .form-column { width: 50% !important; max-width: 50% !important; flex: 0 0 50% !important; box-sizing: border-box !important; } 
            [data-fieldname="notings_display"], [data-fieldname="dak_display"], .eoffice-scroll-container { width: 100% !important; max-width: 100% !important; box-sizing: border-box !important; } 
            
            [data-fieldname="attached_files"] .link-btn { display: none !important; } 
            [data-fieldname="attached_files"] .grid-row-open { display: none !important; } 
        `;

        const is_iframe_context = (window.self !== window.top) || window.location.href.includes('view=iframe');

        if (is_iframe_context) {
            css += `
                .standard-sidebar, .layout-side-section, .sidebar-container, .sidebar-toggle-btn, .desk-sidebar, .page-sidebar, div[class*="sidebar"] { display: none !important; width: 0 !important; max-width: 0 !important; }
                .navbar, header, .page-head, .page-actions, .form-page-actions { display: none !important; height: 0 !important; }
                .layout-main-section, .page-content { border-left: none !important; margin-left: 0 !important; padding: 0 !important; width: 100% !important; min-height: 100vh !important; }
                .page-container, #body { padding-top: 0 !important; padding-bottom: 0 !important; }
                .page-breadcrumbs { display: none !important; }
            `;
            
            setInterval(() => {
                $('.standard-sidebar, .layout-side-section, .sidebar-container, .desk-sidebar, .page-sidebar, .navbar, header, .page-head').remove();
                $('.layout-main-section, .page-content').css({'margin-left': '0', 'border': 'none', 'padding': '0', 'width': '100%'});
            }, 100);
        }
        $('head').append(`<style id="eoffice-full-width-css">${css}</style>`);
    }
}

// --- NEW EVENT-DRIVEN RENDERER ---
function render_attached_files_ui(frm) {
    if (!frm.fields_dict['attached_files'] || !frm.fields_dict['attached_files'].grid) return;
    
    setTimeout(() => {
        $('[data-fieldname="attached_files"] .grid-row').each(function() {
            let $row = $(this);
            let docname = $row.attr('data-name');
            if (!docname) return;

            // 1. Inject custom Open button
            let $cell = $row.find('[data-fieldname="open_file"]');
            if ($cell.length && !$cell.find('.custom-open-btn').length) {
                $cell.html(`<button type="button" class="btn btn-xs btn-default custom-open-btn" data-row-name="${docname}" style="position: relative; z-index: 100;"><i class="fa fa-folder-open text-warning"></i> Open</button>`);
            }

            // 2. Handle detached state logic
            let row_doc = frappe.get_doc('Attached Files Log', docname);
            if (row_doc && row_doc.status === 'Detached') {
                $row.find('.grid-row-check, input[type="checkbox"]').prop('checked', false).prop('disabled', true);
                $row.find('.frappe-checkbox, .grid-row-check').css({'visibility': 'hidden', 'pointer-events': 'none'});
                $row.css('color', '#a3a3a3');
            }
        });
    }, 50);
}

// Hook into standard Child Table events
frappe.ui.form.on('Attached Files Log', {
    attached_files_add: function(frm) {
        render_attached_files_ui(frm);
    },
    attached_files_remove: function(frm) {
        render_attached_files_ui(frm);
    }
});
