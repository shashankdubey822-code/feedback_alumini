/* ========================================
   Deep Learning Integration (Frontend)
   Polls the backend queue status and drives
   the DL processing popup via CSS classes.
   ======================================== */

document.addEventListener('DOMContentLoaded', () => {
    const popup   = document.getElementById('dl-processing-popup');
    const textEl  = document.getElementById('dl-processing-text');
    if (!popup || !textEl) return;

    let wasProcessing = false;

    async function checkDLStatus() {
        try {
            const url = (typeof API_BASE !== 'undefined' ? API_BASE : '') + '/api/v1/dl-status';
            const res = await fetch(url);
            if (!res.ok) return;
            const data = await res.json();

            if (data.processing_count > 0) {
                textEl.textContent = `Processing ${data.processing_count} AI record${data.processing_count > 1 ? 's' : ''}…`;
                popup.classList.add('visible');
                wasProcessing = true;
            } else {
                popup.classList.remove('visible');
                if (wasProcessing) {
                    wasProcessing = false;
                    // Silent refresh to surface newly processed DL data
                    if (typeof applyFilters === 'function') {
                        setTimeout(applyFilters, 1000);
                    }
                }
            }
        } catch (err) {
            console.error('[DL] Poll failed:', err);
        }
    }

    setInterval(checkDLStatus, 10000);
    setTimeout(checkDLStatus, 1500);
});
