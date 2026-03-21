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


// ========== ENHANCED CLIPBOARD (FIX: ERROR HANDLING + FALLBACK) ==========
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


