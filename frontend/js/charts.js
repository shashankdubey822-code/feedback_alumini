// ========== CHARTS (WITH AXIS LABELS) ==========
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
                    backgroundColor: chart.backgroundColors || (chart.type === 'doughnut'
                        ? chart.labels.map((_, i) => CHART_COLORS[i % CHART_COLORS.length])
                        : 'rgba(99, 102, 241, 0.6)'),
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


