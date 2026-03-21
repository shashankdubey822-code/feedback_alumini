/* ========================================
   DataLens — Advanced Frontend Logic
   Python API + AI Insights + Axis Labels
   ======================================== */

// ========== STATE ==========
const state = {
    analytics: null,
    columns: [],
    columnTypes: {},
    fileName: '',
    currentPage: 1,
    rowsPerPage: 25,
    sortColumn: null,
    sortDirection: 'asc',
    tableData: [],
    charts: [],
};

const API_BASE = '';

// ========== REQUEST MANAGEMENT (FIX: Prevent duplicate requests) ==========
const pendingRequests = new Map(); // Track active requests
let currentAutoRefreshController = null; // AbortController for auto-refresh

// Utility: Create unique request key
function getRequestKey(url, method, body) {
    return `${method}:${url}:${body ? JSON.stringify(body) : ''}`;
}

// Utility: Abort pending request if exists
function abortPendingRequest(key) {
    if (pendingRequests.has(key)) {
        pendingRequests.get(key).abort();
        pendingRequests.delete(key);
        console.log(`[REQUEST] Aborted duplicate: ${key}`);
    }
}

// Enhanced fetch with abort controller and duplicate prevention
async function safeFetch(url, options = {}) {
    const key = getRequestKey(url, options.method || 'GET', options.body);
    
    // Abort any existing request with same key
    abortPendingRequest(key);
    
    // Create new AbortController
    const controller = new AbortController();
    pendingRequests.set(key, controller);
    
    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal
        });
        
        pendingRequests.delete(key);
        return response;
    } catch (error) {
        pendingRequests.delete(key);
        if (error.name === 'AbortError') {
            console.log(`[REQUEST] Aborted: ${key}`);
            throw new Error('Request was cancelled');
        }
        throw error;
    }
}

// ========== COLOR PALETTE ==========
const CHART_COLORS = [
    '#6366f1', '#a855f7', '#22d3ee', '#34d399', '#fbbf24',
    '#fb7185', '#fb923c', '#8b5cf6', '#14b8a6', '#f43f5e',
    '#0ea5e9', '#84cc16', '#e879f9', '#f97316', '#06b6d4',
    '#10b981', '#eab308', '#ef4444', '#3b82f6', '#d946ef',
];

const SPEAKER_COLORS = [
    '#6366f1', '#a855f7', '#22d3ee', '#34d399', '#fbbf24',
    '#fb7185', '#fb923c', '#8b5cf6', '#14b8a6', '#f43f5e',
];

// ========== INITIALIZATION ==========
document.addEventListener('DOMContentLoaded', () => {
    setupUploadHandlers();
    setupDashboardHandlers();
    setupSidebarNav();
    setupModal();
    setupAdminAuth();
    loadInitialData();
});

// ========== TOAST NOTIFICATIONS ==========
function showNotification(message, type = 'info') {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 16px;
        border-radius: 8px;
        font-size: 14px;
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
        max-width: 400px;
        word-wrap: break-word;
        font-family: Inter, sans-serif;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    `;

    if (type === 'error') {
        toast.style.background = '#ef4444';
        toast.style.color = '#fff';
    } else if (type === 'success') {
        toast.style.background = '#10b981';
        toast.style.color = '#fff';
    } else {
        toast.style.background = '#6366f1';
        toast.style.color = '#fff';
    }

    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ========== ENHANCED CLIPBOARD (FIX: Error handling + fallback) ==========
async function copyToClipboard(text, successMessage = 'Copied to clipboard!') {
    try {
        // Try modern Clipboard API first
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
            showNotification(successMessage, 'success');
            return true;
        } else {
            // Fallback for older browsers or HTTP (non-HTTPS)
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.left = '-9999px';
            textArea.style.top = '-9999px';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            
            try {
                const successful = document.execCommand('copy');
                document.body.removeChild(textArea);
                
                if (successful) {
                    showNotification(successMessage, 'success');
                    return true;
                } else {
                    throw new Error('execCommand failed');
                }
            } catch (err) {
                document.body.removeChild(textArea);
                throw err;
            }
        }
    } catch (error) {
        console.error('Clipboard error:', error);
        showNotification('Failed to copy. Please copy manually.', 'error');
        
        // Show the text in an alert as final fallback
        alert(`Please copy this manually:\n\n${text}`);
        return false;
    }
}

// ========== POPUP BLOCKER DETECTION ==========
function safeWindowOpen(url, target = '_blank') {
    try {
        const newWindow = window.open(url, target);
        
        if (!newWindow || newWindow.closed || typeof newWindow.closed === 'undefined') {
            // Popup was blocked
            showNotification('Popup blocked! Please allow popups for this site.', 'error');
            
            // Show URL as fallback
            const userChoice = confirm(`Popup was blocked. URL:\n\n${url}\n\nCopy to clipboard?`);
            if (userChoice) {
                copyToClipboard(url, 'URL copied!');
            }
            return false;
        }
        
        return true;
    } catch (error) {
        console.error('Window open error:', error);
        showNotification('Could not open link. Please disable popup blocker.', 'error');
        return false;
    }
}

// ========== CONFIGURATION VALIDATION (CHECK ON STARTUP) ==========
async function validateBackendConfiguration() {
    try {
        const response = await fetch(`${API_BASE}/api/admin/config/validate`);
        const data = await response.json();
        
        if (!data.success || !data.all_valid) {
            console.warn('[CONFIG] Backend configuration issues detected:', data.checks);
            
            const issues = [];
            if (data.checks) {
                if (!data.checks.apps_script_url?.valid) {
                    issues.push('Google Apps Script URL not configured');
                }
                if (!data.checks.database?.exists) {
                    issues.push('Database not found');
                }
                if (data.checks.apps_script_secret?.is_default) {
                    issues.push('Using default secret (security risk)');
                }
            }
            
            if (issues.length > 0) {
                showNotification(`⚠️ Configuration warnings: ${issues.join(', ')}`, 'error');
            }
            
            return false;
        }
        
        console.log('[CONFIG] Backend configuration validated successfully');
        return true;
    } catch (error) {
        console.error('[CONFIG] Failed to validate configuration:', error);
        // Don't block the app if validation endpoint fails
        return true;
    }
}

// ========== DATA LOADING ==========
async function loadInitialData() {
    try {
        // Validate configuration first
        await validateBackendConfiguration();
        
        console.log("loadInitialData: Fetching /api/data");
        const response = await fetch(`${API_BASE}/api/data`);
        console.log("loadInitialData: Response status", response.status);
        if (!response.ok) {
            console.log("loadInitialData: No data (404), showing admin prompt");
            // Show admin prompt if 404
            document.getElementById('loading-status').textContent = 'No data available. Admin upload required.';
            document.getElementById('loading-status').style.color = '#fbbf24';
            document.getElementById('btn-show-admin').style.display = 'inline-block';
            document.querySelector('#loading-screen .brand-icon').style.animation = 'none';
            return;
        }
        
        console.log("loadInitialData: Parsing JSON");
        const analytics = await response.json();
        console.log("loadInitialData: Setting state variables");
        state.analytics = analytics;
        const allowedColumns = [
            'timestamp_original',
            'name_of_student',
            'department_original',
            'roll_no_original',
            'date_of_lecture',
            'alumni_speaker_name',
            'session_help_understanding',
            'aspect_most_valuable',
            'session_rating',
            'improvements_suggestions',
            'future_topics'
        ];

        state.friendlyNames = {
            'timestamp_original': 'Timestamp',
            'name_of_student': 'Name of Student',
            'department_original': 'Department',
            'roll_no_original': 'Roll No.',
            'date_of_lecture': 'Date of the Session',
            'alumni_speaker_name': 'Alumni Speaker Name',
            'session_help_understanding': 'Did the session help you gain a better understanding...?',
            'aspect_most_valuable': 'What aspect of the session did you find most valuable?',
            'session_rating': 'How would you rate the session overall?',
            'improvements_suggestions': 'What improvements or suggestions would you recommend...',
            'future_topics': "Any specific topics or areas you'd like future alumni speakers to cover?"
        };

        // strictly bind dashboard table to only these 11 columns
        state.columns = analytics.meta.columns.filter(col => allowedColumns.includes(col));
        state.columns.sort((a, b) => allowedColumns.indexOf(a) - allowedColumns.indexOf(b));
        state.columnTypes = analytics.meta.columnTypes;
        state.tableData = analytics.tableData || [];
        state.fileName = analytics.meta.filename || 'Database Record';

        // Auto-sort by timestamp in descending order (latest first)
        const timestampCol = state.columns.find(col => col.toUpperCase().includes('TIMESTAMP'));
        if (timestampCol) {
            state.sortColumn = timestampCol;
            state.sortDirection = 'desc';
            sortTableData();
        }

        console.log("loadInitialData: Scheduling switchToDashboardFromLoading");
        setTimeout(() => {
            console.log("Timeout triggered: Switching screens and rendering");
            switchToDashboardFromLoading();
            renderDashboard();
            console.log("Timeout triggered: Render complete");
        }, 300);
    } catch (err) {
        document.getElementById('loading-status').textContent = 'Failed to connect to server.';
        document.getElementById('loading-status').style.color = '#ef4444';
        document.querySelector('#loading-screen .brand-icon').style.animation = 'none';
        console.error(err);
    }
}

function switchToDashboardFromLoading() {
    document.getElementById('loading-screen').classList.remove('active');
    document.getElementById('dashboard-screen').classList.add('active');
    document.getElementById('file-badge').textContent = state.fileName;
    
    // Default to overview section
    showSection('overview-section');
}

function showSection(sectionId) {
    document.querySelectorAll('.dashboard-section').forEach(s => s.classList.remove('active'));
    document.getElementById(sectionId).classList.add('active');
    
    document.querySelectorAll('.sidebar .nav-item').forEach(btn => {
        if (btn.dataset.section === sectionId) btn.classList.add('active');
        else btn.classList.remove('active');
    });
}

// ========== FILE UPLOAD ==========
function setupUploadHandlers() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
    });
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) handleFile(file);
    });
}

async function handleFile(file) {
    if (!file.name.match(/\.(csv|tsv|txt)$/i)) {
        showNotification('Please upload a CSV, TSV, or TXT file.', 'error');
        return;
    }
    
    const token = localStorage.getItem('adminToken');
    if (!token) {
        showNotification('Admin session expired', 'error');
        return;
    }

    state.fileName = file.name;
    showProgress('Uploading to database...', 40);

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE}/api/admin/upload_csv`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData,
        });

        if (!response.ok) {
            let errorMessage = 'Upload failed';
            try {
                const err = await response.json();
                errorMessage = err.error || errorMessage;
            } catch (e) {
                errorMessage = `Server Error: ${response.status} ${response.statusText}`;
            }
            throw new Error(errorMessage);
        }

        showProgress('Done!', 100);

        setTimeout(() => {
            loadInitialData(); // This will call showSection('overview-section') via switchToDashboardFromLoading
        }, 800);

    } catch (err) {
        showNotification('Error: ' + err.message, 'error');
        hideProgress();
    }
}

