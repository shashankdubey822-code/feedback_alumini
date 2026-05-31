window.DashboardPageModules = window.DashboardPageModules || {};

window.DashboardPageModules.charts = {
    sectionId: 'charts-section',

    render() {
        if (typeof renderCharts === 'function') {
            renderCharts((state.analytics && state.analytics.charts) || []);
        }
    },

    refresh() {
        this.render();
    },
};
