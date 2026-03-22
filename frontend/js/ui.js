/* ui.js — screen helpers used by app.js */

// ========== SCREEN SWITCHING ==========
function showSection(sectionId) {
    document.querySelectorAll('.dashboard-section').forEach(sec => sec.classList.remove('active'));
    const target = document.getElementById(sectionId);
    if (target) {
        target.classList.add('active');
        window.scrollTo(0, 0);
    }
    document.querySelectorAll('.sidebar .nav-item').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.section === sectionId);
    });
    if (sectionId !== 'overview-section' && Object.keys((window.state && state.activeFilters) || {}).length > 0) {
        if (typeof clearAllFilters === 'function') clearAllFilters();
    }
}

function switchToDashboard() {
    showSection('overview-section');
    const badge = document.getElementById('file-badge');
    if (badge && window.state) badge.textContent = state.fileName || 'No file loaded';
}

function switchToUpload() {
    showSection('upload-section');
    if (typeof hideProgress === 'function') hideProgress();
    const fi = document.getElementById('file-input');
    const li = document.getElementById('google-link-input');
    if (fi) fi.value = '';
    if (li) li.value = '';
    if (typeof destroyCharts === 'function') destroyCharts();
}

// ========== MODAL HANDLERS ==========
function setupModals() {
    const pairs = [
        ['modal-close',          'data-modal'],
        ['admin-login-close',    'admin-login-modal'],
        ['feedback-modal-close', 'feedback-modal'],
    ];
    pairs.forEach(([btnId, modalId]) => {
        const btn = document.getElementById(btnId);
        const modal = document.getElementById(modalId);
        if (btn && modal) btn.addEventListener('click', () => modal.classList.add('hidden'));
    });
    // Close on backdrop click
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', e => {
            if (e.target === overlay) overlay.classList.add('hidden');
        });
    });
}
