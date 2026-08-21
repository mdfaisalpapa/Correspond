$(document).ready(function() {
    // 1. Check if the user lacks administrative workspace roles
    if (!frappe.user.has_role("System Manager") && !frappe.user.has_role("Workspace Manager")) {
        
        // 2. Inject strict CSS specifically targeting Frappe v16 attributes
        let style = document.createElement('style');
        style.innerHTML = `
            .workspace-page button[data-label="Edit"],
            .page-actions button[data-label="Edit"],
            .page-actions button[title="Edit"] {
                display: none !important;
            }
        `;
        document.head.appendChild(style);

        // 3. The Ultimate Lock: MutationObserver
        // This watches the browser engine in real-time and destroys the button when Vue renders it
        const observer = new MutationObserver(() => {
            if (frappe.get_route && frappe.get_route()[0] === 'workspace') {
                
                // Actively hunt for the button by its exact text and annihilate it
                $('.page-actions button, .standard-actions button').each(function() {
                    let btn_text = $(this).text().trim();
                    if (btn_text === 'Edit' || btn_text === 'Edit Workspace') {
                        $(this).remove();
                    }
                });
            }
        });

        // Attach the observer to the main body to monitor all Vue DOM changes
        observer.observe(document.body, { childList: true, subtree: true });
    }
});
