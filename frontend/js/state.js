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
    activeFilters: {}, // Initialize to prevent rendering errors
    allSpeakers: [],   // Cached list for autocomplete
};

const API_BASE = '';


// ========== REQUEST MANAGEMENT (FIX: PREVENT DUPLICATE REQUESTS) ==========
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


