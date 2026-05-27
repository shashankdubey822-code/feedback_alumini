/* api.js — upload handlers and progress helpers */

// ========== FILE UPLOAD ==========
function setupUploadHandlers() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    if (!dropZone || !fileInput) return;

    dropZone.addEventListener('click', (e) => {
        if (e.target.id === 'google-link-input' || e.target.id === 'btn-google-fetch') {
            return;
        }
        fileInput.click();
    });
    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', e => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
    });
    fileInput.addEventListener('change', e => {
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
    if (!token) { showNotification('Admin session expired', 'error'); return; }

    state.fileName = file.name;
    showProgress('Uploading to database...', 40);

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE}/api/admin/upload_csv`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
            body: formData,
        });
        if (!response.ok) {
            let msg = 'Upload failed';
            try { const err = await response.json(); msg = err.error || msg; } catch (_) {}
            throw new Error(msg);
        }
        showProgress('Done!', 100);
        setTimeout(() => loadInitialData(), 800);
    } catch (err) {
        showNotification('Error: ' + err.message, 'error');
        hideProgress();
    }
}

function showProgress(text, pct) {
    const el = document.getElementById('upload-progress');
    if (!el) return;
    el.classList.remove('hidden');
    document.getElementById('progress-fill').style.width = pct + '%';
    document.getElementById('progress-text').textContent = text;
}

function hideProgress() {
    const el = document.getElementById('upload-progress');
    if (el) el.classList.add('hidden');
}
