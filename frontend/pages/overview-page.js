window.DashboardPageModules = window.DashboardPageModules || {};

window.DashboardPageModules.overview = {
    sectionId: 'overview-section',

    render() {
        const analytics = state.analytics || {};
        if (typeof renderKPIs === 'function') renderKPIs(analytics.kpis || []);
        if (typeof renderFilters === 'function') renderFilters(analytics.filters || []);
        if (typeof renderAIInsights === 'function') renderAIInsights(analytics.aiInsights || []);
    },

    refresh() {
        this.render();
    },
};
