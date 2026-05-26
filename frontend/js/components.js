// ========== RENDER DASHBOARD ==========
function renderDashboard() {
    const a = state.analytics;
    if (!a) return;

    try { renderKPIs(a.kpis); } catch (e) { console.error("Error renderKPIs:", e); }
    try { renderFilters(a.filters); } catch (e) { console.error("Error renderFilters:", e); }
    try { renderAIInsights(a.aiInsights); } catch (e) { console.error("Error renderAIInsights:", e); }
    try { renderCharts(a.charts); } catch (e) { console.error("Error renderCharts:", e); }
    try { renderDeepAnalysis(a.deepAnalysis); } catch (e) { console.error("Error renderDeepAnalysis:", e); }
    try { renderSentiment(a.sentiment); } catch (e) { console.error("Error renderSentiment:", e); }
    try { renderKeywords(a.keywords); } catch (e) { console.error("Error renderKeywords:", e); }
    try { renderSpeakers(a.speakerStats); } catch (e) { console.error("Error renderSpeakers:", e); }
    try { renderTable(); } catch (e) { console.error("Error renderTable:", e); }

    // Hide sections with no data
    try { toggleSectionVisibility('speakers-section', a.speakerStats && a.speakerStats.length > 0); } catch (e) { }
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
            html += `<div class="filter-multiselect" data-column="${escAttr(f.column)}" data-type="categorical">`;
            html += `<div class="multiselect-options">`;
            f.options.forEach(opt => {
                const active = state.activeFilters || {};
                const checked = (active[f.column] || []).includes(opt.value);
                html += `
                    <label class="multiselect-item">
                        <input type="checkbox" value="${escAttr(opt.value)}" ${checked ? 'checked' : ''}>
                        <span class="multiselect-text">${esc(truncate(opt.value, 28))}</span>
                        <span class="multiselect-count">${opt.count}</span>
                    </label>
                `;
            });
            html += `</div></div>`;
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

    // Add listeners for checkboxes in multiselect
    container.querySelectorAll('.filter-multiselect input[type="checkbox"]').forEach(cb => {
        cb.addEventListener('change', applyFilters);
    });

    // Initialize smart calendars for date filters
    container.querySelectorAll('.calendar-trigger').forEach(el => {
        new SmartCalendar(el, JSON.parse(el.dataset.dates || '[]'), () => applyFilters());
    });

    // Update speaker suggestions for autocomplete in Form Manager
    updateSpeakerSuggestions(filters);
}

function updateSpeakerSuggestions(filters) {
    const speakerFilter = filters.find(f => f.column === 'alumni_speaker_name');
    if (!speakerFilter || !speakerFilter.options) return;

    // Cache the full list for autocomplete (even when filtered)
    state.allSpeakers = speakerFilter.options.map(o => o.value);
}

/**
 * Speaker name matches query: full string starts with query, or any word starts with query (prefix-only).
 */
function speakerNameMatchesQuery(query, name) {
    const q = query.trim().toLowerCase();
    if (!q) return false;
    const n = name.toLowerCase();
    if (n.startsWith(q)) return true;
    return n.split(/\s+/).some((w) => w.startsWith(q));
}

function speakerMatchRank(query, name) {
    const q = query.trim().toLowerCase();
    const n = name.toLowerCase();
    if (n.startsWith(q)) return 0;
    return 1;
}

/**
 * Autocomplete: only show rows while something still matches; hide entirely when none (no "no match" banner).
 */
let selectedSuggestionIdx = -1;

