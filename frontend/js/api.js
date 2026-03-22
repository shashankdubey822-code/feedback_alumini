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


// ███ SYSTEM CHECKUP LOGIC ███
async function performSystemCheckup() {
    console.log('[CHECKUP] Starting System Integrity Check...');
    const modal = document.getElementById('system-checkup-modal');
    modal.classList.remove('hidden');
    
    const results = { db: false, script: false, webhook: false };
    
    try {
        // Step 1: Call full-check endpoint
        const response = await fetch(`${API_BASE}/api/v1/diagnostics/full-check`);
        const data = await response.json();
        
        // Update DB UI
        updateCheckupUI('check-db', data.checks.database.status === 'ok', 
            data.checks.database.status === 'ok' ? `Connected (${data.checks.database.rows} rows)` : data.checks.database.message);
        results.db = data.checks.database.status === 'ok';

        // Update Script UI
        updateCheckupUI('check-script', data.checks.apps_script.status === 'ok', 
            data.checks.apps_script.status === 'ok' ? `Active (${data.checks.apps_script.latency_ms}ms)` : data.checks.apps_script.message);
        results.script = data.checks.apps_script.status === 'ok';

        // Update Webhook UI
        updateCheckupUI('check-webhook', data.checks.webhook.status === 'ok', 
            data.checks.webhook.status === 'ok' ? 'Ready for sync' : data.checks.webhook.message);
        results.webhook = data.checks.webhook.status === 'ok';

        // --- NEW: Deep Trace Logic ---
        const traceSection = document.getElementById('deep-trace-section');
        traceSection.style.display = 'block';
        
        // 1. Render Endpoints
        const endpointGrid = document.getElementById('endpoint-grid');
        endpointGrid.innerHTML = '';
        Object.entries(data.checks.endpoints).forEach(([path, info]) => {
            const div = document.createElement('div');
            div.style.cssText = 'display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.03); padding:6px 10px; border-radius:6px; border:1px solid rgba(255,255,255,0.05);';
            div.innerHTML = `
                <span style="font-size:10px; color:#94a3b8; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:120px;" title="${path}">${path}</span>
                <span style="font-size:9px; font-weight:700; color:${info.status === 'ok' ? '#34d399' : '#ef4444'}">${info.status === 'ok' ? 'UP' : 'DOWN'}</span>
            `;
            endpointGrid.appendChild(div);
        });

        // 2. Render Webhook Trace
        const traceLog = document.getElementById('webhook-log-trace');
        const history = data.checks.webhook_history;
        let traceHtml = `<div style="margin-bottom:8px; display:flex; gap:12px; font-size:9px; color:#6366f1;">
            <span>Success: ${history.success_count}</span>
            <span>Errors: ${history.error_count}</span>
            <span>Last Sync: ${history.last_sync || 'None'}</span>
        </div>`;
        
        if (history.recent_events.length === 0) {
            traceHtml += '<div style="color:#475569; font-style:italic;">No recent entries in webhook_errors.log</div>';
        } else {
            history.recent_events.forEach(line => {
                const isError = line.toLowerCase().includes('error') || line.toLowerCase().includes('failed') || line.toLowerCase().includes('unauthorized');
                traceHtml += `<div style="margin-bottom:2px; color:${isError ? '#fca5a5' : '#94a3b8'}; border-left:2px solid ${isError ? '#ef4444' : '#34d399'}; padding-left:6px;">${line}</div>`;
            });
        }
        traceLog.innerHTML = traceHtml;

        if (data.healthy) {
            console.log('[CHECKUP] All systems healthy.');
            // Give user time to see the trace before hiding if it was manual retry
            const delay = document.getElementById('checkup-footer').style.display === 'block' ? 4000 : 2500;
            setTimeout(() => modal.classList.add('hidden'), delay);
        } else {
            console.warn('[CHECKUP] Systems degraded:', data.checks);
            document.getElementById('checkup-footer').style.display = 'block';
        }
        
    } catch (error) {
        console.error('[CHECKUP] Diagnostic failed:', error);
        updateCheckupUI('check-db', false, 'Backend unreachable');
        document.getElementById('checkup-footer').style.display = 'block';
    }
}

function updateCheckupUI(id, success, message) {
    const item = document.getElementById(id);
    const badge = item.querySelector('.status-badge');
    const msg = item.querySelector('.status-msg');
    
    badge.textContent = success ? 'SUCCESS' : 'FAILED';
    badge.style.background = success ? 'rgba(34, 211, 102, 0.1)' : 'rgba(239, 68, 68, 0.1)';
    badge.style.color = success ? '#34d399' : '#ef4444';
    msg.textContent = message;
    msg.style.color = success ? '#8b8b9e' : '#fca5a5';
}

// ========== DATA LOADING ==========
async function loadInitialData() {
    try {
        // Validate configuration & perform system check
        await performSystemCheckup();
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
            document.getElementById('upload-screen').classList.remove('active');
            document.getElementById('loading-screen').classList.add('active');
            loadInitialData();
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


