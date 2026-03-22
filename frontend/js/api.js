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


