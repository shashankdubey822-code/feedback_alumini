/* main.js — App initialization entry point */

// ========== INITIALIZATION ==========
document.addEventListener('DOMContentLoaded', () => {
    setupUploadHandlers();    // api.js
    setupSidebarNav();        // app.js (canonical sidebar setup)
    setupDashboardHandlers(); // app.js
    setupModals();            // ui.js
    setupModal();             // components.js (data modal keyboard/backdrop)
    initSpeakerAutocomplete(); // components.js
    setupAdminAuth();         // admin.js
    loadInitialData();        // app.js
});