function showProgress(text, pct) {
    const el = document.getElementById('upload-progress');
    el.classList.remove('hidden');
    document.getElementById('progress-fill').style.width = pct + '%';
    document.getElementById('progress-text').textContent = text;
}

function hideProgress() {
    document.getElementById('upload-progress').classList.add('hidden');
}

// ========== NAVIGATION ==========
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
    document.querySelectorAll('.sidebar .nav-item').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.section === sectionId);
    });

    // SCOPING: If leaving overview, reset filters to show global data in other sections
    if (sectionId !== 'overview-section' && Object.keys(state.activeFilters || {}).length > 0) {
        clearAllFilters();
    }
}

function switchToDashboard() {
    showSection('overview-section');
    document.getElementById('file-badge').textContent = state.fileName || 'No file loaded';
}

function switchToUpload() {
    showSection('upload-section');
    document.getElementById('file-input').value = '';
    document.getElementById('google-link-input').value = '';
    destroyCharts();
}

// ========== SIDEBAR NAVIGATION ==========
function setupSidebarNav() {
    document.querySelectorAll('.sidebar .nav-item').forEach((btn) => {
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

// ========== ADMIN AUTH & LOGIC ==========
function setupAdminAuth() {
    const btnShowAdmin = document.getElementById('btn-show-admin');
    const modal = document.getElementById('admin-login-modal');
    const btnClose = document.getElementById('admin-login-close');
    const btnSubmit = document.getElementById('btn-admin-submit');
    const errorMsg = document.getElementById('admin-login-error');
    
    if (btnShowAdmin) {
        btnShowAdmin.addEventListener('click', () => {
            if (localStorage.getItem('adminToken')) {
                showAdminPanel();
            } else {
                modal.classList.remove('hidden');
            }
        });
    }

    if (btnClose) {
        btnClose.addEventListener('click', () => modal.classList.add('hidden'));
    }

    if (btnSubmit) {
        btnSubmit.addEventListener('click', async () => {
            const pwd = document.getElementById('admin-password').value;
            try {
                const res = await fetch(`${API_BASE}/api/admin/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password: pwd })
                });
                const data = await res.json();
                if (res.ok && data.success) {
                    localStorage.setItem('adminToken', data.token);
                    modal.classList.add('hidden');
                    errorMsg.style.display = 'none';
                    showAdminPanel();
                } else {
                    errorMsg.style.display = 'block';
                }
            } catch (e) {
                errorMsg.style.display = 'block';
                errorMsg.textContent = 'Connection error';
            }
        });
    }


    const btnGoogleFetch = document.getElementById('btn-google-fetch');
    if (btnGoogleFetch) {
        btnGoogleFetch.addEventListener('click', async () => {
            const url = document.getElementById('google-link-input').value.trim();
            if (!url) {
                showNotification('Please enter a valid Google Sheets link', 'error');
                return;
            }

            const token = localStorage.getItem('adminToken');
            if (!token) {
                showNotification('Admin session expired', 'error');
                return;
            }

            showProgress('Fetching from Google...', 30);
            
            try {
                const res = await fetch(`${API_BASE}/api/admin/fetch_google_link`, {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({ url })
                });
                
                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.error || 'Fetch failed');
                }

                showProgress('Data loaded successfully!', 100);
                setTimeout(() => {
                    loadInitialData();
                }, 1000);
            } catch (err) {
                showNotification('Error: ' + err.message, 'error');
                hideProgress();
            }
        });
    }
}

function showAdminPanel() {
    if (!localStorage.getItem('adminToken')) {
        document.getElementById('admin-login-modal').classList.remove('hidden');
        return;
    }
    showSection('upload-section');
}

// ========== RENDER DASHBOARD ==========
function renderDashboard() {
    const a = state.analytics;
    if (!a) return;

    try { renderKPIs(a.kpis); } catch(e) { console.error("Error renderKPIs:", e); }
    try { renderFilters(a.filters); } catch(e) { console.error("Error renderFilters:", e); }
    try { renderAIInsights(a.aiInsights); } catch(e) { console.error("Error renderAIInsights:", e); }
    try { renderCharts(a.charts); } catch(e) { console.error("Error renderCharts:", e); }
    try { renderTimeTrends(a.timeTrends); } catch(e) { console.error("Error renderTimeTrends:", e); }
    try { renderSentiment(a.sentiment); } catch(e) { console.error("Error renderSentiment:", e); }
    try { renderKeywords(a.keywords); } catch(e) { console.error("Error renderKeywords:", e); }
    try { renderSpeakers(a.speakerStats); } catch(e) { console.error("Error renderSpeakers:", e); }
    try { renderTable(); } catch(e) { console.error("Error renderTable:", e); }

    // Hide sections with no data
    try { toggleSectionVisibility('speakers-section', a.speakerStats && a.speakerStats.length > 0); } catch(e) {}
}

function toggleSectionVisibility(sectionId, hasData) {
    // Hide sidebar nav items for empty sections
    const navBtn = document.querySelector(`[data-section="${sectionId}"]`);
    if (navBtn) {
        navBtn.style.display = hasData ? 'flex' : 'none';
    }
}

// ========== AI INSIGHTS ==========
function renderAIInsights(insights) {
    const container = document.getElementById('insights-container');
    container.innerHTML = '';

    if (!insights || insights.length === 0) {
        container.innerHTML = '<div class="empty-state">No AI insights available.</div>';
        return;
    }

    insights.forEach((insight, idx) => {
        const card = document.createElement('div');
        card.className = 'insight-card';
        card.style.animationDelay = `${idx * 0.08}s`;

        const typeClass = `insight-${insight.type}`;

        card.innerHTML = `
            <div class="insight-icon">${insight.icon}</div>
            <div class="insight-content">
                <p class="insight-text">${esc(insight.text)}</p>
            </div>
        `;
        card.classList.add(typeClass);
        container.appendChild(card);
    });
}

// ========== KPI CARDS ==========
function renderKPIs(kpis) {
    const container = document.getElementById('kpi-grid');
    container.innerHTML = '';

    kpis.forEach((kpi) => {
        const card = document.createElement('div');
        card.className = 'kpi-card';
        card.innerHTML = `
            <div class="kpi-label">${esc(kpi.label)}</div>
            <div class="kpi-value">${esc(String(kpi.value))}</div>
            ${kpi.sub ? `<div class="kpi-sub">${esc(kpi.sub)}</div>` : ''}
        `;
        container.appendChild(card);
    });
}

// ========== FILTERS ==========
function renderFilters(filters) {
    const container = document.getElementById('filters-grid');
    container.innerHTML = '';

    filters.forEach((f) => {
        const item = document.createElement('div');
        item.className = 'filter-item';

        const badgeClass = f.type === 'date' ? 'badge-date' : f.type === 'numeric' ? 'badge-num' : f.type === 'categorical' ? 'badge-cat' : 'badge-text';
        const typeLabel = f.type === 'date' ? 'Date' : f.type === 'numeric' ? 'Num' : f.type === 'categorical' ? 'Cat' : 'Text';

        let html = `<div class="filter-label">${esc(truncate(f.column, 22))} <span class="filter-type-badge ${badgeClass}">${typeLabel}</span></div>`;

        if (f.type === 'categorical' && f.options) {
            html += `<select class="filter-select" data-column="${escAttr(f.column)}" data-type="categorical">`;
            html += `<option value="">All (${f.options.length})</option>`;
            f.options.forEach(opt => {
                html += `<option value="${escAttr(opt.value)}">${esc(truncate(opt.value, 28))} (${opt.count})</option>`;
            });
            html += `</select>`;
        } else if (f.type === 'date' && f.options) {
            html += `<div class="filter-date-range">`;
            html += `<div class="calendar-input-wrap"><input type="text" class="filter-input calendar-trigger" data-column="${escAttr(f.column)}" data-type="date-from" data-dates='${JSON.stringify(f.options)}' placeholder="From..." readonly><svg class="calendar-input-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg></div>`;
            html += `<div class="calendar-input-wrap"><input type="text" class="filter-input calendar-trigger" data-column="${escAttr(f.column)}" data-type="date-to" data-dates='${JSON.stringify(f.options)}' placeholder="To..." readonly><svg class="calendar-input-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg></div>`;
            html += `</div>`;
        } else if (f.type === 'numeric') {
            html += `<input type="text" class="filter-input" data-column="${escAttr(f.column)}" data-type="numeric" placeholder="e.g. >3, <5, 3-5, =4">`;
        } else {
            html += `<input type="text" class="filter-input" data-column="${escAttr(f.column)}" data-type="text" placeholder="Search...">`;
        }

        item.innerHTML = html;
        container.appendChild(item);
    });

    container.querySelectorAll('.filter-input:not(.calendar-trigger), .filter-select').forEach(el => {
        el.addEventListener('change', applyFilters);
        el.addEventListener('input', debounce(applyFilters, 400));
    });

    // Initialize smart calendars for date filters
    container.querySelectorAll('.calendar-trigger').forEach(el => {
        new SmartCalendar(el, JSON.parse(el.dataset.dates || '[]'), () => applyFilters());
    });
}

async function applyFilters() {
    const globalSearch = document.getElementById('global-search').value.trim();
    const filters = {};

    document.querySelectorAll('#filters-grid [data-column]').forEach(el => {
        const col = el.dataset.column;
        const dtype = el.dataset.type;
        const val = el.value.trim();
        if (!val) return;

        if (dtype === 'date-from') {
            if (!filters[col]) filters[col] = {};
            if (typeof filters[col] === 'object') filters[col].from = val;
        } else if (dtype === 'date-to') {
            if (!filters[col]) filters[col] = {};
            if (typeof filters[col] === 'object') filters[col].to = val;
        } else {
            filters[col] = val;
        }
    });

    try {
        const response = await fetch(`${API_BASE}/api/filter`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filters, search: globalSearch }),
        });

        if (!response.ok) throw new Error('Filter failed');

        const analytics = await response.json();
        // Check if data actually changed simply using string length as a fast heuristic
        const currentDataHash = JSON.stringify(state.tableData).length;
        const newDataHash = JSON.stringify(analytics.tableData || []).length;
        
        state.analytics = analytics;
        state.tableData = analytics.tableData || [];
        state.currentPage = 1;

        // Prevent full re-render flicker on auto-refresh if identical
        if (currentDataHash !== newDataHash) {
            renderKPIs(analytics.kpis);
            renderAIInsights(analytics.aiInsights);
            renderCharts(analytics.charts);
            renderTimeTrends(analytics.timeTrends);
            renderSentiment(analytics.sentiment);
            renderKeywords(analytics.keywords);
            renderSpeakers(analytics.speakerStats);
            renderTable();
        }
    } catch (err) {
        console.error('Filter error:', err);
    }
}

function clearAllFilters() {
    document.querySelectorAll('#filters-grid .filter-input, #filters-grid .filter-select').forEach(el => {
        el.value = '';
    });
    document.getElementById('global-search').value = '';
    applyFilters();
}

// ========== CHARTS (with axis labels) ==========
function destroyCharts() {
    state.charts.forEach(c => c.destroy());
    state.charts = [];
}

function renderCharts(charts) {
    destroyCharts();
    const container = document.getElementById('charts-grid');
    container.innerHTML = '';

    if (!charts || charts.length === 0) {
        container.innerHTML = '<div class="empty-state">No chartable data found.</div>';
        return;
    }

    charts.forEach((chart) => {
        const card = document.createElement('div');
        card.className = 'chart-card';

        let headerHTML = `<div class="chart-card-header"><div class="chart-card-title">${esc(chart.title)}</div>`;
        if (chart.normalized) {
            headerHTML += `<span class="chart-badge-normalized">🔗 Fuzzy Matched</span>`;
        }
        headerHTML += `</div>`;

        card.innerHTML = `${headerHTML}<div class="chart-canvas-wrapper"><canvas></canvas></div>`;
        container.appendChild(card);

        const canvas = card.querySelector('canvas');
        const chartInstance = new Chart(canvas, {
            type: chart.type,
            data: {
                // Doughnut charts show labels in legend — keep full names there.
                // Bar/line charts show labels on the axis — truncate to avoid overlap.
                labels: chart.type === 'doughnut'
                    ? chart.labels
                    : chart.labels.map(l => truncate(l, 22)),
                datasets: [{
                    label: chart.yLabel || 'Count',
                    data: chart.data,
                    backgroundColor: chart.type === 'doughnut'
                        ? chart.labels.map((_, i) => CHART_COLORS[i % CHART_COLORS.length])
                        : 'rgba(99, 102, 241, 0.6)',
                    borderColor: chart.type === 'doughnut' ? 'transparent' : '#6366f1',
                    borderWidth: chart.type === 'doughnut' ? 0 : 1,
                    borderRadius: chart.type === 'bar' ? 6 : 0,
                }],
            },
            options: getChartOptions(chart.type, chart.xLabel, chart.yLabel, chart),
        });
        state.charts.push(chartInstance);
    });
}



function renderTimeTrends(timeTrends) {
    const container = document.getElementById('trends-grid');
    container.innerHTML = '';

    if (!timeTrends || timeTrends.length === 0) {
        container.innerHTML = '<div class="empty-state">Not enough time data for trends.</div>';
        return;
    }

    timeTrends.forEach(trend => {
        if (trend.responseCount && trend.responseCount.labels.length >= 2) {
            const card = document.createElement('div');
            card.className = 'chart-card';
            card.innerHTML = `
                <div class="chart-card-header"><div class="chart-card-title">Responses Over Time</div></div>
                <div class="chart-canvas-wrapper"><canvas></canvas></div>
            `;
            container.appendChild(card);

            const chart = new Chart(card.querySelector('canvas'), {
                type: 'line',
                data: {
                    labels: trend.responseCount.labels,
                    datasets: [{
                        label: 'Responses',
                        data: trend.responseCount.data,
                        borderColor: '#6366f1',
                        backgroundColor: 'rgba(99, 102, 241, 0.1)',
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#6366f1',
                        pointRadius: 5,
                        pointHoverRadius: 7,
                    }],
                },
                options: getChartOptions('line',
                    trend.responseCount.xLabel || 'Month',
                    trend.responseCount.yLabel || 'Number of Responses'
                ),
            });
            state.charts.push(chart);
        }

        if (trend.ratingTrends) {
            trend.ratingTrends.forEach((rt, idx) => {
                if (rt.labels.length < 2) return;
                const card = document.createElement('div');
                card.className = 'chart-card';
                card.innerHTML = `
                    <div class="chart-card-header"><div class="chart-card-title">${esc(truncate(rt.column, 30))} — Monthly Trend</div></div>
                    <div class="chart-canvas-wrapper"><canvas></canvas></div>
                `;
                container.appendChild(card);

                const chart = new Chart(card.querySelector('canvas'), {
                    type: 'line',
                    data: {
                        labels: rt.labels,
                        datasets: [{
                            label: `Avg ${truncate(rt.column, 15)}`,
                            data: rt.data,
                            borderColor: CHART_COLORS[(idx + 3) % CHART_COLORS.length],
                            backgroundColor: `${CHART_COLORS[(idx + 3) % CHART_COLORS.length]}1a`,
                            fill: true,
                            tension: 0.4,
                            pointRadius: 5,
                            pointHoverRadius: 7,
                        }],
                    },
                    options: getChartOptions('line',
                        rt.xLabel || 'Month',
                        rt.yLabel || `Average ${truncate(rt.column, 20)}`,
                        {
                            title: rt.column,
                            column: rt.column,
                            labels: rt.labels,
                            data: rt.data
                        }
                    ),
                });
                state.charts.push(chart);
            });
        }
    });
}

function getChartOptions(type, xLabel, yLabel, chartData) {
    const base = {
        responsive: true,
        maintainAspectRatio: false,
        onClick: (event, elements) => {
            if (!elements || elements.length === 0 || !chartData) return;
            const index = elements[0].index;
            const clickedLabel = chartData.labels[index];
            const clickedValue = chartData.data[index];
            const binBoundary = chartData.binBoundaries ? chartData.binBoundaries[index] : null;
            openDataModal(chartData.title, clickedLabel, clickedValue, chartData.column, chartData.columnType, binBoundary);
        },
        plugins: {
            legend: {
                display: type === 'doughnut',
                position: 'bottom',
                labels: {
                    color: '#8b8b9e',
                    font: { family: 'Inter', size: 11 },
                    padding: 12,
                    usePointStyle: true,
                    pointStyleWidth: 8,
                },
            },
            tooltip: {
                backgroundColor: '#1a1a2e',
                titleColor: '#f0f0f5',
                bodyColor: '#8b8b9e',
                borderColor: 'rgba(255,255,255,0.1)',
                borderWidth: 1,
                cornerRadius: 8,
                padding: 10,
                titleFont: { family: 'Inter', weight: '600' },
                bodyFont: { family: 'Inter' },
                callbacks: {
                    // Always show full (non-truncated) label on hover
                    title: function(tooltipItems) {
                        if (chartData && chartData.labels && tooltipItems.length > 0) {
                            const idx = tooltipItems[0].dataIndex;
                            if (chartData.labels[idx] !== undefined) {
                                return String(chartData.labels[idx]);
                            }
                        }
                        return tooltipItems.map(item => item.label);
                    },
                },
            },
        },
    };

    if (type === 'bar' || type === 'line') {
        const isHorizontal = chartData && chartData.horizontal;
        if (isHorizontal) {
            base.indexAxis = 'y';
        }
        base.scales = {
            x: {
                title: {
                    display: true,
                    text: isHorizontal ? (yLabel || '') : (xLabel || ''),
                    color: '#8a8aa3',
                    font: { family: 'Inter', size: 11, weight: '600' },
                    padding: { top: 8 },
                },
                ticks: { color: '#5a5a6e', font: { family: 'Inter', size: 10 }, maxRotation: 45 },
                grid: { color: 'rgba(255,255,255,0.03)' },
            },
            y: {
                title: {
                    display: true,
                    text: isHorizontal ? (xLabel || '') : (yLabel || ''),
                    color: '#8a8aa3',
                    font: { family: 'Inter', size: 11, weight: '600' },
                    padding: { bottom: 8 },
                },
                ticks: {
                    color: '#5a5a6e',
                    font: { family: 'Inter', size: 10 },
                    callback: function(value) {
                        if (Number.isInteger(value)) return value;
                        return value.toFixed(1);
                    },
                },
                grid: { color: 'rgba(255,255,255,0.03)' },
                beginAtZero: true,
            },
        };
    }

    if (type === 'doughnut') {
        base.cutout = '60%';
    }

    return base;
}

// ========== SENTIMENT (AI-filtered) ==========
function renderSentiment(sentimentData) {
    const container = document.getElementById('sentiment-grid');
    const noteEl = document.getElementById('sentiment-note');
    container.innerHTML = '';

    if (!sentimentData || sentimentData.length === 0) {
        container.innerHTML = '<div class="empty-state">No opinion/feedback columns detected for sentiment analysis.</div>';
        if (noteEl) noteEl.textContent = 'Only subjective text columns (suggestions, feedback, topics) are analyzed. Names, departments, and IDs are excluded.';
        return;
    }

    if (noteEl) noteEl.textContent = 'AI automatically filters non-answers (No, Nil, NA, Nothing, etc.) before analysis. Only opinion/feedback columns are analyzed.';

    sentimentData.forEach(s => {
        const card = document.createElement('div');
        card.className = 'sentiment-card';

        const polarity = s.avgPolarity;
        const sentimentClass = polarity > 0.1 ? 'positive' : polarity < -0.1 ? 'negative' : 'neutral';
        const sentimentLabel = sentimentClass === 'positive' ? '😊' : sentimentClass === 'negative' ? '😟' : '😐';
        const total = s.total || 1;

        card.innerHTML = `
            <div class="sentiment-card-title">${esc(truncate(s.column, 40))}</div>
            <div class="sentiment-meter">
                <div class="sentiment-gauge">
                    <div class="sentiment-gauge-label ${sentimentClass}">${sentimentLabel}</div>
                    <canvas></canvas>
                </div>
                <div class="sentiment-stats">
                    <div class="sentiment-stat-row">
                        <span class="sentiment-dot positive"></span>
                        <span style="color: var(--text-secondary); font-size: 12px; min-width: 60px;">Positive</span>
                        <div class="sentiment-bar-track">
                            <div class="sentiment-bar-fill positive" style="width: ${(s.positive / total * 100).toFixed(0)}%"></div>
                        </div>
                        <span class="sentiment-count">${s.positive}</span>
                    </div>
                    <div class="sentiment-stat-row">
                        <span class="sentiment-dot neutral"></span>
                        <span style="color: var(--text-secondary); font-size: 12px; min-width: 60px;">Neutral</span>
                        <div class="sentiment-bar-track">
                            <div class="sentiment-bar-fill neutral" style="width: ${(s.neutral / total * 100).toFixed(0)}%"></div>
                        </div>
                        <span class="sentiment-count">${s.neutral}</span>
                    </div>
                    <div class="sentiment-stat-row">
                        <span class="sentiment-dot negative"></span>
                        <span style="color: var(--text-secondary); font-size: 12px; min-width: 60px;">Negative</span>
                        <div class="sentiment-bar-track">
                            <div class="sentiment-bar-fill negative" style="width: ${(s.negative / total * 100).toFixed(0)}%"></div>
                        </div>
                        <span class="sentiment-count">${s.negative}</span>
                    </div>
                </div>
            </div>
            <div class="sentiment-footer">
                <span>Polarity: <strong>${polarity.toFixed(3)}</strong></span>
                <span>Subjectivity: <strong>${s.avgSubjectivity.toFixed(3)}</strong></span>
                ${s.nonAnswers > 0 ? `<span class="non-answer-badge">🧹 ${s.nonAnswers} non-answers filtered</span>` : ''}
            </div>
        `;
        container.appendChild(card);

        drawSentimentGauge(card.querySelector('.sentiment-gauge canvas'), polarity);
    });
}

function drawSentimentGauge(canvas, polarity) {
    const ctx = canvas.getContext('2d');
    const size = 100;
    canvas.width = size * 2;
    canvas.height = size * 2;
    canvas.style.width = size + 'px';
    canvas.style.height = size + 'px';

    const cx = size, cy = size, r = 75;
    const startAngle = Math.PI * 0.75;
    const endAngle = Math.PI * 2.25;
    const normalized = (polarity + 1) / 2;
    const valueAngle = startAngle + (endAngle - startAngle) * normalized;

    ctx.beginPath();
    ctx.arc(cx, cy, r, startAngle, endAngle);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
    ctx.lineWidth = 12;
    ctx.lineCap = 'round';
    ctx.stroke();

    const gradient = ctx.createLinearGradient(0, 0, size * 2, 0);
    gradient.addColorStop(0, '#fb7185');
    gradient.addColorStop(0.5, '#fbbf24');
    gradient.addColorStop(1, '#34d399');

    ctx.beginPath();
    ctx.arc(cx, cy, r, startAngle, valueAngle);
    ctx.strokeStyle = gradient;
    ctx.lineWidth = 12;
    ctx.lineCap = 'round';
    ctx.stroke();
}

// ========== KEYWORDS / WORD CLOUD (with bigrams) ==========
function renderKeywords(keywordsData) {
    const container = document.getElementById('keywords-grid');
    container.innerHTML = '';

    if (!keywordsData || keywordsData.length === 0) {
        container.innerHTML = '<div class="empty-state">No keywords extracted. Only opinion/feedback columns are analyzed.</div>';
        return;
    }

    keywordsData.forEach(kw => {
        const card = document.createElement('div');
        card.className = 'keyword-card';

        const maxCount = Math.max(...kw.words.map(w => w.count));
        const minCount = Math.min(...kw.words.map(w => w.count));

        let cloudHTML = '<div class="word-cloud">';
        kw.words.slice(0, 25).forEach((word, idx) => {
            const size = 11 + ((word.count - minCount) / (maxCount - minCount + 1)) * 14;
            const opacity = 0.5 + ((word.count - minCount) / (maxCount - minCount + 1)) * 0.5;
            const color = CHART_COLORS[idx % CHART_COLORS.length];
            const bgColor = color + '18';
            const isBigram = word.type === 'bigram';
            const bigramClass = isBigram ? 'bigram-tag' : '';
            cloudHTML += `<span class="word-tag ${bigramClass}" style="font-size: ${size}px; background: ${bgColor}; color: ${color}; opacity: ${opacity};" title="${word.count} occurrences${isBigram ? ' (phrase)' : ''}">${isBigram ? '⟨ ' : ''}${esc(word.text)}${isBigram ? ' ⟩' : ''}</span>`;
        });
        cloudHTML += '</div>';

        card.innerHTML = `
            <div class="keyword-card-title">${esc(truncate(kw.column, 40))} — Keywords & Phrases</div>
            ${cloudHTML}
        `;
        container.appendChild(card);
    });
}

// ========== SPEAKERS ==========
function renderSpeakers(speakerStats) {
    const cardsContainer = document.getElementById('speakers-grid');
    const chartsContainer = document.getElementById('speaker-charts-grid');
    cardsContainer.innerHTML = '';
    chartsContainer.innerHTML = '';

    if (!speakerStats || speakerStats.length === 0) {
        return;
    }

    speakerStats.forEach(ss => {
        ss.speakers.forEach((speaker, idx) => {
            const card = document.createElement('div');
            card.className = 'speaker-card';

            const color = SPEAKER_COLORS[idx % SPEAKER_COLORS.length];
            const initial = speaker.name.charAt(0).toUpperCase();
            const sentClass = speaker.sentiment > 0.1 ? 'positive' : speaker.sentiment < -0.1 ? 'negative' : 'neutral';
            const sentLabel = sentClass === 'positive' ? '😊 Positive' : sentClass === 'negative' ? '😟 Negative' : '😐 Neutral';

            const ratingKeys = Object.keys(speaker.ratings || {});
            const mainRating = ratingKeys.length > 0 ? speaker.ratings[ratingKeys[0]] : null;

            card.innerHTML = `
                <div class="speaker-avatar" style="background: ${color}">${initial}</div>
                <div class="speaker-name">${esc(speaker.name)}</div>
                <div class="speaker-meta">${speaker.count} response${speaker.count > 1 ? 's' : ''}</div>
                <div class="speaker-stats-row">
                    ${mainRating !== null ? `<div class="speaker-stat"><div class="speaker-stat-value" style="color: ${color}">${mainRating}</div><div class="speaker-stat-label">Avg Rating</div></div>` : ''}
                    <div class="speaker-stat"><div class="speaker-stat-value" style="color: ${color}">${speaker.count}</div><div class="speaker-stat-label">Responses</div></div>
                </div>
                <div class="speaker-sentiment-pill ${sentClass}">${sentLabel} (${speaker.sentiment.toFixed(2)})</div>
            `;
            
            card.addEventListener('click', () => {
                openDataModal('Speaker Analysis', speaker.name, speaker.count, ss.column, 'categorical', null);
            });

            cardsContainer.appendChild(card);
        });

        if (ss.speakers.length >= 2) {
            const ratingKeys = Object.keys(ss.speakers[0]?.ratings || {});
            if (ratingKeys.length > 0) {
                const card = document.createElement('div');
                card.className = 'chart-card';
                card.innerHTML = `
                    <div class="chart-card-header"><div class="chart-card-title">Speaker Comparison — Avg ${esc(truncate(ratingKeys[0], 25))}</div></div>
                    <div class="chart-canvas-wrapper"><canvas></canvas></div>
                `;
                chartsContainer.appendChild(card);

                const labels = ss.speakers.map(s => truncate(s.name, 16));
                const data = ss.speakers.map(s => s.ratings[ratingKeys[0]] || 0);
                const colors = ss.speakers.map((_, i) => SPEAKER_COLORS[i % SPEAKER_COLORS.length]);
                const isHorizontal = labels.length > 6;

                const chart = new Chart(card.querySelector('canvas'), {
                    type: 'bar',
                    data: {
                        labels,
                        datasets: [{
                            label: `Avg ${truncate(ratingKeys[0], 15)}`,
                            data,
                            backgroundColor: colors,
                            borderRadius: 6,
                            borderWidth: 0,
                        }],
                    },
                    options: getChartOptions('bar', 'Speaker Name', `Average ${truncate(ratingKeys[0], 20)}`, {
                        title: `Speaker Avg ${ratingKeys[0]}`,
                        column: 'Speaker Name',
                        labels,
                        data
                    }),
                });
                state.charts.push(chart);
            }

            // Sentiment comparison
            const card2 = document.createElement('div');
            card2.className = 'chart-card';
            card2.innerHTML = `
                <div class="chart-card-header"><div class="chart-card-title">Speaker Sentiment Comparison</div></div>
                <div class="chart-canvas-wrapper"><canvas></canvas></div>
            `;
            chartsContainer.appendChild(card2);

            const isHorizontal2 = ss.speakers.length > 6;

            const sentChart = new Chart(card2.querySelector('canvas'), {
                type: 'bar',
                data: {
                    labels: ss.speakers.map(s => truncate(s.name, 16)),
                    datasets: [{
                        label: 'Sentiment Score',
                        data: ss.speakers.map(s => s.sentiment),
                        backgroundColor: ss.speakers.map(s =>
                            s.sentiment > 0.1 ? 'rgba(52, 211, 153, 0.6)' :
                            s.sentiment < -0.1 ? 'rgba(251, 113, 133, 0.6)' :
                            'rgba(251, 191, 36, 0.6)'
                        ),
                        borderRadius: 6,
                        borderWidth: 0,
                    }],
                },
                options: getChartOptions('bar', 'Speaker Name', 'Sentiment Score (-1 to +1)', {
                    title: 'Speaker Sentiment',
                    column: 'Speaker Name',
                    labels: ss.speakers.map(s => s.name),
                    data: ss.speakers.map(s => s.sentiment)
                }),
            });
            state.charts.push(sentChart);
        }
    });
}

// ========== DATA TABLE ==========
function renderTable() {
    buildTableHead();
    buildTableBody();
    buildPagination();
    updateShowingCount();
}

function buildTableHead() {
    const thead = document.getElementById('table-head');
    thead.innerHTML = '';
    const tr = document.createElement('tr');

    state.columns.forEach(col => {
        const th = document.createElement('th');
        const displayName = state.friendlyNames && state.friendlyNames[col] ? state.friendlyNames[col] : col;
        th.textContent = truncate(displayName, 35);
        th.title = displayName;

        const arrow = document.createElement('span');
        arrow.className = 'sort-arrow';
        arrow.textContent = '↕';
        th.appendChild(arrow);

        if (state.sortColumn === col) {
            th.classList.add(state.sortDirection === 'asc' ? 'sorted-asc' : 'sorted-desc');
            arrow.textContent = state.sortDirection === 'asc' ? '↑' : '↓';
        }

        th.addEventListener('click', () => {
            if (state.sortColumn === col) {
                state.sortDirection = state.sortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                state.sortColumn = col;
                state.sortDirection = 'asc';
            }
            sortTableData();
            buildTableBody();
            buildPagination();
            buildTableHead();
        });

        tr.appendChild(th);
    });

    thead.appendChild(tr);
}

function sortTableData() {
    const col = state.sortColumn;
    const dir = state.sortDirection === 'asc' ? 1 : -1;
    const type = state.columnTypes[col] || 'text';

    state.tableData.sort((a, b) => {
        let va = a[col] || '';
        let vb = b[col] || '';

        if (type === 'numeric') {
            va = parseFloat(va) || 0;
            vb = parseFloat(vb) || 0;
            return (va - vb) * dir;
        }

        return va.localeCompare(vb) * dir;
    });
}

function buildTableBody() {
    const tbody = document.getElementById('table-body');
    tbody.innerHTML = '';

    const start = (state.currentPage - 1) * state.rowsPerPage;
    const end = Math.min(start + state.rowsPerPage, state.tableData.length);
    const pageData = state.tableData.slice(start, end);

    if (pageData.length === 0) {
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = state.columns.length;
        td.style.textAlign = 'center';
        td.style.padding = '40px';
        td.style.color = 'var(--text-muted)';
        td.textContent = 'No data matches the current filters.';
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
    }

    pageData.forEach(row => {
        const tr = document.createElement('tr');
        state.columns.forEach(col => {
            const td = document.createElement('td');
            td.textContent = row[col] || '';
            td.title = row[col] || '';
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
}

function buildPagination() {
    const container = document.getElementById('pagination');
    container.innerHTML = '';

    const totalPages = Math.ceil(state.tableData.length / state.rowsPerPage);
    if (totalPages <= 1) return;

    const prevBtn = createPageBtn('←', state.currentPage > 1, () => {
        state.currentPage--;
        buildTableBody();
        buildPagination();
        updateShowingCount();
    });
    container.appendChild(prevBtn);

    const pages = getPageNumbers(state.currentPage, totalPages);
    pages.forEach(p => {
        if (p === '...') {
            const dots = document.createElement('span');
            dots.textContent = '...';
            dots.style.color = 'var(--text-muted)';
            dots.style.padding = '0 4px';
            container.appendChild(dots);
        } else {
            const btn = createPageBtn(p, true, () => {
                state.currentPage = p;
                buildTableBody();
                buildPagination();
                updateShowingCount();
            });
            if (p === state.currentPage) btn.classList.add('active');
            container.appendChild(btn);
        }
    });

    const nextBtn = createPageBtn('→', state.currentPage < totalPages, () => {
        state.currentPage++;
        buildTableBody();
        buildPagination();
        updateShowingCount();
    });
    container.appendChild(nextBtn);
}

function createPageBtn(text, enabled, onClick) {
    const btn = document.createElement('button');
    btn.className = 'page-btn';
    btn.textContent = text;
    btn.disabled = !enabled;
    if (enabled) btn.addEventListener('click', onClick);
    return btn;
}

function getPageNumbers(current, total) {
    if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
    const pages = [];
    if (current <= 4) {
        for (let i = 1; i <= 5; i++) pages.push(i);
        pages.push('...', total);
    } else if (current >= total - 3) {
        pages.push(1, '...');
        for (let i = total - 4; i <= total; i++) pages.push(i);
    } else {
        pages.push(1, '...');
        for (let i = current - 1; i <= current + 1; i++) pages.push(i);
        pages.push('...', total);
    }
    return pages;
}

function updateShowingCount() {
    const total = state.tableData.length;
    const start = total > 0 ? (state.currentPage - 1) * state.rowsPerPage + 1 : 0;
    const end = Math.min(state.currentPage * state.rowsPerPage, total);
    document.getElementById('showing-count').textContent = `Showing ${start}–${end} of ${total} rows`;
}

// ========== DOWNLOAD ==========
function downloadFilteredCSV() {
    if (!state.tableData || state.tableData.length === 0) {
        showNotification('No data to download.', 'error');
        return;
    }

    const header = state.columns.map(col => {
        let name = state.friendlyNames && state.friendlyNames[col] ? state.friendlyNames[col] : col;
        return name.includes(',') || name.includes('"') ? `"${name.replace(/"/g, '""')}"` : name;
    }).join(',');
    const rows = state.tableData.map(row =>
        state.columns.map(col => {
            const val = row[col] || '';
            return val.includes(',') || val.includes('"') ? `"${val.replace(/"/g, '""')}"` : val;
        }).join(',')
    );

    const csv = [header, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `filtered_${state.fileName || 'data.csv'}`;
    a.click();
    URL.revokeObjectURL(url);
}

// ========== UTILITIES ==========
function truncate(str, len) {
    if (!str) return '';
    return str.length > len ? str.substring(0, len) + '…' : str;
}

function esc(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function escAttr(str) {
    return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function debounce(fn, delay) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

// ========== DATA MODAL LOGIC ==========
function setupModal() {
    const modal = document.getElementById('data-modal');
    const closeBtn = document.getElementById('modal-close');

    if (!modal || !closeBtn) return;

    closeBtn.addEventListener('click', () => {
        modal.classList.add('hidden');
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('hidden');
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !modal.classList.contains('hidden')) {
            modal.classList.add('hidden');
        }
    });
}

function openDataModal(chartTitle, clickedLabel, clickedValue, column, columnType, binBoundary) {
    if (!state.tableData || state.tableData.length === 0) return;

    const modal = document.getElementById('data-modal');
    const title = document.getElementById('modal-title');
    const thead = document.getElementById('modal-table-head');
    const tbody = document.getElementById('modal-table-body');

    title.textContent = `Raw Data: ${chartTitle} \u2192 ${clickedLabel}`;

    let filteredRows;

    if (column && columnType === 'numeric' && binBoundary) {
        // Numeric bin: filter rows within the numeric range
        filteredRows = state.tableData.filter(row => {
            const numVal = parseFloat(String(row[column] || '').trim());
            if (isNaN(numVal)) return false;
            if (binBoundary.exact !== undefined) {
                return numVal === binBoundary.exact;
            }
            // Range bin: [min, max). Last bin is inclusive on both ends.
            if (binBoundary.isLast) {
                return numVal >= binBoundary.min && numVal <= binBoundary.max;
            }
            return numVal >= binBoundary.min && numVal < binBoundary.max;
        });
    } else if (column) {
        // Categorical: exact match on the specific column only
        const searchLabel = String(clickedLabel).toLowerCase().trim();
        filteredRows = state.tableData.filter(row => {
            return String(row[column] || '').toLowerCase().trim() === searchLabel;
        });
    } else {
        // Fallback (speaker charts, etc.): exact match across all columns
        const searchLabel = String(clickedLabel).toLowerCase().trim();
        filteredRows = state.tableData.filter(row => {
            return Object.values(row).some(v =>
                String(v).toLowerCase().trim() === searchLabel
            );
        });
    }

    thead.innerHTML = '';
    tbody.innerHTML = '';

    if (state.columns.length > 0) {
        const trHead = document.createElement('tr');
        state.columns.forEach(col => {
            const th = document.createElement('th');
            th.textContent = state.friendlyNames && state.friendlyNames[col] ? state.friendlyNames[col] : col;
            trHead.appendChild(th);
        });
        thead.appendChild(trHead);
    }

    if (filteredRows.length === 0) {
        const trEmpty = document.createElement('tr');
        const tdEmpty = document.createElement('td');
        tdEmpty.colSpan = state.columns.length;
        tdEmpty.textContent = 'No matching data rows found for this segment.';
        tdEmpty.style.textAlign = 'center';
        tdEmpty.style.padding = '30px';
        trEmpty.appendChild(tdEmpty);
        tbody.appendChild(trEmpty);
    } else {
        filteredRows.forEach(row => {
            const tr = document.createElement('tr');
            state.columns.forEach(col => {
                const td = document.createElement('td');
                td.textContent = row[col] !== undefined && row[col] !== null ? row[col] : '';
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
    }

    modal.classList.remove('hidden');
}

// ═══════════════════════════════════════════════════════════════════
//  SMART CALENDAR — Data-Aware Date Picker
//  Only dates present in the input data are clickable.
//  Month navigation restricted to data range.
// ═══════════════════════════════════════════════════════════════════
class SmartCalendar {
    constructor(inputEl, availableDates, onSelect) {
        this.input = inputEl;
        this.onSelect = onSelect;
        this.selectedDate = null;

        // Parse available dates into a Set of 'YYYY-MM-DD' strings
        this.availableDates = new Set();
        this.availableMonths = new Set();
        this.parsedDates = [];

        availableDates.forEach(d => {
            this.availableDates.add(d);
            const parts = d.split('-');
            if (parts.length === 3) {
                this.availableMonths.add(`${parts[0]}-${parts[1]}`);
                this.parsedDates.push(new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2])));
            }
        });

        // Determine min/max months
        if (this.parsedDates.length > 0) {
            this.parsedDates.sort((a, b) => a - b);
            this.minDate = this.parsedDates[0];
            this.maxDate = this.parsedDates[this.parsedDates.length - 1];
            this.minMonth = new Date(this.minDate.getFullYear(), this.minDate.getMonth(), 1);
            this.maxMonth = new Date(this.maxDate.getFullYear(), this.maxDate.getMonth(), 1);
        } else {
            const now = new Date();
            this.minMonth = now;
            this.maxMonth = now;
        }

        this.currentMonth = new Date(this.minMonth);
        this.popup = null;
        this.isOpen = false;

        this.input.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggle();
        });

        document.addEventListener('click', (e) => {
            if (this.isOpen && this.popup && !this.popup.contains(e.target) && e.target !== this.input) {
                this.close();
            }
        });
    }

    toggle() {
        this.isOpen ? this.close() : this.open();
    }

    open() {
        this.close(); // close any existing
        this.isOpen = true;
        this.popup = document.createElement('div');
        this.popup.className = 'smart-calendar-popup';
        this.render();

        // Position popup below input
        const rect = this.input.getBoundingClientRect();
        this.popup.style.position = 'fixed';
        this.popup.style.top = (rect.bottom + 6) + 'px';
        this.popup.style.left = rect.left + 'px';
        this.popup.style.zIndex = '10000';

        document.body.appendChild(this.popup);

        // Adjust if off-screen
        requestAnimationFrame(() => {
            const popRect = this.popup.getBoundingClientRect();
            if (popRect.right > window.innerWidth) {
                this.popup.style.left = (window.innerWidth - popRect.width - 12) + 'px';
            }
            if (popRect.bottom > window.innerHeight) {
                this.popup.style.top = (rect.top - popRect.height - 6) + 'px';
            }
        });
    }

    close() {
        if (this.popup) {
            this.popup.remove();
            this.popup = null;
        }
        this.isOpen = false;
    }

    canGoPrev() {
        const prev = new Date(this.currentMonth.getFullYear(), this.currentMonth.getMonth() - 1, 1);
        return prev >= this.minMonth;
    }

    canGoNext() {
        const next = new Date(this.currentMonth.getFullYear(), this.currentMonth.getMonth() + 1, 1);
        return next <= this.maxMonth;
    }

    render() {
        if (!this.popup) return;

        const year = this.currentMonth.getFullYear();
        const month = this.currentMonth.getMonth();
        const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'];
        const dayNames = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

        const firstDay = new Date(year, month, 1).getDay();
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const prevDisabled = !this.canGoPrev();
        const nextDisabled = !this.canGoNext();

        let html = `<div class="sc-header">`;
        html += `<button class="sc-nav-btn ${prevDisabled ? 'sc-disabled' : ''}" data-dir="prev" ${prevDisabled ? 'disabled' : ''}>`;
        html += `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6"/></svg></button>`;
        html += `<span class="sc-month-label">${monthNames[month]} ${year}</span>`;
        html += `<button class="sc-nav-btn ${nextDisabled ? 'sc-disabled' : ''}" data-dir="next" ${nextDisabled ? 'disabled' : ''}>`;
        html += `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg></button>`;
        html += `</div>`;

        // Day names header
        html += `<div class="sc-day-names">`;
        dayNames.forEach(d => { html += `<span class="sc-day-name">${d}</span>`; });
        html += `</div>`;

        // Day grid
        html += `<div class="sc-grid">`;

        // Empty slots before first day
        for (let i = 0; i < firstDay; i++) {
            html += `<span class="sc-day sc-empty"></span>`;
        }

        // Actual days
        for (let d = 1; d <= daysInMonth; d++) {
            const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
            const isAvailable = this.availableDates.has(dateStr);
            const isSelected = this.selectedDate === dateStr;
            const today = new Date();
            const isToday = d === today.getDate() && month === today.getMonth() && year === today.getFullYear();

            let classes = 'sc-day';
            if (isAvailable) classes += ' sc-available';
            else classes += ' sc-unavailable';
            if (isSelected) classes += ' sc-selected';
            if (isToday) classes += ' sc-today';

            if (isAvailable) {
                html += `<button class="${classes}" data-date="${dateStr}">${d}</button>`;
            } else {
                html += `<span class="${classes}">${d}</span>`;
            }
        }

        html += `</div>`;

        // Data badge
        const monthKey = `${year}-${String(month + 1).padStart(2, '0')}`;
        const datesThisMonth = [...this.availableDates].filter(d => d.startsWith(monthKey)).length;
        html += `<div class="sc-footer">`;
        html += `<span class="sc-data-count">${datesThisMonth} date${datesThisMonth !== 1 ? 's' : ''} with data</span>`;
        if (this.selectedDate) {
            html += `<button class="sc-clear-btn">Clear</button>`;
        }
        html += `</div>`;

        this.popup.innerHTML = html;

        // Event listeners
        this.popup.querySelectorAll('.sc-nav-btn:not(.sc-disabled)').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const dir = btn.dataset.dir;
                if (dir === 'prev' && this.canGoPrev()) {
                    this.currentMonth = new Date(year, month - 1, 1);
                } else if (dir === 'next' && this.canGoNext()) {
                    this.currentMonth = new Date(year, month + 1, 1);
                }
                this.render();
            });
        });

        this.popup.querySelectorAll('.sc-day.sc-available').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.selectedDate = btn.dataset.date;
                this.input.value = btn.dataset.date;
                this.render();
                setTimeout(() => {
                    this.close();
                    if (this.onSelect) this.onSelect();
                }, 150);
            });
        });

        const clearBtn = this.popup.querySelector('.sc-clear-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.selectedDate = null;
                this.input.value = '';
                this.render();
                if (this.onSelect) this.onSelect();
            });
        }
    }
}


