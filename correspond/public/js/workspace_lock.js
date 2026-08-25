$(document).ready(function() {
    
    // =========================================================
    // 1. WORKSPACE LOCKDOWN
    // =========================================================
    if (!frappe.user.has_role("System Manager") && !frappe.user.has_role("Workspace Manager")) {
        let style = document.createElement('style');
        style.innerHTML = `
            .workspace-page button[data-label="Edit"],
            .page-actions button[data-label="Edit"],
            .page-actions button[title="Edit"] { display: none !important; }
        `;
        document.head.appendChild(style);

        setInterval(() => {
            let route = typeof frappe.get_route === 'function' ? frappe.get_route() : null;
            if (route && route[0] === 'workspace') {
                $('.page-actions button, .standard-actions button').each(function() {
                    let btn_text = $(this).text().trim();
                    if (btn_text === 'Edit' || btn_text === 'Edit Workspace') $(this).remove();
                });
            }
        }, 1000);
    }

    // =========================================================
    // 2. PRINT VIEW BREADCRUMB (DOCUMENT-SPECIFIC)
    // =========================================================
    function override_print_breadcrumb() {
        let route = typeof frappe.get_route === 'function' ? frappe.get_route() : null;
        
        if (route && (route[0] === 'printview' || route[0] === 'print') && route[1] === 'Outward Dak') {
            
            // Extract the specific Document ID from the route
            let docname = route[2];
            let session_key = 'outward_dak_source_' + docname;
            
            // Read from the unique document memory slot
            let target_report = sessionStorage.getItem(session_key) || "Dak Outbox";
            let target_link = "/app/query-report/" + encodeURIComponent(target_report);

            if (target_report === "File" || target_report === "Return to File") {
                target_report = "Return to File";
                target_link = "#";
            }

            let attempts = 0;
            let interval = setInterval(() => {
                attempts++;
                let $bc_link = $('.page-title a, .breadcrumb-item a, .page-breadcrumbs a, a[href*="outward-dak"]').filter(function() {
                    return $(this).text().trim().includes("Outward Dak");
                });

                if ($bc_link.length > 0) {
                    $bc_link.text(target_report);
                    if (target_report === "Return to File") {
                        $bc_link.attr('href', '#').attr('onclick', 'window.history.back(); return false;');
                    } else {
                        $bc_link.attr('href', target_link).removeAttr('onclick');
                    }
                    clearInterval(interval);
                }
                
                if (attempts > 40) clearInterval(interval);
            }, 100);
        }
    }

    setTimeout(override_print_breadcrumb, 300);

    if (window.frappe && frappe.router) {
        frappe.router.on('change', override_print_breadcrumb);
    }
});