function renderSpeakerAutocomplete(query) {
    const dropdown = document.getElementById('speaker-autocomplete-dropdown');
    if (!dropdown) return;

    if (!query || query.length < 1) {
        dropdown.innerHTML = '';
        dropdown.classList.remove('active');
        return;
    }

    const list = Array.isArray(state.allSpeakers) ? state.allSpeakers : [];
    const matches = list
        .filter((name) => speakerNameMatchesQuery(query, name))
        .sort((a, b) => {
            const ra = speakerMatchRank(query, a);
            const rb = speakerMatchRank(query, b);
            if (ra !== rb) return ra - rb;
            return a.localeCompare(b, undefined, { sensitivity: 'base' });
        })
        .slice(0, 10);

    if (matches.length === 0) {
        dropdown.innerHTML = '';
        dropdown.classList.remove('active');
        return;
    }

    selectedSuggestionIdx = -1;
    dropdown.innerHTML = '';
    const qLower = query.trim().toLowerCase();
    matches.forEach((name, idx) => {
        const item = document.createElement('div');
        item.className = 'autocomplete-item';
        item.dataset.index = String(idx);

        const nLower = name.toLowerCase();
        let html = '';
        if (nLower.startsWith(qLower)) {
            html =
                `<span class="match-highlight">${esc(name.slice(0, query.trim().length))}</span>` +
                esc(name.slice(query.trim().length));
        } else {
            const parts = name.split(/(\s+)/);
            for (const part of parts) {
                if (!part.trim()) {
                    html += esc(part);
                    continue;
                }
                const pl = part.toLowerCase();
                if (pl.startsWith(qLower)) {
                    html +=
                        `<span class="match-highlight">${esc(part.slice(0, query.trim().length))}</span>` +
                        esc(part.slice(query.trim().length));
                } else {
                    html += esc(part);
                }
            }
        }

        item.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            <span>${html}</span>
        `;

        item.addEventListener('click', () => {
            selectSpeaker(name);
        });
        dropdown.appendChild(item);
    });
    dropdown.classList.add('active');
}

function selectSpeaker(name) {
    const input = document.getElementById('fb-speaker-name');
    const dropdown = document.getElementById('speaker-autocomplete-dropdown');
    if (input) input.value = name;
    if (dropdown) dropdown.classList.remove('active');
}

function initSpeakerAutocomplete() {
    const input = document.getElementById('fb-speaker-name');
    const dropdown = document.getElementById('speaker-autocomplete-dropdown');
    if (!input || !dropdown) return;

    input.addEventListener('input', (e) => {
        renderSpeakerAutocomplete(e.target.value);
    });

    input.addEventListener('keydown', (e) => {
        const items = dropdown.querySelectorAll('.autocomplete-item');
        if (!dropdown.classList.contains('active') || items.length === 0) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            selectedSuggestionIdx = (selectedSuggestionIdx + 1) % items.length;
            updateSelection(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            selectedSuggestionIdx = (selectedSuggestionIdx - 1 + items.length) % items.length;
            updateSelection(items);
        } else if (e.key === 'Enter' && selectedSuggestionIdx !== -1) {
            e.preventDefault();
            items[selectedSuggestionIdx].click();
        } else if (e.key === 'Escape') {
            dropdown.classList.remove('active');
        }
    });

    function updateSelection(items) {
        items.forEach((item, idx) => {
            item.classList.toggle('selected', idx === selectedSuggestionIdx);
            if (idx === selectedSuggestionIdx) item.scrollIntoView({ block: 'nearest' });
        });
    }

    // Close on click outside
    document.addEventListener('click', (e) => {
        if (!input.contains(e.target) && !dropdown.contains(e.target)) {
            dropdown.classList.remove('active');
        }
    });
}

async function applyFilters() {
    const globalSearch = document.getElementById('global-search').value.trim();
    const filters = {};

    // Standard inputs
    document.querySelectorAll('#filters-grid .filter-input[data-column]').forEach(el => {
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

    // Multi-selects (categorical)
    document.querySelectorAll('#filters-grid .filter-multiselect').forEach(div => {
        const col = div.dataset.column;
        const selected = Array.from(div.querySelectorAll('input[type="checkbox"]:checked')).map(cb => cb.value);
        if (selected.length > 0) {
            filters[col] = selected;
        }
    });

    state.activeFilters = filters; // Keep track of current state
    try {
        const response = await fetch(`${API_BASE}/api/filter`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filters, search: globalSearch }),
        });

        if (!response.ok) throw new Error('Filter failed');

        const analytics = await response.json();
        // Content-based hash: compare first+last row IDs and total count for reliable change detection
        const hashRows = (rows) => {
            if (!rows || rows.length === 0) return '0::';
            return `${rows.length}:${JSON.stringify(rows[0])}:${JSON.stringify(rows[rows.length - 1])}`;
        };
        const currentDataHash = hashRows(state.tableData);
        const newDataHash = hashRows(analytics.tableData || []);

        state.analytics = analytics;
        state.tableData = analytics.tableData || [];
        state.currentPage = 1;

        // Prevent full re-render flicker on auto-refresh if identical
        if (currentDataHash !== newDataHash) {
            renderKPIs(analytics.kpis);
            renderAIInsights(analytics.aiInsights);
            renderCharts(analytics.charts);
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
    document.querySelectorAll('#filters-grid .filter-input').forEach(el => {
        el.value = '';
    });
    document.querySelectorAll('#filters-grid .filter-multiselect input[type="checkbox"]').forEach(cb => {
        cb.checked = false;
    });
    document.getElementById('global-search').value = '';
    applyFilters();
}


// ========== DEEP ANALYSIS ==========
function renderDeepAnalysis(da) {
    const container = document.getElementById('deep-actionable-grid');
    const subsection = document.getElementById('deep-actionable-subsection');

    if (!da || (!da.actionableStats && (!da.categories || da.categories.length === 0))) {
        if (subsection) subsection.style.display = 'none';
        return;
    }

    if (subsection) subsection.style.display = 'block';
    if (container) container.innerHTML = '';

    const actStats = da.actionableStats || { actionable: 0, non_actionable: 0 };
    const totalAct = actStats.actionable + actStats.non_actionable;

    if (totalAct > 0 && container) {
        const actCard = document.createElement('div');
        actCard.className = 'chart-card';
        actCard.innerHTML = `
            <div class="chart-card-header"><div class="chart-card-title">Actionability Filter</div></div>
            <div class="chart-canvas-wrapper"><canvas></canvas></div>
        `;
        container.appendChild(actCard);

        const actChart = new Chart(actCard.querySelector('canvas'), {
            type: 'doughnut',
            data: {
                labels: ['Actionable Suggestions', 'Generic/Non-Answers'],
                datasets: [{
                    data: [actStats.actionable, actStats.non_actionable],
                    backgroundColor: ['#34d399', '#fb7185'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                onClick: (e, elements, chart) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const label = chart.data.labels[index];
                        const count = chart.data.datasets[0].data[index];
                        openDataModal('Actionability Filter', label, count, 'dl_processed', 'dl_actionability', null);
                    }
                },
                plugins: {
                    legend: { position: 'bottom', labels: { color: '#8b8b9e' } }
                }
            }
        });
        state.charts.push(actChart);
    }

    const cats = da.categories || [];
    if (cats.length > 0 && container) {
        const catCard = document.createElement('div');
        catCard.className = 'chart-card';
        catCard.innerHTML = `
            <div class="chart-card-header"><div class="chart-card-title">Suggestion Categories</div></div>
            <div class="chart-canvas-wrapper"><canvas></canvas></div>
        `;
        container.appendChild(catCard);

        const catChart = new Chart(catCard.querySelector('canvas'), {
            type: 'bar',
            data: {
                labels: cats.map(c => truncate(c.name, 18)),
                datasets: [{
                    label: 'Suggestions',
                    data: cats.map(c => c.value),
                    backgroundColor: CHART_COLORS,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                onClick: (e, elements, chart) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        // Use full category names from raw array, not the truncated chart label!
                        const fullLabel = cats[index].name;
                        const count = cats[index].value;
                        openDataModal('Suggestion Categories', fullLabel, count, 'dl_processed', 'dl_category', null);
                    }
                },
                plugins: { legend: { display: false } },
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#8b8b9e' } },
                    x: { grid: { display: false }, ticks: { color: '#8b8b9e' } }
                }
            }
        });
        state.charts.push(catChart);
    }
}


// ========== KPI CARDS ==========
// ========== SENTIMENT (AI-FILTERED) ==========
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
                    <div class="sentiment-stat-row clickable-sentiment" data-sentiment="POSITIVE" data-col="${esc(s.column)}">
                        <span class="sentiment-dot positive"></span>
                        <span style="color: var(--text-secondary); font-size: 12px; min-width: 60px;">Positive</span>
                        <div class="sentiment-bar-track">
                            <div class="sentiment-bar-fill positive" style="width: ${(s.positive / total * 100).toFixed(0)}%"></div>
                        </div>
                        <span class="sentiment-count">${s.positive}</span>
                    </div>
                    <div class="sentiment-stat-row clickable-sentiment" data-sentiment="NEUTRAL" data-col="${esc(s.column)}">
                        <span class="sentiment-dot neutral"></span>
                        <span style="color: var(--text-secondary); font-size: 12px; min-width: 60px;">Neutral</span>
                        <div class="sentiment-bar-track">
                            <div class="sentiment-bar-fill neutral" style="width: ${(s.neutral / total * 100).toFixed(0)}%"></div>
                        </div>
                        <span class="sentiment-count">${s.neutral}</span>
                    </div>
                    <div class="sentiment-stat-row clickable-sentiment" data-sentiment="NEGATIVE" data-col="${esc(s.column)}">
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

        card.querySelectorAll('.clickable-sentiment').forEach(row => {
            row.style.cursor = 'pointer';
            row.title = 'Click to view students';

            // Add slight hover effect via JS since CSS isn't easily modifiable right now
            row.addEventListener('mouseenter', () => row.style.backgroundColor = 'rgba(255,255,255,0.05)');
            row.addEventListener('mouseleave', () => row.style.backgroundColor = 'transparent');

            row.addEventListener('click', () => {
                const sent = row.getAttribute('data-sentiment');
                const colTitle = row.getAttribute('data-col');
                openDataModal(colTitle, sent, s[sent.toLowerCase()], 'dl_processed', 'dl_sentiment', colTitle);
            });
        });
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


// ========== KEYWORDS / WORD CLOUD (WITH BIGRAMS) ==========
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

        const cloudContainer = document.createElement('div');
        cloudContainer.className = 'word-cloud';

        kw.words.slice(0, 25).forEach((word, idx) => {
            const size = 11 + ((word.count - minCount) / (maxCount - minCount + 1)) * 14;
            const opacity = 0.5 + ((word.count - minCount) / (maxCount - minCount + 1)) * 0.5;
            const color = CHART_COLORS[idx % CHART_COLORS.length];
            const bgColor = color + '18';
            const isBigram = word.type === 'bigram';

            const span = document.createElement('span');
            span.className = `word-tag ${isBigram ? 'bigram-tag' : ''}`;
            span.style.fontSize = `${size}px`;
            span.style.background = bgColor;
            span.style.color = color;
            span.style.opacity = opacity;
            span.title = `${word.count} occurrences${isBigram ? ' (phrase)' : ''} - Click to see students`;
            span.style.cursor = 'pointer';
            span.textContent = `${isBigram ? '⟨ ' : ''}${word.text}${isBigram ? ' ⟩' : ''}`;

            span.addEventListener('click', () => {
                openDataModal('Trending Topics', word.text, word.count, kw.column, 'dl_keyword', null);
            });
            cloudContainer.appendChild(span);
        });

        card.innerHTML = `
            <div class="keyword-card-title">${esc(truncate(kw.column, 40))} — Keywords & Phrases</div>
        `;
        card.appendChild(cloudContainer);
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
                        column: 'alumni_speaker_name',
                        labels: ss.speakers.map(s => s.name),
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
                    column: 'alumni_speaker_name',
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
        if (columnType === 'text') {
            // Text: substring inclusion on the specific column
            const searchLabel = String(clickedLabel).toLowerCase().trim();
            filteredRows = state.tableData.filter(row => {
                return String(row[column] || '').toLowerCase().includes(searchLabel);
            });
        } else if (columnType === 'dl_category') {
            const searchLabel = String(clickedLabel).toLowerCase().trim();
            filteredRows = state.tableData.filter(row => {
                if (!row['dl_keywords']) return false;
                try {
                    const dl = JSON.parse(row['dl_keywords']);
                    if (!dl.category) return false;
                    return String(dl.category).toLowerCase().trim() === searchLabel;
                } catch (e) { return false; }
            });
        } else if (columnType === 'dl_sentiment') {
            filteredRows = state.tableData.filter(row => {
                const targetSent = String(clickedLabel).toUpperCase().trim();
                if (binBoundary === 'Deep Analysis: Overall Extracted Sentiment') {
                    return String(row['dl_sentiment_label'] || '').toUpperCase().trim() === targetSent;
                }
                if (!row['dl_keywords']) return false;
                try {
                    const dl = JSON.parse(row['dl_keywords']);
                    if (binBoundary.includes('Suggestions') || binBoundary.includes('Improvements')) {
                        return String(dl.improvements_sentiment || '').toUpperCase().trim() === targetSent;
                    }
                    if (binBoundary.includes('Valuable')) {
                        return String(dl.valuable_sentiment || '').toUpperCase().trim() === targetSent;
                    }
                } catch (e) { return false; }
                return false;
            });
        } else if (columnType === 'dl_keyword') {
            const searchLabel = String(clickedLabel).toLowerCase().trim();
            filteredRows = state.tableData.filter(row => {
                if (!row['dl_keywords']) return false;
                try {
                    const dl = JSON.parse(row['dl_keywords']);
                    let keywordsToSearch = [];
                    if (column.includes('Future Topics')) {
                        keywordsToSearch = dl.future_keywords || [];
                    } else if (column.includes('Valuable')) {
                        keywordsToSearch = dl.val_keywords || [];
                    } else if (column.includes('Improvement')) {
                        keywordsToSearch = dl.imp_keywords || [];
                    } else {
                        keywordsToSearch = (dl.general_keywords || []).concat(dl.future_keywords || []);
                    }
                    return keywordsToSearch.some(kwData => {
                        const word = Array.isArray(kwData) ? kwData[0] : kwData;
                        return String(word).toLowerCase().trim() === searchLabel;
                    });
                } catch (e) { return false; }
            });
        } else if (columnType === 'dl_actionability') {
            const isActionable = clickedLabel === 'Actionable Suggestions';
            filteredRows = state.tableData.filter(row => {
                if (!row['dl_keywords']) return false;
                try {
                    const dl = JSON.parse(row['dl_keywords']);
                    return !!dl.is_actionable === isActionable;
                } catch (e) { return false; }
            });
        } else {
            // Categorical: exact match on the specific column only
            const searchLabel = String(clickedLabel).toLowerCase().trim();
            filteredRows = state.tableData.filter(row => {
                return String(row[column] || '').toLowerCase().trim() === searchLabel;
            });
        }
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



// ==========  ==========
//  FEEDBACK FORM MANAGER

// ==========  ==========
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

    async function loadSpeakerNamesForForm() {
        if (!getToken()) return;
        try {
            const res = await fetch(`${API_BASE}/api/admin/speaker-names`, { headers: authHeaders() });
            const data = await res.json();
            if (data.success && Array.isArray(data.names) && data.names.length) {
                state.allSpeakers = data.names;
            }
        } catch (e) {
            console.warn('[speakers] Could not load speaker list:', e);
        }
    }

    function setVenueDateMinToday() {
        const d = document.getElementById('fb-venue-date');
        if (!d) return;
        const t = new Date();
        const yyyy = t.getFullYear();
        const mm = String(t.getMonth() + 1).padStart(2, '0');
        const dd = String(t.getDate()).padStart(2, '0');
        d.min = `${yyyy}-${mm}-${dd}`;
        if (d.value && d.value < d.min) d.value = '';
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
                        setVenueDateMinToday();
                        loadSpeakerNamesForForm();
                        loadEvents();
                    }
                    origSubmit.removeEventListener('click', handler);
                }, 300);
            };
            origSubmit.addEventListener('click', handler);
            return;
        }
        resetForm();
        setVenueDateMinToday();
        loadSpeakerNamesForForm();
        document.getElementById('feedback-modal').classList.remove('hidden');
        loadEvents();
    }

    function closeFeedbackModal() {
        document.getElementById('feedback-modal').classList.add('hidden');
    }

    function resetForm() {
        document.getElementById('fb-speaker-name').value = '';
        document.getElementById('fb-venue-date').value = '';
        const dd = document.getElementById('speaker-autocomplete-dropdown');
        if (dd) {
            dd.innerHTML = '';
            dd.classList.remove('active');
        }
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
        const date = document.getElementById('fb-venue-date').value.trim();

        if (!speaker || !date) {
            showStatus('Please fill in both Speaker Name and Venue Date.', 'error');
            return;
        }

        const dateInput = document.getElementById('fb-venue-date');
        if (dateInput && dateInput.min && date < dateInput.min) {
            showStatus('Venue date cannot be before today.', 'error');
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
            const res = await fetch(`${API_BASE}/api/admin/events`, { headers: authHeaders() });
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

                let isExpired = ev.status === 'closed';
                let timeRemainingStr = '';

                if (hasForm && !isExpired && ev.created_at) {
                    // Normalize sqlite timestamp missing "T" or timezone
                    let dateStr = ev.created_at;
                    if (!dateStr.includes('T')) dateStr = dateStr.replace(' ', 'T');
                    if (!dateStr.endsWith('Z')) dateStr += 'Z';

                    const createdDate = new Date(dateStr);
                    const expiryDate = new Date(createdDate.getTime() + 24 * 60 * 60 * 1000);
                    const now = new Date();
                    const diff = expiryDate - now;
                    if (diff <= 0) {
                        isExpired = true;
                    } else {
                        const h = Math.floor(diff / (1000 * 60 * 60)).toString().padStart(2, '0');
                        const m = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60)).toString().padStart(2, '0');
                        const s = Math.floor((diff % (1000 * 60)) / 1000).toString().padStart(2, '0');
                        timeRemainingStr = `<span class="form-timer" data-expiry="${expiryDate.getTime()}" data-form-id="${ev.form_id}" style="color:#f97316;font-family:monospace;font-size:13px;font-weight:700;background:rgba(249,115,22,0.1);padding:5px 10px;border-radius:8px;border:1px solid rgba(249,115,22,0.3);min-width:110px;display:inline-block;text-align:center;">⏱ ${h}:${m}:${s}</span>`;
                    }
                }

                card.innerHTML = `
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
                        <div>
                            <div style="display:flex;align-items:center;gap:8px;">
                                <div style="font-size:13px;font-weight:800;color:#000000;">${esc(ev.speaker_name)}</div>
                                ${timeRemainingStr}
                            </div>
                            <div style="font-size:11px;color:#555b6e;margin-top:2px;">${esc(ev.venue_date)} &nbsp;·&nbsp; ${ev.responses} response${ev.responses !== 1 ? 's' : ''}</div>
                        </div>
                        <span style="font-size:10px;padding:3px 8px;border-radius:12px;font-weight:600;${hasForm ? (isExpired ? 'background:rgba(239,68,68,0.1);color:#ef4444;border:1px solid rgba(239,68,68,0.2);' : 'background:rgba(34,211,102,0.1);color:#34d399;border:1px solid rgba(34,211,102,0.2);') : 'background:rgba(251,191,36,0.1);color:#fbbf24;border:1px solid rgba(251,191,36,0.2);'}">
                            ${hasForm ? (isExpired ? 'Expired' : 'Ready') : 'No Form'}
                        </span>
                    </div>
                    ${hasForm ? `
                    <div style="display:flex;gap:6px;margin-top:8px;align-items:center;">
                        <button data-copy-url="${ev.form_url}" class="btn-copy-event-url"
                            style="flex:1;padding:6px;border-radius:6px;background:rgba(99,102,241,0.15);color:#a5b4fc;border:1px solid rgba(99,102,241,0.25);font-size:11px;cursor:pointer;font-family:Inter;font-weight:600;">Copy</button>
                        <button data-open-url="${ev.form_url}" class="btn-open-event-url"
                            style="flex:1;padding:6px;border-radius:6px;background:rgba(99,102,241,0.15);color:#a5b4fc;border:1px solid rgba(99,102,241,0.25);font-size:11px;cursor:pointer;font-family:Inter;font-weight:600;">Open</button>
                        ${!isExpired ? `<button data-form="${ev.form_id}" data-speaker="${esc(ev.speaker_name)}" class="btn-close-form"
                            style="flex:1;padding:6px;border-radius:6px;background:rgba(239,68,68,0.15);color:#dc2626;border:1px solid rgba(239,68,68,0.3);font-size:11px;cursor:pointer;font-family:Inter;font-weight:600;">Close Form</button>` : ''}
                    </div>` : `
                    <button data-event-id="${ev.id}" class="btn-generate-existing"
                        style="width:100%;margin-top:8px;padding:6px;border-radius:6px;background:rgba(251,191,36,0.1);color:#fbbf24;border:1px solid rgba(251,191,36,0.2);font-size:11px;cursor:pointer;font-family:Inter;font-weight:600;">Generate Form</button>`}
                `;
                list.appendChild(card);
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

            // Open event URL buttons
            list.querySelectorAll('.btn-open-event-url').forEach(btn => {
                btn.addEventListener('click', () => {
                    const url = btn.dataset.openUrl;
                    if (url) {
                        safeWindowOpen(url);
                    }
                });
            });

            list.querySelectorAll('.btn-close-form').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const formId = btn.dataset.form;
                    const speakerName = btn.dataset.speaker || 'this form';
                    if (!formId) return;

                    // Custom confirmation instead of native confirm()
                    const confirmed = window.confirm(
                        `⚠️ Close "${speakerName}" form?\n\nThis will immediately stop accepting new responses. Students currently filling the form will NOT be able to submit.\n\nAre you sure?`
                    );
                    if (!confirmed) return;

                    const originalText = btn.textContent;
                    btn.textContent = 'Closing...';
                    btn.disabled = true;
                    btn.style.opacity = '0.6';
                    try {
                        const r = await fetch(`${API_BASE}/api/admin/close-form`, {
                            method: 'POST', headers: authHeaders(),
                            body: JSON.stringify({ form_id: formId })
                        });
                        const d = await r.json();
                        // Success if status is 'closed' OR message says closed
                        const isSuccess = d.status === 'closed' || (d.message && d.message.toLowerCase().includes('closed'));
                        if (isSuccess) {
                            btn.textContent = '✓ Closed!';
                            btn.style.background = 'rgba(34,197,94,0.15)';
                            btn.style.color = '#16a34a';
                            btn.style.border = '1px solid rgba(34,197,94,0.3)';
                            setTimeout(() => loadEvents(), 1500);
                        } else {
                            btn.textContent = 'Error';
                            btn.style.color = '#ef4444';
                            console.error('[TOGGLE] Close form failed:', d);
                            setTimeout(() => { btn.textContent = originalText; btn.disabled = false; btn.style.opacity = '1'; btn.style.color = '#dc2626'; }, 2500);
                        }
                    } catch (e) {
                        console.error('[TOGGLE] Network error:', e);
                        btn.textContent = 'Error';
                        btn.style.color = '#ef4444';
                        setTimeout(() => { btn.textContent = originalText; btn.disabled = false; btn.style.opacity = '1'; btn.style.color = '#dc2626'; }, 2500);
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

        // "Upload Data" sidebar button
        const btnUploadData = document.getElementById('btn-upload-data');
        if (btnUploadData) {
            btnUploadData.addEventListener('click', () => {
                if (!getToken()) {
                    document.getElementById('admin-login-modal').classList.remove('hidden');
                    const origSubmit = document.getElementById('btn-admin-submit');
                    const handler = () => {
                        setTimeout(() => {
                            if (getToken()) switchToUpload();
                            origSubmit.removeEventListener('click', handler);
                        }, 300);
                    };
                    origSubmit.addEventListener('click', handler);
                } else {
                    switchToUpload();
                }
            });
        }

        // Go Back button on upload screen
        const btnBackToDashboard = document.getElementById('btn-back-to-dashboard');
        if (btnBackToDashboard) {
            btnBackToDashboard.addEventListener('click', () => {
                switchToDashboard();
                loadInitialData();
            });
        }

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

        // Initialize advanced fuzzy autocomplete
        initSpeakerAutocomplete();
    });

    // ── Global Form Timer Updater ────────────────────────────
    // Runs every second. When timer hits 0 → auto-closes form via API
    // regardless of whether admin is logged in or has the modal open.
    async function _autoCloseForm(formId) {
        if (!formId) return;
        try {
            const token = localStorage.getItem('adminToken') || '';
            const r = await fetch(`${API_BASE}/api/admin/close-form`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ form_id: formId })
            });
            const d = await r.json();
            console.log(`[TIMER] Auto-closed form ${formId}:`, d.status || d.error);
        } catch (e) {
            console.warn(`[TIMER] Auto-close failed for ${formId}:`, e);
        }
    }

    setInterval(() => {
        const timers = document.querySelectorAll('.form-timer');
        let needsReload = false;

        timers.forEach(timer => {
            const expiry = parseInt(timer.dataset.expiry, 10);
            if (!expiry) return;

            const diff = expiry - Date.now();
            if (diff <= 0) {
                const formId = timer.dataset.formId;
                timer.textContent = '⛔ Closed';
                timer.style.color = '#ef4444';
                timer.style.background = 'rgba(239,68,68,0.1)';
                timer.style.border = '1px solid rgba(239,68,68,0.3)';
                timer.classList.remove('form-timer'); // stop re-triggering
                needsReload = true;
                if (formId) _autoCloseForm(formId); // auto-close via API
            } else {
                const h = Math.floor(diff / (1000 * 60 * 60)).toString().padStart(2, '0');
                const m = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60)).toString().padStart(2, '0');
                const s = Math.floor((diff % (1000 * 60)) / 1000).toString().padStart(2, '0');
                timer.textContent = `⏱ ${h}:${m}:${s}`;
                // Change colour as time runs low
                if (diff < 3600000) {           // < 1 hour → red urgent
                    timer.style.color = '#ef4444';
                    timer.style.background = 'rgba(239,68,68,0.12)';
                    timer.style.border = '1px solid rgba(239,68,68,0.3)';
                } else if (diff < 7200000) {    // < 2 hours → orange warning
                    timer.style.color = '#f97316';
                    timer.style.background = 'rgba(249,115,22,0.1)';
                    timer.style.border = '1px solid rgba(249,115,22,0.3)';
                }
            }
        });

        if (needsReload) {
            setTimeout(() => loadEvents(), 2000);
        }
    }, 1000);

    // ── Global Dashboard Auto-Polling ────────────────────────

    // Polling every 30 seconds to fetch new webhook data live
    setInterval(() => {
        // Only refresh if the admin is logged in and theoretically looking at the dashboard
        if (getToken() && typeof loadInitialData === 'function') {
            // Optional: check if dashboard is currently active section
            const activeSection = document.querySelector('.sidebar-item.active');
            if (activeSection && activeSection.dataset.section === 'dashboard') {
                loadInitialData(true); // pass true if you have a silent fetch flag, else normal
            }
        }
    }, 30000);

    // --- TOAST NOTIFICATIONS ---
    window.showToast = function (message) {
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.innerHTML = `
            <div class="toast-icon">📢</div>
            <div class="toast-content">${esc(message)}</div>
            <div class="toast-close" onclick="this.parentElement.remove()">×</div>
        `;

        container.appendChild(toast);
        // Trigger reflow for animation
        toast.offsetHeight;
        toast.classList.add('show');

        // Auto-remove after 6 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 500);
        }, 6000);
    };

    // --- NOTIFICATION POLLING ---
    function checkNotifications() {
        fetch('/api/v1/webhook/notifications')
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success' && data.notifications) {
                    data.notifications.forEach(msg => window.showToast(msg));
                }
            })
            .catch(err => console.debug("Notification poll failed (normal if server restarting)"));
    }

    // Start polling every 8 seconds
    setInterval(checkNotifications, 8000);

})();
