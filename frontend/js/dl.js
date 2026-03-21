/* ========================================
   Deep Learning Integration (Frontend)
   Polls the backend queue status and triggers 
   the sliding popup indicator.
   ======================================== */

document.addEventListener('DOMContentLoaded', () => {
    const popup = document.getElementById('dl-processing-popup');
    const textElem = document.getElementById('dl-processing-text');
    let dlPollingInterval = null;

    async function checkDLStatus() {
        try {
            // Need the correct API base URL path from global setup
            const url = (typeof API_BASE !== 'undefined' ? API_BASE : '') + '/api/v1/dl-status';
            const res = await fetch(url);
            
            if (!res.ok) return;
            const data = await res.json();
            
            if (data.processing_count > 0) {
                // Show sliding popup
                popup.style.bottom = '20px';
                textElem.textContent = `Processing ${data.processing_count} AI records...`;
            } else {
                // Hide sliding popup
                popup.style.bottom = '-100px';
                
                // If it was just processing, trigger a silent dashboard refresh to show new DL data
                if (textElem.textContent.includes('Processing')) {
                   textElem.textContent = 'All records analyzed.';
                   if (typeof applyFilters === 'function') {
                       // Trigger a silent refresh block 
                       setTimeout(applyFilters, 1000);
                   }
                }
            }
        } catch (error) {
            console.error('Failed to poll DL status', error);
        }
    }

    // Start polling every 3.5 seconds
    dlPollingInterval = setInterval(checkDLStatus, 3500);
    
    // Initial check right away
    setTimeout(checkDLStatus, 1000);
});
