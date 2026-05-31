window.DashboardPageModules = window.DashboardPageModules || {};

window.DashboardPageModules.aiInsights = {
    sectionId: 'insights-section',

    render() {
        if (typeof renderAIInsights === 'function') {
            renderAIInsights((state.analytics && state.analytics.aiInsights) || []);
        }
    },
};