// ========================================================
//  FEEDBACK FORM MANAGER
// ========================================================
(function () {

    const APPS_SCRIPT_URL = 'https://script.google.com/macros/s/AKfycbxY6D1osK0zBjk6LUeDP0emtLKo7TslMyCvIqWwnlxogSxXP01CuA_MbQ4GRupSpGq2aw/exec';
    let _currentFormUrl = '';

    // ── Token helper (reuses existing auth) ─────────────────
    function getToken() {
        return localStorage.getItem('adminToken') || '';
    }

    function authHeaders() {
        return {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getToken()}`
        };
    }

    // ── Open / close modal ───────────────────────────────────
    function openFeedbackModal() {
        if (!getToken()) {
            // Ask admin to log in first
            document.getElementById('admin-login-modal').classList.remove('hidden');
            // After login, re-open feedback modal
            const origSubmit = document.getElementById('btn-admin-submit');
            const handler = () => {
                setTimeout(() => {
                    if (getToken()) {
                        document.getElementById('feedback-modal').classList.remove('hidden');
                        loadEvents();
                    }
                    origSubmit.removeEventListener('click', handler);
                }, 300);
            };
            origSubmit.addEventListener('click', handler);
            return;
        }
        resetForm();
        document.getElementById('feedback-modal').classList.remove('hidden');
        loadEvents();
    }

    function closeFeedbackModal() {
        document.getElementById('feedback-modal').classList.add('hidden');
    }

    function resetForm() {
        document.getElementById('fb-speaker-name').value = '';
        document.getElementById('fb-venue-date').value = '';
        document.getElementById('fb-status').style.display = 'none';
        document.getElementById('fb-result').style.display = 'none';
        const btn = document.getElementById('btn-generate-form');
        btn.disabled = false;
        btn.textContent = 'Generate Google Form';
        btn.style.opacity = '1';
        _currentFormUrl = '';
    }

    // ── Status helpers ───────────────────────────────────────
    function showStatus(msg, type) {
        const el = document.getElementById('fb-status');
        el.style.display = 'block';
        el.textContent = msg;
        el.style.background = type === 'error'
            ? 'rgba(239,68,68,0.1)' : 'rgba(99,102,241,0.1)';
        el.style.color = type === 'error' ? '#ef4444' : '#a5b4fc';
        el.style.border = type === 'error'
            ? '1px solid rgba(239,68,68,0.2)' : '1px solid rgba(99,102,241,0.2)';
    }

    function hideStatus() {
        document.getElementById('fb-status').style.display = 'none';
    }

    // ── Generate form ────────────────────────────────────────
    async function generateForm() {
        const speaker = document.getElementById('fb-speaker-name').value.trim();
        const date    = document.getElementById('fb-venue-date').value.trim();

        if (!speaker || !date) {
            showStatus('Please fill in both Speaker Name and Venue Date.', 'error');
            return;
        }

        const btn = document.getElementById('btn-generate-form');
        
        // Prevent double-click with proper state management
        if (btn.disabled) {
            console.log('[FORM] Button already disabled, ignoring click');
            return;
        }
        
        btn.disabled = true;
        btn.textContent = 'Creating event & form...';
        btn.style.opacity = '0.7';
        hideStatus();
        document.getElementById('fb-result').style.display = 'none';

        try {
            // ✅ NEW: Use atomic endpoint - creates event AND form in single transaction
            const response = await safeFetch(`${API_BASE}/api/admin/create-event-and-form`, {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify({ speaker_name: speaker, venue_date: date })
            });
            
            const data = await response.json();
            
            if (!data.success) {
                throw new Error(data.error || 'Failed to create event and form');
            }
            
            // Success! Form created atomically
            _currentFormUrl = data.form_url;
            console.log("[FORM] Successfully created:", {
                event_id: data.event_id,
                form_id: data.form_id,
                form_url: data.form_url
            });
            
            const urlEl = document.getElementById('fb-form-url-text');
            urlEl.textContent = _currentFormUrl || 'Error: URL not returned';
            urlEl.style.color = '#ffffff';
            
            document.getElementById('fb-result').style.display = 'block';

            btn.textContent = 'Generate Another Form';
            btn.disabled = false;
            btn.style.opacity = '1';
            
            showNotification('✅ Google Form created successfully!', 'success');
            
            loadEvents(); // refresh list

        } catch (err) {
            console.error('[FORM] Error:', err);
            
            let errorMessage = 'Error: ' + err.message;
            
            // Enhanced error messages
            if (err.message.includes('APPS_SCRIPT_URL')) {
                errorMessage = '⚠️ Google Apps Script not configured. Please contact administrator.';
            } else if (err.message.includes('timeout')) {
                errorMessage = '⏱️ Request timed out. Google Forms may be slow. Please try again.';
            } else if (err.message.includes('Connection failed')) {
                errorMessage = '🌐 Cannot reach Google Apps Script. Check your internet connection.';
            }
            
            showStatus(errorMessage, 'error');
            btn.textContent = 'Generate Google Form';
            btn.disabled = false;
            btn.style.opacity = '1';
        }
    }

    // ── Load events list ─────────────────────────────────────
    async function loadEvents() {
        const list = document.getElementById('fb-events-list');
        list.innerHTML = '<div style="color:#8b8b9e;font-size:13px;text-align:center;padding:16px;">Loading...</div>';
        try {
            const res  = await fetch(`${API_BASE}/api/admin/events`, { headers: authHeaders() });
            const data = await res.json();
            if (!data.success) throw new Error(data.error);

            if (!data.events || data.events.length === 0) {
                list.innerHTML = '<div style="color:#8b8b9e;font-size:13px;text-align:center;padding:20px;">No events yet. Create your first one above!</div>';
                return;
            }

            list.innerHTML = '';
            data.events.forEach(ev => {
                const card = document.createElement('div');
                card.style.cssText = 'background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:10px;padding:14px;';
                const hasForm = !!ev.form_url;
                card.innerHTML = `
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
                        <div>
                            <div style="font-size:13px;font-weight:600;color:#f0f0f5;">${esc(ev.speaker_name)}</div>
                            <div style="font-size:11px;color:#8b8b9e;margin-top:2px;">${esc(ev.venue_date)} &nbsp;·&nbsp; ${ev.responses} response${ev.responses !== 1 ? 's' : ''}</div>
                        </div>
                        <span style="font-size:10px;padding:3px 8px;border-radius:12px;font-weight:600;${hasForm ? 'background:rgba(34,211,102,0.1);color:#34d399;border:1px solid rgba(34,211,102,0.2);' : 'background:rgba(251,191,36,0.1);color:#fbbf24;border:1px solid rgba(251,191,36,0.2);'}">
                            ${hasForm ? 'Form Ready' : 'No Form'}
                        </span>
                    </div>
                    ${hasForm ? `
                    <div style="display:flex;gap:6px;margin-top:8px;">
                        <button data-copy-url="${ev.form_url}" class="btn-copy-event-url"
                            style="flex:1;padding:6px;border-radius:6px;background:rgba(99,102,241,0.15);color:#a5b4fc;border:1px solid rgba(99,102,241,0.25);font-size:11px;cursor:pointer;font-family:Inter;font-weight:600;">Copy</button>
                        <button data-open-url="${ev.form_url}" class="btn-open-event-url"
                            style="flex:1;padding:6px;border-radius:6px;background:rgba(99,102,241,0.15);color:#a5b4fc;border:1px solid rgba(99,102,241,0.25);font-size:11px;cursor:pointer;font-family:Inter;font-weight:600;">Open</button>
                        <button data-form="${ev.form_id}" class="btn-toggle-form"
                            style="flex:1;padding:6px;border-radius:6px;background:rgba(239,68,68,0.15);color:#fca5a5;border:1px solid rgba(239,68,68,0.25);font-size:11px;cursor:pointer;font-family:Inter;font-weight:600;">Toggle</button>
                        <button data-event-id="${ev.id}" class="btn-sync-responses"
                            style="flex:1;padding:6px;border-radius:6px;background:rgba(168,85,247,0.15);color:#c084fc;border:1px solid rgba(168,85,247,0.25);font-size:11px;cursor:pointer;font-family:Inter;font-weight:600;">Sync</button>
                    </div>` : `
                    <button data-event-id="${ev.id}" class="btn-generate-existing"
                        style="width:100%;margin-top:8px;padding:6px;border-radius:6px;background:rgba(251,191,36,0.1);color:#fbbf24;border:1px solid rgba(251,191,36,0.2);font-size:11px;cursor:pointer;font-family:Inter;font-weight:600;">Generate Form</button>`}
                `;
                list.appendChild(card);
            });

            // Sync response buttons (enhanced with better feedback)
            list.querySelectorAll('.btn-sync-responses').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const id = btn.dataset.eventId;
                    
                    // Prevent double-click
                    if (btn.disabled) return;
                    
                    const originalText = btn.textContent;
                    btn.textContent = 'Syncing...';
                    btn.disabled = true;
                    
                    try {
                        const r = await safeFetch(`${API_BASE}/api/admin/sync-responses`, {
                            method: 'POST',
                            headers: authHeaders(),
                            body: JSON.stringify({ event_id: parseInt(id) })
                        });
                        const d = await r.json();
                        
                        if (d.success) {
                            // Show detailed sync info
                            const synced = d.synced || 0;
                            const skipped = d.skipped || 0;
                            const total = d.total || 0;
                            
                            if (synced > 0) {
                                btn.textContent = `✓ ${synced} new`;
                                showNotification(`Synced ${synced} responses (${skipped} duplicates skipped)`, 'success');
                            } else {
                                btn.textContent = 'Up to date';
                                showNotification('All responses already synced', 'info');
                            }
                            
                            // Reload events to update response count
                            setTimeout(() => loadEvents(), 1000);
                        } else {
                            btn.textContent = 'Error';
                            showNotification(`Sync failed: ${d.error || 'Unknown error'}`, 'error');
                        }
                        
                        // Reset button after delay
                        setTimeout(() => { 
                            btn.textContent = originalText; 
                            btn.disabled = false; 
                        }, 3000);
                        
                    } catch (e) {
                        console.error('[SYNC] Error:', e);
                        btn.textContent = 'Failed';
                        showNotification(`Sync error: ${e.message}`, 'error');
                        setTimeout(() => { 
                            btn.textContent = originalText; 
                            btn.disabled = false; 
                        }, 3000);
                    }
                });
            });

            // Copy event URL buttons (with enhanced clipboard)
            list.querySelectorAll('.btn-copy-event-url').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const url = btn.dataset.copyUrl;
                    if (url) {
                        const originalText = btn.textContent;
                        const success = await copyToClipboard(url, 'Form link copied!');
                        if (success) {
                            btn.textContent = 'Copied!';
                            setTimeout(() => { btn.textContent = originalText; }, 1500);
                        }
                    }
                });
            });

            // Open event URL buttons (with popup blocker detection)
            list.querySelectorAll('.btn-open-event-url').forEach(btn => {
                btn.addEventListener('click', () => {
                    const url = btn.dataset.openUrl;
                    if (url) {
                        safeWindowOpen(url);
                    }
                });
            });

            // Toggle form status buttons
            list.querySelectorAll('.btn-toggle-form').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const formId = btn.dataset.form;
                    if (!formId) return;
                    btn.textContent = '...';
                    btn.disabled = true;
                    try {
                        const r = await fetch(`${API_BASE}/api/admin/toggle-form`, {
                            method: 'POST', headers: authHeaders(),
                            body: JSON.stringify({ form_id: formId })
                        });
                        const d = await r.json();
                        btn.textContent = d.success ? (d.accepting_responses ? 'Opened!' : 'Closed!') : 'Error';
                        setTimeout(() => { btn.textContent = 'Toggle'; btn.disabled = false; }, 2000);
                    } catch (e) {
                        btn.textContent = 'Error';
                        setTimeout(() => { btn.textContent = 'Toggle'; btn.disabled = false; }, 2000);
                    }
                });
            });

            // Generate form for existing event
            list.querySelectorAll('.btn-generate-existing').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const id = btn.dataset.eventId;
                    btn.textContent = 'Generating...';
                    btn.disabled = true;
                    try {
                        const r = await fetch(`${API_BASE}/api/admin/generate-form`, {
                            method: 'POST', headers: authHeaders(),
                            body: JSON.stringify({ event_id: parseInt(id) })
                        });
                        const d = await r.json();
                        if (d.success) loadEvents();
                        else { btn.textContent = 'Error'; setTimeout(() => { btn.textContent = 'Generate Form'; btn.disabled = false; }, 2000); }
                    } catch (e) {
                        btn.textContent = 'Error';
                        setTimeout(() => { btn.textContent = 'Generate Form'; btn.disabled = false; }, 2000);
                    }
                });
            });

        } catch (err) {
            list.innerHTML = `<div style="color:#ef4444;font-size:13px;text-align:center;padding:16px;">Error: ${err.message}</div>`;
        }
    }

    // ── Wire everything up on DOMContentLoaded ───────────────
    document.addEventListener('DOMContentLoaded', () => {

        // "Admin Panel" (Manage Forms) sidebar button → now opens Feedback Modal
        const btnAdminPanel = document.getElementById('btn-admin-panel');
        if (btnAdminPanel) {
            // Remove existing listener by cloning
            const newBtn = btnAdminPanel.cloneNode(true);
            btnAdminPanel.parentNode.replaceChild(newBtn, btnAdminPanel);
            newBtn.addEventListener('click', openFeedbackModal);
        }

        // "Upload Data" button is now handled by the generic setupSidebarNav selector


        // Close button
        document.getElementById('feedback-modal-close')
            ?.addEventListener('click', closeFeedbackModal);

        // Click outside to close
        document.getElementById('feedback-modal')
            ?.addEventListener('click', (e) => {
                if (e.target === document.getElementById('feedback-modal')) closeFeedbackModal();
            });

        // Generate form button
        document.getElementById('btn-generate-form')
            ?.addEventListener('click', generateForm);

        // Refresh events list
        document.getElementById('btn-refresh-events')
            ?.addEventListener('click', loadEvents);

        // Copy form URL
        document.getElementById('btn-copy-form-url')
            ?.addEventListener('click', () => {
                if (_currentFormUrl) {
                    copyToClipboard(_currentFormUrl, 'Form link copied!');
                } else {
                    showNotification('No form URL available', 'error');
                }
            });

        // Open form in new tab
        document.getElementById('btn-open-form-url')
            ?.addEventListener('click', () => {
                if (_currentFormUrl) {
                    safeWindowOpen(_currentFormUrl);
                } else {
                    showNotification('No form URL available', 'error');
                }
            });
    });

})();
