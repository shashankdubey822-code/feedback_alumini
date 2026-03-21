// ========== SCREEN SWITCHING ==========
function switchToDashboard() {
    document.getElementById('upload-screen').classList.remove('active');
    document.getElementById('dashboard-screen').classList.add('active');
    document.getElementById('file-badge').textContent = state.fileName;
}

function switchToUpload() {
    document.getElementById('dashboard-screen').classList.remove('active');
    document.getElementById('upload-screen').classList.add('active');
    hideProgress();
    document.getElementById('file-input').value = '';
    document.getElementById('google-link-input').value = '';
    destroyCharts();
}


// ========== SIDEBAR NAVIGATION ==========
function setupSidebarNav() {
    document.querySelectorAll('.sidebar-nav .nav-item').forEach((btn) => {
        btn.addEventListener('click', () => {
            const targetId = btn.dataset.section;

            document.querySelectorAll('.sidebar-nav .nav-item').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            document.querySelectorAll('.dashboard-section').forEach(s => s.classList.remove('active'));
            document.getElementById(targetId).classList.add('active');

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


// ========== DASHBOARD HANDLERS ==========
function setupDashboardHandlers() {
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


