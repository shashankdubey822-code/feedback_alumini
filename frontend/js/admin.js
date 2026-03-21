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

    const btnBackToDashboard = document.getElementById('btn-back-to-dashboard');
    if (btnBackToDashboard) {
        btnBackToDashboard.addEventListener('click', () => {
            document.getElementById('upload-screen').classList.remove('active');
            document.getElementById('loading-screen').classList.add('active');
            document.getElementById('dashboard-screen').classList.remove('active');
            loadInitialData();
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
                    document.getElementById('upload-screen').classList.remove('active');
                    document.getElementById('loading-screen').classList.add('active');
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
    document.getElementById('loading-screen').classList.remove('active');
    document.getElementById('dashboard-screen').classList.remove('active');
    document.getElementById('upload-screen').classList.add('active');
    hideProgress();
    document.getElementById('file-input').value = '';
    const googleInput = document.getElementById('google-link-input');
    if (googleInput) googleInput.value = '';
}


