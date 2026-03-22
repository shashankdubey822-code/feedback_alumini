// ========== SCREEN SWITCHING ==========
function showSection(sectionId) {
    // Hide all dashboard sections
    document.querySelectorAll('.dashboard-section').forEach(sec => {
        sec.classList.remove('active');
    });
    
    // Show target section
    const target = document.getElementById(sectionId);
    if (target) {
        target.classList.add('active');
        // Ensure scroll to top
        window.scrollTo(0, 0);
    }

    // Update sidebar active state
    document.querySelectorAll('.sidebar .nav-item, .sidebar-nav .nav-item').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.section === sectionId);
    });

    // SCOPING: If leaving overview, reset filters to show global data in other sections
    const activeFilters = (window.state && state.activeFilters) ? state.activeFilters : {};
    if (sectionId !== 'overview-section' && Object.keys(activeFilters).length > 0) {
        if (typeof clearAllFilters === 'function') clearAllFilters();
    }
}

function switchToDashboard() {
    showSection('overview-section');
    if (window.state && state.fileName) {
        const badge = document.getElementById('file-badge');
        if (badge) badge.textContent = state.fileName;
    }
}

function switchToUpload() {
    showSection('upload-section');
    if (typeof hideProgress === 'function') hideProgress();
    const fileInput = document.getElementById('file-input');
    const linkInput = document.getElementById('google-link-input');
    if (fileInput) fileInput.value = '';
    if (linkInput) linkInput.value = '';
    if (typeof destroyCharts === 'function') destroyCharts();
}


// ========== SIDEBAR NAVIGATION ==========
function setupSidebarNav() {
    document.querySelectorAll('.sidebar-nav .nav-item').forEach((btn) => {
        btn.addEventListener('click', () => {
            const targetId = btn.dataset.section;
            if (targetId) showSection(targetId);
            document.getElementById('sidebar').classList.remove('open');
        });
    });

    const toggle = document.getElementById('sidebar-toggle');
    if (toggle) {
        toggle.addEventListener('click', () => {
            document.getElementById('sidebar').classList.toggle('open');
        });
    }
}


// ========== MODAL HANDLERS ==========
function setupModals() {
    // Data Modal
    const dataModal = document.getElementById('data-modal');
    const dataModalClose = document.getElementById('modal-close');
    if (dataModalClose) {
        dataModalClose.addEventListener('click', () => dataModal.classList.add('hidden'));
    }

    // Admin Login Modal
    const adminModal = document.getElementById('admin-login-modal');
    const adminModalClose = document.getElementById('admin-login-close');
    if (adminModalClose) {
        adminModalClose.addEventListener('click', () => adminModal.classList.add('hidden'));
    }

    // Feedback Form Modal
    const feedbackModal = document.getElementById('feedback-modal');
    const feedbackModalClose = document.getElementById('feedback-modal-close');
    if (feedbackModalClose) {
        feedbackModalClose.addEventListener('click', () => feedbackModal.classList.add('hidden'));
    }

    // System Checkup Modal
    const checkupModal = document.getElementById('system-checkup-modal');
    const checkupModalClose = document.getElementById('checkup-modal-close');
    if (checkupModalClose) {
        checkupModalClose.addEventListener('click', () => checkupModal.classList.add('hidden'));
    }
    
    const btnRetry = document.getElementById('btn-checkup-retry');
    if (btnRetry) {
        btnRetry.addEventListener('click', () => {
             // Reset UI and run again
             document.querySelectorAll('.checkup-item .status-badge').forEach(b => {
                 b.textContent = 'Checking...';
                 b.style.background = 'rgba(255,255,255,0.05)';
                 b.style.color = '#8b8b9e';
             });
             performSystemCheckup();
        });
    }
}

// Modify setupDashboardHandlers to include setupModals
function setupDashboardHandlers() {
    setupModals();
    const btnAdminPanel = document.getElementById('btn-admin-panel');
    if (btnAdminPanel) {
        btnAdminPanel.addEventListener('click', showAdminPanel);
    }
    document.getElementById('btn-clear-filters').addEventListener('click', clearAllFilters);
    document.getElementById('global-search').addEventListener('input', debounce(applyFilters, 400));

    // Auto-refresh the dashboard live (Webhooks sync) - ENHANCED with abort control
    setInterval(async () => {
        const dash = document.getElementById('dashboard-screen');
        if (!dash || !dash.classList.contains('active')) return;
        
        const searchVal = document.getElementById('global-search').value.trim();
        if (searchVal.length > 0) return; // Don't disrupt active searching
        
        try {
            // Abort any pending auto-refresh request
            if (currentAutoRefreshController) {
                currentAutoRefreshController.abort();
                console.log('[AUTO-REFRESH] Aborted previous request');
            }
            
            // Create new AbortController for this refresh
            currentAutoRefreshController = new AbortController();
            
            // We just re-run the normal filter workflow silently to pull new webhook data
            await applyFilters(true); // true = silent flag
            
            currentAutoRefreshController = null;
        } catch(e) {
            if (e.name !== 'AbortError') {
                console.error('[AUTO-REFRESH] Error:', e);
            }
            currentAutoRefreshController = null;
        }
    }, 10000);
}


